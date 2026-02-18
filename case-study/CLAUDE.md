# The Case Study Project

Isometric action roguelike with shooter elements, supporting 1-4 player local/online co-op multiplayer.

## Tech Stack

- **Language:** C# / .NET 8.0
- **Framework:** MonoGame (DesktopGL)
- **ECS:** Arch ECS library
- **Networking:** LiteNetLib (UDP), MessagePack serialization
- **Fonts:** FontStashSharp
- **Build:** MSBuild / dotnet CLI

## Code Quality Standards

- Ensure all changes follow MonoGame/C#/ECS best practices for game design
- Prioritize robustness and stability as primary concerns
- Prefer defensive coding with proper null checks and error handling
- Maintain consistent performance characteristics (avoid allocations in hot paths)
- Follow existing architectural patterns established in the codebase

## Project Structure

```
GameProject/
├── src/
│   ├── GameProject.Engine/     # Core game engine (class library)
│   ├── GameProject.Desktop/    # Game executable (MonoGame WinExe)
│   └── GameProject.DevTools/   # Developer console and testing tools
├── Content/                     # Game assets (sprites, audio, data)
└── Art/                         # Source art assets

MCP/
└── context7_mcp/               # MCP server for architecture context

.claude/context/                # Architecture documentation
```

## Task Management (Slash Commands)

Use these commands to manage parallel agent workstreams with isolated branches:

```bash
/start-task add ice nova ability     # Creates: task/add-ice-nova-ability-20260106
/finish-task                          # Commit and prepare for merge
/abandon-task                         # Preserve as tag, delete branch, return to main
/list-tasks                           # Show active branches and abandoned tags
```

### Workflow

1. **Start**: `/start-task <description>` - auto-names branch, switches to it
2. **Work**: Make changes with agents (branch isolates your work)
3. **Finish**: `/finish-task` - commit and merge to main
4. **Or Abandon**: `/abandon-task` - preserves work as `abandoned/*` tag, returns to main

### Rollback Options

| Scenario | Solution |
|----------|----------|
| Bad edit in session | `Esc+Esc` or `/rewind` |
| Bad commit | `git reset --hard HEAD~1` |
| Entire task failed | `/abandon-task` |
| Review abandoned work | `git checkout abandoned/task-name` |

## Build & Run

```bash
# Build the game
cd GameProject
dotnet build

# Run the game
cd src/GameProject.Desktop
dotnet run

# Run network test (2 clients)
cd src/GameProject.DevTools
dotnet run -- network-test --players 2

# Run with auto-ready and auto-start
dotnet run -- nt --players 2 --auto-ready --auto-start
```

## Architecture Overview

### ECS Pattern
- **Components** (`ECS/Components/`): Data-only structs (TransformComponent, HealthComponent, etc.)
- **Systems** (`ECS/Systems/`): Logic processors with priority ordering (lower = earlier)
- **EntityFactory**: Archetype-based entity creation (CreatePlayer, CreateEnemy, etc.)
- **Performance**: Systems that gather entities per-frame must use `SystemGatherBuffers` instead of `new List<>()` to avoid GC pressure. See CameraSystem, SpriteRenderSystem, etc. for examples.

### System Registration & Cross-System References
When a system needs to reference another system (e.g., subscribing to events), use `ISystemScheduler.GetSystem<T>()` in `Initialize()`:

```csharp
public override void Initialize(GameContext context)
{
    if (context.TryGetService<ISystemScheduler>(out var scheduler))
    {
        _otherSystem = scheduler.GetSystem<OtherSystem>();
        _otherSystem?.OnSomeEvent += HandleEvent;
    }
}
```

**IMPORTANT**: `ISystemScheduler` must be registered as a service **before** `Initialize()` is called on systems. In `GameMain.cs`, the order is:
```csharp
_systemScheduler = new SystemScheduler();
RegisterSystems();
_context.Services.RegisterSingleton<ISystemScheduler>(_systemScheduler);  // BEFORE Initialize!
_systemScheduler.Initialize(_context);  // Now systems can get ISystemScheduler
```

If you see "Could not get ISystemScheduler" errors, it means the service was registered after `Initialize()` was called.

### New System Checklist

**CRITICAL**: When creating a new ECS system, it MUST be registered in `GameProjectGame.RegisterSystems()` or it will never run. This is a common bug - the system file exists but does nothing because it's not registered.

**Checklist for new systems:**
1. Create the system class in `ECS/Systems/`
2. Set appropriate `Priority` (lower = runs earlier)
3. **Register in `GameProjectGame.RegisterSystems()`** ← Most commonly forgotten step!
4. If subscribing to events from another system, use `ISystemScheduler.GetSystem<T>()` in `Initialize()`

**Common symptoms of unregistered systems:**
- System exists but feature doesn't work
- No errors or exceptions (silent failure)
- Event handlers never called
- `Initialize()` never runs

