# =============================================================================
# Context Retrieval MCP Server — Template
# =============================================================================
#
# WHAT THIS IS:
#   A clean, project-agnostic template for the context-retrieval MCP server
#   (Tier 3 of the codified context architecture). Copy this into your project
#   and customize the data dicts — the tool implementations are generic.
#
# WHAT THIS DOES:
#   Provides 7 MCP tools that let AI agents discover:
#   - Which subsystems exist and what files belong to each
#   - Which context documents are relevant to a given task
#   - Which specialized agent to invoke for a task
#   - Full-text search across all context documents
#
# HOW TO ADAPT:
#   1. Update PROJECT_ROOT, SOURCE_ROOT, CONTEXT_DIR paths (below)
#   2. Replace SUBSYSTEMS dict with your project's subsystems
#   3. Replace AGENTS dict with your project's agents (or leave empty)
#   4. Optionally populate CONTEXT_DESCRIPTIONS for richer doc metadata
#   5. Install: pip install -e .
#   6. Register in .mcp.json: { "mcpServers": { "context-retrieval":
#      { "command": "context-retrieval-mcp" } } }
#
# The 7 tool functions are project-agnostic — they operate on whatever data
# is in SUBSYSTEMS and AGENTS. You should not need to modify them.
#
# For a production example (~1,600 lines, 20 subsystems, 19 agents), see
# the case study server at mcp-server/server.py in the companion repo.
# =============================================================================

"""
Context Retrieval MCP Server

Provides context discovery for AI coding agents to find relevant
project architecture and files when starting new tasks.
"""

import logging
import re
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Suppress verbose MCP logging
logging.getLogger("mcp").setLevel(logging.ERROR)

# =============================================================================
# Path Configuration — TODO: Update these for your project
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent  # Your project root
SOURCE_ROOT = PROJECT_ROOT / "src"           # Where source code lives
CONTEXT_DIR = PROJECT_ROOT / ".claude" / "context"  # Where context docs live

# Create the FastMCP server
mcp = FastMCP("Context Retrieval")


# =============================================================================
# Architecture Data — REPLACE WITH YOUR PROJECT'S DATA
# =============================================================================

# Each subsystem maps a key to: name, description, keywords, and key files.
# Keywords are matched against task descriptions for retrieval.
# Files should be relative paths from SOURCE_ROOT (source files) or
# PROJECT_ROOT (context docs).

SUBSYSTEMS = {
    # REPLACE THESE with your project's subsystems. Each entry needs:
    #   - name: Human-readable subsystem name
    #   - description: What it does (1-2 sentences)
    #   - keywords: Terms that match task descriptions to this subsystem
    #   - files: Key source files and context docs (relative paths)
    #
    # Aim for 5-20 subsystems covering your project's major areas.

    "authentication": {
        "name": "Authentication & Authorization",
        "description": "User authentication, session management, and access control",
        "keywords": ["auth", "login", "session", "token", "permission", "role", "jwt", "password", "oauth"],
        "files": [
            "auth/auth_service.py",
            "auth/middleware.py",
            ".claude/context/auth-system.md",
        ],
    },
    "database": {
        "name": "Database & Data Access",
        "description": "Database models, migrations, and query patterns",
        "keywords": ["database", "model", "migration", "query", "orm", "schema", "table", "sql"],
        "files": [
            "models/user.py",
            "models/base.py",
            "database/connection.py",
            ".claude/context/data-model.md",
        ],
    },
    "api": {
        "name": "API Layer",
        "description": "REST API endpoints, request validation, and response formatting",
        "keywords": ["api", "endpoint", "route", "request", "response", "validation", "rest", "handler"],
        "files": [
            "routes/users.py",
            "routes/products.py",
            "middleware/validation.py",
            ".claude/context/api-patterns.md",
        ],
    },
}


# Each agent maps an ID to: name, description, triggers, and model.
# Triggers are keywords matched against task descriptions for routing.
# Model is "opus" (judgment-heavy tasks) or "sonnet" (pattern-following).

AGENTS = {
    # REPLACE THESE with your project's agents, or leave empty if not using
    # specialized agents yet. Each entry needs:
    #   - name: Human-readable agent name
    #   - description: What the agent does
    #   - triggers: Keywords that route tasks to this agent
    #   - model: "opus" for judgment-heavy, "sonnet" for pattern-following

    "code-reviewer": {
        "name": "Code Reviewer",
        "description": "Reviews code changes for correctness, style, and best practices",
        "triggers": ["review", "refactor", "quality", "patterns", "cleanup", "code review"],
        "model": "opus",
    },
    "test-writer": {
        "name": "Test Writer",
        "description": "Generates and maintains test suites with good coverage",
        "triggers": ["test", "coverage", "assertion", "mock", "fixture", "unit test", "integration test"],
        "model": "sonnet",
    },
}


