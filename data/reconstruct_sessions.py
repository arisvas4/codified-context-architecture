#!/usr/bin/env python3
"""
Reconstruct Claude Code session data from the gap period (Dec 15 2025 - Jan 15 2026)
where conversation JSONL files were purged.

Combines three data sources:
1. Todo files (~/.claude/todos/*.json) - session task lists with file mod times
2. Git commits (game-project repo) - commit messages, dates, file change stats
3. Shell snapshots (~/.claude/shell-snapshots/) - bash command history by epoch

Outputs records in the same CSV format as prompts.csv for merging.

Usage:
    python reconstruct_sessions.py --preview      # Show what would be reconstructed
    python reconstruct_sessions.py --merge         # Append to existing prompts.csv
    python reconstruct_sessions.py --stats         # Show summary statistics
    python reconstruct_sessions.py --preview --stats  # Preview with stats
"""

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(r"c:\Users\big-a\Coding Projects\game-project")
GAP_START = datetime(2025, 12, 15, tzinfo=timezone.utc)
GAP_END = datetime(2026, 1, 16, tzinfo=timezone.utc)  # exclusive upper bound
GAP_START_EPOCH_S = int(GAP_START.timestamp())
GAP_END_EPOCH_S = int(GAP_END.timestamp())
GAP_START_EPOCH_MS = GAP_START_EPOCH_S * 1000
GAP_END_EPOCH_MS = GAP_END_EPOCH_S * 1000

CSV_COLUMNS = [
    'id', 'timestamp', 'date', 'time', 'prompt', 'prompt_full', 'word_count', 'char_count',
    'category', 'category_secondary', 'session_id', 'conversation_file', 'git_branch',
    'model', 'response_tokens_in', 'response_tokens_out', 'response_cache_read',
    'response_cache_create', 'tools_used', 'tool_count', 'agents_spawned', 'agent_types',
    'platform', 'prompt_hash',
    'cost_input_usd', 'cost_output_usd', 'cost_cache_read_usd', 'cost_cache_write_usd', 'cost_total_usd'
]

# Category definitions (copied from extract_prompts.py for self-containment)
CATEGORIES = {
    'physics': ['physics', 'collision', 'velocity', 'knockback', 'spatial', 'raycast', 'force', 'movement'],
    'networking': ['network', 'multiplayer', 'sync', 'lobby', 'host', 'client', 'interpolation', 'latency', 'packet', 'message', 'peer'],
    'rendering': ['render', 'sprite', 'animation', 'camera', 'texture', 'particle', 'visual', 'draw', 'effect', 'bloom', 'shader'],
    'ui': ['menu', 'button', 'ui', 'hud', 'interface', 'overlay', 'screen', 'panel', 'dialog', 'modal', 'tooltip'],
    'combat': ['damage', 'health', 'projectile', 'ability', 'attack', 'weapon', 'powerup', 'fireball', 'bullet'],
    'ai': ['ai', 'behavior', 'enemy', 'chase', 'wander', 'pathfind', 'aggro', 'target', 'flee'],
    'spawning': ['spawn', 'wave', 'spawner'],
    'dungeon': ['dungeon', 'procedural', 'bsp', 'room', 'corridor', 'generation', 'level', 'floor'],
    'input': ['input', 'keyboard', 'controller', 'gamepad', 'controls', 'keybind', 'mouse'],
    'ecs': ['entity', 'component', 'system', 'archetype', 'query', 'world'],
    'artwork': ['sprite', 'texture', 'asset', 'image', 'art', 'placeholder', 'atlas', 'png', 'blender', 'meshy'],
    'devtools': ['debug', 'preview', 'test', 'devtools', 'console', 'cli'],
    'audio': ['sound', 'audio', 'music', 'sfx', 'volume'],
    'content': ['content', 'definition', 'json', 'data', 'load', 'config'],
    'save': ['save', 'load', 'profile', 'slot', 'progress'],
    'hero': ['hero', 'player', 'character', 'class', 'drone'],
    'gamestate': ['state', 'transition', 'hub', 'survival', 'adventure', 'defense', 'payload', 'boss'],
    'build': ['dotnet', 'build', 'compile', 'launch', 'run', 'terminal', 'install', 'homebrew', 'npm', 'nuget'],
    'tooling': ['agent', 'mcp', 'context7', 'claude', 'skill', 'hook'],
    'leveldesign': ['ldtk', 'tiled', 'tilemap', 'tileset', 'map editor', 'room template'],
    'refactor': ['refactor', 'cleanup', 'organize', 'rename', 'restructure'],
    'planning': ['plan', 'phase', 'implement', 'approach', 'what is next', 'begin with', 'what is task', 'what is step',
                 'vertical slice', 'conclude', 'scope', 'roadmap', 'milestone', 'prioritize', 'backlog'],
    'debugging': ['fix', 'bug', 'wrong', 'broken', "doesn't work", 'not working', 'still not', 'why does',
                  'why is', 'issue', 'off by', 'offset', 'misalign', 'crash', 'exception', 'error', 'null ref'],
    'game_design': ['kirby', 'vamp survivor', 'noita', 'wizard with a gun', 'hades', 'diablo', 'design',
                    'mechanic', 'how many combo', 'how many abilit', 'compare to', 'what do you think',
                    'balance', 'feel', 'pacing', 'fun'],
    'documentation': ['document', 'context file', 'write up', 'write about', 'add notes', 'changelog',
                      'devlog', 'readme', 'whitepaper', 'update.*context'],
}

