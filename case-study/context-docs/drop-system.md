<!-- v1 | last-verified: 2026-02-15 -->
# Drop System

Host-authoritative loot drop system with deterministic RNG, radial distribution, and network synchronization.

## Architecture Overview

### Two-Pass Radial Drop Distribution

When an enemy dies, all drops are accumulated first (pass 1: roll), then distributed radially around the death point (pass 2: spawn). This prevents items from stacking on top of each other.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PASS 1: ROLL ALL DROPS (Host Only)                      │
│                     CombatSystem.RollDrops()                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. XP crystal (always, from enemy.XPValue)                 [SpawnRandom]  │
│  2. Gold bag (5% chance, config-driven)                     [SpawnRandom]  │
│  3. Power-up (5% chance, weighted type selection)            [SpawnRandom]  │
│  4. Collectible(s) (drop table, 0-N items)                  [SpawnRandom]  │
│  5. Boss cores (guaranteed, pre-forged, epic rarity)        [MapRandom]    │
│                                                                             │
│  Result: List<PendingDrop> with kind + data, no positions yet              │
└──────────┬──────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PASS 2: DISTRIBUTE & SPAWN (Host Only)                  │
│                     CombatSystem.SpawnDropBatch()                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  For each drop i of N total:                                                │
│    1. offset = GetDropSpawnOffset(i, N, SpawnRandom, minR, maxR)           │
│    2. position = deathPoint + offset                                        │
│    3. EntityFactory.Create*(position)                                       │
│    4. Network broadcast with final position                                 │
│                                                                             │
│  Radial layout:                                                             │
│    angle = i * (2π / N) + random jitter (±0.3 rad)                         │
│    distance = minRadius + random * (maxRadius - minRadius)                  │
└──────────┬──────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         NETWORK BROADCAST (Host → Clients)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  Per-type messages (existing, unchanged):                                   │
│  - VacuumPickupSpawnMessage (XP crystals, gold bags — includes velocity)   │
│  - PowerUpSpawnMessage                                                      │
│  - CollectibleSpawnMessage                                                  │
│  - ItemDropMessage (orbs, mods, cores)                                      │
│  All include final (X, Y) world position after radial offset               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Radial Distribution Radius

| Enemy Type | Min Radius | Max Radius | Typical Drops |
|------------|-----------|-----------|---------------|
| Regular enemy | 12px | 20px | 1-3 (XP + maybe gold/powerup) |
| Boss | 50px | 90px | 4-8 (XP + gold + cores + powerup + collectibles) |

### Drop Kind Enum

```csharp
private enum DropKind : byte { XPCrystal, GoldBag, PowerUp, Collectible, BossCore }
```

### Spawner Deaths (NOT radially distributed)

Spawner deaths only drop a single Orb/Mod (`TrySpawnItemDrop`). Since there's only one item, no radial distribution is needed — it spawns at the exact death position.

### Destructible Deaths (separate spread logic)

Destructible objects (crates, barrels, urns) have their own spread logic for multi-drops (±30px random square). They are handled separately from the radial system.

## Item Types

Three droppable item types handled by a unified `ItemDropComponent`:

| Type | DropType | Description | Source |
|------|----------|-------------|--------|
| **Orb** | 0 | Element source (Fire, Ice, etc.) | Spawners (70%) |
| **Mod** | 1 | Modifier (SplitShot, Explosive, etc.) | Spawners (30%) |
| **Core** | 2 | Pre-forged equipment with ForgedModType | Bosses only |

### Unified Drop Component

The `ItemDropComponent` uses a type discriminator for single-query ECS efficiency:

```csharp
public enum DropType : byte
{
    Orb = 0,   // Element-based orb component
    Mod = 1,   // Modifier component
    Core = 2   // Pre-forged core (boss drops only)
}

public struct ItemDropComponent
{
    public string ItemId;           // Unique ID for inventory
    public DropType Type;           // Item type discriminator
    public byte SubType;            // OrbType or ModType as byte
    public CoreRarity Rarity;       // Rarity level
    public int ItemLevel;           // 1-25 from world tier
    public float PickupRadius;      // 32f default
    public float Lifetime;          // Legacy: 30s countdown (deprecated)
    public double SpawnTime;        // Synced time at spawn (for expiration)
    public bool IsPickedUp;         // Network race condition guard
    public double PickupRequestTime; // Client timeout tracking
    public byte ForgedModType;      // For Cores: 255 = none
    public byte PowerLevel;         // For Cores: 1-5
}
```

