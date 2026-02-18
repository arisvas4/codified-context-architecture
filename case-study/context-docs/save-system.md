<!-- v1 | last-verified: 2026-02-15 -->
# Save System Architecture

## Overview

The save system manages persistent hero data and in-memory run state for crash recovery. It uses a two-tier architecture:

1. **ISaveService / HeroSave** - Persistent storage (JSON on disk)
2. **IProgressionService / HeroRunState** - In-memory state for level transitions

## File Locations

```
%LocalAppData%/GameProject/
├── saves.json      # Hero save data (HeroSave[])
└── profiles.json   # Player profiles (PlayerProfile[])
```

## Key Services

| Service | Purpose |
|---------|---------|
| `ISaveService` | Hero save CRUD, XP/gold/cores management, disk persistence |
| `IProfileService` | Player profiles that own heroes, slot management |
| `IProgressionService` | In-memory run state capture/restore during level transitions |

---

## HeroSave Schema

```csharp
public class HeroSave
{
    // Identity
    string Id;              // GUID
    string Name;
    HeroClass HeroClass;    // Brute, Mage, Rogue, Ranger
    HeroVisualConfig VisualConfig;
    long CreateTime;

    // Progression
    int Level;              // 1-60
    int CurrentXP;
    int Gold;
    int AugmentPoints;      // Earned from leveling, spent on cores
    int Act;                // 1-5, determines run length

    // Equipment
    CoreInventory Cores;    // Equipped + inventory cores
    Dictionary<StatType, float> LevelStats;   // From leveling
    Dictionary<StatType, int> UpgradeTiers;   // From shop purchases

    // Level Completion
    List<string> CompletedLevelIds;  // e.g., ["GLADE_1", "GLADE_2"]

    // Run State (Save & Continue)
    float? RunTimerSecondsRemaining;
    string? SavedLevelId;
    int SavedArmIndex;      // -1 = none
    int? SavedWorldSeed;
    bool HasActiveRun => RunTimerSecondsRemaining > 0 && SavedLevelId != null;

    // Autosave State (Crash Recovery)
    float? CurrentHealth;           // Null = full HP on spawn
    int? CurrentShields;            // Shield powerup charges
    List<SavedBuffEntry>? ActiveBuffs;  // Powerups with timers
    int? GoldAtLevelStart;          // For non-victory restoration
}
```

### Run State vs Autosave State

| Field Type | Purpose | When Cleared |
|------------|---------|--------------|
| **Run State** | Save & Continue feature | `ClearRunState()` on victory/death |
| **Autosave State** | Crash recovery within a run | Same as Run State |

---

## Autosave Flow

### Trigger Points

| When | What's Saved | What's Discarded |
|------|--------------|------------------|
| Return to Hub (from Adventure/Boss) | XP, health, buffs, timer, position | Gold earned that level |
| Victory completion (panel 3) | Everything including gold | Nothing |
| Game startup (MenuState) | N/A | Clears stale SelectedHeroes |

### Gold Checkpoint System

```
Level Enter:
  if (GoldAtLevelStart == null)
    GoldAtLevelStart = currentGold  // Snapshot BEFORE gameplay

Hub Return (non-victory):
  gold = GoldAtLevelStart           // Restore checkpoint
  GoldAtLevelStart = null           // Clear checkpoint

Victory:
  GoldAtLevelStart = null           // Clear checkpoint, keep gold
```

---

## State Transition Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                        LEVEL ENTRY                                │
├──────────────────────────────────────────────────────────────────┤
│ AdventureState.Enter() / BossState.Enter()                       │
│   1. SnapshotGoldAtLevelStart() → HeroSave.GoldAtLevelStart      │
│   2. Create player entities via EntityFactory                     │
│   3. PostCreationSystem restores health/buffs from HeroRunState  │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                        GAMEPLAY                                   │
├──────────────────────────────────────────────────────────────────┤
│ - Gold incremented via SaveService.AddGold() (immediate)         │
│ - XP incremented via SaveService.AddXP() (immediate)             │
│ - Health/buffs stored in ECS components (not persisted yet)      │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                        LEVEL EXIT                                 │
├──────────────────────────────────────────────────────────────────┤
│ AdventureState.Exit() / BossState.Exit()                         │
│   1. CaptureRunStateBeforeExit() → IProgressionService           │
│      - Extracts health, shields, buffs from ECS                  │
│      - Host-only (clients skip)                                  │
│   2. base.Exit() clears World                                    │
└──────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
┌─────────────────────────┐   ┌─────────────────────────┐
│      HUB RETURN         │   │     VICTORY             │
├─────────────────────────┤   ├─────────────────────────┤
│ AutosaveHeroesOnHubReturn│   │ AutosaveHeroes()       │
│   - Gold = checkpoint   │   │   - Gold KEPT          │
│   - Merge health/buffs  │   │   - Clear checkpoint   │
│   - Save run position   │   │   - Clear run state    │
└─────────────────────────┘   └─────────────────────────┘
```

---

## Key Components

### PostCreationSystem (Priority 5)

Restores health/buffs after entity creation:

```csharp
public sealed class PostCreationSystem : BaseSystem
{
    private HashSet<Entity> _processedEntities = new();

