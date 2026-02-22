# Case Study 5: Coordinate Wizard -- Instant Diagnosis

This excerpt demonstrates a read-only specialized agent (`coordinate-wizard`) instantly diagnosing an isometric rendering bug that would have required significant investigation by a general-purpose agent. The domain-specific knowledge encoded in the agent's prompt -- about IsometricCorrection, WorldToIsoWorld, and the difference between Pattern A (camera matrix) and Pattern B (VirtualToPhysical) rendering -- enables it to read 5 files and produce a precise, line-numbered diagnosis in a single response.

**Architectural tiers demonstrated**: Tier 2 (specialized agent with domain expertise)

**Session context**: January 25, 2026. Improving a boss fight. After tuning attack frequencies and ranges, the human noticed beam telegraphs rendering off-screen while still dealing damage at the correct position. 4 edits fixed the issue.

## Key Interaction 1: Human Reports Visual Bug

> **Human** (turn 7):
> the beam attack is showing off arena but still hitting me. I expect that there's some coordinate issues in play. Check with the 2D artist about making the correct isometric maneuvers for this attack. I expect that the meteor blast might have the same issue

> **Assistant** (turn 7):
> I see the issue -- the beam telegraph is rendering in the wrong position, likely due to isometric coordinate conversion problems. Let me consult the coordinate wizard agent to diagnose this.
>
> [Invokes `Task(agent=coordinate-wizard)`]

## Key Interaction 2: Coordinate Wizard Reads Files and Diagnoses

> **Coordinate Wizard** (full diagnostic session -- 5 file reads, 1 grep, ~30 seconds):
>
> I'll investigate this coordinate issue with boss attack telegraphs. Let me examine the relevant files.
>
> [Reads: BossAttackSystem.cs, EnemyTelegraphComponent.cs, TelegraphRenderSystem.cs, IsometricGridHelper.cs, SpriteRenderSystem.cs]
>
> [Greps for `IsometricCorrection` across the engine directory]

> **Coordinate Wizard** (diagnosis):
>
> ## Diagnostic Analysis: Boss Telegraph Coordinate Issue
>
> ### Root Cause Identified
>
> The bug is in `TelegraphRenderSystem.cs`. The system converts positions to isometric space using `WorldToIsoWorld()`, but **fails to add the IsometricCorrection** that all other render systems use.
>
> ### How Other Render Systems Do It Correctly
>
> In `SpriteRenderSystem.cs` (line 165):
> ```csharp
> var worldCorrection = context.IsometricCorrection;
> var drawPosition = IsometricGridHelper.WorldToIsoWorld(
>     transform.Position, tileWidth) + worldCorrection;
> ```
>
> ### How TelegraphRenderSystem Does It Wrong
>
> In `TelegraphRenderSystem.cs` (lines 97, 113, 143):
> ```csharp
> var isoCenter = IsometricGridHelper.WorldToIsoWorld(center, tileWidth);  // NO CORRECTION!
> var isoStart = IsometricGridHelper.WorldToIsoWorld(start, tileWidth);    // NO CORRECTION!
> var isoOrigin = IsometricGridHelper.WorldToIsoWorld(origin, tileWidth);  // NO CORRECTION!
> ```
>
> ### Trace of the Bug
>
> 1. Boss at world position (1000, 1000)
> 2. `WorldToIsoWorld(1000, 1000)` produces isometric position (~0, ~125)
> 3. Sprite renderer adds `IsometricCorrection` (say +800, +200) making draw position (~800, ~325)
> 4. Telegraph renderer does NOT add correction, draws at (~0, ~125)
> 5. Result: Telegraph appears offset by ~800px horizontally, ~200px vertically
>
> ### Recommended Fix
>
> **File:** `ECS/Systems/TelegraphRenderSystem.cs`
>
> Add `context.IsometricCorrection` to all position conversions. [... provides exact before/after code for lines 97, 113, 143 ...]
>
> I am a diagnostic-only agent. Here is my analysis and recommended fix. Coordinate math is complex -- please have `code-reviewer-game-dev` review any implementation.

## Key Interaction 3: Main Agent Applies the Fix

> **Assistant** (turn 7, continued):
> The coordinate wizard identified the issue. The `TelegraphRenderSystem` is missing the `IsometricCorrection` that all other render systems use. Let me fix this:
>
> [4 Edit operations on TelegraphRenderSystem.cs, then builds successfully]
>
> Fixed the telegraph coordinate issue. The changes:
> 1. Added `worldCorrection` variable from `context.IsometricCorrection`
> 2. Applied correction to all three drawing methods (circle, line, cone)
> 3. Fixed direction vector transformation to use proper isometric math

## Annotation

This is the clearest example of the specialized agent pattern paying off. The coordinate-wizard agent carries deep domain knowledge about the project's five coordinate spaces (World, Isometric, Grid, Virtual Screen, Physical Screen) and the common failure modes when converting between them. The missing `IsometricCorrection` is a pattern that recurs whenever a new render system is added -- any system that converts world positions to screen positions must add this offset, and forgetting it produces exactly the symptom described (visually offset but functionally correct).

The agent read 5 files, identified the root cause by comparing TelegraphRenderSystem against the known-correct SpriteRenderSystem, and provided line-numbered before/after code. The main agent applied the fix verbatim with 4 edits. Total time from bug report to compiled fix: under 2 minutes. Without the specialized agent, this diagnosis would have required understanding the isometric rendering pipeline from scratch -- a task that typically consumes an entire context window for a general-purpose agent.

The diagnostic-only constraint (the agent explicitly cannot edit files) is also visible: it ends with "I am a diagnostic-only agent" and recommends a code review. This separation of concerns -- diagnosis vs. implementation -- prevents the specialized agent from making changes outside its expertise while ensuring its analysis is thorough.