### Type-Safe Factory Methods

```csharp
// Create from item instances
ItemDropComponent.CreateOrb(Orb orb);
ItemDropComponent.CreateMod(Mod mod);
ItemDropComponent.CreateCore(Core core, ModType? forgedMod = null);

// Create from network message
ItemDropComponent.CreateFromNetwork(itemId, type, subType, rarity, itemLevel,
    forgedModType, powerLevel, spawnTime);

// Safe extraction (TryGet pattern)
if (drop.TryGetOrb(out var orb)) { ... }
if (drop.TryGetMod(out var mod)) { ... }
if (drop.TryGetCore(out var core)) { ... }
```

## Drop Sources

### 1. Regular Enemy Death (Radial Distribution)

Triggered in `CombatSystem.TriggerDeathEffects()` → `RollDrops()` → `SpawnDropBatch()`:

All drops from a single enemy death are rolled first, then spawned radially:

| Drop | Chance | RNG Stream | Notes |
|------|--------|------------|-------|
| XP crystal | 100% | SpawnRandom | Amount from `enemy.XPValue` |
| Gold bag | 5% | SpawnRandom | Amount based on XP × gold ratio |
| Power-up | 5% | SpawnRandom | Weighted type selection |
| Collectible(s) | Drop table | SpawnRandom | 0-N items from collectibles.json |

**Radial spread:** 12-20px radius, evenly distributed around death point.

### 2. Spawner Death (Portals)

Triggered in `CombatSystem.TriggerDeathEffects()` → `TrySpawnItemDrop()` (standalone, not radially distributed):

**Drop parameters:**
- **Drop rate:** 5% in RELEASE, 100% in DEBUG
- **Item distribution:** 70% Orbs, 30% Mods
- **Rarity weights:** Common 50%, Uncommon 30%, Rare 14%, Epic 5%, Legendary 1%
- **Spread:** None (single item at exact death position)

### 3. Boss Death (Radial Distribution, Wide Spread)

Boss deaths go through the same two-pass system as regular enemies, but with additional drops and wider spread:

| Drop | Chance | RNG Stream | Notes |
|------|--------|------------|-------|
| XP crystal | 100% | SpawnRandom | From `enemy.XPValue` |
| Gold bag | 5% | SpawnRandom | Same as regular |
| Power-up | 5% | SpawnRandom | Same as regular |
| Collectible(s) | Drop table | SpawnRandom | Uses `boss_kill` table |
| Pre-forged Cores | 100% | MapRandom | `boss.GuaranteedCoreDrops` count (default: 2) |

Boss rewards (XP/gold awards to all players) are handled by `HandleActBossRewards()` separately via network reward messages.

**Boss core parameters:**
- **Count:** `BossComponent.GuaranteedCoreDrops` (default: 2)
- **Type:** Pre-forged Cores with random ForgedModType
- **Rarity:** Always Epic
- **Power level:** 2 (start upgraded)

**Radial spread:** 50-90px radius (wider than regular enemies for visual impact).

## Network Synchronization

### Message Types

| Message | Direction | Delivery | Purpose |
|---------|-----------|----------|---------|
| `ItemDropMessage` | Host → All | ReliableOrdered | Item spawned |
| `ItemPickupRequestMessage` | Client → Host | ReliableOrdered | Request validation |
| `ItemPickedUpMessage` | Host → All | ReliableOrdered | Pickup confirmed |
| `ItemPickupRejectedMessage` | Host → Client | ReliableOrdered | Race condition rejection |

### Network Flow

**Enemy/Boss Death (radial batch):**
```
Host enemy dies → TriggerDeathEffects()
  ├─ RollDrops() → List<PendingDrop>         [No entities created yet]
  └─ SpawnDropBatch()
       └─ For each drop:
            ├─ GetDropSpawnOffset(i, total, SpawnRandom, minR, maxR)
            ├─ Create entity at deathPoint + offset
            └─ Broadcast per-type message with final (X, Y)

Client receives spawn messages
  └─ Creates entity at the host-specified position
```

**Spawner Death (single item):**
```
Host spawner dies → TrySpawnItemDrop()
  ├─ Roll drop chance (SpawnRandom)
  ├─ Roll properties (SpawnRandom)
  ├─ Create entity at exact death position
  └─ Broadcast ItemDropMessage
```

