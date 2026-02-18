#!/usr/bin/env python3
"""
Context Drift Detection for SessionStart hook.

Checks recent git commits and conversation logs to detect when code changes
happen without corresponding context doc updates, and when debugging-heavy
sessions might warrant agent/doc updates.

Output goes to stdout and is injected into Claude's session context.
Empty output = no warnings (silent).

Usage:
    python3 .claude/scripts/context-drift-check.py             # Check for drift
    python3 .claude/scripts/context-drift-check.py --dismiss   # Dismiss current warnings
"""

import ast
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


# Debugging keywords (matches extract_prompts.py CATEGORIES['debugging'])
DEBUG_KEYWORDS = [
    "fix", "bug", "wrong", "broken", "doesn't work", "not working",
    "still not", "why does", "why is", "issue", "crash", "exception",
    "error", "null ref",
]

MAX_COMMITS = 10
MAX_SESSIONS = 3
MAX_LINES_PER_SESSION = 5000  # Cap for large session files
DEBUG_SCORE_THRESHOLD = 50
DISMISS_MAX_SHOWS = 2  # Auto-dismiss after showing N times without new commits
STATE_FILE = ".claude/scripts/.drift-state.json"

# Priority tiers: determines agent behavior when drift is detected
SUBSYSTEM_PRIORITY = {
    # HIGH: Structural — wrong docs cause agent failures, desync bugs, broken patterns
    "networking": "HIGH",
    "damage": "HIGH",
    "combat": "HIGH",
    "ecs": "HIGH",
    "game-states": "HIGH",
    "services": "HIGH",
    # MEDIUM: Important but less likely to cause cascading problems
    "turbo": "MEDIUM",
    "boss": "MEDIUM",
    "dungeon-generation": "MEDIUM",
    "physics": "MEDIUM",
    "spawning": "MEDIUM",
    "core-fusion": "MEDIUM",
    "collectibles": "MEDIUM",
    "vacuum-pickups": "MEDIUM",
    # LOW: Rarely causes agent issues if docs are slightly stale (suppressed)
    "ai": "LOW",
    "rendering": "LOW",
    "ui": "LOW",
    "content": "LOW",
    "audio": "LOW",
    "devtools": "LOW",
}


def find_repo_root() -> Path | None:
    """Find the git repo root from the script's location."""
    # Script lives at .claude/scripts/ so repo root is 2 levels up
    script_dir = Path(__file__).resolve().parent
    candidate = script_dir.parent.parent
    if (candidate / ".git").exists():
        return candidate
    # Fallback: try cwd
    cwd = Path.cwd()
    if (cwd / ".git").exists():
        return cwd
    return None


def parse_subsystems(server_py_path: Path) -> list:
    """Parse SUBSYSTEMS dict from server.py and build subsystem->code/docs mapping.

    Returns list of: {
        "name": "networking",
        "code_patterns": ["Network/", "ECS/Systems/NetworkSyncSystem.cs", ...],
        "docs": ["network-multiplayer-system.md", "play-modes.md", ...],
    }
    """
    if not server_py_path.exists():
        return []

    text = server_py_path.read_text(encoding="utf-8")

    # Parse the full Python file and walk the AST to find SUBSYSTEMS assignment.
    # This handles inline comments, string literals with braces, etc.
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    subsystems = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "SUBSYSTEMS":
                    try:
                        subsystems = ast.literal_eval(node.value)
                    except (ValueError, SyntaxError):
                        return []

    if not subsystems or not isinstance(subsystems, dict):
        return []

    result = []
    for key, info in subsystems.items():
        files = info.get("files", [])
        code_patterns = []
        doc_basenames = []

        for f in files:
            if f.startswith(".claude/context/") and f.endswith(".md"):
                doc_basenames.append(os.path.basename(f))
            else:
                # Keep exact file paths and directory prefixes as-is
                code_patterns.append(f)

        if code_patterns and doc_basenames:
            result.append({
                "name": key,
                "code_patterns": code_patterns,
                "docs": doc_basenames,
            })

    return result