**Recent examples of this bug:**
- `ChestInteractionSystem` - existed but chests weren't openable
- `ShrineInteractionSystem` - existed but shrines weren't activatable
- `ItemPickupSystem` - existed but orbs/mods couldn't be picked up

### Service Layer
- Custom DI via `ServiceContainer`
- Access: `context.GetService<T>()` or `context.TryGetService<T>(out var service)`
- Key services: ICollisionService, ISpatialService, IContentService, INetworkService, IProfileService, IDamageService, ICombatFeedbackService, IInputService

### Game States
- State machine pattern: `GameStateManager` handles transitions
- States: Menu, PlayMenu, Settings, Hub (with overlays), Adventure, Shop, GameOver, Victory
- Note: Hero selection/creation now via HubState overlays
- Lifecycle: `Enter()` → `Update(deltaTime)` / `Draw(spriteBatch)` → `Exit()`

### Networking
- Host-authoritative P2P model with LiteNetLib
- Supports up to 4 players per client (local co-op + online)
- Lobby codes for LAN discovery, direct IP for internet (default port: 5555)
- Host-authoritative spawning via EnemySpawn messages
- Host-authoritative damage via DamageReport → HealthSyncBatch flow
- **Server reconciliation** for player positions (industry standard, like Source Engine)
- **Clock synchronization** keeps clients aligned with host's authoritative time
- **Adaptive interpolation delay** (75-150ms) based on network jitter

## Key Conventions

### File Organization
- One class per file, matching filename
- Components are `readonly struct` with public fields
- Systems inherit from `ISystem` with `Priority` and `Update()`

### Naming
- Interfaces: `IServiceName`
- Components: `XxxComponent`
- Systems: `XxxSystem`
- Game states: `XxxState`

### Data Files
- JSON definitions in `Content/Data/` (heroes.json, enemies.json, levels.json, etc.)
- Loaded via `IContentService.GetDefinition<T>()`

### AbilityContext Pattern

For multi-component calculations (damage scaling, radius, cooldowns), use `AbilityContext`:

```csharp
// In ability systems
var ctx = new AbilityContext(ref combat, ref computed, context.TotalTime);
var damage = ctx.GetScaledDamage(abilityMultiplier);
var radius = ctx.GetScaledRadius(baseRadius);
var canUse = ctx.IsOffCooldown(lastUsed, baseCooldown);
```

**When to use:**
- ✅ Calculations involving CombatComponent + ComputedStatsComponent
- ✅ Formulas used in multiple abilities
- ❌ One-off calculations (inline is fine)

**Benefits:**
- Reduces parameter passing (7 params → 4 params)
- Centralizes stat formulas (prevents duplication)
- Zero performance cost (readonly ref struct)
- Makes adding new stats easier (update 1 method instead of 15+ locations)

## Game Modes

| Mode | Description |
|------|-------------|
| Adventure | Procedural dungeon exploration |
| ActBoss | Boss encounter battles |

## Ghost Mode (Player Death)

When players die, they enter ghost mode instead of becoming passive spectators:

| Aspect | Behavior |
|--------|----------|
| Movement | Float through walls (clamped to world bounds) |
| Visual | 50% transparent with cyan tint |
| Combat | Cannot fire or deal damage |
| Abilities | Dodge only (dash impulse, no damage) |
| Power-ups | Cannot collect |

**Key implementation notes:**
- Uses `IsGhost` flag on `PlayerComponent` (NOT a separate entity)
- Network synced via `PlayerSnapshot.IsGhost`
- `LevelStateBase.InitializeCommon()` resets `HealthSystem._deathProcessed` between levels
- See `.claude/context/ghost-mode.md` for full documentation

## Turbo System (3-Bar Gauge)

3-bar gauge powering dodge (1 bar, Shift/B) and hold-to-charge turbo abilities (1-3 bars, Space/A). Recharges at 0.143 bars/sec (7s per bar). Dash has i-frames + 0.1s grace, breaks destructibles, uses step subdivision to prevent wall clipping. Turbo abilities: Lvl1 TurboShot (piercing), Lvl2 StompAoE, Lvl3 TurboBall (massive piercing ball). Systems: TurboRechargeSystem (26), TurboDashSystem (27), TurboAbilitySystem (29). Network-synced via PlayerSnapshot (IsDashing, IsDashInvulnerable, DashDir, TurboCharge).

See `.claude/context/turbo-system.md` for full documentation.

## Augment Tokens

Orb/Mod tokens upgrade item PowerLevel (1-5). Banked on pickup, spent via radial dial. Drop from bosses and chests.

**Details**: OrbAugmentToken → Orb/Core PL, ModAugmentToken → Mod PL. Instant bank on pickup → `HeroSave.OrbTokens`/`ModTokens`. Spending: `RadialDialMode.TokenPickup`, d-pad selects slot, action upgrades (+1 PL, clamped 1-5). Recycle ~50g. Drops: boss kills (~13%), rare chests (~4%), epic chests (~7%).