# Optional: Descriptions for context documents in .claude/context/.
# Files not listed here will use their filename as the description.
CONTEXT_DESCRIPTIONS = {
    # "architecture": "Core architecture overview and design patterns",
    # "auth-system": "Authentication and session management patterns",
    # "data-model": "Database schema, relationships, and migration strategy",
    # "api-patterns": "REST API conventions, error handling, and validation",
}


# =============================================================================
# MCP Tools — These are project-agnostic. No changes needed.
# =============================================================================

@mcp.tool()
def suggest_agent(task_description: str) -> dict:
    """
    Suggest which specialized agent to invoke for a given task.

    Use this at the start of a task to get agent recommendations based on
    keyword matching against registered agents.

    Args:
        task_description: Description of the task you're about to perform

    Returns:
        Dictionary with recommended agent(s), matched triggers, and confidence
    """
    task_lower = task_description.lower()
    task_words = set(re.findall(r'\b\w+\b', task_lower))
    matches = []

    # Precompute trigger uniqueness: triggers in fewer agents are more informative
    trigger_agent_count: dict[str, int] = {}
    for info in AGENTS.values():
        for t in info["triggers"]:
            trigger_agent_count[t] = trigger_agent_count.get(t, 0) + 1

    for agent_id, info in AGENTS.items():
        score = 0.0
        matched_triggers = []

        for trigger in info["triggers"]:
            trigger_words = trigger.split()
            matched = False
            if len(trigger_words) == 1:
                # Single-word: exact word boundary match (not substring)
                matched = trigger in task_words
            else:
                # Multi-word phrase: check as substring (word order matters)
                matched = trigger in task_lower

            if matched:
                # Base score: multi-word triggers worth more
                base = len(trigger_words)
                # Uniqueness bonus: triggers in fewer agents score higher
                uniqueness = 1.0 / trigger_agent_count.get(trigger, 1)
                score += base * (1.0 + uniqueness)
                matched_triggers.append(trigger)

        # Also check description (weak signal)
        if any(word in info["description"].lower() for word in task_words if len(word) > 3):
            score += 0.5

        if score > 0:
            matches.append({
                "agent": agent_id,
                "name": info["name"],
                "description": info["description"],
                "model": info["model"],
                "score": score,
                "matched_triggers": matched_triggers,
            })

    # Sort by score descending
    matches.sort(key=lambda x: x["score"], reverse=True)

    # Determine confidence level
    top_score = matches[0]["score"] if matches else 0
    confidence = "high" if top_score >= 4 else "medium" if top_score >= 2 else "low" if top_score >= 1 else "none"

    result = {
        "task": task_description,
        "recommendation": matches[0]["agent"] if matches else None,
        "confidence": confidence,
        "suggested_agents": matches[:3],  # Top 3
        "should_invoke": confidence in ["high", "medium"],
    }

    # Add disambiguation hint when top agents are tied
    if len(matches) >= 2 and matches[0]["score"] == matches[1]["score"]:
        tied = [m["agent"] for m in matches if m["score"] == matches[0]["score"]]
        result["disambiguation"] = f"Tied between {', '.join(tied)}. Check which files you're modifying to decide."

    return result


@mcp.tool()
def list_agents() -> dict:
    """
    List all available specialized agents with their descriptions.

    Returns:
        Dictionary of agent names, descriptions, and models
    """
    return {
        agent_id: {
            "name": info["name"],
            "description": info["description"],
            "model": info["model"],
            "triggers": info["triggers"],
        }
        for agent_id, info in AGENTS.items()
    }


@mcp.tool()
def list_subsystems() -> dict:
    """
    List all architectural subsystems with brief descriptions.

    Returns:
        Dictionary of subsystem names and descriptions
    """
    return {
        key: {
            "name": info["name"],
            "description": info["description"],
            "keywords": info["keywords"],
        }
        for key, info in SUBSYSTEMS.items()
    }