### Pickup Flow (3 Code Paths)

```csharp
if (_networkService.IsOffline())
{
    // OFFLINE (Modes 1-2): Pickup immediately
    PickupItem(context, entity, ref drop, ref tag, playerId, heroSaveId, position);
}
else if (_networkService.IsAuthoritative())
{
    // HOST (Modes 3-4): Pickup and broadcast
    PickupItem(...);
    BroadcastItemPickup(context, tag.UniqueId, drop, playerId);
}
else
{
    // CLIENT (Modes 5-6): Request validation from host
    SendPickupRequest(context, tag.UniqueId, playerId);
    drop.IsPickedUp = true;  // Prevent duplicate requests
    drop.PickupRequestTime = context.GetSyncedTime();  // For timeout
}
```

### Host Validation (ProcessPendingPickupRequests)

Host validates client pickup requests and sends confirmations or rejections:

```csharp
// Host receives ItemPickupRequestMessage
if (!EntityExists(msg.EntityId) || drop.IsPickedUp || tag.MarkedForDeletion)
{
    SendPickupRejection(msg.EntityId, msg.PlayerId);
    continue;
}

// Valid pickup
PickupItem(context, entity, ref drop, ref tag, msg.PlayerId, heroSaveId, position);
BroadcastItemPickup(context, tag.UniqueId, drop, msg.PlayerId);
```

### Client Timeout

Clients automatically retry if no host response within 2 seconds:

```csharp
if (drop.IsPickedUp && drop.PickupRequestTime > 0 &&
    context.GetSyncedTime() - drop.PickupRequestTime > ItemDropComponent.PickupRequestTimeout)
{
    drop.IsPickedUp = false;
    drop.PickupRequestTime = 0;
    // Will retry pickup on next collision
}
```

## Item Expiration

Uses synced time for network-safe expiration across all clients:

```csharp
// Check expiration using synced time
if (drop.SpawnTime > 0)
{
    var elapsed = context.GetSyncedTime() - drop.SpawnTime;
    if (elapsed >= ItemDropComponent.DefaultLifetime)  // 30 seconds
    {
        tag.MarkedForDeletion = true;
        return;
    }
}
else
{
    // Legacy fallback for items spawned before migration
    drop.Lifetime -= deltaTime;
    if (drop.Lifetime <= 0)
    {
        tag.MarkedForDeletion = true;
    }
}
```

## Inventory Addition

Based on item type discriminator:

```csharp
if (drop.TryGetOrb(out var orb))
    _saveService.AddOrb(saveId, orb);
else if (drop.TryGetMod(out var mod))
    _saveService.AddMod(saveId, mod);
else if (drop.TryGetCore(out var core))
    _saveService.AddCore(saveId, core);
```

## Rarity System

### Drop Weights

```csharp
public static int GetRarityDropWeight(CoreRarity rarity) => rarity switch
{
    CoreRarity.Common => 50,     // 50%
    CoreRarity.Uncommon => 30,   // 30%
    CoreRarity.Rare => 14,       // 14%
    CoreRarity.Epic => 5,        // 5%
    CoreRarity.Legendary => 1,   // 1%
    _ => 50
};
```

### Stat Multipliers

```csharp
public static float GetRarityStatMultiplier(CoreRarity rarity) => rarity switch
{
    CoreRarity.Common => 1.0f,
    CoreRarity.Uncommon => 1.25f,
    CoreRarity.Rare => 1.5f,
    CoreRarity.Epic => 2.0f,
    CoreRarity.Legendary => 3.0f,
    _ => 1.0f
};
```

## Item Level System

### World Tier Mapping

```csharp
public static (int min, int max) GetItemLevelRange(int worldTier) => worldTier switch
{
    1 => (1, 5),    // Levels 1-5
    2 => (6, 10),   // Levels 6-10
    3 => (11, 15),  // Levels 11-15
    4 => (16, 20),  // Levels 16-20
    5 => (21, 25),  // Levels 21-25
    _ => (1, 5)
};
```

### Item Level Stat Scaling

```csharp
// 10% per level: ItemLevel 1 = 1.0x, ItemLevel 25 = 3.4x
var itemLevelMultiplier = 1f + (ItemLevel - 1) * 0.1f;
```

## Key Files