See `.claude/context/item-system.md` for details.

## Power-Ups (15 active)

| Category | Types |
|----------|-------|
| **Timed Stat Buffs** | FireRate (+50%), Damage (+50%), Speed (+30%), Defense (-50% taken), Critical (+25%), Penetration (pierce 2), DoubleXP |
| **Special Buffs** | Berserk (30s, risky +100% dmg), TimeWarp (10s enemy slow), ExplosiveRounds |
| **Stacking/Instant** | Shield (1-3 hits), Nuke (instakill), Magnet (pull pickups), GravityWell |

## XP Crystals & Gold Bags (Vacuum Pickups)

Vampire Survivors-style vacuum physics: Burst → Float → Attract → Collect. XP crystals (4 visual tiers) and gold bags from enemies/destructibles.

**Details**: Burst (0.25s pop) → Float (bob) → Attract (vacuum 150px) → Collect. XP tiers: Yellow (<10), Cyan (<30), Purple (<100), Red (100+). Gold: 5% enemy, 80% destructible. Multiplayer: XP split evenly + 25% collector bonus; gold collector-only. Systems: VacuumPhysicsSystem (35), VacuumCollectionSystem (79).

See `.claude/context/vacuum-pickup-system.md` for full documentation.

## Core & Fusion System

Equipment system: Orbs (elemental) + Mods (modifiers) → fuse into Cores → equip via SlotBasedEquipment.

**Item Types:**
- **Orbs**: 8 elemental types providing stats + abilities
- **Mods**: 10 modifier types (SplitShot, Explosive, Homing, etc.)
- **Cores**: Forged from Orb+Orb/Mod+optional Mod (34% stat penalty)

**Item Levels & Power:**
- **ItemLevel** (1-25): Set at drop time, clamped to hero level. Determines base stat scaling
- **PowerLevel** (1-5): Shared by all items (Orbs, Mods, Cores) via `CoreComponent` base class. Upgraded with Augment Tokens
- **Fusion**: Inherits the max PowerLevel from all input items
- XPLevel has been removed from Cores

**Equipment:** `SlotBasedEquipment` is the only equipment system (CoreInventory has been deleted).

**Core Types (8 elements):**

| Type | Primary Stats | Ability |
|------|---------------|---------|
| Fire | Damage, Crit | Ignite (burn DoT) |
| Ice | Defense, Speed | SlowAura |
| Lightning | Damage, Speed | ChainLightning |
| Earth | MaxHP, Defense | Thorns |
| Void | Damage, Lifesteal | HealOnKill |
| Light | MaxHP, Healing | SummonAssistant |
| Dark | Damage, Crit | ShadowExplosion |
| Nature | MaxHP, Regen | DamageTrail |

**Key files:** `Core/Orb.cs`, `Core/Mod.cs`, `Core/Core.cs`, `Core/AugmentToken.cs`, `Core/SlotBasedEquipment.cs`

See `.claude/context/item-system.md` for full architecture.

## Network Testing

```bash
# Quick 2-player test (from src/GameProject.DevTools)
dotnet run -- nt --players 2 --auto-ready --auto-start

# Manual host/client (from src/GameProject.Desktop)
dotnet run -- --host --player-name "Host"
dotnet run -- --join 127.0.0.1:5555 --player-name "Client"
```

Key args: `--host [port]`, `--join <ip:port>`, `--auto-ready`, `--auto-start`, `--latency <ms>`, `--packet-loss <0-100>`, `--local-players <1-4>`. See `.claude/context/network-operations.md` for full CLI reference and test plans.

## Play Modes

7 modes collapse into 3 code paths via `NetworkHelper`: `IsOffline()` (modes 1-2), `IsAuthoritative()` (modes 3-4), `IsClient()` (modes 5-6). Always handle all 3 paths when modifying game state. Local player count (1-4) is orthogonal to network mode.

**Modes**: 1=Solo, 2=LocalMP, 3=HostSolo, 4=Host+Local, 5=ClientSolo, 6=Client+Local, 7=Mixed. **Helpers**: `IsOffline()`, `IsOnline()`, `IsAuthoritative()` (host OR offline), `IsClient()`, `GetModeTag()`. Always exclude ghosts (`!player.IsGhost`) from pickup/damage in all 3 paths.

See `.claude/context/play-modes.md` for mode table, code patterns, and helper methods. See `.claude/context/play-mode-testing.md` for testing guide.

## Context7 MCP Server

Use context7 MCP tools FIRST when exploring unfamiliar code - faster than manual searching.

