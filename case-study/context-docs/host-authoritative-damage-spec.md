<!-- v1 | last-verified: 2026-02-15 -->
# Host-Authoritative Damage System Specification

## Overview

This document describes a **client-prediction with host-authoritative reconciliation** model for networked damage in the case study project. The goal is responsive gameplay (instant damage feedback) while maintaining a single source of truth (host) for game state.

This pattern is used by games like Diablo 3, Path of Exile, and other action RPGs with authoritative servers.

---

## Design Goals

1. **Instant feedback**: Players see damage numbers immediately when they hit enemies
2. **Host authority**: Only the host's health values are "real" - clients predict but defer to host
3. **Bandwidth efficiency**: Batch messages, tiered sync rates based on importance
4. **Desync recovery**: Automatic reconciliation when client prediction diverges from host
5. **Death consistency**: All players see enemies die at the same moment

---

## Architecture

### The Two Health Values

Every networked entity with health has TWO values:

```csharp
public struct HealthComponent
{
    public float Current;           // Authoritative (host's truth)
    public float PredictedCurrent;  // Client-side prediction (instant feedback)
}
```

**On Host:**
- `Current` is updated immediately when damage occurs
- `PredictedCurrent` always equals `Current` (no prediction needed)

**On Clients:**
- `PredictedCurrent` is updated immediately when local player deals damage (instant feedback)
- `Current` is updated when host sends `HealthSyncBatchMessage`
- UI/rendering should display `PredictedCurrent` for responsiveness

### System Responsibilities

| System | Priority | Role |
|--------|----------|------|
| CombatSystem | 60 | Detects hits, calls ApplyDamage |
| DamageAuthoritySystem | 62 | Network sync, reconciliation |
| CleanupSystem | 201 | Entity deletion |

**Critical**: Only ONE system should handle damage application and network sync. If multiple systems (e.g., CombatSystem and AbilitySystem) both apply damage with their own network logic, you'll get desyncs.

---

## Message Types

### 1. DamageReportMessage (Client → Host)

**Purpose**: Client reports damage it dealt locally. Host validates and applies.

**Delivery**: `ReliableOrdered` - every damage report must arrive, in order.

```csharp
struct DamageReportMessage
{
    int Frame;              // Client frame when damage occurred
    int SourcePlayerId;     // Which player dealt the damage
    DamageEvent[] Events;   // Array of damage events
}

struct DamageEvent
{
    int TargetId;     // UniqueId of damaged entity
    float Damage;     // Damage amount
    bool IsCrit;      // For damage text styling
    bool IsExplosive; // For VFX
}
```

**When sent**: End of each frame, if client dealt any damage.

**Flow**:
```
Client projectile hits enemy
  → Update PredictedCurrent immediately (instant feedback)
  → Queue DamageEvent

End of frame
  → Batch all DamageEvents into DamageReportMessage
  → Send to host (ReliableOrdered)
```

### 2. HealthSyncBatchMessage (Host → Clients)

**Purpose**: Host sends authoritative health values. Clients reconcile predictions.

**Delivery**: `UnreliableSequenced` - only latest matters, drop old packets.

```csharp
struct HealthSyncBatchMessage
{
    int Frame;              // Host frame when captured
    HealthSync[] Updates;   // Array of health updates
}

struct HealthSync
{
    int EntityId;    // UniqueId of entity
    float Health;    // Authoritative health value
    bool IsDead;     // Death flag (fallback if death batch missed)
}
```

**Send frequency**: Tiered based on entity importance:

| Tier | Entities | Frequency | Rationale |
|------|----------|-----------|-----------|
| Critical | Bosses, Spawners | Every frame (60 Hz) | Must be exact |
| Important | On-screen enemies | 10 Hz | Visible to player |
| Background | Off-screen enemies | 1 Hz | Player doesn't see them |

### 3. EnemyDeathBatchMessage (Host → Clients)

