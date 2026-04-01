# Context Retrieval MCP Server — Template

A clean, project-agnostic template for the context-retrieval MCP server (Tier 3 of the codified context infrastructure). Copy this into your project and customize.

## Quick Setup

```bash
# 1. Copy this directory into your project
cp -r quickstart/mcp-server /path/to/your-project/mcp-server

# 2. Install dependencies
cd /path/to/your-project/mcp-server
pip install -e .

# 3. Add .mcp.json to your project root
```

Create `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "context-retrieval": {
      "command": "context-retrieval-mcp"
    }
  }
}
```

Restart Claude Code to pick up the new MCP server.

## What to Customize

Open `server.py` and update these sections:

### 1. Path Variables (top of file)

```python
PROJECT_ROOT = Path(__file__).parent.parent  # Your project root
SOURCE_ROOT = PROJECT_ROOT / "src"           # Where source code lives
CONTEXT_DIR = PROJECT_ROOT / ".claude" / "context"  # Context docs location
```

### 2. SUBSYSTEMS Dict

Replace the placeholder entries with your project's subsystems. Each entry maps a key to:
- `name`: Human-readable subsystem name
- `description`: What it does (1-2 sentences)
- `keywords`: Terms that match task descriptions to this subsystem
- `files`: Key source files and context doc paths (relative to SOURCE_ROOT)

Aim for 5-20 subsystems covering your project's major architectural areas.

### 3. AGENTS Dict

Replace with your project's specialized agents (from `.claude/agents/`), or leave empty if not using agents yet. Each entry maps an agent ID to:
- `name`: Human-readable agent name
- `description`: What the agent does
- `triggers`: Keywords that route tasks to this agent
- `model`: `"opus"` for judgment-heavy tasks, `"sonnet"` for pattern-following

### 4. CONTEXT_DESCRIPTIONS Dict (optional)

Add descriptions for your `.claude/context/*.md` files. Files not listed here will still be discoverable but will have empty descriptions.

## 7 Tools Provided

| Tool | Purpose |
|------|---------|
| `list_subsystems()` | Enumerate all architectural subsystems |
| `get_files_for_subsystem(subsystem)` | Get key files for a specific subsystem |
| `find_relevant_context(task_description)` | Match a task to relevant subsystems and files |
| `get_context_files()` | List all context documents in `.claude/context/` |
| `search_context_documents(query)` | Full-text search across context documents |
| `suggest_agent(task_description)` | Recommend which agent to invoke for a task |
| `list_agents()` | Enumerate all agents with descriptions and triggers |

The tool implementations are project-agnostic — they operate on whatever data is in `SUBSYSTEMS` and `AGENTS`. You should not need to modify the tool functions.

## Production Example

For a real-world implementation (~1,600 lines, 20 subsystems, 19 agents), see `mcp-server/server.py` in the companion repo root. That server powers the case study described in the paper.

## Further Reading

- [Companion repo README](../README.md) for the full bootstrapping sequence
- [mcp-server/README.md](../../mcp-server/README.md) for the case study server documentation
- [Codified Context paper](https://arxiv.org/abs/2602.20478) (arXiv:2602.20478)