    public override void Update(...)
    {
        // Query players, skip already processed
        if (_processedEntities.Contains(entity)) return;
        _processedEntities.Add(entity);

        // Get saved state
        var runState = _progressionService.GetRunState(player.HeroSaveId);
        if (runState == null) return; // Fresh spawn

        // Restore health, shields, buffs
        health.Current = runState.CurrentHealth;
        health.Shields = runState.CurrentShields;
        // ... restore buffs
    }

    public void Reset() => _processedEntities.Clear();
}
```

**Note:** `Reset()` is called in `GameStateManager.ChangeState()` to prevent unbounded HashSet growth.

### ProgressionService

In-memory cache for run state during level transitions:

```csharp
public sealed class ProgressionService : IProgressionService
{
    private Dictionary<string, HeroRunState> _cachedStates = new();

    // Capture ECS state before entities destroyed
    void CaptureRunState(World world, IReadOnlyList<string> localHeroSaveIds);

    // Retrieve for restoration
    HeroRunState? GetRunState(string heroSaveId);

    // Clear on victory or new run
    void ClearRunState(string heroSaveId);
    void ClearAllRunStates();
}
```

---

## Network Considerations

| Scenario | Behavior |
|----------|----------|
| Host | Captures ECS state, broadcasts via network sync |
| Client | Skips capture (restores from synced HeroSave) |
| Gold sync | Handled by `GoldAwardMessage`, not autosave |

**Host-only capture pattern:**
```csharp
if (_networkService == null || !_networkService.IsNetworked || _networkService.IsHost)
{
    progressionService.CaptureRunState(context.World, localHeroIds);
}
```

---

## Profile System

Profiles own heroes and manage player identity:

```csharp
public class PlayerProfile
{
    string Id;              // GUID (or TestProfileId for Test)
    string Name;            // "Player", "Guest1", etc.
    List<string> HeroIds;   // Heroes owned by this profile
    int LastUsedSlot;       // Controller slot (0-3)
    string AvatarId;        // Visual avatar
}
```

### Default Profiles

| Profile | Purpose |
|---------|---------|
| Player | Primary user, adopts orphaned heroes |
| Guest1-3 | Local co-op guests |
| Test | DEV PLAY/SHOP, owns Test hero |

### Hero Limits

- 12 heroes per profile
- 12 profiles maximum
- Test hero always exists (recreated if deleted)

---

## Debug Commands

| Command | Description |
|---------|-------------|
| `herodata` | Display all saved hero data |
| `herodata [id]` | Display specific hero by ID substring |

---

## Key Files

| File | Purpose |
|------|---------|
| `Services/Interfaces/ISaveService.cs` | HeroSave schema, SavedBuffEntry |
| `Services/Implementation/SaveService.cs` | Disk persistence, CRUD operations |
| `Services/Interfaces/IProgressionService.cs` | HeroRunState, capture/restore interface |
| `Services/Implementation/ProgressionService.cs` | In-memory state cache |
| `Services/Implementation/ProfileService.cs` | Profile management |
| `ECS/Systems/PostCreationSystem.cs` | Health/buff restoration after spawn |
| `GameStates/GameStateManager.cs` | Calls PostCreationSystem.Reset() |
| `GameStates/States/AdventureState.cs` | Gold snapshot, run state capture |
| `GameStates/States/BossState.cs` | Same as AdventureState |
| `GameStates/States/HubState.cs` | Autosave on hub return |
| `GameStates/States/VictoryState.cs` | Autosave after victory |
| `GameStates/States/MenuState.cs` | Clears stale heroes on startup |

## References

### Source Files
- `Services/Interfaces/ISaveService.cs` — HeroSave schema, SavedBuffEntry
- `Services/Implementation/SaveService.cs` — Disk persistence, CRUD operations
- `Services/Interfaces/IProgressionService.cs` — HeroRunState, capture/restore interface
- `Services/Implementation/ProgressionService.cs` — In-memory state cache
- `ECS/Systems/PostCreationSystem.cs` — Health/buff restoration after spawn
- `GameStates/States/HubState.cs` — Autosave on hub return
- `GameStates/States/VictoryState.cs` — Autosave after victory

### Related Context Docs
- [item-system.md](item-system.md) — Equipment persistence (Orbs, Mods, Cores)
- [collectible-system.md](collectible-system.md) — Persistent stat scrolls stored in HeroSave