**Purpose**: Immediate death notification. Clients delete entity and spawn VFX.

**Delivery**: `ReliableOrdered` - deaths must never be missed.

```csharp
struct EnemyDeathBatchMessage
{
    int Frame;              // Host frame when deaths occurred
    EnemyDeath[] Deaths;    // Array of death events
}

struct EnemyDeath
{
    int EnemyId;        // UniqueId of dead entity
    int KillerPlayerId; // For kill attribution/scoring
    float X, Y;         // Position for VFX spawning
}
```

**When sent**: Immediately when any entity dies on host (not batched by time).

---

## Detailed Flows

### Flow A: Client Hits Enemy

```
Frame N on CLIENT:
1. Projectile collision detected with Enemy #42
2. CombatSystem.ApplyDamage() called:
   - health.PredictedCurrent -= 10  (instant feedback)
   - Create damage text particle "-10"
   - Queue DamageEvent(targetId=42, damage=10)
3. End of frame: Send DamageReportMessage to host

Frame N+latency on HOST:
4. HandleDamageReport() receives message
5. Validate: Entity exists? Damage reasonable? Target is enemy?
6. Apply damage: health.Current -= 10
7. Check death: if health.Current <= 0 → mark IsDead, queue death broadcast
8. Next host frame: GatherHealthSyncs() includes Entity #42

Frame N+latency+1 on HOST:
9. Send HealthSyncBatchMessage with Entity #42's new health
10. If dead: Send EnemyDeathBatchMessage immediately

Frame N+2*latency on CLIENT:
11. Receive HealthSyncBatchMessage
12. ReconcileHealth(): Compare PredictedCurrent vs host's value
    - If diff < 5: Lerp smoothly (hide jitter)
    - If diff > 5: Snap to host value (desync correction)
13. Update Current = host's value
```

### Flow B: Host Hits Enemy

```
Frame N on HOST:
1. Host's local player projectile hits Enemy #42
2. CombatSystem.ApplyDamage() called:
   - health.Current -= 10 (authoritative, immediate)
   - health.PredictedCurrent -= 10 (keep in sync)
   - Create damage text particle
3. Check death: if health.Current <= 0 → mark IsDead, queue death broadcast
4. GatherHealthSyncs() will include this entity for next sync

Frame N on HOST (same frame):
5. Send HealthSyncBatchMessage to all clients
6. If dead: Send EnemyDeathBatchMessage to all clients

Frame N+latency on CLIENTS:
7. Receive HealthSyncBatchMessage, update health
8. If EnemyDeathBatchMessage received:
   - Mark entity IsDead, MarkedForDeletion
   - Spawn death VFX at position
```

### Flow C: Death Synchronization

Deaths require special handling to ensure all players see the death at the same time and VFX spawn correctly.

**On Host**:
```
1. health.Current drops to 0 (from host damage OR client damage report)
2. Set health.IsDead = true
3. Set tag.MarkedForDeletion = true
4. Set health.DeathBroadcastFrame = currentFrame (prevent duplicate broadcast)
5. Queue EnemyDeath in _pendingDeathBroadcasts
6. End of frame: Send EnemyDeathBatchMessage (ReliableOrdered)
```

**On Client**:
```
1. Receive EnemyDeathBatchMessage
2. For each death:
   - Find entity by UniqueId
   - Skip if already dead (idempotent)
   - Set health.IsDead = true, Current = 0, PredictedCurrent = 0
   - Set tag.MarkedForDeletion = true
   - Spawn VFX at death position
3. CleanupSystem will delete entity next frame
```

---

## Reconciliation Algorithm