@mcp.tool()
def get_files_for_subsystem(subsystem: str) -> dict:
    """
    Get key file paths for a specific subsystem.

    Args:
        subsystem: Subsystem key (e.g., 'authentication', 'database', 'api')

    Returns:
        Dictionary with subsystem info and file paths
    """
    if subsystem not in SUBSYSTEMS:
        return {
            "error": f"Unknown subsystem: {subsystem}",
            "available": list(SUBSYSTEMS.keys()),
        }

    info = SUBSYSTEMS[subsystem]
    base_path = str(SOURCE_ROOT.relative_to(PROJECT_ROOT))

    return {
        "subsystem": subsystem,
        "name": info["name"],
        "description": info["description"],
        "files": [f"{base_path}/{f}" for f in info["files"]],
    }


@mcp.tool()
def find_relevant_context(task_description: str) -> dict:
    """
    Find relevant architecture sections and files for a given task.

    Args:
        task_description: Description of the task to find context for

    Returns:
        Dictionary with relevant subsystems and suggested files
    """
    task_lower = task_description.lower()

    # Score each subsystem based on keyword matches
    matches = []
    for key, info in SUBSYSTEMS.items():
        score = 0
        matched_keywords = []

        for keyword in info["keywords"]:
            if keyword in task_lower:
                score += 1
                matched_keywords.append(keyword)

        # Also check name and description
        if info["name"].lower() in task_lower:
            score += 2

        if score > 0:
            matches.append({
                "subsystem": key,
                "name": info["name"],
                "score": score,
                "matched_keywords": matched_keywords,
                "files": info["files"],
            })

    # Sort by score descending
    matches.sort(key=lambda x: x["score"], reverse=True)

    # Build file list from top matches
    base_path = str(SOURCE_ROOT.relative_to(PROJECT_ROOT))
    suggested_files = []
    for match in matches[:3]:  # Top 3 matches
        for f in match["files"]:
            full_path = f"{base_path}/{f}"
            if full_path not in suggested_files:
                suggested_files.append(full_path)

    return {
        "task": task_description,
        "relevant_subsystems": matches[:5],  # Top 5 matches
        "suggested_files": suggested_files[:10],  # Top 10 files
    }


@mcp.tool()
def get_context_files() -> dict:
    """
    List all available context documents in .claude/context/.

    Returns:
        Dictionary with context file names and paths
    """
    if not CONTEXT_DIR.exists():
        return {"error": "Context directory not found", "expected": str(CONTEXT_DIR)}

    files = []
    for f in CONTEXT_DIR.glob("*.md"):
        description = CONTEXT_DESCRIPTIONS.get(f.stem, "")
        files.append({
            "name": f.stem,
            "path": str(f.relative_to(PROJECT_ROOT)),
            "description": description,
        })

    return {
        "context_directory": str(CONTEXT_DIR.relative_to(PROJECT_ROOT)),
        "files": sorted(files, key=lambda x: x["name"]),
    }


@mcp.tool()
def search_context_documents(query: str) -> dict:
    """
    Search all context documents for a keyword or phrase.

    Args:
        query: Search term or phrase to find in context documents

    Returns:
        Dictionary with matching sections from context documents
    """
    if not CONTEXT_DIR.exists():
        return {"error": "Context directory not found"}

    query_lower = query.lower()
    results = []

    for doc_file in CONTEXT_DIR.glob("*.md"):
        try:
            content = doc_file.read_text(encoding="utf-8")
            lines = content.split("\n")

            # Find matching lines with context
            matches = []
            for i, line in enumerate(lines):
                if query_lower in line.lower():
                    # Get surrounding context (2 lines before and after)
                    start = max(0, i - 2)
                    end = min(len(lines), i + 3)
                    context_lines = lines[start:end]
                    matches.append({
                        "line_number": i + 1,
                        "context": "\n".join(context_lines),
                    })

            if matches:
                results.append({
                    "document": doc_file.stem,
                    "path": str(doc_file.relative_to(PROJECT_ROOT)),
                    "matches": matches[:10],  # Limit to 10 matches per doc
                    "total_matches": len(matches),
                })
        except Exception:
            continue

    # Also search SUBSYSTEMS keywords
    subsystem_matches = []
    for key, info in SUBSYSTEMS.items():
        if query_lower in info["name"].lower() or query_lower in info["description"].lower():
            subsystem_matches.append({
                "subsystem": key,
                "name": info["name"],
                "description": info["description"],
            })
        else:
            for keyword in info["keywords"]:
                if query_lower in keyword.lower():
                    subsystem_matches.append({
                        "subsystem": key,
                        "name": info["name"],
                        "matched_keyword": keyword,
                    })
                    break

    return {
        "query": query,
        "document_matches": results,
        "subsystem_matches": subsystem_matches,
    }


# =============================================================================
# Entry Point
# =============================================================================

def main():
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
