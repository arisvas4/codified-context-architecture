# Constitution Template (CLAUDE.md)

> **Usage**: Copy this file into your project root as `CLAUDE.md`. Replace all
> `[BRACKETED PLACEHOLDERS]` with your project-specific details. Delete sections
> that don't apply. Remove all `<!-- ANNOTATION -->` comments once customized.
>
> **Section ordering matters.** The constitution is organized from most architecturally
> significant (agent orchestration, context retrieval, subsystem mapping) to most
> conventional (build commands, file references). This ordering reflects our finding
> that the agent orchestration layer and structured context retrieval are the primary
> differentiators of the codified context architecture — without them, CLAUDE.md is
> just another README.

---

# [PROJECT NAME]

<!-- ANNOTATION: One-sentence description. The AI agent reads this first to calibrate
     every response. Be specific about genre/domain — "REST API for healthcare scheduling"
     is better than "a web app". -->

[One-sentence description of what this project is and does.]

## Tech Stack

<!-- ANNOTATION: Explicit tech stack prevents the agent from suggesting incompatible
     libraries or writing code for the wrong framework version. List every major
     dependency — the agent will respect these as constraints. -->

- **Language:** [e.g., TypeScript 5.x, Python 3.12, C# / .NET 8.0]
- **Framework:** [e.g., Next.js 14, FastAPI, MonoGame]
- **Database:** [e.g., PostgreSQL 16, SQLite, DynamoDB]
- **ORM / Data layer:** [e.g., Prisma, SQLAlchemy, Dapper]
- **Testing:** [e.g., Jest + Playwright, pytest, xUnit]
- **Build:** [e.g., Vite, webpack, MSBuild / dotnet CLI]

---

<!-- ═══════════════════════════════════════════════════════════════════════
     LAYER 3: AGENT ORCHESTRATION (highest architectural novelty)

     This section defines WHEN specialized agents are invoked. In the
     codified context architecture, this is the primary mechanism for
     injecting domain expertise — each agent carries its own knowledge
     base in its AGENT.md spec. The trigger table is the "routing layer"
     that connects tasks to the right specialist.
     ═══════════════════════════════════════════════════════════════════════ -->

## Custom Agents

<!-- ANNOTATION: The trigger table is the MOST IMPORTANT section for multi-agent
     architectures. It tells the orchestrating agent WHEN to hand off work to a
     specialist instead of attempting it with general knowledge. Without this table,
     agents attempt work outside their expertise and produce lower-quality output.

     Two trigger categories:
     - AUTOMATIC: Agent MUST be invoked when the condition matches (pre-change)
     - POST-CHANGE: Agent invoked AFTER work is done (quality gate)

     The Quick Reference table gives model/cost guidance for each agent. -->

Specialized agents in `[agents directory]`. **Invoke agents proactively** when trigger conditions match.

### Automatic Triggers (MUST invoke if condition matches)

| If you are touching or researching... | Invoke Agent |
|---------------------------------------|--------------|
| [Trigger condition 1 — e.g., database schema changes, migrations] | `[agent-name]` |
| [Trigger condition 2 — e.g., API contract changes, OpenAPI spec] | `[agent-name]` |
| [Trigger condition 3 — e.g., UI layout, responsive design, accessibility] | `[agent-name]` |
| [Trigger condition 4 — e.g., performance issues, profiling, optimization] | `[agent-name]` |
| [Trigger condition 5 — e.g., security, auth, permissions] | `[agent-name]` |
| [Trigger condition 6 — e.g., complex domain math, coordinate systems] | `[agent-name]` |

### Post-Change Triggers (invoke AFTER completing work)

| After modifying... | Invoke |
|--------------------|--------|
| [e.g., Any file in `src/api/`] | `[code-reviewer-agent]` |
| [e.g., Database models or migrations] | `[code-reviewer-agent]` |
| [e.g., Auth or permission logic] | `[security-reviewer-agent]` |

### Skip Agents Only For

- Trivial one-line fixes (typos, single variable renames)
- Build/run commands already documented above

### Quick Reference

| Agent | Model | Primary Focus |
|-------|-------|---------------|
| `[agent-name]` | [opus/sonnet] | [One-line description] |
| `[agent-name]` | [opus/sonnet] | [One-line description] |
| `[agent-name]` | [opus/sonnet] | [One-line description] |

---

<!-- ═══════════════════════════════════════════════════════════════════════
     LAYER 2: CONTEXT RETRIEVAL (MCP server + subsystem mapping)

     This section defines HOW agents find architecture context. The MCP
     server provides structured lookups (faster and cheaper than grepping
     the entire codebase), while the subsystem reference maps logical
     domains to concrete file paths.
     ═══════════════════════════════════════════════════════════════════════ -->

## Context Retrieval Tools (MCP)

<!-- ANNOTATION: If you use an MCP server for architecture context, document the
     available tools HERE near the top. This tells the agent to use structured lookups
     FIRST instead of grep-scanning the codebase. The tool table is a lookup reference
     the agent consults on every task.

     If you don't use MCP tools, delete this section entirely and move the Subsystem
     Reference under Architecture Overview instead. -->

Use context retrieval tools FIRST when exploring unfamiliar code — faster than manual searching.

| Tool | Use For |
|------|---------|
| `list_subsystems()` | See all architectural subsystems |
| `get_files_for_subsystem("[name]")` | Get key files for a subsystem |
| `find_relevant_context("[task description]")` | Find files relevant to a task |
| `search_context_documents("[keyword]")` | Search architecture docs by keyword |
| `suggest_agent("[task description]")` | Get recommended agent for a task |
| `list_agents()` | See all available agents with triggers |

### Subsystem Reference

<!-- ANNOTATION: A lookup table mapping logical subsystems to their key files. This is
     the agent's "table of contents" for your codebase. Each row should map to a
     context doc in .claude/context/ that provides deep-dive documentation.
     The MCP server reads this mapping to power its retrieval tools. -->

| Key | Description | Key Files |
|-----|-------------|-----------|
| `[subsystem-1]` | [What it does] | [file1], [file2], [context-doc.md] |
| `[subsystem-2]` | [What it does] | [file1], [file2], [context-doc.md] |
| `[subsystem-3]` | [What it does] | [file1], [file2], [context-doc.md] |

## Context Documentation

<!-- ANNOTATION: List the detailed architecture docs that live in .claude/context/.
     These are the "cold memory" knowledge base that agents retrieve on-demand via
     the MCP server. Each doc covers one subsystem in depth. -->

[N] detailed docs in `.claude/context/`. Key docs:

- `[doc-name].md` — [What it covers]
- `[doc-name].md` — [What it covers]
- `[doc-name].md` — [What it covers]

---

<!-- ═══════════════════════════════════════════════════════════════════════
     INTEGRITY MAINTENANCE: Drift detection + post-feature checklist

     These sections define the feedback loop that keeps the architecture
     documentation accurate as code evolves. Without drift detection,
     context docs go stale within weeks.
     ═══════════════════════════════════════════════════════════════════════ -->

## Post-Feature Checklist

<!-- ANNOTATION: This section prevents documentation drift. After structural changes,
     the agent checks each item and updates what's needed. Customize the list to match
     YOUR project's documentation surfaces. Also note what DOESN'T need updates to
     prevent busywork on trivial changes. -->

After structural changes (new modules, new API endpoints, changed architectural patterns, new services), consider updating:

- [ ] **Code Review** — Invoke `[reviewer-agent]` if you modified [critical directories]
- [ ] **Context Docs** — Update `.claude/context/*.md` if you changed how a subsystem works
- [ ] **This file (CLAUDE.md)** — Update if you added/removed systems, services, commands, or conventions
- [ ] **MCP server.py** — Update SUBSYSTEMS dict if you added/renamed/deleted source files
- [ ] **Agent specs** — Update agent AGENT.md only if the agent's workflow or patterns changed
- [ ] **Validation** — Run `.claude/scripts/validate-architecture.sh` — 0 errors

**Skip docs for:** bug fixes in existing code, value tweaks, asset changes, cosmetic adjustments, adding items using existing patterns.

<!-- ANNOTATION: If you use automated drift detection (hooks that check for stale docs),
     document the priority levels and expected agent responses here. This turns reactive
     doc maintenance into a proactive system. -->

**Automated drift detection:** A SessionStart hook runs `context-drift-check.py` and injects prioritized warnings:
- **HIGH**: Automatically update the flagged context docs before starting other work.
- **MEDIUM**: Mention the drift to the user and ask if they want to address it.
- **LOW**: Suppressed (not shown). No action needed.

---

<!-- ═══════════════════════════════════════════════════════════════════════
     LAYER 1: HOT-MEMORY CONSTITUTION (conventional project docs)

     Everything below this line is standard project documentation that
     would appear in any well-maintained CLAUDE.md. It's important but
     not architecturally novel — the sections above are what distinguish
     the codified context approach.
     ═══════════════════════════════════════════════════════════════════════ -->

## Architecture Overview

<!-- ANNOTATION: Describe the 2-4 major architectural patterns your project uses.
     The agent uses this to decide WHERE to put new code and HOW to structure it.
     Include a code snippet showing the canonical pattern if your architecture has
     a specific registration/wiring convention. -->

### [Primary Pattern Name] (e.g., MVC, ECS, Hexagonal, Event-Driven)

- **[Layer/Component A]** (`path/`): [What it contains and its responsibility]
- **[Layer/Component B]** (`path/`): [What it contains and its responsibility]
- **[Layer/Component C]** (`path/`): [What it contains and its responsibility]

### [Service / Dependency Injection Pattern]

<!-- ANNOTATION: Describe how components find each other. Whether it's a DI container,
     service locator, module imports, or manual wiring — the agent needs to know HOW
     to wire up new code it creates. -->

- [How services are registered — e.g., "Auto-discovered via decorators" or "Manual registration in AppModule"]
- [How services are accessed — e.g., "Constructor injection" or "context.GetService<T>()"]
- Key services: [List the 5-8 most important interfaces/classes]

### [State Management / Lifecycle Pattern]

<!-- ANNOTATION: If your app has distinct states, modes, or lifecycle phases, describe
     them here. This prevents the agent from writing code that runs at the wrong time. -->

- [e.g., State machine with transitions: Init -> Running -> Paused -> Shutdown]
- Lifecycle: `[method1]()` -> `[method2]()` -> `[method3]()`

## New [Component/Module] Checklist

<!-- ANNOTATION: This section prevents the #1 agent bug: creating a file that never gets
     wired up. Every framework has a registration step that's easy to forget — document
     it here with symptoms of the failure. Include REAL examples of past bugs. -->

**CRITICAL**: When creating a new [component/module/handler], it MUST be [registered/imported/declared] in `[registration file]` or it will never [run/be discovered/be available].

**Checklist:**
1. Create the [component] in `[directory/]`
2. [Framework-specific step, e.g., "Add route to router", "Register in DI container"]
3. **[The step most commonly forgotten]** <-- Most commonly forgotten step!
4. [Any wiring/event subscription steps]

**Common symptoms of missing registration:**
- [e.g., "Endpoint returns 404 but handler file exists"]
- [e.g., "System exists but feature doesn't work — no errors (silent failure)"]

## Code Quality Standards

<!-- ANNOTATION: These are imperative constraints the agent must follow on every edit.
     Keep them actionable and specific to YOUR project. 5-8 bullet points. -->

- [Constraint 1 — e.g., All functions must have JSDoc comments with @param and @returns]
- [Constraint 2 — e.g., No raw SQL queries; use the ORM query builder exclusively]
- [Constraint 3 — e.g., Prefer defensive coding with proper null checks and error handling]
- [Constraint 4 — e.g., All API endpoints must validate input with Zod schemas]
- [Constraint 5 — e.g., Follow existing architectural patterns established in the codebase]

## Project Structure

<!-- ANNOTATION: An ASCII tree gives the agent spatial awareness. Only include 2-3 levels
     deep — enough for navigation, not a full directory listing. -->

```
[project-root]/
├── src/
│   ├── [module-a]/        # [Purpose]
│   ├── [module-b]/        # [Purpose]
│   └── [module-c]/        # [Purpose]
├── tests/                  # [Test organization]
├── config/                 # [Configuration files]
└── .claude/
    ├── context/            # Architecture documentation (Layer 2)
    ├── agents/             # Specialized agent specs (Layer 3)
    └── scripts/            # Validation and drift detection
```

## Build & Run

<!-- ANNOTATION: Copy-paste-ready commands the agent can execute verbatim. -->

```bash
# Install dependencies
[e.g., npm install / pip install -r requirements.txt / dotnet restore]

# Build
[e.g., npm run build / python -m build / dotnet build]

# Run (development)
[e.g., npm run dev / uvicorn main:app --reload / dotnet run]

# Run tests
[e.g., npm test / pytest / dotnet test]
```

## Key Conventions

### File Organization

- [e.g., One class/component per file, filename matches export name]
- [e.g., Group by feature: `features/auth/`, `features/billing/`]

### Naming Conventions

- [e.g., Interfaces: `IServiceName` / Components: `XxxComponent` / Hooks: `useXxx`]
- [e.g., Database tables: snake_case plural / API routes: kebab-case]

### Data & Configuration

- [e.g., JSON definitions in `config/` loaded via ConfigService]
- [e.g., Environment variables via `.env` files]

### [Project-Specific Pattern]

<!-- ANNOTATION: If your project has a recurring code pattern used in 5+ places, document
     it with a code snippet. Delete this section if you don't have one yet. -->

```[language]
// Example of [pattern name] — used in [where]
[canonical code snippet, 5-10 lines]
```

## Key Files Reference

<!-- ANNOTATION: The agent's "cheat sheet" for navigation. Map logical areas to specific
     file paths. Keep it accurate — when files move, update this table FIRST. -->

| Area | Files |
|------|-------|
| Entry point | `[e.g., src/main.ts, src/index.py, Program.cs]` |
| App configuration | `[e.g., src/app.module.ts, settings.py]` |
| Routing / Controllers | `[e.g., src/routes/, src/controllers/]` |
| Business logic | `[e.g., src/services/, src/domain/]` |
| Data access | `[e.g., src/repositories/, src/models/]` |
| Authentication | `[e.g., src/auth/, middleware/auth.ts]` |
| Tests | `[e.g., tests/, __tests__/, *.test.ts]` |

## Known TODOs

<!-- ANNOTATION: Parking lot for acknowledged gaps. Prevents the agent from "fixing"
     things that are intentionally incomplete. -->

- [Known incomplete feature or missing functionality]
- [Another known gap]