| Tool | Use For |
|------|---------|
| `list_subsystems()` | See all subsystems |
| `get_files_for_subsystem("networking")` | Get key files for a subsystem |
| `find_relevant_context("add ranged enemy")` | Find files for a task |
| `search_context_documents("BSP")` | Search architecture docs |
| `suggest_agent("fix camera offset")` | Get recommended agent for a task |
| `list_agents()` | See all available agents with triggers |

### Subsystem Reference

| Key | Description | Key Files |
|-----|-------------|-----------|
| `ecs` | Entity Component System (Arch ECS) | Components/, Systems/, EntityFactory.cs |
| `networking` | Host-authoritative P2P networking | NetworkService.cs, Messages/, DamageAuthoritySystem.cs |
| `physics` | Collision and movement | PhysicsSystem.cs, CollisionService.cs |
| `combat` | Damage, health, projectiles, abilities, ghost mode | CombatSystem.cs, HealthSystem.cs, ghost-mode.md |
| `turbo` | 3-bar gauge: dodge (i-frames) + hold-to-charge abilities | TurboDashSystem.cs, TurboAbilitySystem.cs, turbo-system.md |
| `damage` | Host-authoritative damage validation | DamageAuthoritySystem.cs, DamageService.cs, DamageMessages.cs |
| `ai` | Enemy behavior and pathfinding | AISystem.cs, AIBehaviors/ |
| `spawning` | Enemy/powerup wave spawning | SpawnSystem.cs, NetworkSpawnSystem.cs |
| `collectibles` | Instant/permanent pickups (StatScroll, Food, etc.) with JSON drop tables | CollectibleSystem.cs, collectibles.json, CollectibleDropHelper |
| `vacuum-pickups` | XP crystals and gold bags with vacuum physics (burst → float → attract → collect) | VacuumPhysicsSystem.cs, VacuumCollectionSystem.cs, vacuum-pickup-system.md |
| `dungeon-generation` | Procedural dungeons (Adventure mode) | Procedural/, dungeon-generation.md |
| `input` | Keyboard/mouse/gamepad handling | InputService.cs, MovementSystem.cs |
| `rendering` | Sprite rendering and camera | SpriteRenderSystem.cs, Camera2D.cs |
| `game-states` | State machine (Menu, Hub, etc.) | GameStateManager.cs, States/ |
| `content` | Asset loading and definitions | ContentService.cs, Content/Data/ |
| `devtools` | CLI testing and dungeon preview | DevTools/DungeonPreview/, DevTools/NetworkTesting/ |
| `dungeon-debug` | In-game debug overlay and export | Procedural/Debug/ |
| `test-arena` | Immortal target dummies for combat testing | TestArenaState.cs, TestDummyHealingSystem.cs, test-arena.md |

## Custom Agents

Specialized agents in `.claude/agents/`. **Invoke agents proactively** - they catch errors and accelerate development.

### Automatic Triggers (MUST invoke if condition matches)

| If you are touching OR researching... | Invoke Agent |
|------------------------|--------------|
| Complex code, nested conditionals, long methods, state files >500 lines | `code-simplifier` |
| Coordinates, WorldToScreen, camera, ViewMode, lightmap, half-res | `coordinate-wizard` |
| New ECS components or systems, entity archetypes | `ecs-component-designer` |
| Sprites, atlases, animation metadata, spritesheets, placeholders | `sprite-2d-artist` |
| Meshy, Blender, 3D models, rigging, retexturing, toon shading | `model-3d-artist` |
| Sound effects, WAV generation, audio APIs, Freesound, ElevenLabs, SFX timing | `audio-designer` |
| Performance issues, >1ms systems, network sync, latency | `debugger` |
| Dungeon seeds, BSP tree, room connectivity, procedural generation | `dungeon-tester` |
| New network message types, sync patterns, determinism, CombatRng, desync | `network-protocol-designer` |
| New abilities end-to-end (component, system, VFX, balance) | `ability-designer` |
| HLSL shaders, mgfxc compilation, multi-texture patterns | `shader-wizard` |
| LDtk maps, hub editing, portal connections, layer validation | `ldtk-validator` |
| UI/UX design, menus, buttons, lists, dialogs, overlays, scaling, interactions | `ui-and-ux-agent` |
| Level creation, dungeonConfig tuning, spawning/waves, tile selection, difficulty | `level-designer` |
| Game feel, player experience, fun factor, pacing, mechanics evaluation | `game-design-brainstorm` |
| Game systems design, feature scoping, mechanics brainstorming, complexity tradeoffs | `game-design-brainstorm` |
| Core systems architecture, pooling, spatial partitioning, physics patterns, AI navigation | `systems-designer` |

### Post-Change Triggers (invoke AFTER completing work)

| After modifying... | Invoke |
|--------------------|--------|
| Any file in `ECS/Systems/` | `code-reviewer-game-dev` |
| Any file in `Network/` | `code-reviewer-game-dev` |
| Physics, collision, or spatial logic | `code-reviewer-game-dev` |