SYSTEM_PATTERNS = [
    'request interrupted',
    '<local-command-',
    'compacted',
    'goodbye',
    'catch you later',
    'warmup',
]

CONFIRMATION_WORDS = {
    'yes', 'no', 'yea', 'yeah', 'nope', 'sure', 'ok', 'okay', 'continue', 'proceed', 'both', 'neither',
    'yep', 'yup', 'looks good', 'go ahead', 'do it', 'sounds good', 'correct', 'right', 'exactly',
    'retry', 'redo', 'rewrite', 're-write', 'repeat', 'b', 'a',
}


# ---------------------------------------------------------------------------
# Shared utilities (mirroring extract_prompts.py)
# ---------------------------------------------------------------------------

def compute_hash(timestamp: str, prompt: str) -> str:
    """Compute SHA256 hash for deduplication."""
    content = f"{timestamp}:{prompt}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]


def classify_prompt(text: str) -> Tuple[str, str]:
    """Classify prompt into primary and secondary categories."""
    text_lower = text.lower()
    text_stripped = text.strip().lower()

    for pattern in SYSTEM_PATTERNS:
        if pattern in text_lower:
            return 'system', ''

    if text_stripped in CONFIRMATION_WORDS or (len(text_stripped) <= 30 and any(
        text_stripped.startswith(w) for w in CONFIRMATION_WORDS
    )):
        return 'confirmation', ''

    scores: Dict[str, int] = {}
    for category, keywords in CATEGORIES.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[category] = score

    if not scores:
        return 'other', ''

    sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary = sorted_cats[0][0]
    secondary = sorted_cats[1][0] if len(sorted_cats) > 1 else ''
    return primary, secondary


