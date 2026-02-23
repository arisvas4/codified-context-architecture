# Quickstart: Codified Context Factory Agents

Three standalone agents that set up the **codified context infrastructure** from scratch. Download this folder, copy the agents into your project, and let your AI assistant do the rest.

## Quick Start (For Humans)

These agents implement the architecture described in "Codified Context: Infrastructure for AI Agents in a Complex Codebase" (Vasilopoulos, 2026). They work with any AI coding assistant that supports custom agent specifications (e.g., Claude Code's `.claude/agents/` directory).

**What they do:**

| Factory | Creates | Tier |
|---------|---------|-------|
| `constitution-factory` | Your project's CLAUDE.md (root instruction document loaded every session) | Tier 1: Constitution |
| `agent-factory` | Specialized domain-expert agents with deep codified knowledge | Tier 2: Agents |
| `context-factory` | Knowledge base documents in `.claude/context/` | Tier 3: Knowledge Base |

**Setup in 3 steps:**

1. Copy the three factory folders into your project's `.claude/agents/` directory
2. Ask your AI assistant to read this README
3. Run the `constitution-factory` first — it creates the foundation everything else builds on

> **Tip:** The fastest way to get started is to paste this to your AI assistant:
>
> *"Read the bootstrap README and help me set up the codified context infrastructure for this project."*

The AI will handle the rest — reading the factory specs, asking you the right questions, and generating your project's knowledge infrastructure.

---

## AI-Readable Setup Guide

*The sections below are optimized for AI assistants. If you are a human, you can skip to "What Each Factory Does" for an overview, or let your AI assistant read this entire file and guide you through setup.*

### Installation

1. Copy the three factory directories into the target project:
   ```
   your-project/
   └── .claude/agents/
       ├── constitution-factory/AGENT.md
       ├── agent-factory/AGENT.md
       └── context-factory/AGENT.md
   ```

2. Verify the files are in place:
   ```bash
   ls .claude/agents/*/AGENT.md
   ```

3. The factories are now available as agents. Each factory asks exactly 3 questions before generating anything.

### Bootstrapping Sequence

Follow this order. Each tier builds on the previous one.

#### Phase 1: Constitution (do this first)

Invoke `constitution-factory`. It will ask:

| # | Question | Purpose |
|---|----------|---------|
| 1 | What is this project? | Tech stack, domain, purpose |
| 2 | How mature is it? | Greenfield / Active / Mature — determines depth |
| 3 | What should agents prioritize? | Code quality standards and principles |

**Output:** A `CLAUDE.md` file at the project root containing architecture overview, build commands, conventions, key files reference, and (for active/mature projects) infrastructure governance checklists. Optionally scaffolds MCP retrieval infrastructure.

**Expected size:** Greenfield 200-400 lines, Active 400-700 lines, Mature 700-1200+ lines.

#### Phase 2: Agents (as domains emerge)

You do not need to create all agents upfront. Create agents when:
- A domain has recurring failure modes (the AI keeps making the same category of mistake)
- A domain requires specialized knowledge that generic prompting misses
- You want to delegate a complex workflow to a domain expert

Invoke `agent-factory`. It will ask:

| # | Question | Purpose |
|---|----------|---------|
| 1 | What does this agent do? | Domain, purpose, scope |
| 2 | Read-only or read-write? | Advisory vs. builder |
| 3 | Knowledge depth? | Light (150-250 lines) / Standard (300-500) / Deep (700-1000+) |

**Output:** An `AGENT.md` file in `.claude/agents/{agent-id}/`, plus updates to the constitution's trigger tables and MCP registry (if they exist).

#### Phase 3: Knowledge Base (as systems grow)

Create context documents when a subsystem becomes complex enough that its conventions, patterns, and edge cases don't fit in the constitution's breadcrumb summary.

Invoke `context-factory`. It will ask:

| # | Question | Purpose |
|---|----------|---------|
| 1 | What is this context doc about? | System, feature, or domain |
| 2 | Current reality or blueprint? | Documenting existing vs. planned systems |
| 3 | Knowledge depth? | Compact (150-250) / Standard (300-500) / Comprehensive (600-1000+) |

**Output:** A `.claude/context/{topic}.md` file, plus MCP subsystem registration and bidirectional cross-references to related docs.

### What Each Factory Does

#### Constitution Factory (`constitution-factory`)

Creates the root instruction document (CLAUDE.md) that AI agents load at the start of every session. The constitution is simultaneously scannable (agents read it every time), comprehensive (covers every major system), and prescriptive (tells agents what to do, not just describes how things work).

**Key capabilities:**
- Detects tech stack from build files (package.json, *.csproj, pyproject.toml, Cargo.toml, etc.)
- Discovers project structure, build commands, and conventions from the codebase
- Generates feature breadcrumbs (5-10 line summaries with cross-references to detailed docs)
- Creates agent trigger tables and MCP subsystem references if infrastructure exists
- Adapts to 5 project domains: Game Dev, Web App, CLI/Library, Data Science/ML, General
- Optionally scaffolds MCP retrieval server for active/mature projects

#### Agent Factory (`agent-factory`)

Creates specialized domain-expert agents that embed deep codified knowledge. Agents blend two knowledge sources: codebase exploration (real file paths, API signatures, code patterns) and AI expertise (industry-standard patterns, checklists, decision frameworks).

**Key capabilities:**
- Produces read-only (advisory) or read-write (builder) agents
- Three depth tiers: Light (validators), Standard (most agents), Deep (complex domains)
- Automatically selects model (opus for judgment-heavy, sonnet for pattern-following)
- Generates trigger keywords for automatic routing
- Handles all registration points (constitution tables, MCP registry)

#### Context Factory (`context-factory`)

Creates knowledge base documents — AI-parseable system blueprints that serve as the backbone of the agent ecosystem. These are the detailed specifications that agents load on-demand when working in a specific domain.

**Key capabilities:**
- Produces current-reality docs, blueprints (planned systems), or mixed
- Three depth tiers: Compact, Standard, Comprehensive
- Adapts to 5 content types: System docs, Content definitions, Network/Protocol, Visual/Design specs, Blueprints
- Optimizes for information density (tables over prose, compact chains over ASCII art)
- Handles MCP registration and bidirectional cross-referencing

### Architecture Overview

The three-tier architecture separates project knowledge by loading strategy:

```
Tier 1: Constitution (Hot Memory)
  Always loaded every session. Conventions, orchestration rules,
  agent trigger tables. ~1-5% of total knowledge, high signal density.
  File: CLAUDE.md at project root.

Tier 2: Specialized Agents (Domain Specialists)
  Invoked per task via trigger table routing. Each agent embeds
  deep domain knowledge (~70% domain content, ~30% behavioral rules).
  Files: .claude/agents/{agent-id}/AGENT.md

Tier 3: Knowledge Base (Cold Memory)
  Retrieved on-demand via MCP or manual loading. Detailed system
  specifications, API references, tuning constants.
  Files: .claude/context/{topic}.md
```

**Key design principles:**
- Hot/cold separation prevents context window exhaustion as knowledge scales
- Agents are domain experts, not generic helpers — they carry project-specific patterns
- The constitution orchestrates routing: trigger tables map file changes to specialist agents
- Context docs are AI-first (information-dense tables) and human-readable second
- All three tiers can be AI-generated under human architectural direction

### Adapting for Your Tool

These factories are written for Claude Code's `.claude/agents/` system, but the patterns are transferable:

| Component | Claude Code | Other Tools |
|-----------|------------|-------------|
| Constitution | `CLAUDE.md` at project root | `.cursorrules`, `.github/copilot-instructions.md`, custom system prompts |
| Agent specs | `.claude/agents/{id}/AGENT.md` with frontmatter | Custom prompt files, tool configurations, or system prompt templates |
| Knowledge base | `.claude/context/*.md` + MCP retrieval | RAG pipelines, prompt includes, documentation directories |
| MCP retrieval | FastMCP server with keyword matching | Embedding-based retrieval, file watchers, IDE plugins |

**To adapt the factories for a different tool:**
1. Use the constitution factory's output (CLAUDE.md) as a template for your tool's instruction format
2. Convert agent AGENT.md files into your tool's prompt/configuration format
3. Keep context docs as-is (markdown is universal) but adapt the retrieval mechanism

### Growth Pattern

A typical bootstrapping timeline:

| Phase | What to create | When |
|-------|---------------|------|
| Day 1 | Constitution only | Project start — even a general gist helps |
| Week 1-2 | First 1-2 agents | When you notice recurring mistakes in a domain |
| Week 2-4 | First 3-5 context docs | When subsystems get complex enough to need specs |
| Ongoing | New agents + docs as needed | When new domains emerge or failure modes repeat |

The knowledge-to-code ratio typically grows from ~10% early on to ~20–25% at maturity (the case study in the paper reached ~24%). This is not documentation overhead — it is infrastructure that prevents bugs and accelerates development.