def get_head_sha(repo_root: Path) -> str | None:
    """Get current HEAD commit SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=2, cwd=repo_root,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def load_state(repo_root: Path) -> dict:
    """Load drift state: {"head_sha": str, "times_shown": int}."""
    state_path = repo_root / STATE_FILE
    if state_path.exists():
        try:
            return json.loads(state_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_state(repo_root: Path, state: dict) -> None:
    """Save drift state to disk."""
    state_path = repo_root / STATE_FILE
    try:
        state_path.write_text(json.dumps(state))
    except OSError:
        pass


def detect_code_doc_drift(repo_root: Path, subsystems: list) -> list:
    """Check recent commits for code changes without doc updates.

    Returns list of: {"subsystem": str, "code_files": [str], "expected_docs": [str]}
    """
    if not subsystems:
        return []

    try:
        result = subprocess.run(
            ["git", "log", f"--max-count={MAX_COMMITS}", "--name-only", "--format=%H"],
            capture_output=True, text=True, timeout=2, cwd=repo_root,
        )
        if result.returncode != 0:
            return []
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    # Parse commits: group files by commit
    commits = []
    current_files = []
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if len(line) == 40 and all(c in "0123456789abcdef" for c in line):
            if current_files:
                commits.append(current_files)
            current_files = []
        else:
            current_files.append(line)
    if current_files:
        commits.append(current_files)

    # Collect all doc files touched across ALL recent commits
    engine_prefix = "GameProject/src/GameProject.Engine/"
    all_doc_basenames = set()
    all_code_files = set()
    for files in commits:
        for f in files:
            if f.startswith(".claude/context/") and f.endswith(".md"):
                all_doc_basenames.add(os.path.basename(f))
            if f == "CLAUDE.md":
                all_doc_basenames.add("CLAUDE.md")
            if f.startswith(engine_prefix) and not f.endswith(".md"):
                all_code_files.add(f[len(engine_prefix):])

    # For each subsystem, check if its code was touched without its docs
    flagged = []
    for sub in subsystems:
        matched_code = []
        for code_file in all_code_files:
            for pattern in sub["code_patterns"]:
                if pattern.endswith("/"):
                    if code_file.startswith(pattern):
                        matched_code.append(code_file)
                        break
                elif code_file == pattern or code_file.endswith("/" + pattern):
                    matched_code.append(code_file)
                    break

        if not matched_code:
            continue

        # Check if ANY of this subsystem's docs were updated
        missing_docs = [d for d in sub["docs"] if d not in all_doc_basenames]
        if missing_docs:
            priority = SUBSYSTEM_PRIORITY.get(sub["name"], "LOW")
            if priority == "LOW":
                continue  # Suppress LOW priority drift entirely
            flagged.append({
                "subsystem": sub["name"],
                "priority": priority,
                "code_files": sorted(matched_code)[:3],
                "expected_docs": missing_docs[:3],
            })

    return flagged


def find_project_dirs() -> list[Path]:
    """Find Claude project directories for game-project."""
    claude_projects = Path.home() / ".claude" / "projects"
    if not claude_projects.exists():
        return []
    return [
        d for d in claude_projects.iterdir()
        if d.is_dir() and "game-project" in d.name
    ]


def analyze_last_sessions(project_dirs: list[Path]) -> dict | None:
    """Analyze recent session logs for debugging intensity.

    Returns: {"score": int, "edit_build_cycles": int, "debug_prompts": int, "build_count": int}
    or None if no qualifying sessions found.
    """
    # Collect all JSONL files across project dirs, caching stat results
    file_mtimes = []
    for d in project_dirs:
        for f in d.glob("*.jsonl"):
            if f.name.startswith("agent-"):
                continue
            st = f.stat()
            if st.st_size < 1024:
                continue
            file_mtimes.append((f, st.st_mtime))

    # Sort by modification time, newest first
    file_mtimes.sort(key=lambda x: x[1], reverse=True)

    # Skip the very newest file if modified in the last 60s (likely current session)
    now = time.time()
    if file_mtimes and (now - file_mtimes[0][1]) < 60:
        file_mtimes = file_mtimes[1:]

    all_files = [f for f, _ in file_mtimes]

    # Analyze up to MAX_SESSIONS
    best_score = None
    for session_file in all_files[:MAX_SESSIONS]:
        info = _analyze_single_session(session_file)
        if info and (best_score is None or info["score"] > best_score["score"]):
            best_score = info

    return best_score


def _analyze_single_session(filepath: Path) -> dict | None:
    """Score a single session JSONL for debugging intensity."""
    edit_count = 0
    build_count = 0
    debug_prompts = 0
    recent_tools = []  # Track tool sequence for edit->build detection
    edit_build_cycles = 0

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f):
                if line_num >= MAX_LINES_PER_SESSION:
                    break
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = obj.get("type")

                # Count debug-related user prompts
                if msg_type == "user":
                    content = obj.get("message", {}).get("content", [])
                    text = ""
                    if isinstance(content, str):
                        text = content.lower()
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                t = item.get("text", "")
                                if not t.startswith("<ide_") and not t.startswith("<system"):
                                    text = t.lower()
                                    break

                    if text and any(kw in text for kw in DEBUG_KEYWORDS):
                        debug_prompts += 1

                # Count tool usage patterns
                elif msg_type == "assistant":
                    content = obj.get("message", {}).get("content", [])
                    if not isinstance(content, list):
                        continue
                    for item in content:
                        if not isinstance(item, dict) or item.get("type") != "tool_use":
                            continue
                        name = item.get("name", "")

                        if name in ("Edit", "Write"):
                            edit_count += 1
                            recent_tools.append("edit")
                        elif name == "Bash":
                            cmd = item.get("input", {}).get("command", "")
                            if "dotnet build" in cmd or "dotnet run" in cmd:
                                build_count += 1
                                # Check if there was a recent edit (edit->build cycle)
                                if "edit" in recent_tools[-5:]:
                                    edit_build_cycles += 1
                                recent_tools.append("build")
                            else:
                                recent_tools.append("other")
                        else:
                            recent_tools.append("other")

    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None

    score = min(100,
        (edit_build_cycles * 10) +
        (debug_prompts * 5) +
        (30 if build_count > 5 else 0)
    )

    return {
        "score": score,
        "edit_build_cycles": edit_build_cycles,
        "debug_prompts": debug_prompts,
        "build_count": build_count,
    }


def format_output(drift: list, session_info: dict | None, times_shown: int = 0) -> str:
    """Format warnings for stdout injection, grouped by priority tier."""
    parts = []

    if drift:
        remaining = max(0, DISMISS_MAX_SHOWS - times_shown)
        dismiss_note = f"(showing {times_shown}/{DISMISS_MAX_SHOWS} — auto-dismisses after {remaining} more)"

        # Group by priority tier
        high = [d for d in drift if d.get("priority") == "HIGH"]
        medium = [d for d in drift if d.get("priority") == "MEDIUM"]

        if high:
            lines = [f"CONTEXT DRIFT [HIGH — auto-update recommended] {dismiss_note}:"]
            for item in high[:3]:
                code_examples = ", ".join(os.path.basename(f) for f in item["code_files"][:2])
                docs = ", ".join(item["expected_docs"][:3])
                lines.append(f"  - {item['subsystem']} ({code_examples}) -> update: {docs}")
            parts.append("\n".join(lines))

        if medium:
            lines = [f"CONTEXT DRIFT [MEDIUM — mention to user] {dismiss_note}:"]
            for item in medium[:3]:
                code_examples = ", ".join(os.path.basename(f) for f in item["code_files"][:2])
                docs = ", ".join(item["expected_docs"][:3])
                lines.append(f"  - {item['subsystem']} ({code_examples}) -> consider: {docs}")
            parts.append("\n".join(lines))

    if session_info and session_info["score"] >= DEBUG_SCORE_THRESHOLD:
        s = session_info
        parts.append(
            f"DEBUGGING SESSION: Last session was debugging-heavy "
            f"({s['edit_build_cycles']} edit-build cycles, "
            f"{s['debug_prompts']} debug prompts, "
            f"score {s['score']}/100). "
            f"If bugs revealed gaps in documentation, consider updating "
            f"relevant context docs or agent descriptions with lessons learned."
        )

    return "\n\n".join(parts)


def main():
    try:
        repo_root = find_repo_root()
        if not repo_root:
            return

        # Handle --dismiss flag (manual override)
        if "--dismiss" in sys.argv:
            head = get_head_sha(repo_root)
            if head:
                save_state(repo_root, {"head_sha": head, "times_shown": DISMISS_MAX_SHOWS})
                print(f"Drift warnings dismissed at {head[:8]}.")
            return

        # 1. Parse SUBSYSTEMS mapping
        server_py = repo_root / "MCP" / "context7_mcp" / "server.py"
        mapping = parse_subsystems(server_py)

        # 2. Detect code/doc drift from recent commits
        drift = detect_code_doc_drift(repo_root, mapping) if mapping else []

        # Deduplicate: if same doc suggested by multiple subsystems, keep the first
        seen_docs = set()
        deduped = []
        for item in drift:
            new_docs = [d for d in item["expected_docs"] if d not in seen_docs]
            if new_docs:
                seen_docs.update(new_docs)
                item["expected_docs"] = new_docs
                deduped.append(item)
        drift = deduped

        # 3. Auto-dismiss logic for code drift
        #    - If HEAD changed since last check, reset counter (new commits = fresh warnings)
        #    - Show warning for DISMISS_MAX_SHOWS sessions, then suppress
        #    - If docs were updated (no drift detected), clear state
        head = get_head_sha(repo_root)
        state = load_state(repo_root)
        times_shown = 0

        if drift and head:
            if state.get("head_sha") == head:
                # Same HEAD — check if we've shown enough times
                times_shown = state.get("times_shown", 0)
                if times_shown >= DISMISS_MAX_SHOWS:
                    drift = []  # Auto-dismiss: already shown N times
                else:
                    times_shown += 1
                    save_state(repo_root, {"head_sha": head, "times_shown": times_shown})
            else:
                # New HEAD — reset counter, show fresh (count this as showing 1)
                times_shown = 1
                save_state(repo_root, {"head_sha": head, "times_shown": 1})
        elif not drift:
            # No drift (docs were updated or no code changes) — clear state
            if state:
                save_state(repo_root, {})

        # 4. Analyze recent session logs
        project_dirs = find_project_dirs()
        session_info = analyze_last_sessions(project_dirs) if project_dirs else None

        # 5. Output warnings (empty = silent)
        output = format_output(drift, session_info, times_shown)
        if output:
            print(output)

    except Exception:
        # Never block session start
        pass


if __name__ == "__main__":
    main()
