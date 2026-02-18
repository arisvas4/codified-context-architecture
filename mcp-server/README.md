# Context7 MCP Server

A context-retrieval MCP (Model Context Protocol) server that implements **Layer 2** of the codified context architecture. It gives Claude Code on-demand access to project architecture knowledge without loading everything into the prompt.

## What It Does

The server exposes 7 tools via the MCP protocol:

| Tool | Purpose |
|------|---------|
| `list_subsystems()` | Enumerate all architectural subsystems |
| `get_files_for_subsystem(subsystem)` | Get key files and docs for a subsystem |
| `find_relevant_context(task_description)` | Fuzzy-match a task to relevant subsystems and files |
| `get_context_files()` | List all context documents in `.claude/context/` |
| `search_context_documents(query)` | Full-text search across all context documents |
| `suggest_agent(task_description)` | Recommend which specialized agent to invoke |
| `list_agents()` | Enumerate all agents with descriptions and triggers |

The first 5 tools implement **context retrieval** — they let the AI agent find relevant architecture docs and source files for any task. The last 2 implement **agent routing** — they help the AI agent (or a Plan-mode orchestrator) choose the right specialized sub-agent.

## Architecture

```
┌─────────────────────────────────────────────┐
│  Claude Code (AI Agent)                     │
│  ┌──────────────────────────────────────┐   │
│  │  "I need to fix the camera system"   │   │
│  └──────────────┬───────────────────────┘   │
│                 │ MCP tool call              │
│  ┌──────────────▼───────────────────────┐   │
│  │  Context7 MCP Server                 │   │
│  │  ┌─────────────────────────────────┐ │   │
│  │  │  SUBSYSTEMS dict (the index)    │ │   │
│  │  │  - keywords per subsystem       │ │   │
│  │  │  - file paths per subsystem     │ │   │
│  │  │  - context doc paths            │ │   │
│  │  └──────────────┬──────────────────┘ │   │
│  │                 │ keyword matching    │   │
│  │  ┌──────────────▼──────────────────┐ │   │
│  │  │  Returns: rendering subsystem   │ │   │
│  │  │  Files: Camera2D.cs, ...        │ │   │
│  │  │  Docs: coordinate-systems.md    │ │   │
│  │  └─────────────────────────────────┘ │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

## Key Data Structures

### SUBSYSTEMS dict

The core index. Maps subsystem keys to metadata:

```python
SUBSYSTEMS = {
    "rendering": {
        "name": "Sprite Rendering & Camera",
        "description": "...",
        "keywords": ["sprite", "camera", "draw", "render", ...],
        "files": [
            "ECS/Systems/SpriteRenderSystem.cs",
            "Camera/Camera2D.cs",
            ".claude/context/coordinate-systems.md",
        ],
    },
    # ... ~20 subsystems
}
```

**How retrieval works**: When the agent calls `find_relevant_context("fix camera offset")`, the server tokenizes the task description, matches tokens against each subsystem's keywords, and returns the top-scoring subsystems with their files.

### AGENTS dict

Maps agent names to metadata for routing:

```python
AGENTS = {
    "coordinate-wizard": {
        "description": "Isometric coordinate and camera specialist",
        "triggers": ["camera", "isometric", "world-to-screen", ...],
        "model": "opus",
    },
    # ... 19 agents in the case study
}
```

## Setup

### Prerequisites

- Python 3.10+
- `mcp` package (`pip install mcp`)

### Installation

```bash
# From the mcp-server/ directory
pip install -e .
```

### Claude Code Integration

Add to your project's `.claude/settings.json`:

```json
{
  "mcpServers": {
    "context7": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "/path/to/your/mcp-server"
    }
  }
}
```

Or if installed as a package:

```json
{
  "mcpServers": {
    "context7": {
      "command": "context7-mcp"
    }
  }
}
```

### Path Configuration

Update these variables at the top of `server.py` to match your project:

```python
PROJECT_ROOT = Path(__file__).parent.parent.parent  # Adjust to your layout
ENGINE_ROOT = PROJECT_ROOT / "src"                   # Where source code lives
CONTEXT_DIR = PROJECT_ROOT / ".claude" / "context"   # Where context docs live
```

## Adapting for Your Project

1. **Replace the SUBSYSTEMS dict** with your project's subsystems. Each entry needs:
   - `name`: Human-readable name
   - `description`: What the subsystem does
   - `keywords`: Tokens that match task descriptions to this subsystem
   - `files`: Relative paths to key source files and context docs

2. **Replace the AGENTS dict** (or remove `suggest_agent`/`list_agents` if you don't use specialized agents)

3. **The tool functions are generic** — they operate on whatever data is in SUBSYSTEMS/AGENTS. You shouldn't need to modify the `@mcp.tool` implementations.

4. **Keep the index accurate** — When you add/rename/delete source files, update the SUBSYSTEMS dict. The `validate-architecture.sh` script (in `framework/scripts/`) automates checking for stale references.

## How It Fits in the Architecture

```
Layer 3: Specialized Agents (19 domain experts)
    ↑ suggest_agent() routes tasks to agents
Layer 2: Context Retrieval (THIS SERVER)
    ↑ find_relevant_context() discovers docs
Layer 1: Constitution (CLAUDE.md)
    ↑ always loaded, references Layer 2 tools
```

The constitution (CLAUDE.md) instructs the AI agent to call MCP tools *first* when exploring unfamiliar code. This creates a pull-based retrieval pattern where the agent requests exactly the context it needs, rather than having everything loaded upfront.

## File Structure

```
mcp-server/
├── server.py        # Main server (~1,600 lines, mostly data)
├── pyproject.toml   # Package configuration
├── __init__.py      # Package exports
├── __main__.py      # Entry point
└── README.md        # This file
```

The server is intentionally a single file. The SUBSYSTEMS and AGENTS dicts are large but serve as a readable, grep-able index that's easy to maintain alongside the codebase.
