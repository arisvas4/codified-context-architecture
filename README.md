# Codified Context: Infrastructure for AI Agents in a Complex Codebase

A *codified context infrastructure* — structured, machine-readable project knowledge that AI coding agents depend on to maintain coherence across sessions, follow conventions, and avoid repeating mistakes.

Companion repository to: *"Codified Context: Infrastructure for AI Agents in a Complex Codebase"* by Aris Vasilopoulos ([arXiv, forthcoming](#links)).

## The Problem

LLM-based coding agents lack persistent memory: each session begins without awareness of prior sessions, established conventions, or past mistakes. Single-file manifests (`.cursorrules`, `CLAUDE.md`) help with small projects, but they do not scale beyond modest codebases — a 1,000-line prototype can be fully described in a single prompt, but a 100,000-line system cannot. Without structured knowledge transfer, agents on large projects:
- Forget architectural conventions and repeat known mistakes
- Lose context about subsystem interactions across files
- Require lengthy re-explanations of project structure
- Make inconsistent decisions that drift from established patterns

## The Solution: Three-Tier Context Infrastructure

```
┌─────────────────────────────────────────────────────────────┐
│  Tier 1: CONSTITUTION (Hot Memory — always loaded)          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ CLAUDE.md                                             │  │
│  │ • Conventions, build commands, naming standards       │  │
│  │ • System registration checklists                      │  │
│  │ • Agent trigger table (when to invoke which agent)    │  │
│  │ • Key file reference map                              │  │
│  └───────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  Tier 2: SPECIALIZED AGENTS                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ Code     │ │ Network  │ │ Debug    │ │ UI/UX    │      │
│  │ Reviewer │ │ Protocol │ │ Profiler │ │ Designer │  ... │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│  Domain experts with focused prompts + context access       │
├─────────────────────────────────────────────────────────────┤
│  Tier 3: KNOWLEDGE BASE + RETRIEVAL (Cold Memory)           │
│  ┌──────────────────────┐  ┌──────────────────────────┐    │
│  │ .claude/context/*.md │  │ MCP Retrieval Service    │    │
│  │ • Subsystem specs    │  │ • list_subsystems()      │    │
│  │ • Architecture docs  │  │ • find_relevant_context() │    │
│  │ • Protocol docs      │  │ • search_context_docs()   │    │
│  │ • Pattern guides     │  │ • get_files_for_subsystem()│   │
│  └──────────────────────┘  └──────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

**Tier 1** (hot memory) is loaded into every agent session automatically. It contains project conventions, checklists, and orchestration protocols that route tasks to specialized agents.

**Tier 2** consists of specialized agents — domain-expert personas with focused prompts and embedded project knowledge. They are invoked automatically based on trigger conditions in the constitution.

**Tier 3** (cold memory) contains detailed specification documents loaded on demand. An MCP retrieval service maps tasks to relevant files, so agents only load what they need.

## Key Findings (from the Paper)

| Metric | Value |
|--------|-------|
| Knowledge-to-code ratio | ~24% (1 line of documentation per 4 lines of code) |
| Context infrastructure | ~26,000 lines across constitution + 34 specs + 19 agents |
| Agent amplification | 2,801 prompts → 1,197 agent invocations → 16,522 agent turns |

## Repository Structure

```
quickstart/             Factory agents to bootstrap the architecture
  constitution-factory/       Generate a constitution for any project
  agent-factory/              Generate specialized agents
  context-factory/            Generate context base documents
  README.md                   Setup guide

framework/              Generic templates to build your own architecture
  constitution-template.md    Annotated CLAUDE.md skeleton
  context-docs/               Example context base documents
  agent-specs/                Example agent specifications
  scripts/                    Validation and staleness detection

mcp-server/             MCP retrieval service (Tier 3 implementation)
  server.py                   All 6 tools with example subsystems
  pyproject.toml              Package configuration
  README.md                   Setup instructions

case-study/             Real artifacts from the paper's case study project
  CLAUDE.md                   The actual constitution (~660 lines, sanitized)
  context-docs/               Real knowledge base documents
  agent-specs/                4 real agent specifications
  mcp-server/                 The full MCP server

data/                   Interaction data and analysis
  extract_prompts.py          Prompt extraction from Claude Code JSONL
  data-collection-methodology.md
  data-extraction-methodology.md
  README.md

paper/                  Paper reference, abstract, and citation
```

## Quick Start

### 1. Create Your Constitution

Copy and customize `framework/constitution-template.md` → your project's `CLAUDE.md`:

```bash
cp framework/constitution-template.md /your-project/CLAUDE.md
# Edit sections: Tech Stack, Build Commands, Architecture, Conventions
```

### 2. Write Context Documents

For each major subsystem, create a spec in `.claude/context/`:

```bash
mkdir -p /your-project/.claude/context
cp framework/context-docs/example-save-system.md /your-project/.claude/context/save-system.md
# Edit to match your project's actual architecture
```

### 3. Set Up MCP Retrieval

Install the MCP server for on-demand context loading:

```bash
cp -r mcp-server/ /your-project/MCP/context_mcp/
# Edit SUBSYSTEMS dict in server.py to match your project
# Add to .claude/settings.json:
# { "mcpServers": { "context": { "command": "python", "args": ["-m", "MCP.context_mcp"] } } }
```

### 4. Add Specialized Agents

Create agent specifications in `.claude/agents/`:

```bash
mkdir -p /your-project/.claude/agents/code-reviewer
cp framework/agent-specs/example-code-reviewer.md /your-project/.claude/agents/code-reviewer/AGENT.md
```

### 5. Validate Cross-References

Run the validation script to check that all three tiers reference each other correctly:

```bash
cp framework/scripts/validate-architecture.sh /your-project/.claude/scripts/
bash /your-project/.claude/scripts/validate-architecture.sh
```

## Design Principles

1. **Documentation as infrastructure.** Context documents are load-bearing artifacts that AI agents depend on to produce correct output — living specifications, not passive reference material. When a specification goes stale, agents generate code based on outdated information.

2. **Written for AI, not humans.** Context documents use tables, code blocks, and explicit patterns rather than prose. Agents parse structured content more reliably than natural language descriptions.

3. **Hot/cold memory separation.** The constitution (hot memory) is always present. Specifications (cold memory) are loaded on demand via MCP retrieval. This keeps token usage efficient while making deep context available when needed.

4. **Cross-referenced and validated.** The constitution references context docs, context docs reference source files, and the MCP server indexes both. A validation script checks all cross-references on every session start.

5. **Iteratively grown, not designed upfront.** The infrastructure emerged from real development needs. Documents were created when agents made mistakes, not as a planning exercise. Start small and add context as patterns emerge.

6. **Agents as domain experts.** Specialized agents carry focused prompts and embedded domain knowledge, invoked automatically by trigger conditions. A code reviewer is invoked after every system modification; a network specialist is invoked for any sync-related work.

## Links

- **Paper:** arXiv *(forthcoming)*
- **Author:** [Aris Vasilopoulos](https://github.com/arisvas4)

## License

MIT
