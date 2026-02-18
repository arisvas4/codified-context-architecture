<!-- v1 | last-verified: 2026-02-15 -->
# Ghost Mode & Player Death Flow

## Overview

When a player dies in the case study project, they enter "ghost mode" - an invulnerable, semi-transparent state where they can float through walls and watch teammates while still having limited interaction (dash/stomp for fun movement).

## Ghost Mode Behavior

| Aspect | Behavior |
|--------|----------|
| **Movement** | Can move freely through walls, clamped to world bounds |
| **Visual** | 50% transparent with cyan tint (no shader, SpriteBatch color multiplication) |
| **Combat** | Cannot fire projectiles or deal damage |
| **Abilities** | Stomp only (visual + dash impulse, no damage/knockback) |
| **Power-ups** | Cannot collect items |
| **Health Bar** | Hidden |
| **Camera** | Still follows ghost (they're still a player entity) |
| **GameOver** | Ghosts count as dead - when all players are ghosts, GameOver triggers |

## Architecture

### IsGhost Flag (NOT a separate entity)

Ghost mode uses an `IsGhost` flag on `PlayerComponent` rather than creating a separate ghost entity/archetype.

**Why:**
1. `PlayerSnapshot` uses `PlayerId` (0-3), not `UniqueId` - entity lifecycle irrelevant for network sync
2. VictoryOverlay, GameOverState, Permadeath all query `SelectedHeroes[]` by index, not entities
3. No archetype change = no entity ID change = no network desync
4. Simpler: just toggle a flag vs destroy/create entity

### Key Files

| File | Ghost Mode Logic |
|------|------------------|
| `PlayerComponent.cs` | `IsGhost` flag definition |
| `SyncMessages.cs` | `PlayerSnapshot.IsGhost` for network sync |
| `NetworkSyncSystem.cs` | Sync `IsGhost` (4 places: CreatePlayerSnapshot, ApplyPlayerUpdates x3) |
| `HealthSystem.cs` | Sets `IsGhost = true` on death |
| `SpriteRenderSystem.cs` | Ghost transparency + hide health bar |
| `MovementSystem.cs` | `if (player.IsDead && !player.IsGhost) return;` |
| `PhysicsSystem.cs` | Skip wall collision for ghosts |
| `ProjectileSystem.cs` | Block projectile creation for ghosts |
| `AbilitySystem.cs` | Allow stomp, block other abilities |
| `PowerUpSystem.cs` | Exclude ghosts from collection |
| `LevelStateBase.cs` | Reset death tracking between levels |

## Death Flow

```
Player health reaches 0
         ↓
HealthSystem.Update() detects !isAlive
         ↓
if (!_deathProcessed.Contains(playerId))
         ↓
    ├── _deathProcessed.Add(playerId)
    ├── ProcessPlayerDeath() - marks hero for permadeath
    ├── player.IsGhost = true
    └── CreateTextParticle("GHOST MODE", Cyan)
         ↓
All players dead? → GameOver triggers
         ↓
GameOverState shows core banking UI
         ↓
RETRY or RETURN TO HUB
         ↓
Level transition clears entities
         ↓
LevelStateBase.InitializeCommon() resets HealthSystem._deathProcessed
         ↓
New level spawns fresh players (IsGhost = false)
```

## Critical: Death Tracking Reset

### The Problem

HealthSystem uses a `_deathProcessed` HashSet to prevent double-processing deaths. This set persists across level transitions because:
1. Systems are singletons (survive `World.Clear()`)
2. Player IDs (0-3) are reused across levels
3. Only entities are cleared, not system state

Without reset, ghost mode fails on subsequent deaths because the player ID is already in `_deathProcessed`.

### The Fix

`LevelStateBase.InitializeCommon()` calls `HealthSystem.ResetHealTracking()` on every level entry:

```csharp
// CRITICAL: Reset HealthSystem death tracking between levels.
// Systems persist across level transitions but player IDs (0-3) are reused.
// Without reset, ghost mode fails on RETRY or subsequent levels.
if (context.TryGetService<ISystemScheduler>(out var scheduler))
{
    var healthSystem = scheduler.GetSystem<HealthSystem>();
    healthSystem?.ResetHealTracking();
}
```

This covers ALL level entry paths:
- New run from hub
- RETRY from GameOver
- Next level from portal room
- Repeat level from portal room

## Network Sync

Ghost mode syncs via the existing `PlayerSnapshot` mechanism:

1. Host sets `player.IsGhost = true` in HealthSystem
2. `IsGhost` included in `PlayerSnapshot` (`[Key(14)]`)
3. Clients receive snapshot at 30Hz via `GameSnapshot`
4. Clients apply `IsGhost` in `ApplyPlayerUpdates()`
5. Ghost movement syncs via existing position fields

**Late join:** Client receives snapshot with `IsDead=true, IsGhost=true`, applies immediately.

**Bandwidth:** +1 byte per player per snapshot = ~120 bytes/sec for 4 players (negligible).

## Visual Effect (No Shader)

Ghost transparency is achieved via SpriteBatch color multiplication:

```csharp
if (player.IsGhost)
{
    // 50% transparency with cyan tint
    renderColor = new Color(
        (byte)(renderColor.R * 0.7f),
        (byte)(renderColor.G * 0.7f + 255 * 0.3f),  // Boost green
        (byte)(renderColor.B * 0.7f + 255 * 0.3f),  // Boost blue
        (byte)(renderColor.A * 0.5f)                 // 50% alpha
    );
}
```

MonoGame's `SpriteBatch.Draw()` multiplies texture color by tint color, so:
- Reducing red channel → less red
- Boosting green/blue → cyan shift
- Reducing alpha → transparency

## Testing Ghost Mode

### Single-Player
1. Die in Adventure → "GHOST MODE" text appears
2. WASD/gamepad moves through walls
3. Action button → stomp dash (no damage)
4. Cannot collect power-ups
5. Semi-transparent cyan appearance

### Reliability (Regression)
1. **First death:** Ghost mode ✓
2. **RETRY:** GameOver → RETRY → Die → Ghost mode ✓
3. **New level:** Complete → Next → Die → Ghost mode ✓
4. **Hub return:** Hub → New run → Die → Ghost mode ✓

### Multiplayer
```bash
dotnet run -- --host --player-name "Host"
dotnet run -- --join 127.0.0.1:5555 --player-name "Client"
```
1. Host dies → Client sees ghost
2. Client dies → Host sees ghost
3. Late join after death → sees ghost correctly

## Related Systems

- **Permadeath:** Operates on `SelectedHeroes[]`, not entities - ghost state irrelevant
- **Victory:** Queries `SelectedHeroes[]` - ghosts display correctly
- **Resurrection (future):** Would toggle `IsGhost = false` on existing entity
- **Enemy targeting:** Combat queries `!IsDead` - ghosts ignored

## References

### Source Files
- `ECS/Components/Player/PlayerComponent.cs` — IsGhost flag definition
- `ECS/Systems/HealthSystem.cs` — Sets IsGhost = true on death
- `ECS/Systems/NetworkSyncSystem.cs` — Sync IsGhost via PlayerSnapshot
- `ECS/Systems/SpriteRenderSystem.cs` — Ghost transparency + hide health bar
- `ECS/Systems/MovementSystem.cs` — Ghost movement (float through walls)
- `ECS/Systems/PhysicsSystem.cs` — Skip wall collision for ghosts
- `ECS/Systems/ProjectileSystem.cs` — Block projectile creation for ghosts
- `GameStates/LevelStateBase.cs` — Reset death tracking between levels

### Related Context Docs
- [network-multiplayer-system.md](network-multiplayer-system.md) — PlayerSnapshot.IsGhost sync
- [play-modes.md](play-modes.md) — Network mode handling for ghost state