### Skip Agents Only For
- Trivial one-line fixes (typos, single variable renames)
- Build/run commands already documented above

### Quick Reference

| Agent | Model | Primary Focus |
|-------|-------|---------------|
| `code-simplifier` | opus | Simplify complex code, state file refactoring, readability |
| `coordinate-wizard` | opus | Isometric math, camera transforms, ViewMode |
| `code-reviewer-game-dev` | opus | Post-change code review for ECS, network, physics |
| `network-protocol-designer` | opus | Message types, sync patterns, **determinism expert** (CombatRng, counter sync, desync debugging) |
| `ability-designer` | opus | End-to-end ability implementation (ECS + network + VFX + balance) |
| `debugger` | opus | Performance profiling, network debugging |
| `game-design-brainstorm` | opus | Systems design, feature scoping, player experience critique |
| `systems-designer` | opus | Core systems architecture, industry patterns, multiplayer frameworks |
| `ecs-component-designer` | sonnet | Arch ECS patterns, entity archetypes |
| `sprite-2d-artist` | sonnet | Atlas packing, animation, LDtk sprites, placeholders |
| `model-3d-artist` | sonnet | Meshy → Blender → sprites pipeline |
| `audio-designer` | sonnet | WAV generation, audio APIs, ECS audio timing |
| `dungeon-tester` | sonnet | Seed testing, BSP validation |
| `shader-wizard` | sonnet | HLSL, effects, multi-texture |
| `ldtk-validator` | sonnet | Map validation, portal routing |
| `ui-and-ux-agent` | sonnet | UI/UX design, menus, dialogs, interactions |
| `level-designer` | sonnet | Level config, dungeonConfig, spawning, tiles |

## DevTools CLI

```bash
cd src/GameProject.DevTools

# Dungeon preview
dotnet run -- dp --seed 12345 -v

# Network test (2 players)
dotnet run -- nt --players 2 --auto-ready --auto-start

# HUD Preview (headless MonoGame, uses same in-game SpriteBatch code)
dotnet run -- hp --preset 4players              # Single preset
dotnet run -- hp --all-presets                   # All 6 presets
dotnet run -- hp --all-presets --all-resolutions # Matrix: 6 presets x 4 resolutions
dotnet run -- hp --fonts                         # Font comparison sheet (all active fonts)
dotnet run -- hp -r 854x480 --preset 4players   # Custom resolution

# Radial Dial Preview (headless MonoGame, renders radial dial UI states)
dotnet run -- rd --preset orb-pickup              # Single preset (default 1080p)
dotnet run -- rd --all-presets                    # All 10 presets
dotnet run -- rd --all-presets --all-resolutions  # Matrix: 10 presets x 4 resolutions
dotnet run -- rd --preset orb-fusion -r 1280x720  # Custom resolution

# Headless MonoGame Renderer (pixel-perfect captures)
dotnet run -- render --state menu               # Main menu
dotnet run -- render --state hud --players 4    # HUD with 4 players
dotnet run -- render --state settings           # Settings screen
dotnet run -- render --state victory --panel shop  # Victory shop panel
dotnet run -- render --state pause              # Pause overlay
dotnet run -- render --state hub                # Hub world
dotnet run -- r --state menu --all-resolutions  # All 4 resolutions
dotnet run -- r --all-states                    # All 10 states at default resolution
dotnet run -- r --all-states --all-resolutions  # Full matrix (10 states x 4 resolutions)
# Supported states: menu, settings, playmenu, shop, victory, gameover, hub, pause, hud, boss
# --panel flag: advance multi-page states (victory: shop, progress)
```

See `dungeon-tester` and `debugger` agents for detailed options.

### Agent-Readable Debug Output

All debug output saves to `Content/Debug/`:

| Directory | Tool | Description |
|-----------|------|-------------|
| `Content/Debug/HudPreviews/` | `hp` CLI | Headless MonoGame HUD preview PNGs (pixel-perfect match to in-game) |
| `Content/Debug/RadialDialPreviews/` | `rd` CLI | Radial dial UI state PNGs (orb pickup, fusion, token, scroll) |
| `Content/Debug/Renders/` | `render` CLI | Headless MonoGame renders (pixel-perfect, any state) |
| `Content/Debug/Screenshots/` | F5 / `screenshot` | In-game screenshots |
| `Content/Debug/StateDumps/` | `dump` command | ECS entity state JSON dumps |
| `Content/Debug/DungeonPreviews/` | `dp` CLI | Dungeon layout PNGs |

### HUD Preview Presets

| Preset | Description |
|--------|-------------|
| `default` | 1 player — Lv12, HP 156/200, Gold 1234, Turbo 67% |
| `4players` | All 4 corners — varied stats |
| `low-health` | P1 at 15% HP (red warning) |
| `downed` | P2 in ghost/downed state |
| `full-turbo` | All 3 turbo bars full |
| `empty` | 1 player — zero stats baseline |

