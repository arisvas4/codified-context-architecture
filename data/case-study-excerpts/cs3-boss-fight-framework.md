# Case Study 3: Boss Fight Framework -- Architectural Inheritance via Context Documents

This excerpt demonstrates the `systems-designer` agent reading an existing Tier 3 context document (`enemy-combat-system.md`) as its very first action before designing a new subsystem. The agent's design inherits established patterns (the Config/State component split, the Idle->Windup->Execute->Recovery state machine, the zero-bandwidth network model) rather than inventing new ones, because the context document made these patterns visible and explicit.

**Architectural tiers demonstrated**: Tier 3 (knowledge base as design input) + Tier 2 (specialized agent)

**Session context**: January 24-25, 2026. Multi-continuation session (9.3MB) implementing a multi-phase boss fight system. The `systems-designer` agent was spawned in the background alongside an `ecs-component-designer` agent to review the framework plan before implementation began.

## Key Interaction 1: Human Requests Agent Review Before Implementation

> **Human**:
> have the system design and ecs agents review the plan in background for feedback before we start implementation

> **Assistant**:
> I'll launch both the systems-designer and ecs-component-designer agents in parallel to review the plan and provide feedback before we start implementation.
>
> [Spawns `systems-designer` agent:]
> "Review the boss fight framework plan at `boss-fight-framework.md`
>
> Focus on:
> 1. **System architecture**: Are the 3 new systems (BossPhaseSystem, BossAttackSystem, BossMinionSystem) properly separated?
> 2. **Attack selection pattern**: Is the weighted random + cooldown + sequence approach sound for multiplayer ARPGs?
> 3. **Network architecture**: Zero-bandwidth phase transitions via HP-derived state -- is this robust?
> 4. **Player count scaling**: HP/attack speed/minion scaling formulas
> 5. **Performance concerns**: 4 players + 10 minions + boss with complex attacks
> 6. **Scalability**: Can this handle 5 act bosses with different mechanics?"

## Key Interaction 2: Agent's First Actions (from agent sub-session)

> **Agent** (`systems-designer`, first 3 tool calls executed in parallel):
>
> 1. `Read enemy-combat-system.md` -- the Tier 3 context doc for the existing enemy system
> 2. `Read enemies.json` -- the data definitions for current enemies
> 3. `mcp__context7__get_files_for_subsystem("combat")` -- queries the retrieval service for all combat-related source files
>
> [Then reads 12 more source files: EnemyAttackConfigComponent.cs, EnemyAttackStateComponent.cs, EnemyComponent.cs, EnemyAttackSystem.cs, SpawnSystem.cs, EnemyDefinition.cs, BossState.cs, EntityFactory.cs, BossComponent.cs, BossAbilitySystem.cs, BossDefinition.cs, bosses.json, DamageMessages.cs]

> **Agent** (after exploration):
> I now have a comprehensive understanding of the existing architecture. Let me create the detailed boss fight framework design document.

## Key Interaction 3: Design Inherits Existing Patterns

> **Agent** (design document, opening):
> # Boss Fight Framework Design
>
> ## Overview
> This document outlines a comprehensive boss fight framework for the project, **building on the existing enemy attack system**. The design supports multi-phase bosses with diverse movesets, minion spawning, enrage mechanics, and arena hazards while maintaining network safety through the zero-bandwidth model.
>
> ## Component Architecture
>
> ### 1. Extended BossComponent (not a new component)
> The existing `BossComponent` is extended to hold all phase-related data [...]
>
> ### Network Synchronization
>
> **Zero-Bandwidth (Client Predicted):**
> - Phase transitions (derived from synced HP)
> - Attack selection (deterministic from synced time + seed)
> - Telegraphs (local visuals)
>
> **Host-Authoritative Messages:**
> - Minion spawning (extended `EnemySpawnMessage` with `isBossMinion` flag)
> - Damage validation (existing flow)

## Key Interaction 4: Human Verifies Pattern Reuse

> **Human** (after Phase 1 implementation):
> have the code review agent evaluate the phase 1 implementation. Also, are we amply re-using what we should from enemy combat system?

## Annotation

This interaction demonstrates "architectural inheritance" -- the mechanism by which new subsystems absorb established patterns from existing documentation rather than reinventing them. The systems-designer agent's very first action was to read `enemy-combat-system.md`, the Tier 3 context document describing the existing attack system's patterns. This is not accidental: the agent's prompt referenced the document, and the agent treated it as authoritative.

The resulting design explicitly builds on existing patterns: it extends `BossComponent` rather than creating a new component, reuses the Config/State split pattern from enemy attacks, maintains the zero-bandwidth network model documented in the context doc, and extends `EnemySpawnMessage` for minion spawning rather than creating a new message type. The human's later question -- "are we amply re-using what we should from enemy combat system?" -- confirms that pattern reuse was an explicit design goal, not just a side effect. The context document made the existing patterns visible and queryable, enabling the agent to inherit them by design rather than discover them by accident.
