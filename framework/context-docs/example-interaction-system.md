<!--
FRAMEWORK NOTE — Example Context Doc: Event-Driven Interaction System
=====================================================================
SOURCE: Real context doc from the case study (432 lines).

PATTERN: Behavioral Contract Documentation
- Documents an event-driven system with publisher/subscriber decoupling
- Specifies interaction types, proximity rules, and UI prompt behavior
- Lists subscriber systems that react to interaction events

WHY THIS EXAMPLE:
This doc demonstrates a different pattern from the case-study examples
(which focus on state management, network protocols, and combat). Here
the focus is on *system decoupling* — the InteractionSystem fires events
and multiple subscriber systems react independently. This is a common
architectural pattern (observer/event bus) worth documenting explicitly
so the AI agent understands the contracts between systems.

PAIRED WITH: example-architect.md (the type of agent that would design
and evaluate systems like this).

KEY SECTIONS TO STUDY:
- Architecture Overview: ASCII diagram showing pub/sub relationships
- Key Files: maps concepts to source code locations
- Interaction Types: enum-based type system for extensibility
- Network Considerations: how interactions sync in multiplayer

ANNOTATIONS: Look for "<!-- ANNOTATION: -->" comments throughout.
Remove these when adapting for your own project.
-->

<!-- v1 | last-verified: 2026-02-15 -->
# Interactable System

The interactable system allows players to interact with entities in the world by pressing the action button (E on keyboard, A/X on controller) when within range.

## Architecture Overview

```
InteractionSystem (Priority 198)
├── Detects player proximity to InteractableComponent entities
├── Fires OnInteraction event when action button pressed
└── Tracks nearest interactable per player for UI prompts

Subscriber Systems:
├── HubState → Handles Drone, DroneDelete, DroneSelect, SaveReturn, CoreBank
├── ChestInteractionSystem (Priority 82) → Handles Chest opening
└── ShrineInteractionSystem (Priority 83) → Handles Shrine activation
```

## Key Files

| File | Purpose |
|------|---------|
| [InteractableComponent.cs](../../GameProject/src/GameProject.Engine/ECS/Components/Interaction/InteractableComponent.cs) | Component + InteractionType enum |
| [InteractionSystem.cs](../../GameProject/src/GameProject.Engine/ECS/Systems/InteractionSystem.cs) | Core proximity detection + event firing |
| [ChestComponent.cs](../../GameProject/src/GameProject.Engine/ECS/Components/Interaction/ChestComponent.cs) | Chest entity state |
| [ShrineComponent.cs](../../GameProject/src/GameProject.Engine/ECS/Components/Interaction/ShrineComponent.cs) | Shrine entity state |
| [ChestInteractionSystem.cs](../../GameProject/src/GameProject.Engine/ECS/Systems/ChestInteractionSystem.cs) | Chest opening + loot spawning |
| [ShrineInteractionSystem.cs](../../GameProject/src/GameProject.Engine/ECS/Systems/ShrineInteractionSystem.cs) | Shrine activation + effects |
| [HubState.cs](../../GameProject/src/GameProject.Engine/GameStates/States/HubState.cs) | Handles Hub-specific interactions |

## InteractableComponent

```csharp
public struct InteractableComponent
{
    public float InteractionRadius;  // Range in world units
    public InteractionType Type;     // Which handler processes this
    public string PromptText;        // UI text shown when in range
    public bool IsEnabled;           // Can be disabled after use
}
```

### Factory Methods

| Method | Radius | Type | Prompt |
|--------|--------|------|--------|
| `Drone()` | 80 | Drone | "Create Hero" |
| `DroneDelete()` | 80 | DroneDelete | "Delete Hero" |
| `DroneSelect()` | 80 | DroneSelect | "Select Hero" |
| `Shop()` | 100 | Shop | "Open Shop" |
| `Portal()` | 60 | Portal | "Enter" |
| `NPC(text)` | 80 | NPC | Custom |
| `SaveReturn()` | 80 | SaveReturn | "Save & Return" |
| `CoreBank()` | 80 | CoreBank | "Core Vault" |
| `Chest(tier)` | 60 | Chest | "Open Chest" / "Open Rare Chest" |
| `Shrine(type)` | 70 | Shrine | "Activate Shrine" |

## InteractionType Enum

```csharp
public enum InteractionType
{
    None,
    Drone,       // Hero creation drone (Hub)
    DroneDelete, // Hero deletion drone (Hub)
    DroneSelect, // Hero selection drone (Hub)
    Shop,        // Merchant NPC
    Portal,      // Level portal
    NPC,         // Generic NPC dialogue
    SaveReturn,  // Save & return drone (portal rooms)
    CoreBank,    // Core vault terminal (Hub)
    Chest,       // Loot chest
    Shrine       // Effect shrine
}
```