### Radial Dial Preview Presets

| Preset | Mode | Description |
|--------|------|-------------|
| `orb-pickup` | ItemPickup | Ice Orb incoming, no selection (Nav card) |
| `orb-equip` | ItemPickup | Ice Orb incoming, empty top slot selected (Equip card) |
| `orb-recycle` | ItemPickup | Ice Orb incoming, recycle selected (Recycle card) |
| `orb-fusion` | ItemPickup | Ice Orb incoming, Fire Orb slot selected (Fusion two-card layout) |
| `mod-replace` | ItemPickup | Split Mod incoming, Homing Mod slot selected (Mod replace card) |
| `orbtoken-pickup` | TokenPickup | Orb token, 3 tokens, no selection |
| `orbtoken-imbue` | TokenPickup | Orb token, Fire Orb slot selected (Augment card) |
| `modtoken-imbue` | TokenPickup | Mod token, Homing Mod slot selected (Augment card) |
| `scroll` | ScrollPickup | Stat scroll with STR/LCK/SPD + recycle |
| `4players` | Mixed | P1 orb-pickup, P2 no dial, P3 token-imbue, P4 mod-replace |

## Font System

**Active fonts** (loaded by ContentService): `Content/Fonts/active/`
- **Cinzel-Black.ttf** — Player IDs (P1-P4), decorative headers
- **Inter-Regular/Medium/SemiBold/Bold.ttf** — All other UI text

**Candidate fonts** (stored for experimentation, not loaded):
- `Content/Fonts/display/` — Sci-fi/tactical headers (Oxanium, Chakra Petch, etc.)
- `Content/Fonts/fantasy/` — Gothic/fantasy accents (Pirata One, Cinzel Decorative, etc.)
- `Content/Fonts/body/` — High-readability body text (Exo 2, Kanit, Saira, Barlow)
- `Content/Fonts/mono/` — Monospace/data display (Space Mono, JetBrains Mono, etc.)

To try a different font: move TTF to `active/`, update `ContentService.LoadFonts()` mapping.

```csharp
// Get named font in code
var font = contentService.GetNamedFont("cinzel", 20);       // Player IDs
var font = contentService.GetNamedFont("inter", 14);         // UI text
var font = contentService.GetNamedFont("inter-bold", 15);    // Bold UI text (HP values)
var font = contentService.GetNamedScaledFont("cinzel", 20, scale); // Auto-scaled
```

## Debug Console (In-Game)

