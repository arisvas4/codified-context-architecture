# Case Study 4: Save System Documentation -- Coordination Document

This excerpt demonstrates how a sub-agent, tasked with exploring game state transitions, discovers and uses pre-existing context documentation (`.claude/context/`) as a navigational map for the codebase. The agent uses MCP tools to survey subsystems, then falls back to filesystem globbing to discover coordination documents like `save-system.md`, which it cites as the authoritative reference for save persistence architecture -- even without reading it in full.

**Architectural tiers demonstrated**: Tier 3 (knowledge base as coordination point)

**Session context**: January 21, 2026. Building systematic play-mode guidelines for 7 network configurations. 3 parallel Explore agents launched; this excerpt follows the agent investigating game state transitions and player management.

## Key Interaction 1: Human Task and Agent Dispatch

> **Human** (turn 1):
> update claude code guidelines to make all changes, flows, and implementations with the following play modes in mind: offline single-player, offline multiplayer, online single-player as host, online as host with local multiplayer, online single-player as client, online multi-player as client, and online multiplayer with multiple clients. Give a little context for each of these as to whether or not they're redundant in our code system and whether there are best practices.

> **Assistant** (turn 1):
> I'll explore the codebase to understand the current networking architecture and how different play modes are handled, then design guidelines for addressing all these scenarios systematically.
>
> [Launches 3 parallel Task agents: networking architecture, game state transitions, ECS system patterns]

> **Agent prompt** (dispatched to Explore sub-agent):
> Explore how game state transitions and player management work across different scenarios:
> 1. Find how game states handle: Starting a game, Player creation and joining, Level transitions
> 2. Look for: How local players are tracked, How networked players are handled differently
> 3. Search for any existing documentation or patterns about: Player count handling, Local multiplayer setup [...]

## Key Interaction 2: Agent Uses MCP, Then Discovers Context Docs via Globbing

> **Sub-agent** (exploration phase):
> I'll explore how game state transitions and player management work across different scenarios. Let me start by getting context about the subsystems and then dive into the specific files.
>
> [Calls `mcp__context7__list_subsystems({})`, `mcp__context7__get_files_for_subsystem("game-states")`, `mcp__context7__find_relevant_context("game state transitions...")`]
>
> [... reads GameStateManager.cs, PlayMenuState.cs, HubState.cs, AdventureState.cs, VictoryState.cs, PlayerComponent.cs, NetworkService.cs, EntityFactory.cs, LevelStateBase.cs ...]
>
> Perfect! Now let me search for more information about how the lobby and network coordination works:
>
> [Calls `Glob("*.md", path=".claude/context/")`]

> **Tool result**:
> ```
> .claude/context/save-system.md
> .claude/context/network-debugging.md
> .claude/context/game-flow-act1-vertical-slice.md
> .claude/context/dungeon-generation.md
> .claude/context/architecture.md
> .claude/context/content-pipeline.md
> .claude/context/host-authoritative-damage-spec.md
> ```

## Key Interaction 3: Agent Cites Context Doc as Authoritative Source

> **Sub-agent** (final report, excerpt from Section 8):
>
> ### 8. SAVE PERSISTENCE & STATE RECOVERY
>
> - **MenuState** clears stale heroes on entry (crash recovery)
> - **GameStateService** stores run state: `SelectedHeroes`, `ActiveProfileIds`, level timer, portal room parameters
> - **ProgressionService** (new): Handles in-memory run state separate from disk saves
> - **File**: `.claude/context/save-system.md`

## Annotation

This excerpt demonstrates the coordination document pattern at its most organic. The sub-agent was tasked with understanding game state transitions -- not the save system specifically. Yet during its exploration, it discovered `.claude/context/save-system.md` through filesystem globbing and immediately recognized it as the canonical reference for save persistence architecture. Without needing to read the full document, the agent cited it as the authoritative pointer in its summary report, making it available to the orchestrating session.

This is the coordination document acting as a stable waypoint: it doesn't need to be read cover-to-cover every time. Its mere existence in a discoverable location (with a descriptive filename) is enough for agents to route future save-related work through it. The README notes that 74 sessions referenced `save-system.md` over the project's lifetime -- this excerpt shows one instance of the discovery mechanism that enabled that reuse.