## Interaction Types Detail

### Hub Drones

Three drones in the Hub for hero management:

| Drone | Purpose | Handler |
|-------|---------|---------|
| **Creation Drone** | Opens hero creation overlay | HubState.HandleInteraction |
| **Delete Drone** | Opens hero deletion confirmation | HubState.HandleInteraction |
| **Select Drone** | Opens hero selection list | HubState.HandleInteraction |

Created via `EntityFactory.CreateDrone()`, uses `EntityType.NPC`.

### Core Bank

Terminal in the Hub for depositing/withdrawing cores (persistent storage).

- Opens `CoreBankOverlay` via HubState
- Allows transferring cores between hero inventory and shared vault

### Save & Return

Drone in portal rooms allowing mid-run saves:

- Saves current progress (XP, health, buffs)
- Restores gold to level-start checkpoint
- Returns player to Hub
- **Disabled in networked play** (Phase 2 TODO)

### Portals

Level transition portals. Note: Current implementation uses collision-based activation via `RiftComponent`, not `InteractableComponent`. The `InteractableComponent.Portal()` factory exists for future use.

### Shop

Merchant NPCs. Handler not yet implemented - `InteractableComponent.Shop()` factory available.

### NPCs

Generic dialogue NPCs. Handler not yet implemented - `InteractableComponent.NPC(promptText)` factory available.

---

## Chests

Loot containers that burst open with gold and items when interacted with.

### ChestComponent

```csharp
public struct ChestComponent
{
    public ChestTier Tier;       // Common, Rare, Epic
    public bool IsOpened;        // One-time use
    public int MinDrops, MaxDrops;
    public int GoldMin, GoldMax;
    public float OrbModChance;   // Chance to drop orb/mod instead of collectible
}
```

### Chest Tiers

| Tier | Drops | Gold | Orb/Mod Chance | Gold Bags |
|------|-------|------|----------------|-----------|
| Common | 1-2 | 10-25 | 15% | 3 |
| Rare | 2-3 | 25-50 | 25% | 5 |
| Epic | 3-4 | 50-100 | 40% | 8 |

### Chest Behavior

1. Player presses E within range
2. **Gold bags** burst out with radial velocities
   - Auto-attract to opener (via `VacuumPhysicsComponent.TargetPlayerId`)
   - Opener gets all gold
3. **Item drops** burst out and land on floor
   - Require E to pickup (no auto-attract)
   - Can be: collectibles (food, scrolls, etc.) OR orbs/mods
4. Chest entity is **deleted** after opening

### Burst Physics

Chests use more exaggerated burst than XP gems:
- `BurstSpeed`: 200 (vs 120 for gems)
- `BurstUpwardForce`: 400
- `BurstGravity`: 700
- `BurstDuration`: 0.5s

### Drop Tables

Configured in `collectibles.json`:
- `chest_common` - Weighted toward snacks and minor scrolls
- `chest_rare` - Better tiers, includes stopwatch and book
- `chest_epic` - Best tiers, high orb/AP/stopwatch chance

### Creating Chests

```csharp
// Via EntityFactory
context.EntityFactory.CreateChest(ChestTier.Rare, position);

// Debug console
chest rare        // Spawn rare chest near player
chest epic 3      // Spawn 3 epic chests
```

---

## Shrines

Room-wide effect triggers that activate once per dungeon run.

### ShrineComponent

```csharp
public struct ShrineComponent
{
    public ShrineType Type;
    public bool IsActivated;
    public float Cooldown;        // 0 = one-time use
    public double LastActivated;
}
```

### Shrine Types

Currently implemented:

| Type | Effect |
|------|--------|
| **GoldEruption** | Bursts 20-30 gold bags covering 800px radius |

### Gold Eruption Behavior

1. Player presses E within range
2. **20-30 gold bags** burst in all directions
   - 800px spread radius
   - 5-25 gold per bag
   - **NO auto-attract** - falls to floor
   - Any player can collect
   - Gold stops at walls (walkability check)
3. Shrine interaction is **disabled** (one-time use)
4. Shrine entity remains visible (could add "depleted" visual state)

### Burst Physics

Shrines use even more exaggerated burst than chests:
- `BurstSpeed`: 350
- `BurstUpwardForce`: 250
- `SpreadRadius`: 800px

### Creating Shrines

```csharp
// Via EntityFactory
context.EntityFactory.CreateShrine(ShrineType.GoldEruption, position);

// Debug console
shrine golderuption    // Spawn gold eruption shrine
shrine                 // Default is gold eruption
```

---

## Adding New Interaction Types

### 1. Add to InteractionType enum

```csharp
// In InteractableComponent.cs
public enum InteractionType
{
    // ... existing types
    MyNewType  // Add here
}
```