| File | Purpose |
|------|---------|
| [ItemDropComponent.cs](../../TrialOfFive.MonoGame/src/TrialOfFive.Engine/ECS/Components/Combat/ItemDropComponent.cs) | Unified drop component with DropType discriminator |
| [ItemDropMessages.cs](../../TrialOfFive.MonoGame/src/TrialOfFive.Engine/Network/Messages/ItemDropMessages.cs) | Network messages (ItemDrop, ItemPickupRequest, etc.) |
| [ItemPickupSystem.cs](../../TrialOfFive.MonoGame/src/TrialOfFive.Engine/ECS/Systems/ItemPickupSystem.cs) | Pickup collision, network validation, inventory addition |
| [CombatSystem.cs](../../TrialOfFive.MonoGame/src/TrialOfFive.Engine/ECS/Systems/CombatSystem.cs) | `RollDrops()`, `SpawnDropBatch()`, `TrySpawnItemDrop()`, `HandleActBossRewards()` |
| [EntityFactory.cs](../../TrialOfFive.MonoGame/src/TrialOfFive.Engine/ECS/Archetypes/EntityFactory.cs) | `CreateItemDrop()`, `CreateOrbDrop()`, `CreateModDrop()`, `CreateForgedCoreDrop()` |
| [CoreDefinitions.cs](../../TrialOfFive.MonoGame/src/TrialOfFive.Engine/Core/CoreDefinitions.cs) | Drop rates, rarity weights, item level ranges |
| [SaveService.cs](../../TrialOfFive.MonoGame/src/TrialOfFive.Engine/Services/Implementation/SaveService.cs) | `AddCore()`, `AddOrb()`, `AddMod()` |

### Legacy Files (Deprecated)

| File | Status |
|------|--------|
| `CoreDropComponent.cs` | Deprecated - use `ItemDropComponent` |
| `CorePickupSystem.cs` | Deprecated - use `ItemPickupSystem` |
| `CoreMessages.cs` | Deprecated - use `ItemDropMessages.cs` |

## Debug Configuration

```csharp
#if DEBUG
    public const float DebugDropRate = 1.0f;  // 100% drops for testing
    public static float DropRate => DebugDropRate;
#else
    public static float DropRate => BaseDropRate;  // 5%
#endif
```

## Network Safety Checklist

When modifying the drop system:

- [x] All RNG uses `context.SpawnRandom` (deterministic) — boss cores use `MapRandom` (separate stream)
- [x] Drop decisions gated on `networkService.IsHost` (inside host gate in `TriggerDeathEffects`)
- [x] Radial positions computed on host BEFORE network broadcast
- [x] Network messages include `Frame` for ordering
- [x] `UniqueId` assigned by host and sent in message
- [x] Client creates entity with matching `networkUniqueId`
- [x] `SpawnTime` synced via message for consistent expiration
- [x] `IsPickedUp` flag prevents duplicate pickup requests
- [x] Host validates pickup requests before confirming
- [x] Rejection message resets `IsPickedUp` for retry
- [x] Client timeout (2s) prevents stuck items
- [x] All messages use `ReliableOrdered` delivery
- [x] `SpawnRandom` order changes are safe — clients receive absolute positions, never see host RNG state

## References

### Source Files
- `ECS/Components/Combat/ItemDropComponent.cs` — Unified drop component with DropType discriminator
- `Network/Messages/ItemDropMessages.cs` — Network messages (ItemDrop, ItemPickupRequest, etc.)
- `ECS/Systems/ItemPickupSystem.cs` — Pickup collision, network validation, inventory addition
- `ECS/Systems/CombatSystem.cs` — RollDrops, SpawnDropBatch, TrySpawnItemDrop
- `ECS/Archetypes/EntityFactory.cs` — CreateItemDrop, CreateOrbDrop, CreateModDrop
- `Core/CoreDefinitions.cs` — Drop rates, rarity weights, item level ranges
- `Services/Implementation/SaveService.cs` — AddCore, AddOrb, AddMod persistence

### Related Context Docs
- [item-system.md](item-system.md) — Orb/Mod/Core equipment and PowerLevel system
- [collectible-system.md](collectible-system.md) — Instant/permanent pickups (StatScroll, Food, etc.)
- [vacuum-pickup-system.md](vacuum-pickup-system.md) — XP crystals and gold bags with vacuum physics
- [network-determinism-architecture.md](network-determinism-architecture.md) — Deterministic RNG for drop rolls