def load_existing_hashes(csv_path: Path) -> Set[str]:
    """Load existing prompt hashes from CSV to avoid duplicates."""
    hashes = set()
    if csv_path.exists():
        try:
            with open(csv_path, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    h = row.get('prompt_hash', '')
                    if h:
                        hashes.add(h)
        except Exception as e:
            print(f"  Warning: Could not read existing CSV: {e}")
    return hashes


def make_record(
    timestamp_iso: str,
    prompt_text: str,
    session_id: str = '',
    git_branch: str = '',
    tools_used: str = '',
    tool_count: int = 0,
) -> Dict:
    """Build a CSV-compatible record dict from reconstructed data."""
    try:
        dt = datetime.fromisoformat(timestamp_iso.replace('Z', '+00:00'))
        date_str = dt.strftime('%Y-%m-%d')
        time_str = dt.strftime('%H:%M:%S')
    except Exception:
        date_str = ''
        time_str = ''

    category, category_secondary = classify_prompt(prompt_text)
    word_count = len(prompt_text.split())
    char_count = len(prompt_text)
    prompt_hash = compute_hash(timestamp_iso, prompt_text)

    return {
        'id': 0,  # assigned later
        'timestamp': timestamp_iso,
        'date': date_str,
        'time': time_str,
        'prompt': prompt_text[:500] if len(prompt_text) > 500 else prompt_text,
        'prompt_full': prompt_text if len(prompt_text) > 500 else '',
        'word_count': word_count,
        'char_count': char_count,
        'category': category,
        'category_secondary': category_secondary,
        'session_id': session_id,
        'conversation_file': 'reconstructed',
        'git_branch': git_branch,
        'model': '',
        'response_tokens_in': 0,
        'response_tokens_out': 0,
        'response_cache_read': 0,
        'response_cache_create': 0,
        'tools_used': tools_used,
        'tool_count': tool_count,
        'agents_spawned': 0,
        'agent_types': '',
        'platform': 'windows',
        'prompt_hash': prompt_hash,
        'cost_input_usd': 0.0,
        'cost_output_usd': 0.0,
        'cost_cache_read_usd': 0.0,
        'cost_cache_write_usd': 0.0,
        'cost_total_usd': 0.0,
    }


# ---------------------------------------------------------------------------
# Source 1: Todo files
# ---------------------------------------------------------------------------

def parse_todo_files() -> List[Dict]:
    """
    Parse ~/.claude/todos/*.json for sessions in the gap period.

    Each file is named {session_id}-agent-{session_id}.json.
    Contains a JSON array of {content, status, activeForm}.
    Use file modification time as session date.

    Returns one record per session that has at least one non-empty task.
    """
    todos_dir = Path.home() / ".claude" / "todos"
    if not todos_dir.exists():
        print("  Warning: todos directory not found")
        return []

    records: List[Dict] = []
    skipped_empty = 0
    skipped_out_of_range = 0

    for todo_file in sorted(todos_dir.glob("*.json")):
        # Get modification time
        try:
            mtime = todo_file.stat().st_mtime
        except OSError:
            continue

        if mtime < GAP_START_EPOCH_S or mtime >= GAP_END_EPOCH_S:
            skipped_out_of_range += 1
            continue

        # Extract session ID from filename: {uuid}-agent-{uuid}.json
        fname = todo_file.stem  # e.g. "006fd896-...-agent-006fd896-..."
        parts = fname.split('-agent-')
        session_id = parts[0] if parts else fname

        # Read tasks
        try:
            with open(todo_file, 'r', encoding='utf-8') as f:
                tasks = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        if not isinstance(tasks, list) or len(tasks) == 0:
            skipped_empty += 1
            continue

        # Filter to tasks that have actual content
        task_descriptions = []
        completed_count = 0
        pending_count = 0
        in_progress_count = 0

        for task in tasks:
            if not isinstance(task, dict):
                continue
            content = task.get('content', '').strip()
            if not content:
                continue
            task_descriptions.append(content)
            status = task.get('status', '')
            if status == 'completed':
                completed_count += 1
            elif status == 'pending':
                pending_count += 1
            elif status == 'in_progress':
                in_progress_count += 1

        if not task_descriptions:
            skipped_empty += 1
            continue

        # Build a combined prompt from all task descriptions
        status_summary = []
        if completed_count:
            status_summary.append(f"{completed_count} completed")
        if in_progress_count:
            status_summary.append(f"{in_progress_count} in-progress")
        if pending_count:
            status_summary.append(f"{pending_count} pending")

        prompt_text = (
            f"[Reconstructed from todo session] Tasks ({', '.join(status_summary)}): "
            + "; ".join(task_descriptions)
        )

        # Convert mtime to ISO timestamp
        dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
        timestamp_iso = dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')

        record = make_record(
            timestamp_iso=timestamp_iso,
            prompt_text=prompt_text,
            session_id=session_id,
        )
        records.append(record)

    print(f"  Todo files: {len(records)} sessions with tasks, "
          f"{skipped_empty} empty, {skipped_out_of_range} out of date range")
    return records


# ---------------------------------------------------------------------------
# Source 2: Git commits
# ---------------------------------------------------------------------------

def parse_git_commits() -> List[Dict]:
    """
    Parse git log for commits in the gap period.

    Runs: git log --all --format="%H|%aI|%s" --numstat
    Creates one record per commit with the commit message as the prompt text.

    Returns list of records.
    """
    try:
        result = subprocess.run(
            ['git', 'log', '--all',
             '--format=%H|%aI|%s',
             '--numstat',
             f'--after={GAP_START.strftime("%Y-%m-%d")}',
             f'--before={GAP_END.strftime("%Y-%m-%d")}'],
            capture_output=True, text=True, encoding='utf-8',
            cwd=str(REPO_ROOT),
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"  Warning: git log failed: {e}")
        return []

    if result.returncode != 0:
        print(f"  Warning: git log returned {result.returncode}: {result.stderr.strip()}")
        return []

    records: List[Dict] = []
    lines = result.stdout.strip().split('\n')

    current_hash = ''
    current_date = ''
    current_msg = ''
    files_added = 0
    files_deleted = 0
    files_changed: List[str] = []

    def flush_commit():
        nonlocal current_hash, current_date, current_msg
        nonlocal files_added, files_deleted, files_changed

        if not current_hash:
            return

        # Summarize file changes
        change_summary = f"+{files_added}/-{files_deleted}" if (files_added or files_deleted) else ""
        changed_dirs = set()
        for fpath in files_changed:
            parts = fpath.split('/')
            if len(parts) > 1:
                changed_dirs.add(parts[0])

        prompt_text = f"[Reconstructed from git commit {current_hash[:8]}] {current_msg}"
        if change_summary:
            prompt_text += f" ({change_summary} lines"
            if changed_dirs:
                prompt_text += f" in {', '.join(sorted(changed_dirs)[:5])}"
            prompt_text += ")"

        # Detect branch from commit (best effort: use main)
        git_branch = 'main'

        record = make_record(
            timestamp_iso=current_date,
            prompt_text=prompt_text,
            git_branch=git_branch,
        )
        records.append(record)

        # Reset
        current_hash = ''
        current_date = ''
        current_msg = ''
        files_added = 0
        files_deleted = 0
        files_changed = []

    for line in lines:
        # Check if this is a commit header line (hash|date|message)
        if '|' in line and len(line.split('|')) >= 3:
            # Looks like a commit header — but verify by checking hash format
            parts = line.split('|', 2)
            potential_hash = parts[0].strip()
            if len(potential_hash) == 40 and all(c in '0123456789abcdef' for c in potential_hash):
                # Flush previous commit
                flush_commit()
                current_hash = potential_hash
                current_date = parts[1].strip()
                current_msg = parts[2].strip()
                continue

        # Numstat line: "added\tdeleted\tfilename" or "-\t-\tbinaryfile"
        line = line.strip()
        if not line:
            continue
        numstat_parts = line.split('\t')
        if len(numstat_parts) >= 3:
            added_str = numstat_parts[0]
            deleted_str = numstat_parts[1]
            filename = numstat_parts[2]
            try:
                files_added += int(added_str)
            except ValueError:
                pass  # binary file shows '-'
            try:
                files_deleted += int(deleted_str)
            except ValueError:
                pass
            files_changed.append(filename)

    # Flush last commit
    flush_commit()

    print(f"  Git commits: {len(records)} commits in gap period")
    return records


# ---------------------------------------------------------------------------
# Source 3: Shell snapshots (context only, no individual records)
# ---------------------------------------------------------------------------

def parse_shell_snapshots() -> Dict[str, int]:
    """
    Parse ~/.claude/shell-snapshots/ for snapshots in the gap period.

    Filenames: snapshot-bash-{epoch_ms}-{random}.sh
    Returns dict of {date_str: count} for context/stats.
    Does NOT create individual CSV records (too granular).
    """
    snapshots_dir = Path.home() / ".claude" / "shell-snapshots"
    if not snapshots_dir.exists():
        print("  Warning: shell-snapshots directory not found")
        return {}

    daily_counts: Dict[str, int] = defaultdict(int)
    total = 0

    for snap_file in snapshots_dir.iterdir():
        if not snap_file.name.startswith('snapshot-bash-'):
            continue

        # Extract epoch_ms from filename
        match = re.match(r'snapshot-bash-(\d+)-', snap_file.name)
        if not match:
            continue

        epoch_ms = int(match.group(1))
        if epoch_ms < GAP_START_EPOCH_MS or epoch_ms >= GAP_END_EPOCH_MS:
            continue

        dt = datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc)
        date_str = dt.strftime('%Y-%m-%d')
        daily_counts[date_str] += 1
        total += 1

    print(f"  Shell snapshots: {total} snapshots across {len(daily_counts)} days in gap period")
    return dict(daily_counts)