```csharp
void ReconcileHealth(ref HealthComponent health, float hostHealth, int hostFrame)
{
    float diff = MathF.Abs(health.PredictedCurrent - hostHealth);

    if (diff < 5f)
    {
        // Small diff: smooth interpolation (hides network jitter)
        health.PredictedCurrent = Lerp(health.PredictedCurrent, hostHealth, 0.3f);
    }
    else
    {
        // Large diff: snap to host (desync correction)
        health.PredictedCurrent = hostHealth;
    }

    // Authoritative value always matches host
    health.Current = hostHealth;
    health.LastReconcileFrame = hostFrame;
}
```

**Why two thresholds?**

- **Small diff (< 5 HP)**: Normal network jitter. Lerp smoothly so players don't see health bar jumping.
- **Large diff (> 5 HP)**: Real desync (missed damage, cheating, bug). Snap immediately to correct state.

---

## Critical Implementation Rules

### Rule 1: Single Damage Path

**ALL damage must go through ONE function.** If CombatSystem and AbilitySystem both have damage logic with network code, you'll get:
- Duplicate health syncs
- Duplicate damage reports
- Desyncs

**Solution**: CombatSystem.ApplyDamage() is the ONLY place damage is applied. AbilitySystem calls into it.

### Rule 2: Host Applies All Local Damage Directly

On host, ALL damage from host-local players applies to `health.Current` immediately.

```csharp
if (_networkService.IsHost)
{
    health.Current -= damage;  // Authoritative
    health.PredictedCurrent = health.Current;  // Keep in sync
    if (health.Current <= 0) ProcessDeath(...);
}
```

Do NOT skip damage based on IsLocalPlayer - host is authoritative over everything.

### Rule 3: Clients Only Update PredictedCurrent

On clients, damage ONLY updates `health.PredictedCurrent`. Never touch `health.Current` directly.

```csharp
if (!_networkService.IsHost)
{
    health.PredictedCurrent -= damage;  // Instant feedback
    QueueDamageReport(...);  // Tell host
    // DO NOT modify health.Current - wait for host sync
}
```

### Rule 4: Never Resurrect Dead Entities

Once `health.IsDead = true`, it stays true. Health syncs with `IsDead = false` for a dead entity are ignored.

```csharp
// In ProcessHealthSyncBatch:
if (health.IsDead) continue;  // Never resurrect
```

### Rule 5: Process Spawns Before Deaths

When client receives both EnemySpawnMessage and EnemyDeathBatchMessage in the same frame (enemy spawned and died instantly on host), process spawns FIRST.

```csharp
void UpdateClient()
{
    ProcessPendingEnemySpawns();  // FIRST - entity must exist
    ProcessPendingHealthSyncs();
    ProcessPendingDeaths();       // LAST - entity deletion
}
```

### Rule 6: DeathBroadcastFrame Prevents Duplicates

Set `health.DeathBroadcastFrame = currentFrame` when queueing a death. GatherDeaths() checks this to avoid broadcasting the same death twice.

```csharp
// Only process if not already broadcast
if (health.IsDead && health.DeathBroadcastFrame == 0)
{
    health.DeathBroadcastFrame = currentFrame;
    _pendingDeathBroadcasts.Add(...);
}
```

---

## HealthComponent Fields Reference