### 2. Create factory method

```csharp
public static InteractableComponent MyNewType() => new()
{
    InteractionRadius = 80f,
    Type = InteractionType.MyNewType,
    PromptText = "Do Thing",
    IsEnabled = true
};
```

### 3. Create handler system (if complex logic)

```csharp
public sealed class MyNewTypeSystem : BaseSystem
{
    private GameContext? _context;
    private InteractionSystem? _interactionSystem;

    public override void Initialize(GameContext context)
    {
        _context = context;
        if (context.TryGetService<ISystemScheduler>(out var scheduler))
        {
            _interactionSystem = scheduler.GetSystem<InteractionSystem>();
            _interactionSystem.OnInteraction += HandleInteraction;
        }
    }

    private void HandleInteraction(int playerId, InteractionType type, Entity entity)
    {
        if (type != InteractionType.MyNewType) return;
        if (_context == null) return;

        // Check ghost mode
        // Check network mode (offline/host/client)
        // Execute logic
    }
}
```

### 4. Or handle in existing state (if simple)

```csharp
// In HubState.HandleInteraction or similar
else if (type == InteractionType.MyNewType)
{
    // Simple logic here
}
```

---

## Network Considerations

### Host-Authoritative Pattern

All interaction systems follow the 3-branch network pattern:

```csharp
if (_networkService.IsOffline())
{
    // OFFLINE: Execute immediately
}
else if (_networkService.IsAuthoritative())
{
    // HOST: Execute + broadcast result
    // TODO: Send MyTypeActivatedMessage
}
else
{
    // CLIENT: Send request, wait for host validation
    // TODO: Send MyTypeRequestMessage
    // Can do local prediction (will be corrected)
}
```

### Current Network Status

| Type | Network Sync |
|------|--------------|
| Chest | Local prediction only (TODO: ChestOpenedMessage) |
| Shrine | Local prediction only (TODO: ShrineActivatedMessage) |
| Drones | Local only (Hub is offline) |
| SaveReturn | Disabled in network mode |

### Future Network Messages

```csharp
// Chest messages (planned)
ChestOpenRequestMessage  // Client → Host
ChestOpenedMessage       // Host → All (with drop data)

// Shrine messages (planned)
ShrineActivateRequestMessage  // Client → Host
ShrineActivatedMessage        // Host → All (with gold bag data)
```

---

## Ghost Mode Restrictions

Ghost players (dead, spectating) **cannot**:
- Open chests
- Activate shrines
- Use drones (create/delete/select hero)

Both ChestInteractionSystem and ShrineInteractionSystem check `player.IsGhost` before processing.

---

## Configuration

Chest and shrine configs in `Content/Data/collectibles.json`:

```json
{
  "chests": {
    "common": { "minDrops": 1, "maxDrops": 2, "goldMin": 10, "goldMax": 25, "orbModChance": 0.15 },
    "rare": { ... },
    "epic": { ... },
    "burstPhysics": { "burstSpeed": 200, "burstUpwardForce": 400, ... }
  },
  "shrines": {
    "goldEruption": {
      "minBags": 20, "maxBags": 30,
      "goldMin": 5, "goldMax": 25,
      "spreadRadius": 800,
      "burstSpeed": 350, ...
    }
  },
  "dropTables": {
    "chest_common": { "entries": [...] },
    "chest_rare": { "entries": [...] },
    "chest_epic": { "entries": [...] }
  }
}
```

---

## Debug Commands

| Command | Description |
|---------|-------------|
| `chest [tier] [count]` | Spawn chest(s) near player (common/rare/epic) |
| `shrine [type] [count]` | Spawn shrine(s) near player (golderuption) |

---

## Interaction Prompt UI

The `InteractionSystem` tracks the nearest interactable per player:

```csharp
// Get nearest interactable for player 0
var entity = interactionSystem.GetNearbyInteractable(0);
var data = interactionSystem.GetNearbyInteractableData(0);

if (entity.HasValue)
{
    // Show prompt: data.PromptText (e.g., "Open Chest")
}
```

UI rendering is handled by the current game state's overlay system.

## References

### Source Files
- `ECS/Components/Interaction/InteractableComponent.cs` — Component and InteractionType enum
- `ECS/Systems/InteractionSystem.cs` — Core proximity detection and event firing
- `ECS/Components/Interaction/ChestComponent.cs` — Chest entity state
- `ECS/Components/Interaction/ShrineComponent.cs` — Shrine entity state
- `ECS/Systems/ChestInteractionSystem.cs` — Chest opening and loot spawning
- `ECS/Systems/ShrineInteractionSystem.cs` — Shrine activation and effects
- `GameStates/States/HubState.cs` — Hub-specific interactions