# ---------------------------------------------------------------------------
# Correlation: match git commits to todo sessions by date
# ---------------------------------------------------------------------------

def correlate_commits_to_sessions(
    todo_records: List[Dict],
    git_records: List[Dict],
) -> List[Dict]:
    """
    For each git commit, try to find a matching todo session by date proximity.
    If found, annotate the git record with the session_id.
    This is best-effort: commits without a close session remain standalone.
    """
    if not todo_records:
        return git_records

    # Build date -> session_id mapping from todos
    session_by_date: Dict[str, str] = {}
    for rec in todo_records:
        date = rec.get('date', '')
        sid = rec.get('session_id', '')
        if date and sid:
            session_by_date[date] = sid

    correlated = 0
    for rec in git_records:
        commit_date = rec.get('date', '')
        if commit_date in session_by_date:
            rec['session_id'] = session_by_date[commit_date]
            correlated += 1
        else:
            # Try adjacent days (+/- 1)
            try:
                dt = datetime.strptime(commit_date, '%Y-%m-%d')
                for delta in [timedelta(days=-1), timedelta(days=1)]:
                    adj_date = (dt + delta).strftime('%Y-%m-%d')
                    if adj_date in session_by_date:
                        rec['session_id'] = session_by_date[adj_date]
                        correlated += 1
                        break
            except ValueError:
                pass

    print(f"  Correlated {correlated}/{len(git_records)} git commits to todo sessions")
    return git_records


