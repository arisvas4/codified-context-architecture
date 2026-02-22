# Case Study 6: Drop System -- Gap Detection and Creation

This excerpt demonstrates the architecture's organic growth pattern. When tasked with refactoring the drop system, the agent's first action is to search for existing context documentation. The MCP tool returns zero matches -- a documentation gap. The agent then reads implementation files to build understanding from source, creates a new context document (`drop-system.md`), and uses it as the basis for multi-agent design consultation. Later in the session, a second context document (`item-system.md`) is created when the human recognizes another gap. This shows how coordination documents emerge from implementation work rather than being planned top-down.

**Architectural tiers demonstrated**: Tier 3 (knowledge base gap detection and creation)

**Session context**: January 25, 2026. Refactoring a drop/loot system after an orb/mod fusion redesign. 9 agent invocations (ecs-component-designer, systems-designer, code-reviewer, network-protocol-designer). 2 context documents created.

## Key Interaction 1: Gap Detection via MCP Search

> **Human** (turn 1):
> we just refactored the core system to use orbs and mods to make cores, but we didn't refactor the drop system to correctly drop the new components. Do we have a summary of the drop system? If not, let's start with making a detailed context file describing everything about the drop system and its determinism

> **Assistant** (turn 1):
> I'll search for information about the drop system and check if there's existing documentation.
>
> [Calls `mcp__context7__search_context_documents({"query": "drop system core drops loot"})`]
> [Calls `mcp__context7__get_files_for_subsystem({"subsystem": "combat"})`]
> [Calls `Grep({"pattern": "CoreDrop|DropComponent|LootDrop"})`]

> **MCP tool result** (search_context_documents):
> ```json
> {
>   "query": "drop system core drops loot",
>   "document_matches": [],
>   "subsystem_matches": []
> }
> ```

> **Assistant** (turn 1, continued):
> No existing documentation on the drop system. Let me read the key files to understand the current implementation.
>
> [Reads: CoreDropComponent.cs, CorePickupSystem.cs, core-fusion-system.md, CombatSystem.cs, CoreMessages.cs, EntityFactory.cs, CoreDefinitions.cs, Core.cs, Orb.cs, Mod.cs, CoreComponent.cs, CoreInventory.cs, BossComponent.cs]
>
> Now I have all the information I need. Let me create the comprehensive context file.
>
> [Writes `.claude/context/drop-system.md`]

## Key Interaction 2: New Doc Enables Multi-Agent Design Consultation

> **Assistant** (turn 1, summary):
> I've created a comprehensive context file at `.claude/context/drop-system.md` documenting the entire drop system. Here's a summary of what I found:
>
> The drop system **only drops Cores** right now, not Orbs or Mods. This is legacy code that predates your fusion refactor. [...]
>
> Would you like me to start implementing the Orb/Mod drop support, or do you want to review the documentation first?

> **Human** (turn 2):
> what do you think about reusing core drop to drop orbs and mods? they're pretty similar item types, just have different ability lists. [...] Have the ECS agent weigh in on what implementation we should do

> **Assistant** (turn 2):
> Good question -- there's a design tradeoff here. Let me get the ECS specialist's perspective.
>
> [Invokes `Task(agent=ecs-component-designer, desc="Evaluate drop component design options")`]

> **Human** (turn 3):
> have the system design agent review and weigh in as well

> [Invokes `Task(agent=systems-designer, desc="Review drop system design proposal")`]

## Key Interaction 3: Second Gap Detected, Second Doc Created

> **Human** (turn 12):
> create an item context file with all this drop rate information, orb information, mod information, and stat information, etc. Anything relevant to balancing the item system. Also include key files to know about for modifying the system

> **Assistant** (turn 12):
> [Reads: Core.cs, FusionTypes.cs, IFusionService.cs, FusionService.cs, CoreInventory.cs]
>
> Now I have all the information I need to create a comprehensive item system context document:
>
> [Writes `.claude/context/item-system.md`]
>
> Created the comprehensive item system context file. The document includes: all 8 Orb types with stats, all 10 Mod types with effects, Core mechanics (4 dimensions of power), rarity multipliers, item level scaling, drop rates, and key files for modification.

## Annotation

This excerpt demonstrates the organic growth mechanism of the coordination document architecture. The session begins with an explicit gap detection: the human asks "do we have a summary?", and the MCP search returns `"document_matches": []`. This empty result is the trigger for documentation creation -- not a planned authoring process, but an emergent response to discovering that no coordination document exists for this subsystem.

The created document (`drop-system.md`) immediately serves two functions: it captures the agent's reverse-engineered understanding of the current implementation, and it becomes the shared reference for the subsequent multi-agent design consultation. When the ECS component designer and systems designer agents are invoked in turns 2-3, they can read this document rather than independently exploring the same source files. The document acts as a cache of institutional knowledge.

The second document creation (`item-system.md` in turn 12) demonstrates the same pattern at a different scale. The human recognizes that item balancing information is scattered across source files and asks for consolidation. This shows the human-agent collaboration in documentation: the human identifies what should be documented (based on their game design needs), and the agent does the extraction work (reading source code, computing stat distributions, identifying key files). Both documents persisted through the rest of the project and were referenced in subsequent sessions.