Press backtick (`) or F12 during gameplay to open the debug console. Host-only for state-modifying commands in networked games.

| Command | Description | Usage |
|---------|-------------|-------|
| `help` | List available commands | `help [command]` |
| `test-arena` | Enter training arena (3 zones: 1 single, 8 tight, 9 spread) | `test-arena` |
| `powerup` | Spawn power-up near player | `powerup <type>` |
| `collectible` | Spawn collectible near player | `collectible <type> [tier]` |
| `spawn` | Spawn enemy near player | `spawn <type> [count]` |
| `destructible` | Spawn destructible near player | `destructible <crate\|barrel\|urn\|pot> [count]` |
| `kill` | Kill all enemies (not bosses, not dummies) | `kill` |
| `killboss` | Set boss HP to 1 | `killboss` |
| `godmode` | Toggle invincibility | `godmode` |
| `boss` | Transition to boss fight | `boss` |
| `hub` | Return to hub | `hub` |
| `victory` | Go to victory state | `victory` |
| `timer` | Get/set run timer | `timer [seconds]` |
| `gold` | Give gold to player | `gold <amount>` |
| `xp` | Give XP to player | `xp <amount>` |
| `act` | Set current act (1-5) | `act <1-5>` |
| `state` | Show game state info | `state` |

**Power-up types:** firerate, damage, speed, defense, critical, penetration, berserk, timewarp, explosive, doublexp, shield, nuke, magnet, gravity

**Collectible types:** statscroll, food, stopwatch, levelbook, aporb (tiers: minor/standard/greater for statscroll, snack/meal/feast for food)

## Art Pipeline

3D-to-2D sprite generation via `tools/asset_pipeline/`. Meshy API (3D) → Blender (render) → atlas packing → MonoGame content. Use `sprite-2d-artist` and `model-3d-artist` agents for workflows.

**Key rules:**
- **Sprite naming:** `{name}_{animation}_{direction}_{frame}.png` (8 directions: S, SW, W, NW, N, NE, E, SE)
- **Content loading:** Direct PNG via `Texture2D.FromStream` (no MGCB pipeline)
- **SkiaShapeFactory:** Cached procedural textures (rounded rects, gradients, circles). Create BEFORE `SpriteBatch.Begin()` (macOS OpenGL)
- **Text pixel-snapping:** Always cast draw positions to `(int)` — prevents wavy baseline with FontStashSharp
- **Glow effects:** Use `BlendState.Additive` second pass (SpriteBatch color is multiplicative)
- **Placeholders:** `python -m tools.asset_pipeline.placeholder_generator --create "abilities/ice_nova" --type ability`
- **Emoji fallback:** Missing sprites use `FallbackEmoji` → SkiaSharp procedural texture. **Toon shader**: `toon_shader.py` (Blender headless), `bake_toon_shader()` for texture export

See `.claude/context/art-pipeline.md` for full pipeline docs (Meshy, Blender, atlas, toon shader, troubleshooting).

## Coordinate Systems & Rendering

Five spaces: World (64x64 square), Isometric (64x32 diamond), Grid, Virtual Screen (1920x1080), Physical Screen. Use `coordinate-wizard` agent for coordinate work.

**Two SpriteBatch patterns:** Pattern A (with camera matrix) for sprites/tiles, Pattern B (without matrix + `VirtualToPhysical()`) for screen-space UI like damage numbers. Missing `VirtualToPhysical()` causes resolution-dependent offset.

**Why VirtualToPhysical**: Camera outputs 1920x1080 virtual coords; at non-1080p, `offset = virtualCenter - physicalCenter` (e.g., 320x180px off at 720p). Scale Y offsets by `Camera.Zoom` or they drift when zooming.

See `.claude/context/coordinate-systems.md` for conversion code, depth sorting, and isometric compensation.
See `.claude/context/floating-text.md` for Pattern B implementation details.

## HLSL Shaders

Shaders are in `Content/Effects/` (.fx source, .mgfx compiled).

**Use the `shader-wizard` agent** for shader questions, multi-texture patterns, compilation issues, and visual debugging.

## Damage Type System

Damage is categorized by type, each reduced by a different stat:

| Type | Reduced By | Examples |
|------|------------|----------|
| Physical | Armor | Bullets, melee, missiles, contact damage |
| Magic | Resist | Fireballs, core abilities (Fire/Ice/Lightning/Dark/Earth), trails |
| True | Nothing | Nuke power-up, execute effects |

**Formula:** `finalDamage = rawDamage * max(0.2, 0.98^stat)` (80% reduction cap)

**Breakpoints:**
- 0 stat = 100% damage taken
- 10 stat = 82% damage taken
- 50 stat = 36% damage taken
- 100 stat = 20% damage taken (cap)

**Key files:** `DamageType.cs`, `HealthComponent.CalculateReducedDamage()`, `DamageAuthoritySystem.cs`

**Network flow:** Client sends raw damage + DamageTypeId → Host applies armor/resist reduction → HealthSyncBatch

## Known TODOs

- Assistant/follower power-up behavior
- Nuke and Ricochet power-up effects

## Post-Feature Checklist

After structural changes (new systems, new message types, changed architectural patterns, new services), consider updating:

- [ ] **Code Review** - Invoke `code-reviewer-game-dev` if you modified `ECS/Systems/`, `Network/`, or physics/collision code
- [ ] **Context Docs** - Update `.claude/context/*.md` if you changed how a subsystem works (not just fixed a bug in it). Use `mcp__context7__get_files_for_subsystem()` to find which docs map to your files
- [ ] **CLAUDE.md** - Update if you added/removed systems, services, commands, or conventions
- [ ] **MCP server.py** - Update SUBSYSTEMS dict if you added/renamed/deleted source files listed there
- [ ] **Agents** - Update agent AGENT.md only if the agent's workflow or referenced patterns changed
- [ ] **Validation** - Run `.claude/scripts/validate-architecture.sh` — 0 errors

**Skip docs for:** bug fixes in existing code, value tweaks, sprite/asset changes, UI color adjustments, adding enemies/items using existing patterns.

**Automated drift detection:** A SessionStart hook runs `context-drift-check.py` and injects prioritized warnings:
- **HIGH**: Automatically update the flagged context docs before starting other work. Read the changed code files, update the doc, then proceed with the user's request.
- **MEDIUM**: Mention the drift to the user in your first response and ask if they want to address it.
- **LOW**: Suppressed (not shown). No action needed.
- **DEBUGGING SESSION**: Mention to the user if bugs revealed gaps in documentation.
Warnings auto-dismiss after being shown twice without new commits, or when the flagged docs get updated.

## Key Files Reference

| Area | Files |
|------|-------|
| Entry point | `GameProject.Desktop/Program.cs` → `GameMain.cs` |
| Game context | `GameProject.Engine/GameContext.cs` |
| Entity creation | `GameProject.Engine/ECS/Archetypes/EntityFactory.cs` |
| Networking | `Network/NetworkService.cs`, `Network/INetworkService.cs` |
| Game states | `GameStates/GameStateManager.cs`, `GameStates/States/*.cs` |
| Physics | `ECS/Systems/PhysicsSystem.cs`, `Services/Implementation/CollisionService.cs` |
| Combat | `ECS/Systems/CombatSystem.cs`, `ECS/Systems/ProjectileSystem.cs` |
| Damage system | `ECS/Systems/DamageAuthoritySystem.cs`, `Services/Implementation/DamageService.cs`, `Network/Messages/DamageMessages.cs` |
| AI | `ECS/Systems/AISystem.cs` |
| Art pipeline | `tools/asset_pipeline/placeholder_generator.py`, `atlas_packer.py`, `headless_renderer.py`, `toon_shader.py` |
| Asset manifest | `Content/Data/asset_manifest.json` |
| Content service | `Services/Implementation/ContentService.cs` |
| Profile/Lobby | `Services/Implementation/ProfileService.cs`, `GameStates/States/PlayMenuState.cs` |
| Save system | `Services/Implementation/SaveService.cs`, `Services/Implementation/ProgressionService.cs` |
| Interactions | `ECS/Systems/InteractionSystem.cs`, `ECS/Components/Interaction/InteractableComponent.cs` |
| Hub overlays | `GameStates/States/HubState.cs`, `UI/HeroCreation/HeroCreationOverlay.cs` |
| Hub map data | `Content/Maps/hub.ldtk` (LDtk level file) |

## Save System

Two-tier: `ISaveService`/`HeroSave` (disk) + `IProgressionService`/`HeroRunState` (memory). Autosaves on hub return and victory.

**Details**: Saves to `LocalAppData/GameProject/saves.json`. Hub return: saves XP/health/buffs, restores gold to `GoldAtLevelStart` checkpoint. Victory: saves everything incl. gold. Startup: clears stale `SelectedHeroes`. Flow: `AdventureState.Exit()` → `CaptureState()` → `HubState.Enter()` merges to HeroSave → `PostCreationSystem.RestoreState()`.

See `.claude/context/save-system.md` for flow diagrams and schema.

## Hub World Editing

The hub world is loaded from `Content/Maps/hub.ldtk` (LDtk JSON format). The procedural generator is only a fallback.

**Use the `ldtk-validator` agent** for portal connections, layer validation, and hub modifications.

## Networking Architecture

Host-authoritative P2P model: Host controls spawning, damage, pickups, game state. Clients predict locally. LiteNetLib UDP + MessagePack serialization.

**Key rules:**
- **Networked entities** (in `EntityByUniqueId`): Players, Enemies, Spawners, Power-ups, Core Drops
- **Local-only** (NOT synced): Projectiles, Particles, Trails — damage synced via `DamageReportMessage`
- **3 delivery modes**: UnreliableSequenced (input/snapshots), ReliableOrdered (spawns/deaths), ReliableUnordered (single updates)
- **GetSyncedTime()**: Use instead of `context.TotalTime` for ALL time-based sync logic (cooldowns, AI, spawns)
- **CombatRng.Roll()**: Deterministic % chance effects (crits, procs) using seed + playerId + shotNumber
- **3-branch code pattern**: `IsOffline()` / `IsAuthoritative()` / `IsClient()` — see [Play Modes](#play-modes)

**Flows**: Reconciliation: error <30px=trust, 30-150px=lerp, >150px=snap. Damage: client `ApplyDamage()` → `PredictedCurrent` + `DamageEvent` queue → host validates → `HealthSyncBatch` (10Hz) or `EnemyDeathBatch` (immediate). Pickup: client marks `IsPickedUp` → host validates → broadcast. **System priorities**: 0=NetworkInput, 50=Spawn, 60=Combat, 62=DamageAuthority, 80=PowerUp, 81=Collectible, 200=NetworkSync, 201=Cleanup.

See `.claude/context/architecture.md` for damage flow, pickup flow, entity sync table, and reconciliation details.
See `.claude/context/network-multiplayer-system.md` for input flow, snapshot sync, MessagePack patterns, and system priorities.
See `.claude/context/network-determinism-architecture.md` for CombatRng, GetSyncedTime, and deterministic RNG patterns.
See `.claude/context/network-operations.md` for testing, debugging, and known issues.

## Context Documentation

34 detailed docs in `.claude/context/` - use `mcp__context7__get_context_files()` to list all. Key docs:

- `art-pipeline.md` - Meshy, Blender, atlas packing, content loading
- `coordinate-systems.md` - Isometric rendering, compensation, 5 coordinate spaces
- `item-system.md` - Orb/Mod/Core equipment, fusion, augment tokens, PowerLevel
- `network-multiplayer-system.md` - Entity sync, damage flow, reconciliation
- `network-operations.md` - Testing, debugging, known issues
- `network-determinism-architecture.md` - CombatRng, GetSyncedTime
- `save-system.md` - Two-tier save architecture (disk + memory)
- `ui-sync-patterns.md` - Network UI sync routing, delivery modes