# ---------------------------------------------------------------------------
# Preview mode
# ---------------------------------------------------------------------------

def print_preview(
    todo_records: List[Dict],
    git_records: List[Dict],
    snapshot_counts: Dict[str, int],
):
    """Print a detailed preview of what would be reconstructed."""
    print("\n" + "=" * 70)
    print("RECONSTRUCTION PREVIEW")
    print("=" * 70)
    print(f"Gap period: {GAP_START.strftime('%Y-%m-%d')} to {GAP_END.strftime('%Y-%m-%d')}")
    print(f"Total records to create: {len(todo_records) + len(git_records)}")
    print(f"  From todo sessions:  {len(todo_records)}")
    print(f"  From git commits:    {len(git_records)}")
    print()

    # Todo sessions detail
    if todo_records:
        print("-" * 70)
        print("TODO SESSIONS (one entry per session with tasks)")
        print("-" * 70)
        for rec in sorted(todo_records, key=lambda r: r['timestamp']):
            prompt = rec['prompt'][:120] + "..." if len(rec['prompt']) > 120 else rec['prompt']
            print(f"  {rec['date']} {rec['time']}  [{rec['category']:12}]  {prompt}")
        print()

    # Git commits detail
    if git_records:
        print("-" * 70)
        print("GIT COMMITS (one entry per commit)")
        print("-" * 70)
        for rec in sorted(git_records, key=lambda r: r['timestamp']):
            prompt = rec['prompt'][:120] + "..." if len(rec['prompt']) > 120 else rec['prompt']
            sid = rec.get('session_id', '')
            sid_tag = f"  [session: {sid[:8]}]" if sid else ""
            print(f"  {rec['date']} {rec['time']}  [{rec['category']:12}]{sid_tag}  {prompt}")
        print()

    # Shell snapshot context
    if snapshot_counts:
        print("-" * 70)
        print("SHELL SNAPSHOTS (context only, not creating records)")
        print("-" * 70)
        for date_str in sorted(snapshot_counts.keys()):
            count = snapshot_counts[date_str]
            bar = "#" * min(count, 50)
            print(f"  {date_str}  {count:3} snapshots  {bar}")
        print()

    # Category breakdown of all reconstructed records
    all_records = todo_records + git_records
    if all_records:
        print("-" * 70)
        print("CATEGORY BREAKDOWN (all reconstructed records)")
        print("-" * 70)
        cats: Dict[str, int] = defaultdict(int)
        for rec in all_records:
            cats[rec['category']] += 1
        for cat, count in sorted(cats.items(), key=lambda x: x[1], reverse=True):
            pct = (count / len(all_records)) * 100
            print(f"  {cat:15}  {count:3}  ({pct:5.1f}%)")
        print()

    # Daily activity
    print("-" * 70)
    print("DAILY ACTIVITY (records + shell snapshots)")
    print("-" * 70)
    daily: Dict[str, Dict[str, int]] = defaultdict(lambda: {'records': 0, 'snapshots': 0})
    for rec in all_records:
        daily[rec['date']]['records'] += 1
    for date_str, count in snapshot_counts.items():
        daily[date_str]['snapshots'] += count

    for date_str in sorted(daily.keys()):
        d = daily[date_str]
        r_bar = "*" * min(d['records'], 30)
        s_bar = "." * min(d['snapshots'] // 3, 20)  # compressed
        print(f"  {date_str}  {d['records']:2} records  {d['snapshots']:3} snapshots  {r_bar}{s_bar}")
    print()


# ---------------------------------------------------------------------------
# Stats mode
# ---------------------------------------------------------------------------

def print_stats(
    todo_records: List[Dict],
    git_records: List[Dict],
    snapshot_counts: Dict[str, int],
    existing_count: int = 0,
):
    """Print summary statistics."""
    all_records = todo_records + git_records
    total_snapshots = sum(snapshot_counts.values())

    print("\n" + "=" * 70)
    print("RECONSTRUCTION STATISTICS")
    print("=" * 70)

    print(f"\nGap period: {GAP_START.strftime('%Y-%m-%d')} to {GAP_END.strftime('%Y-%m-%d')} (32 days)")
    print(f"\nData sources found:")
    print(f"  Todo sessions with tasks:  {len(todo_records):>4}")
    print(f"  Git commits:               {len(git_records):>4}")
    print(f"  Shell snapshots:           {total_snapshots:>4}")
    print(f"  ----------------------------------")
    print(f"  Total reconstructed records: {len(all_records):>3}")

    if existing_count:
        print(f"\n  Existing prompts.csv rows:   {existing_count}")
        print(f"  After merge (estimate):      {existing_count + len(all_records)}")

    # Date coverage
    dates_with_activity = set()
    for rec in all_records:
        if rec.get('date'):
            dates_with_activity.add(rec['date'])
    for d in snapshot_counts:
        dates_with_activity.add(d)

    print(f"\n  Days with any activity:    {len(dates_with_activity)}/32")

    if all_records:
        dates = sorted(r['date'] for r in all_records if r.get('date'))
        print(f"  First record:              {dates[0]}")
        print(f"  Last record:               {dates[-1]}")

        # Word count stats
        word_counts = [r['word_count'] for r in all_records]
        print(f"\n  Avg words per record:      {sum(word_counts) / len(word_counts):.1f}")
        print(f"  Max words in a record:     {max(word_counts)}")

    print()


# ---------------------------------------------------------------------------
# Merge mode
# ---------------------------------------------------------------------------

def merge_to_csv(
    new_records: List[Dict],
    csv_path: Path,
):
    """
    Merge reconstructed records into the existing prompts.csv.
    Deduplicates by prompt_hash. Reassigns sequential IDs.
    """
    existing_hashes = load_existing_hashes(csv_path)
    existing_rows: List[Dict] = []

    # Read existing rows
    if csv_path.exists():
        try:
            with open(csv_path, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert numeric fields
                    for int_field in ['id', 'word_count', 'char_count',
                                      'response_tokens_in', 'response_tokens_out',
                                      'response_cache_read', 'response_cache_create',
                                      'tool_count', 'agents_spawned']:
                        row[int_field] = int(row.get(int_field, 0) or 0)
                    for float_field in ['cost_input_usd', 'cost_output_usd',
                                        'cost_cache_read_usd', 'cost_cache_write_usd',
                                        'cost_total_usd']:
                        row[float_field] = float(row.get(float_field, 0) or 0)
                    existing_rows.append(row)
        except Exception as e:
            print(f"  Error reading existing CSV: {e}")
            return

    # Filter out duplicates from new records
    added = 0
    skipped = 0
    for rec in new_records:
        h = rec.get('prompt_hash', '')
        if h in existing_hashes:
            skipped += 1
            continue
        existing_rows.append(rec)
        existing_hashes.add(h)
        added += 1

    # Sort all rows by timestamp
    existing_rows.sort(key=lambda r: r.get('timestamp', ''))

    # Reassign sequential IDs
    for i, row in enumerate(existing_rows, 1):
        row['id'] = i

    # Write merged CSV
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_MINIMAL,
                                extrasaction='ignore')
        writer.writeheader()
        writer.writerows(existing_rows)

    print(f"\n  Merged into {csv_path.name}:")
    print(f"    Added:    {added} new records")
    print(f"    Skipped:  {skipped} duplicates")
    print(f"    Total:    {len(existing_rows)} rows")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Reconstruct Claude Code session data from the gap period (Dec 15 2025 - Jan 15 2026)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python reconstruct_sessions.py --preview          # See what would be created
  python reconstruct_sessions.py --preview --stats   # Preview with summary stats
  python reconstruct_sessions.py --merge             # Append to prompts.csv
  python reconstruct_sessions.py --merge --stats     # Merge and show stats
        """,
    )
    parser.add_argument('--preview', action='store_true',
                        help='Print summary of what would be reconstructed')
    parser.add_argument('--merge', action='store_true',
                        help='Append reconstructed entries to existing prompts.csv')
    parser.add_argument('--stats', action='store_true',
                        help='Show summary statistics')
    args = parser.parse_args()

    if not args.preview and not args.merge and not args.stats:
        parser.print_help()
        print("\nError: specify at least one of --preview, --merge, or --stats")
        sys.exit(1)

    script_dir = Path(__file__).parent
    csv_path = script_dir / 'prompts.csv'

    print(f"Reconstructing sessions for gap period: "
          f"{GAP_START.strftime('%Y-%m-%d')} to {GAP_END.strftime('%Y-%m-%d')}")
    print(f"Repo: {REPO_ROOT}")
    print()

    # --- Parse all three sources ---
    print("Parsing data sources...")
    todo_records = parse_todo_files()
    git_records = parse_git_commits()
    snapshot_counts = parse_shell_snapshots()

    # --- Correlate commits to sessions ---
    print("\nCorrelating sources...")
    git_records = correlate_commits_to_sessions(todo_records, git_records)

    all_records = todo_records + git_records

    if not all_records:
        print("\nNo records found in the gap period. Nothing to do.")
        return

    # --- Preview ---
    if args.preview:
        print_preview(todo_records, git_records, snapshot_counts)

    # --- Stats ---
    if args.stats:
        existing_count = 0
        if csv_path.exists():
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    existing_count = sum(1 for _ in f) - 1  # minus header
            except Exception:
                pass
        print_stats(todo_records, git_records, snapshot_counts, existing_count)

    # --- Merge ---
    if args.merge:
        print(f"\nMerging {len(all_records)} reconstructed records into {csv_path.name}...")
        merge_to_csv(all_records, csv_path)
        print("\nDone. Reconstructed entries have conversation_file='reconstructed' for identification.")


if __name__ == '__main__':
    main()
