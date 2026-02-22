# Case Study 1: CombatRng Determinism -- Agent as Domain Expert

This excerpt demonstrates the `network-protocol-designer` agent functioning as a domain expert reviewer. The agent was spawned to review a time-synchronization refactor (replacing `context.TotalTime` with `context.GetSyncedTime()` across 17 systems). Its first actions were to read the implementation files, then systematically grep for remaining usages, then read the deterministic RNG implementation (CombatRng.cs). It identified a critical determinism bug that the main orchestrating session had missed: two competing time sources would cause CombatRng hash mismatches across clients.

**Architectural tiers demonstrated**: Tier 3 (knowledge base) + Tier 2 (specialized agent)

**Session context**: January 21-24, 2026. Multi-continuation session implementing clock synchronization for deterministic combat. 5 context exhaustions, 14 agent invocations, 84 edits across 12 files.

## Key Interaction 1: Human Frames the Problem

> **Human** (main session):
> Solve this issue. I think we might need to make a bucket from the timestamp for this to work since the time between the host sending it to the client then the client sending it to the host, the host will already be advanced in time from there. Think hard about this.
>
> Current CombatRng Sync System Summary
> Goal: Ensure deterministic crit/proc rolls across host and client so both see the same result for the same shot.
>
> ```csharp
> // CombatRng.Roll() computes a deterministic result from:
> hash = ComputeHash(gameSeed, playerId, shotNumber, timeBucket, effectType, subIndex)
> result = (hash & 0xFFFF) < (chance * 65536)
> // All inputs must match on host and client for the same result.
> ```
>
> The Bug: Debug output shows CLIENT's hostTime equals localTime (both ~129000ms), meaning the fallback is triggering instead of returning the snapshot timestamp (~122000ms from host). [...]

## Key Interaction 2: Agent Invoked for Plan Review

> **Assistant** (main session, after drafting a fix plan):
> [Spawns `network-protocol-designer` agent with prompt:]
>
> "Review this plan for fixing CombatRng TimeBucket desync. The user is optimistic about the plan and only wants feedback on CRITICAL issues.
>
> **Plan Summary:** The plan fixes two desync points in CombatRng determinism:
> **Part A: Visual Prediction Fixes** -- NetworkInputSystem.cs: Change from `context.TotalTime` (local) to `GetHostTimestampMs()` when computing TimeBucket [...]
> **Part B: Damage Validation Fixes** -- Add `TimeBucket` field to DamageEvent, update DamageAuthoritySystem to use client's bucket for Roll() [...]
>
> **Only flag critical issues** -- things that would break the system, introduce security vulnerabilities, or cause new desyncs."

## Key Interaction 3: Agent Review (from agent sub-session)

> **Agent** (`network-protocol-designer`, first actions):
> I'll conduct a thorough network protocol review of the time synchronization refactor. Let me start by examining the key files.
>
> [Reads `INetworkTimeService.cs`, `NetworkSyncSystem.cs`, `GameContext.cs`]
> [Greps for remaining `context.TotalTime` usages across all systems]
> [Reads `CombatRng.cs` to understand how time feeds into deterministic hashing]

> **Agent** (final review output):
> # Network Protocol Review: Time Synchronization Refactor
>
> **Overall Assessment: MOSTLY CORRECT with 3 CRITICAL ISSUES**
>
> [...]
>
> ### BREAKS DETERMINISM: CombatRng TimeBucket Conflict
>
> **Root Cause:** Two different time sources for the same calculation.
>
> **Critical Code Path:**
> 1. **Client fires projectile** -> `NetworkInputSystem` captures `TimeBucket` from `GetHostTimestampMs()`
> 2. **Client computes crit** -> `ProjectileSystem` uses `GetSyncedTime()` -> different `TimeBucket`!
> 3. **Host validates** -> Uses `TimeBucket` from InputCommand (which came from `GetHostTimestampMs()`)
>
> **Desync Window:**
> - Every 500ms when `TimeBucket` increments
> - ~2% of shots will cross bucket boundaries
> - **Actual: Up to 10% desync** due to 30Hz vs 60Hz mismatch
>
> **Fix:** Use ONE source of truth. Remove `GetHostTimestampMs()`, use `GetSyncedTime()` everywhere.

## Annotation

This interaction demonstrates the agent functioning as a domain expert with deep knowledge of the project's deterministic networking architecture. The agent's review methodology is notable: it did not simply read the files mentioned in the prompt. It independently grepped for `context.TotalTime` across the entire `ECS/Systems/` directory to find usages the human might have missed, then read `CombatRng.cs` to understand how time values feed into the deterministic hash function. This allowed it to identify a subtle bug at the intersection of two subsystems (clock sync and combat RNG) that neither the human nor the main orchestrating session had caught.

The agent's knowledge came from two sources: (1) the Tier 3 context documents (`network-determinism-architecture.md`, `network-multiplayer-system.md`) loaded via its system prompt as a `network-protocol-designer` agent, and (2) its own codebase exploration during the review. The critical finding -- that `GetHostTimestampMs()` updates at 30Hz while `GetSyncedTime()` updates at 60Hz, causing bucket boundary mismatches -- required understanding both the network synchronization model and the CombatRng hashing algorithm simultaneously. This is precisely the kind of cross-subsystem reasoning that the knowledge architecture was designed to support.