| Field | Purpose | Modified By |
|-------|---------|-------------|
| `Current` | Authoritative health (host's truth) | Host: CombatSystem. Client: DamageAuthoritySystem (from sync) |
| `PredictedCurrent` | Client prediction (instant feedback) | CombatSystem (on damage). DamageAuthoritySystem (reconcile) |
| `IsDead` | Death flag (irreversible) | Host: CombatSystem. Client: DamageAuthoritySystem (from death batch) |
| `LastReconcileFrame` | Prevents re-syncing same value | DamageAuthoritySystem |
| `DeathBroadcastFrame` | Prevents duplicate death broadcasts | DamageAuthoritySystem (host only) |

---

## Bandwidth Estimation

At 4 players, 100 enemies, 60 FPS:

| Message | Frequency | Size | Bandwidth |
|---------|-----------|------|-----------|
| DamageReport | ~10/sec per player | ~50 bytes | ~2 KB/sec |
| HealthSyncBatch (Critical) | 60/sec | ~20 bytes | ~1.2 KB/sec |
| HealthSyncBatch (Important) | 10/sec | ~500 bytes | ~5 KB/sec |
| HealthSyncBatch (Background) | 1/sec | ~500 bytes | ~0.5 KB/sec |
| EnemyDeathBatch | ~5/sec | ~50 bytes | ~0.25 KB/sec |

**Total**: ~9 KB/sec for damage sync (well within reasonable limits)

---

## Testing Checklist

- [ ] Host with 1 local player hits enemy → damage applies once, syncs to clients
- [ ] Host with 2 local players hit same enemy → no double damage
- [ ] Client hits enemy → instant feedback, health syncs from host
- [ ] Client and host hit same enemy same frame → health converges correctly
- [ ] Enemy dies on host → all clients see death, VFX spawn at correct position
- [ ] High latency (200ms) → reconciliation snaps instead of lerping
- [ ] 100+ enemies on screen → bandwidth stays reasonable
- [ ] Disconnect/reconnect → new client receives current enemy health

---

## Common Bugs and Solutions

| Bug | Cause | Solution |
|-----|-------|----------|
| Health desyncs | Multiple systems sending HealthSyncBatchMessage | Single damage path through CombatSystem |
| Double damage on host | Both local hit AND damage report apply | Host applies all local damage, ignores self-reports |
| Melee shows 0 damage | Damage text created before damage calculated | Create damage text AFTER calculating damage |
| Deaths not syncing | DeathBroadcastFrame not set | Always set DeathBroadcastFrame when queuing death |
| Entity not found on death | Death processed before spawn | Process spawns before deaths |
| Zombie enemies | IsDead overwritten by health sync | Never resurrect dead entities |

---

## Files to Create/Modify

1. **HealthComponent.cs** - Add PredictedCurrent, LastReconcileFrame, DeathBroadcastFrame
2. **DamageMessages.cs** - DamageEvent, DamageReportMessage, HealthSync, HealthSyncBatchMessage, EnemyDeath, EnemyDeathBatchMessage
3. **DamageAuthoritySystem.cs** - New system for host sync and client reconciliation
4. **CombatSystem.cs** - Modify ApplyDamage to use prediction model
5. **NetworkService.cs** - Add message sending methods and event handlers
6. **INetworkService.cs** - Add interface methods for new messages
7. **NetworkMessageType.cs** - Add new message type enums
8. **NetworkMessageSerializer.cs** - Register new message types

---

## Summary

The host-authoritative damage model provides:

1. **Instant feedback** via PredictedCurrent (clients see damage immediately)
2. **Consistency** via host authority (one source of truth)
3. **Efficiency** via tiered sync rates (less bandwidth for off-screen entities)
4. **Recovery** via reconciliation (automatic desync correction)

The key principle: **Predict optimistically, reconcile authoritatively.** Clients always show the best guess, but defer to host when reality differs.

## References

### Source Files
- `ECS/Systems/DamageAuthoritySystem.cs` — Host-authoritative damage validation and reconciliation
- `ECS/Systems/CombatSystem.cs` — Hit detection and ApplyDamage calls
- `ECS/Systems/HealthSystem.cs` — Health management, death triggers
- `ECS/Components/Combat/HealthComponent.cs` — Authoritative/PredictedCurrent split
- `Network/Messages/DamageMessages.cs` — DamageReportMessage, HealthSyncBatchMessage
- `Services/Implementation/DamageService.cs` — Damage calculation and validation

### Related Context Docs
- [network-multiplayer-system.md](network-multiplayer-system.md) — Entity sync and snapshot flow
- [network-determinism-architecture.md](network-determinism-architecture.md) — CombatRng determinism for damage rolls
- [architecture.md](architecture.md) — Overall host-authoritative architecture
