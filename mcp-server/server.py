# =============================================================================
# FRAMEWORK NOTE — Context Retrieval MCP Server (Layer 2)
# =============================================================================
#
# SOURCE: Real MCP server from the case study project case study (~1,600 lines).
# This is the production server that Claude Code queries via tool calls.
#
# WHAT THIS DOES:
#   Implements Layer 2 (cold-memory retrieval) of the codified context
#   architecture. Provides 7 MCP tools that let the AI agent discover:
#   - Which subsystems exist and what files belong to each
#   - Which context documents are relevant to a given task
#   - Which specialized agent to invoke for a task
#   - Full-text search across all context documents
#
# WHY IT MATTERS:
#   Without retrieval, the AI agent must either (a) load all 34 context docs
#   into the prompt (exceeding context limits) or (b) manually search the
#   codebase (slow, incomplete). The MCP server gives the agent targeted
#   access to architectural knowledge on demand.
#
# KEY DATA STRUCTURES:
#   - SUBSYSTEMS dict (~line 29): Maps subsystem keys to descriptions,
#     keywords, source files, and context doc paths. This is the "index"
#     that makes retrieval work. ~20 subsystems in this case study.
#   - AGENTS dict (~line 1146): Maps agent names to descriptions, triggers,
#     and model assignments. Powers the suggest_agent() tool.
#
# 7 MCP TOOLS (search for @mcp.tool to find each):
#   1. list_subsystems()          — Enumerate all subsystems
#   2. get_files_for_subsystem()  — Get files for a specific subsystem
#   3. find_relevant_context()    — Task-based fuzzy matching across subsystems
#   4. get_context_files()        — List all context documents
#   5. search_context_documents() — Full-text search across context docs
#   6. suggest_agent()            — Recommend agent for a task description
#   7. list_agents()              — Enumerate all agents with metadata
#
# HOW TO ADAPT:
#   1. Replace the SUBSYSTEMS dict with your project's subsystems
#   2. Replace the AGENTS dict with your project's agents (or remove if
#      not using specialized agents)
#   3. Update PROJECT_ROOT, ENGINE_ROOT, CONTEXT_DIR paths
#   4. The tool implementations are generic — they work with any SUBSYSTEMS/
#      AGENTS data. You likely won't need to modify the tool functions.
#   5. Register in Claude Code's settings:
#      "mcpServers": { "context7": { "command": "python", "args": ["-m", "mcp_server"] } }
#
# ANNOTATIONS: Look for "# ANNOTATION:" comments inline below explaining
# non-obvious design choices. Remove these when adapting.
# =============================================================================

"""
Context7 MCP Server

Provides context discovery for Claude Code to find relevant
project architecture and files when starting new tasks.
"""

import logging
import re
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Suppress verbose MCP logging
logging.getLogger("mcp").setLevel(logging.ERROR)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
ENGINE_ROOT = PROJECT_ROOT / "GameProject" / "src" / "GameProject.Engine"
CONTEXT_DIR = PROJECT_ROOT / ".claude" / "context"

# Create the FastMCP server
mcp = FastMCP("Context7")


# =============================================================================
# Architecture Data
# =============================================================================

SUBSYSTEMS = {
    "ecs": {
        "name": "ECS (Entity Component System)",
        "description": "Arch ECS framework with components and systems",
        "keywords": ["entity", "component", "system", "archetype", "query", "world"],
        "files": [
            "GameContext.cs",
            "ECS/Archetypes/EntityFactory.cs",
            "ECS/Components/",
            "ECS/Systems/",
            ".claude/context/interactable-system.md",
            ".claude/context/architecture.md",
        ],
    },
    "services": {
        "name": "Service Layer",
        "description": "Dependency injection and core services",
        "keywords": ["service", "container", "injection", "interface", "collision", "spatial", "content", "audio", "profile", "save", "damage", "feedback", "lighting", "shader", "input"],
        "files": [
            "Services/ServiceContainer.cs",
            "Services/Interfaces/",
            "Services/Implementation/",
        ],
    },
    "game-states": {
        "name": "Game States",
        "description": "State machine for game modes, menus, and lobby",
        "keywords": ["state", "menu", "lobby", "survival", "adventure", "defense", "payload", "boss", "hub", "shop", "playmenu", "profile", "multiplayer"],
        "files": [
            "GameStates/IGameState.cs",
            "GameStates/GameStateManager.cs",
            "GameStates/States/",
            "Services/Implementation/ProfileService.cs",
            "Services/Interfaces/IProfileService.cs",
            ".claude/context/save-system.md",
        ],
    },
    "networking": {
        "name": "Networking",
        "description": "Multiplayer networking with host-authoritative P2P model and MessagePack serialization",
        "keywords": ["network", "multiplayer", "sync", "snapshot", "interpolation", "message", "transport", "lobby", "host", "client", "authority", "damage report", "play mode", "offline", "online", "couch coop", "local multiplayer", "messagepack", "serialization", "serialize", "deserialize"],
        "files": [
            "Network/NetworkService.cs",
            "Network/INetworkService.cs",
            "Network/NetworkHelper.cs",
            "Network/Transport/",
            "Network/Messages/",
            "Network/Messages/DamageMessages.cs",
            "Network/Messages/PowerUpMessages.cs",
            "Network/Sync/",
            "ECS/Systems/NetworkSyncSystem.cs",
            "ECS/Systems/NetworkSpawnSystem.cs",
            "ECS/Systems/NetworkInputSystem.cs",
            "ECS/Systems/DamageAuthoritySystem.cs",
            ".claude/context/play-modes.md",
            ".claude/context/play-mode-testing.md",
            ".claude/context/ui-sync-patterns.md",
            ".claude/context/network-operations.md",
            ".claude/context/network-determinism-architecture.md",
            ".claude/context/network-multiplayer-system.md",
        ],
    },
    "physics": {
        "name": "Physics & Collision",
        "description": "Physics simulation and collision detection",
        "keywords": ["physics", "collision", "velocity", "force", "knockback", "spatial", "raycast", "obstacle"],
        "files": [
            "ECS/Systems/PhysicsSystem.cs",
            "Services/Implementation/CollisionService.cs",
            "Services/Implementation/SpatialService.cs",
            "Services/Interfaces/ICollisionService.cs",
            "Services/Interfaces/ISpatialService.cs",
            ".claude/context/enemy-collision-physics.md",
        ],
    },
    "rendering": {
        "name": "Rendering",
        "description": "Sprite rendering, animation, camera, and procedural shape generation (SkiaSharp)",
        "keywords": ["render", "sprite", "animation", "camera", "draw", "texture", "particle", "trail",
                     "skiasharp", "procedural", "shape", "rounded", "gradient", "ninepatch", "9-slice", "emoji"],
        "files": [
            "ECS/Systems/SpriteRenderSystem.cs",
            "ECS/Systems/AnimationSystem.cs",
            "ECS/Systems/ParticleSystem.cs",
            "Camera/",
            "Rendering/",
            "Rendering/SkiaShapeFactory.cs",
            "Rendering/EmojiTextureGenerator.cs",
            "UI/NinePatch.cs",
            ".claude/context/floating-text.md",
            ".claude/context/coordinate-systems.md",
            ".claude/context/vfx-particle-system.md",
        ],
    },
    "ai": {
        "name": "AI System",
        "description": "Enemy AI behaviors and enemy archetype designs",
        "keywords": ["ai", "behavior", "chase", "wander", "flee", "enemy", "aggro", "target", "archetype", "saboteur", "bloater", "ironclad", "hexweaver", "bonecaller", "webspinner", "blinkfiend", "phaselurk"],
        "files": [
            "ECS/Systems/AISystem.cs",
            "ECS/Components/AIComponent.cs",
            ".claude/context/enemy-archetypes.md",
        ],
    },
    "combat": {
        "name": "Combat",
        "description": "Combat, projectiles, abilities, damage, ghost mode, and deterministic RNG",
        "keywords": ["combat", "damage", "health", "projectile", "ability", "attack", "weapon", "powerup", "death", "kill", "ghost", "spectator", "crit", "critical", "proc", "rng", "deterministic", "combatRng", "shotNumber", "subIndex", "timeBucket"],
        "files": [
            "ECS/Systems/CombatSystem.cs",
            "ECS/Systems/ProjectileSystem.cs",
            "ECS/Systems/HealthSystem.cs",
            "ECS/Systems/AbilitySystem.cs",
            "ECS/Systems/DamageAuthoritySystem.cs",
            "ECS/Components/Combat/CombatComponent.cs",
            "ECS/Components/Combat/HealthComponent.cs",
            "ECS/Components/Combat/ProjectileComponent.cs",
            "ECS/Components/Player/AbilitiesComponent.cs",
            "Services/Interfaces/IDamageService.cs",
            "Services/Interfaces/ICombatFeedbackService.cs",
            "Services/Implementation/DamageService.cs",
            "Services/Implementation/CombatFeedbackService.cs",
            "Network/Messages/DamageMessages.cs",
            "Simulation/CombatRng.cs",
            "ECS/Data/ProjectileData.cs",
            "ECS/Data/ProjectileSpawnParams.cs",
            ".claude/context/ghost-mode.md",
            ".claude/context/enemy-combat-system.md",
            ".claude/context/ability-implementation.md",
        ],
    },
    "turbo": {
        "name": "Turbo System",
        "description": "3-bar turbo gauge: dodge (i-frames, destructible breaking) and hold-to-charge abilities (TurboShot, StompAoE, TurboBall)",
        "keywords": ["turbo", "dash", "dodge", "invulnerable", "i-frame", "iframes", "turboshot", "turboball", "stomp", "charge", "recharge", "gauge"],
        "files": [
            "ECS/Components/Player/TurboGaugeComponent.cs",
            "ECS/Components/Player/TurboAbilityConfigComponent.cs",
            "ECS/Systems/TurboRechargeSystem.cs",
            "ECS/Systems/TurboDashSystem.cs",
            "ECS/Systems/TurboAbilitySystem.cs",
            "Services/Implementation/DamageService.cs",
            "UI/RadialDial/TurboGaugeRenderer.cs",
            ".claude/context/turbo-system.md",
        ],
    },
    "damage": {
        "name": "Damage Authority",
        "description": "Host-authoritative damage validation and health synchronization",
        "keywords": ["damage", "health", "authority", "validate", "sync", "prediction", "reconciliation", "death", "kill", "batch"],
        "files": [
            "ECS/Systems/DamageAuthoritySystem.cs",
            "ECS/Systems/CombatSystem.cs",
            "Services/Interfaces/IDamageService.cs",
            "Services/Implementation/DamageService.cs",
            "Services/Interfaces/ICombatFeedbackService.cs",
            "Services/Implementation/CombatFeedbackService.cs",
            "Network/Messages/DamageMessages.cs",
            "ECS/Components/Combat/HealthComponent.cs",
            ".claude/context/host-authoritative-damage-spec.md",
        ],
    },
    "spawning": {
        "name": "Spawning",
        "description": "Enemy and powerup spawning systems",
        "keywords": ["spawn", "wave", "enemy", "powerup", "spawner"],
        "files": [
            "ECS/Systems/SpawnSystem.cs",
            "ECS/Systems/NetworkSpawnSystem.cs",
            "ECS/Components/SpawnerComponent.cs",
        ],
    },
    "boss": {
        "name": "Boss Fight Framework",
        "description": "Multi-phase boss fights with attack pools, minion spawning, enrage, vulnerability, and shield mechanics",
        "keywords": ["boss", "phase", "enrage", "vulnerability", "shield", "minion", "signature", "attack pool", "multi-phase", "infernus", "dragon"],
        "files": [
            "ECS/Components/Enemy/BossComponent.cs",
            "ECS/Components/Enemy/BossAttackPoolComponent.cs",
            "ECS/Components/Enemy/BossAttackStateComponent.cs",
            "ECS/Components/Enemy/BossMinionComponent.cs",
            "ECS/Systems/BossAbilitySystem.cs",
            "ECS/Systems/BossAttackSystem.cs",
            "Content/Definitions/BossDefinition.cs",
            "Content/Data/bosses.json",
            ".claude/context/boss-fight-framework.md",
            ".claude/context/dragon-boss-system.md",
        ],
    },
    "dungeon-generation": {
        "name": "Procedural Dungeon Generation",
        "description": "BSP + Graph-based procedural dungeon generator for Adventure mode",
        "keywords": [
            "dungeon", "procedural", "generation", "bsp", "room", "corridor",
            "graph", "path", "secret", "template", "micro-template", "populator",
            "adventure", "level", "tile", "door", "key", "treasure", "validation",
            "connectivity", "loop", "interconnected", "dead-end", "target"
        ],
        "files": [
            "Procedural/IDungeonGenerator.cs",
            "Procedural/DungeonGenerationService.cs",
            "Procedural/DungeonConfigLoader.cs",
            "Procedural/DungeonResult.cs",
            "Procedural/BSP/",
            "Procedural/Graph/",
            "Procedural/Rooms/",
            "Procedural/Validation/",
            "Procedural/Population/",
            "Procedural/Templates/",
            "Content/Definitions/DungeonDefinition.cs",
            "Content/Definitions/MicroTemplateDefinition.cs",
            "GameStates/States/AdventureState.cs",
            ".claude/context/dungeon-generation.md",
        ],
    },
    "input": {
        "name": "Input",
        "description": "Input handling with keyboard, mouse, and gamepad support including isometric rotation",
        "keywords": ["input", "keyboard", "controller", "gamepad", "controls", "isometric", "rotation", "direction", "wasd", "cardinal"],
        "files": [
            "Input/",
            "ECS/Systems/InputSystem.cs",
            "Services/Interfaces/IInputService.cs",
            "Services/Implementation/InputService.cs",
            ".claude/context/input-system.md",
        ],
    },
    "aiming": {
        "name": "Aiming System",
        "description": "Mouse/gamepad aiming with isometric coordinate transforms, camera timing, and network determinism",
        "keywords": ["aim", "aiming", "mouse", "target", "fire", "shoot", "projectile", "screen", "world", "coordinate", "isometric", "camera", "determinism", "autofire", "manual"],
        "files": [
            "ECS/Systems/ProjectileSystem.cs",
            "ECS/Systems/CameraSystem.cs",
            "Services/Implementation/InputService.cs",
            "Rendering/IsometricGridHelper.cs",
            "Camera/Camera2D.cs",
            "Input/PlayerInput.cs",
            "Input/InputCommand.cs",
            ".claude/context/aiming-system.md",
        ],
    },
    "devtools": {
        "name": "Developer Tools",
        "description": "CLI utilities for testing, debugging, dungeon preview, HUD preview, headless rendering, layout validation, screenshot capture, and entity state dumping",
        "keywords": ["devtools", "debug", "preview", "dungeon", "seed", "network", "test", "export", "verbose", "png", "image", "ascii", "csv", "visualization", "hud", "headless", "render", "screenshot", "dump", "validate", "font"],
        "files": [
            "../GameProject.DevTools/Program.cs",
            "../GameProject.DevTools/DungeonPreview/DungeonPreviewRunner.cs",
            "../GameProject.DevTools/DungeonPreview/DungeonPreviewConfig.cs",
            "../GameProject.DevTools/DungeonPreview/DungeonImageExporter.cs",
            "../GameProject.DevTools/NetworkTesting/MultiClientLauncher.cs",
            "../GameProject.DevTools/HudPreview/HudPreviewRunner.cs",
            "../GameProject.DevTools/HudPreview/HudPreviewConfig.cs",
            "../GameProject.DevTools/HudPreview/SkiaHudRenderer.cs",
            "../GameProject.DevTools/HudPreview/HudPresets.cs",
            "../GameProject.DevTools/HudPreview/LayoutValidator.cs",
            "../GameProject.DevTools/Render/HeadlessRenderer.cs",
            "../GameProject.DevTools/Render/RenderConfig.cs",
            "UI/Debug/DebugCommandRegistry.cs",
            "Services/Implementation/ContentService.cs",
            ".claude/context/test-arena.md",
            ".claude/context/changelog-devlog.md",
        ],
    },
    "dungeon-debug": {
        "name": "Dungeon Debug & Export",
        "description": "In-game debug overlay rendering, dungeon export to PNG/text/JSON, metadata logging",
        "keywords": ["debug", "overlay", "render", "export", "metadata", "json", "png", "text", "visualization", "dungeon", "room", "corridor", "spawner", "portal"],
        "files": [
            "Procedural/Debug/DungeonDebugRenderer.cs",
            "Procedural/Debug/DungeonExportService.cs",
        ],
    },
    "debug-console": {
        "name": "Debug Console",
        "description": "In-game debug console for testing and development (F12 or backtick to toggle)",
        "keywords": ["debug", "console", "command", "spawn", "powerup", "godmode", "kill", "cheat"],
        "files": [
            "UI/Debug/DebugConsole.cs",
            "UI/Debug/IDebugCommand.cs",
            "UI/Debug/DebugCommandRegistry.cs",
        ],
    },
    "tiled-templates": {
        "name": "Tiled Room Templates",
        "description": "Hand-crafted room templates from Tiled Map Editor for dungeon generation",
        "keywords": ["tiled", "template", "tmx", "tsx", "room", "boss", "treasure", "secret", "tileset", "map", "editor", "hand-crafted"],
        "files": [
            "Procedural/Templates/TiledRoomLoader.cs",
            "Procedural/Templates/RoomTemplateRegistry.cs",
            "Procedural/Templates/RoomTemplateDefinition.cs",
            "Procedural/Population/Populators/RoomTemplatePopulator.cs",
            "Content/Tiled/",
        ],
    },
    "content": {
        "name": "Content & Assets",
        "description": "Asset loading and management, art pipeline (Meshy, Blender, atlas packing)",
        "keywords": ["content", "asset", "texture", "font", "sound", "definition", "load", "pipeline", "meshy", "blender", "atlas"],
        "files": [
            "Services/Implementation/ContentService.cs",
            "Services/Interfaces/IContentService.cs",
            "Content/",
            ".claude/context/art-pipeline.md",
            ".claude/context/tiledlib-api.md",
        ],
    },
    "audio": {
        "name": "Audio System",
        "description": "Sound effect loading, playback, and WAV generation for MonoGame",
        "keywords": ["audio", "sound", "wav", "sfx", "music", "play", "volume", "soundeffect", "soundnames"],
        "files": [
            "Services/Implementation/ContentService.cs",
            "Services/Audio/SoundNames.cs",
            "Content/Audio/",
            ".claude/context/audio-system.md",
        ],
    },
    "collectibles": {
        "name": "Collectible System",
        "description": "Instant and permanent pickup effects: StatScroll, Food, Stopwatch, LevelUpBook, APOrb. Drops from enemies via JSON-driven drop tables.",
        "keywords": [
            "collectible", "pickup", "statscroll", "scroll", "food", "heal", "stopwatch",
            "cooldown", "levelbook", "level up", "ap orb", "augment", "permanent", "instant",
            "tier", "minor", "standard", "greater", "snack", "meal", "feast", "drop", "loot",
            "drop table", "enemy drop", "boss drop", "elite drop"
        ],
        "files": [
            "ECS/Components/Combat/CollectibleComponent.cs",
            "ECS/Systems/CollectibleSystem.cs",
            "ECS/Systems/CombatSystem.cs",  # TrySpawnCollectibleDrop()
            "Network/Messages/CollectibleMessages.cs",
            "Content/Definitions/CollectibleDefinition.cs",  # CollectibleDropHelper
            "Content/Data/collectibles.json",  # dropTables, enemyTypeOverrides
            ".claude/context/collectible-system.md",
            ".claude/context/drop-system.md",
        ],
    },
    "core-fusion": {
        "name": "Core & Fusion System",
        "description": "Equipment system: Orbs + Mods fused into Cores. PowerLevel (1-5) on all items via augment tokens. SlotBasedEquipment (3+3 slots).",
        "keywords": [
            "core", "orb", "mod", "fusion", "forge", "equipment", "equip", "slot",
            "rarity", "item", "stat", "ability", "element", "fire", "ice",
            "lightning", "earth", "void", "light", "dark", "nature", "splitshot",
            "explosive", "homing", "piercing", "critical", "lifesteal",
            "powerlevel", "augment", "token", "upgrade"
        ],
        "files": [
            "Core/CoreComponent.cs",
            "Core/Orb.cs",
            "Core/Mod.cs",
            "Core/Core.cs",
            "Core/SlotBasedEquipment.cs",
            "Core/AugmentToken.cs",
            "Core/FusionTypes.cs",
            "Core/CoreDefinitions.cs",
            "ECS/Components/Player/CoreStatsComponent.cs",
            "ECS/Systems/CoreAbilitySystem.cs",
            "ECS/Systems/CollectibleSystem.cs",
            "UI/Victory/VictoryPanelState.cs",
            "UI/Victory/Logic/VictoryShopLogic.cs",
            "UI/Victory/Logic/VictoryInputHandler.cs",
            "UI/Victory/Tabs/FusionTabRenderer.cs",
            "UI/RadialDial/RadialDialService.cs",
            ".claude/context/item-system.md",
        ],
    },
    "ui": {
        "name": "UI Framework",
        "description": "Unified UI drawing primitives, color palette, scaling, HUD widgets, overlays, and NinePatch panels",
        "keywords": [
            "ui", "hud", "draw", "panel", "button", "overlay", "menu", "widget",
            "color", "scale", "scaledui", "uicolors", "uidrawhelpers", "uistyles",
            "ninepatch", "9-slice", "spritebatch", "font", "text", "progress bar",
            "buff bar", "player widget", "radial dial", "tooltip", "pause",
            "victory", "gameover", "shop", "lobby", "skiashapefactory"
        ],
        "files": [
            "UI/UIColors.cs",
            "UI/UIDrawHelpers.cs",
            "UI/ScaledUI.cs",
            "UI/NinePatch.cs",
            "UI/BuffBarRenderer.cs",
            "UI/PauseOverlay.cs",
            "UI/RadialDial/PlayerWidgetRenderer.cs",
            "UI/RadialDial/RadialDialOverlay.cs",
            "UI/RadialDial/RadialDialService.cs",
            "UI/RadialDial/DialDimensions.cs",
            "UI/RadialDial/TurboGaugeRenderer.cs",
            "UI/RadialDial/ScrollDialRenderer.cs",
            "UI/RadialDial/ItemCardRenderer.cs",
            "UI/Victory/VictoryOverlay.cs",
            "Rendering/SkiaShapeFactory.cs",
            ".claude/context/hud-blueprint.md",
        ],
    },
    "vacuum-pickups": {
        "name": "Vacuum Pickup System",
        "description": "XP crystals and gold bags with Vampire Survivors-style vacuum physics (burst → float → attract → collect)",
        "keywords": [
            "vacuum", "pickup", "xp", "crystal", "gold", "bag", "coin", "pouch",
            "burst", "float", "attract", "collect", "drop", "loot", "enemy death",
            "despawn", "collector bonus", "multiplayer xp", "split", "tier",
            "yellow", "blue", "purple", "red", "small", "medium", "large"
        ],
        "files": [
            "ECS/Components/Combat/VacuumPickupComponent.cs",
            "ECS/Components/Combat/VacuumPhysicsComponent.cs",
            "ECS/Components/Combat/CollectibleComponent.cs",  # EmojiType enum
            "ECS/Systems/VacuumPhysicsSystem.cs",
            "ECS/Systems/VacuumCollectionSystem.cs",
            "ECS/Systems/CombatSystem.cs",  # SpawnXPCrystal, TrySpawnGoldBag
            "ECS/Archetypes/EntityFactory.cs",  # CreateXPCrystal, CreateGoldBag
            "Network/Messages/VacuumPickupMessages.cs",
            "Content/Definitions/CollectibleDefinition.cs",  # VacuumPickupsConfig
            "Content/Definitions/EmojiMappings.cs",  # Emoji unicode mappings
            "Content/Data/collectibles.json",  # vacuumPickups section
            "Services/Audio/SoundNames.cs",  # Pickup sounds
            ".claude/context/vacuum-pickup-system.md",
        ],
    },
}


# =============================================================================
# MCP Resources
# =============================================================================

@mcp.resource("context7://architecture")
def get_full_architecture() -> str:
    """Full architecture overview document."""
    arch_file = CONTEXT_DIR / "architecture.md"
    if arch_file.exists():
        return arch_file.read_text(encoding="utf-8")
    return "Architecture document not found."


@mcp.resource("context7://architecture/ecs")
def get_ecs_architecture() -> str:
    """ECS (Entity Component System) architecture details."""
    return """# ECS Architecture

**Framework:** Arch ECS library

## Components (ECS/Components/)
- **Core:** TagComponent, TransformComponent, VelocityComponent, ColliderComponent, LifetimeComponent
- **Combat:** HealthComponent, CombatComponent, ProjectileComponent, PowerUpComponent, TrailComponent, CoreDropComponent
- **Player:** PlayerComponent, HeroStatsComponent, AbilitiesComponent, ClassAbilityComponent, ActiveBuffsComponent, BuffModifiersComponent, CoreStatsComponent
- **Enemy:** EnemyComponent, AIComponent, SpawnerComponent
- **Rendering:** SpriteComponent, AnimationComponent, LightComponent, EmissiveComponent, ParticleComponent, ParticleEmitterComponent, GlowComponent
- **Rift Visuals:** RiftComponent, RiftInteriorComponent, RiftEdgeComponent
- **Network:** NetworkIdentityComponent, InterpolationComponent
- **Interaction:** InteractableComponent (Type, Radius, IsEnabled)
- **World:** TileComponent, ObjectiveComponent

## Systems (ECS/Systems/)
Priority ordering (lower = earlier):

| Priority | System | Role |
|----------|--------|------|
| 0 | NetworkInputSystem | Collect input, prepare for transmission |
| 1 | SpatialSystem | Build spatial grid for collision queries |
| 10 | MovementSystem | Apply input velocity to entities |
| 14 | BuffSystem | Apply active buff effects |
| 15 | AnimationSystem | Update animation state, direction |
| 20 | AISystem | Update enemy AI, target selection |
| 25 | PhysicsSystem | Apply velocity, knockback, drag, collision |
| 28 | AbilitySystem | Cooldown tracking, ability activation |
| 30 | CameraSystem | Update camera to follow player |
| 40 | ProjectileSystem | Projectile movement, collision, lifetime |
| 49 | NetworkSpawnSystem | Apply spawn messages from host |
| 50 | SpawnSystem | Spawn enemies/power-ups |
| 55 | CorePickupSystem | Handle core drop collection |
| 60 | CombatSystem | Damage application, queue reports |
| 62 | DamageAuthoritySystem | Host validates damage, syncs health |
| 80 | PowerUpSystem | Handle power-up collection |
| 100 | HealthSystem | Process death, respawning |
| 120 | ParticleSystem | Update particles |
| 200 | NetworkSyncSystem | Send/receive snapshots |
| 201 | CleanupSystem | Remove dead entities, clean caches |
| 500 | SpriteRenderSystem | Render sprites to screen |

## Entity Creation
- ECS/Archetypes/EntityFactory.cs - Archetype-based entity creation

| Category | Methods |
|----------|---------|
| Players & Hub | CreatePlayer, CreateAvatar, CreateDrone |
| Combat | CreateEnemy, CreateSpawner, CreateProjectile, CreateTrail |
| Pickups | CreatePowerUp, CreateCoreDrop |
| Effects | CreateParticle, CreateExplosion, CreateLaserBeam |
| Rifts | CreateRiftPortal, CreateRiftSpawner, CreateRiftHazard |

**Network Note:** Projectiles, particles, trails are local-only (not in EntityByUniqueId).

## Key Files
- GameContext.cs - Central game state container with ECS World
- ECS/Archetypes/EntityFactory.cs - Entity archetype creation
- ECS/Components/*.cs - All component definitions
- ECS/Systems/*.cs - All system implementations
"""


@mcp.resource("context7://architecture/services")
def get_services_architecture() -> str:
    """Service layer and dependency injection architecture."""
    return """# Service Architecture

**Pattern:** Custom lightweight DI via ServiceContainer

## Container (Services/ServiceContainer.cs)
- Access via `context.GetService<T>()` or `Services.Get<T>()`
- Supports singleton and factory registration

## Core Services

| Interface | Purpose |
|-----------|---------|
| ICollisionService | Circle/rect collision, raycasting, obstacle resolution |
| ISpatialService | Spatial partitioning, radius/rect queries, buffer pooling |
| IContentService | Asset loading (textures, fonts, sounds, definitions), hot-reload |
| INetworkService | Multiplayer networking, host-authoritative sync |
| IAudioService | Sound playback, spatial audio |
| ISaveService | Save/load game state |
| ISettingsService | Game settings persistence |
| ITileMapService | LDtk map loading, tile rendering |
| IGameStateService | Current game mode tracking |
| IProfileService | Player profile persistence, statistics tracking |
| IInputService | Unified input (keyboard/gamepad/mouse), multi-local-player |
| IDamageService | Centralized damage application with network sync |
| ICombatFeedbackService | Damage numbers, hit flashes, screen shake |
| ILightingService | Dynamic lighting calculations |
| IShaderService | HLSL shader management |
| IPostProcessingService | Screen effects (bloom, color grading) |
| IVirtualFramebufferService | Render target management, virtual resolution |
| ISeparationService | Crowd separation for enemies |

## Key Files
- Services/ServiceContainer.cs - DI container
- Services/Interfaces/*.cs - Service contracts
- Services/Implementation/*.cs - Service implementations
"""


@mcp.resource("context7://architecture/networking")
def get_networking_architecture() -> str:
    """Networking and multiplayer architecture."""
    return """# Networking Architecture

**Model:** Host-authoritative P2P with multi-local-player support (up to 4 players per client)

## NetworkService (Network/NetworkService.cs)
- Modes: Local, Host, Client
- Session states: Disconnected, Connecting, Lobby, Playing, Paused, Ended

## Transport (Network/Transport/)
- LiteNetLibTransport - UDP-based networking
- Delivery modes: Unreliable, UnreliableSequenced, ReliableUnordered, ReliableOrdered

## Message Protocol (Network/Messages/)
| Range | Category | Examples |
|-------|----------|----------|
| 0-19 | Connection | JoinRequest, JoinAccepted, Ping/Pong, AddLocalPlayer |
| 20-29 | Lobby | LobbyState, PlayerJoined, HeroSelected, ProfileSelected |
| 40-59 | Game Control | GameStart, Pause, Resume, LevelChange, GameEnd |
| 60-69 | Input | InputPacket, InputAck |
| 70-79 | Combat | DamageReport, HealthSyncBatch, EnemyDeathBatch, PowerUpPickup* |
| 80-99 | Sync | GameSnapshot, EnemySpawn, SpawnerSpawn, PowerUpSpawn |
| 90-93 | Core | CoreDrop, CorePickupRequest, CorePickedUp, CorePickupRejected |

**Deprecated:** SpawnSeed (replaced by EnemySpawn), HealthUpdate (replaced by HealthSyncBatch)

## Host-Authoritative Damage Flow
```
Client fires → Projectile hits → IDamageService.ApplyDamage()
  ├─ Updates health.PredictedCurrent (instant feedback)
  └─ Queues DamageEvent for host

End of frame → SendDamageReport(batch) → Host

Host receives → DamageAuthoritySystem validates → Applies to health.Current
  ├─ If alive: HealthSyncBatch (10Hz, UnreliableSequenced)
  └─ If dead: EnemyDeathBatch (immediate, ReliableOrdered)
```

## Entity Synchronization
| Entity Type | Networked | Notes |
|-------------|-----------|-------|
| Players, Enemies, Spawners | Yes | Registered in EntityByUniqueId |
| Power-ups, Core Drops | Yes | Registered in EntityByUniqueId |
| Projectiles, Particles, Trails | No | Local-only; damage synced via DamageReport |

## Synchronization (Network/Sync/)
- SnapshotBuffer - Circular buffer (20 snapshots), adaptive delay (75-150ms)
- SnapshotInterpolator - Interpolates remote player positions
- Clock Synchronization - Clients sync to host's authoritative time
- Host-authoritative spawning - EnemySpawn messages replace SpawnSeed

## Network Systems
- NetworkInputSystem (Priority 0) - Input packet handling with redundancy
- NetworkSpawnSystem (Priority 49) - Apply host spawn messages
- DamageAuthoritySystem (Priority 62) - Host validates damage, syncs health
- NetworkSyncSystem (Priority 200) - Snapshot send/receive, reconciliation
- CleanupSystem (Priority 201) - Remove entities, clean EntityByUniqueId cache

## Key Files
- Network/NetworkService.cs - Main network service
- Network/INetworkService.cs - Network interface
- Network/Messages/DamageMessages.cs - DamageReport, HealthSyncBatch, EnemyDeathBatch
- Network/Messages/PowerUpMessages.cs - PowerUp pickup messages
- ECS/Systems/DamageAuthoritySystem.cs - Host damage validation
- Services/Implementation/DamageService.cs - Centralized damage application
"""


@mcp.resource("context7://architecture/game-states")
def get_game_states_architecture() -> str:
    """Game state machine architecture."""
    return """# Game States Architecture

**Pattern:** State machine with lifecycle (Enter -> Update/Draw -> Exit)

## GameStateManager (GameStates/GameStateManager.cs)
- Handles state transitions
- Maintains state dictionary
- Supports push/pop for overlay states

## States (GameStates/States/)

| State | Purpose |
|-------|---------|
| MenuState | Main menu |
| PlayMenuState | Unified lobby (single/local/online multiplayer) |
| SettingsState | Audio, graphics, controls settings |
| HubState | Central hub with portals, hero creation/selection overlays |
| AdventureState | Procedural dungeon exploration (primary game mode) |
| ShopState | In-game shop and upgrades |
| GameOverState | Defeat screen |
| VictoryState | Victory screen |

**Note:** Hero selection, character creation, and deletion are now overlays within HubState.
SurvivalState, PayloadState, DefenseState, and BossState are archived pending rebuild.

## IGameState Interface
- Enter() - Called when state becomes active
- Exit() - Called when leaving state
- Update(GameTime) - Game logic update
- Draw(GameTime) - Rendering
- Pause() / Resume() - Pause handling

## Key Files
- GameStates/IGameState.cs - State interface
- GameStates/GameStateManager.cs - State machine
- GameStates/States/*.cs - Individual state implementations
"""


@mcp.resource("context7://architecture/file-map")
def get_file_map() -> str:
    """Key file locations by subsystem."""
    lines = ["# File Map\n", "Key file locations organized by subsystem.\n"]

    for key, info in SUBSYSTEMS.items():
        lines.append(f"\n## {info['name']}")
        lines.append(f"*{info['description']}*\n")
        for f in info["files"]:
            lines.append(f"- `GameProject.Engine/{f}`")

    return "\n".join(lines)


@mcp.resource("context7://architecture/dungeon-generation")
def get_dungeon_generation_architecture() -> str:
    """Procedural dungeon generation system documentation."""
    dungeon_file = CONTEXT_DIR / "dungeon-generation.md"
    if dungeon_file.exists():
        return dungeon_file.read_text(encoding="utf-8")
    return "Dungeon generation document not found."


@mcp.resource("context7://architecture/tiled-templates")
def get_tiled_templates_architecture() -> str:
    """Tiled room templates documentation."""
    return """# Tiled Room Templates

Hand-crafted room templates created in Tiled Map Editor for the dungeon generation system.

## Directory Structure
```
Content/Tiled/
├── tilesets/
│   └── dungeon_tiles.tsx     # Tile definitions with game properties
└── templates/
    ├── boss_room_01.tmx      # Boss room template
    ├── treasure_room_01.tmx  # Treasure room template
    └── secret_room_01.tmx    # Secret room template
```

## Template System

Templates are loaded from `Content/Tiled/templates/*.tmx` at dungeon generation time:

1. `RoomTemplateRegistry` discovers and loads all .tmx files
2. `RoomTemplatePopulator` applies templates to special rooms (Boss, Treasure, Secret)
3. Template tiles/spawners/treasures override procedural generation

## Creating Templates

1. Open [Tiled Map Editor](https://www.mapeditor.org/)
2. Create new map with 32x32 tile size
3. Add the `dungeon_tiles.tsx` tileset
4. Set `room_type` property on the map

## Map Properties

| Property | Values | Description |
|----------|--------|-------------|
| `room_type` | normal, start, exit, boss, treasure, secret | Type of room this template is for |

## Required Layers

| Layer Name | Type | Purpose |
|------------|------|---------|
| `Floor` | Tile Layer | Floor tiles (GID 0 = wall/empty) |
| `Entities` | Object Layer | Spawners, treasures, entry/exit points |

## Object Types

| Type | Description | Properties |
|------|-------------|------------|
| `spawner` | Enemy spawn point | `enemy_types` (comma-separated) |
| `treasure` | Chest placement | `type` (chest, rare_chest, potion) |
| `portal` | Portal location | For start/exit rooms |
| `entry` | Room entry point | Where corridors connect |
| `exit` | Room exit point | Where corridors connect |

## Tile Properties (in tileset)

| Property | Type | Description |
|----------|------|-------------|
| `tile_id` | string | Game's internal tile identifier (e.g., "stone", "lava") |
| `walkable` | bool | Whether the tile can be walked on |

## Template Selection

Templates are selected based on:
1. Room type matches template's `room_type` property
2. Template dimensions fit within the generated room bounds
3. Random selection when multiple templates match

## Hot Reload

During development, templates can be reloaded at runtime:
```csharp
dungeonGenerator.RoomTemplates.Reload();
```

## Key Files

| File | Purpose |
|------|---------|
| `Procedural/Templates/TiledRoomLoader.cs` | Loads .tmx files via TiledLib |
| `Procedural/Templates/RoomTemplateRegistry.cs` | Manages template pool by room type |
| `Procedural/Templates/RoomTemplateDefinition.cs` | Template data structure |
| `Procedural/Population/Populators/RoomTemplatePopulator.cs` | Applies templates during generation |

## Dependencies

- **TiledLib** NuGet package (v4.0.3) for parsing .tmx/.tsx files
- Tiled Map Editor for creating templates (free at https://www.mapeditor.org/)
"""


@mcp.resource("context7://architecture/input-system")
def get_input_system_architecture() -> str:
    """Input system architecture with keyboard, mouse, and gamepad support."""
    input_file = CONTEXT_DIR / "input-system.md"
    if input_file.exists():
        return input_file.read_text(encoding="utf-8")
    return "Input system document not found."


@mcp.resource("context7://architecture/aiming-system")
def get_aiming_system_architecture() -> str:
    """Aiming system with isometric coordinate transforms, camera timing, and network determinism."""
    aiming_file = CONTEXT_DIR / "aiming-system.md"
    if aiming_file.exists():
        return aiming_file.read_text(encoding="utf-8")
    return "Aiming system document not found."


@mcp.resource("context7://architecture/isometric-input")
def get_isometric_input_architecture() -> str:
    """Isometric input rotation and animation system documentation."""
    return """# Isometric Input Rotation

In Adventure mode (isometric view), the world is rendered at a 45° rotation. To make WASD keys
map to cardinal directions on the isometric grid, input is rotated before being applied to movement.

## The Problem

Without rotation, pressing W moves the character toward the top of the screen (NE on the isometric grid).
Players expect W to move North on the isometric grid (which appears as up-and-left on screen).

## Solution: Two-Stage Rotation

### Stage 1: Input Rotation (InputService)

When `IsIsometricMode = true`, input is rotated -45° before being applied to movement:
- W/Up → North (on isometric grid)
- A/Left → West
- S/Down → South
- D/Right → East

```csharp
// InputService.cs - RotateForIsometric()
// Rotate -45° to align WASD with isometric cardinal directions
const float cos45 = 0.7071068f;
const float sin45 = -0.7071068f;  // Negative for -45°

float newX = x * cos45 - y * sin45;
float newY = x * sin45 + y * cos45;
```

This rotation is applied to:
- All keyboard input (players 1-4 with different key bindings)
- All gamepad input (left stick)
- Network clients receive already-rotated input

### Stage 2: Animation Counter-Rotation (AnimationSystem)

Since velocity is now in world-space (rotated), sprites would face the wrong direction.
AnimationSystem counter-rotates +45° when determining sprite facing direction:

```csharp
// AnimationSystem.cs - RotateForScreenSpace()
// Rotate +45° (inverse of input rotation)
const float cos45 = 0.7071068f;
const float sin45 = 0.7071068f;  // Positive for +45°

return new Vector2(
    dir.X * cos45 - dir.Y * sin45,
    dir.X * sin45 + dir.Y * cos45
);
```

This ensures sprites face the direction the player expects (pressing W shows "moving up" sprite).

## Mode Toggle

AdventureState sets `IsIsometricMode` on state transitions:
```csharp
// AdventureState.Enter()
inputService.IsIsometricMode = true;

// AdventureState.Exit()
inputService.IsIsometricMode = false;
```

## Flow Diagram

```
Input (W key pressed)
  → InputService rotates -45° (when IsIsometricMode = true)
  → MovementSystem sets DesiredDirection (world-space: North on iso grid)
  → PhysicsSystem applies velocity (character moves North on isometric grid)
  → AnimationSystem counter-rotates +45° for sprite facing
  → Sprite shows "moving up on screen" animation
```

## Network Considerations

- Input is rotated BEFORE network transmission
- All clients receive identical rotated input
- Animation counter-rotation is applied locally on each client
- Result: Consistent movement and animations across all networked players

## Multi-Player Support

All 4 local players are covered:
- Player 1: WASD + Space
- Player 2: Arrow keys + Enter
- Player 3: IJKL + U
- Player 4: FGHT + Y

Rotation happens in `PollKeyboard()` and `PollGamepad()`, which are called for all players.

## Key Files

| File | Purpose |
|------|---------|
| `Services/Implementation/InputService.cs` | `RotateForIsometric()` - rotates input -45° |
| `Services/Interfaces/IInputService.cs` | `IsIsometricMode` property |
| `ECS/Systems/AnimationSystem.cs` | `RotateForScreenSpace()` - counter-rotates +45° for sprites |
| `GameStates/States/AdventureState.cs` | Sets `IsIsometricMode = true` on Enter, `false` on Exit |
"""


@mcp.resource("context7://architecture/dungeon-debug")
def get_dungeon_debug_architecture() -> str:
    """Dungeon debug and export tools documentation."""
    return """# Dungeon Debug & Export Tools

In-engine debug overlay rendering and file export services for dungeon visualization.

## DungeonDebugRenderer (In-Game Overlay)

Location: `Procedural/Debug/DungeonDebugRenderer.cs`

Real-time debug overlay that renders on top of the game view (isometric or rotated ortho).

### Features
- Room outlines with color-coding by type
- Corridor center lines between connected rooms
- Portal markers (start = green, exit = magenta)
- Spawner X markers (red)
- Frustum culling for performance
- Cached outline data (only rebuilds when dungeon changes)

### Color Legend (In-Game)

| Color | Meaning |
|-------|---------|
| Bright Green | Normal room outline |
| Yellow | Critical path room |
| Purple | Secret room |
| Orange | Dead end room |
| Green | Start portal |
| Magenta | Exit portal |
| Cyan | Corridor center lines |
| Red X | Spawner location |

### Usage
```csharp
var debugRenderer = new DungeonDebugRenderer();
debugRenderer.SetDungeon(dungeonResult);

// In Draw()
debugRenderer.DrawDebugOverlay(spriteBatch, pixel, dungeon, tileSize, camera,
    contentService, showLabels: true, font, viewMode);
```

### Static Logging
```csharp
DungeonDebugRenderer.LogDungeonStats(dungeonResult);  // Outputs to Debug console
```

---

## DungeonExportService (File Export)

Location: `Procedural/Debug/DungeonExportService.cs`

Exports dungeon data to files during runtime (auto-saves metadata JSON on generation).

### Export Methods

| Method | Output | Use Case |
|--------|--------|----------|
| `ExportAll()` | PNG + TXT + JSON | Full debug export |
| `ExportMetadata()` | JSON only | Auto-save on generation |
| `ExportAsPng()` | PNG image | Visual debugging |
| `ExportAsText()` | ASCII art | Console/log analysis |

### Output Directory
`Content/Debug/DungeonExport/`

### Metadata JSON Structure
```json
{
  "Seed": 3536315802,
  "Timestamp": "2025-12-28T02:33:50",
  "IsValid": true,
  "MapWidth": 140,
  "MapHeight": 140,
  "TileSize": 128,
  "RoomCount": 20,
  "StartPortalX": 11968,
  "StartPortalY": 1600,
  "ExitPortalX": 1984,
  "ExitPortalY": 15936,
  "SpawnerCount": 16,
  "TreasureCount": 10,
  "KeyCount": 0,
  "SwitchCount": 0,
  "RoomTypes": { "Normal": 14, "Secret": 4, "Start": 1, "Exit": 1 }
}
```

### Usage
```csharp
// Export all formats with timestamp
DungeonExportService.ExportAll(dungeon, seed, contentRootPath);

// Export only metadata (lightweight)
var metadataPath = Path.Combine(contentRoot, "Debug/DungeonExport", $"dungeon_{seed}.json");
DungeonExportService.ExportMetadata(dungeon, seed, metadataPath);
```

---

## DevTools CLI (External Tool)

For external dungeon preview without running the game, see `context7://architecture/devtools`.

```bash
# Quick preview
cd src/GameProject.DevTools
dotnet run -- dp --seed 3536315802

# Verbose with room details
dotnet run -- dp -s 3536315802 -v
```
"""


@mcp.resource("context7://architecture/devtools")
def get_devtools_architecture() -> str:
    """Developer tools CLI documentation."""
    return """# Developer Tools (DevTools)

CLI utilities for testing, debugging, and dungeon preview with PNG export.

## Location
```
GameProject/src/GameProject.DevTools/bin/Debug/net8.0/GameProject.DevTools.exe
```

## Commands

| Command | Aliases | Purpose |
|---------|---------|---------|
| `network-test` | `net-test`, `nt` | Launch multiplayer network test |
| `dungeon-preview` | `dp` | Generate and preview a dungeon |
| `help` | `-h`, `--help` | Show help message |

## Dungeon Preview

Generates a dungeon with a specific seed, displays statistics, and exports to PNG/text.

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--seed, -s <n>` | Random seed for generation | 12345 |
| `--output, -o <path>` | Export to file (.png, .txt, or .csv) | auto (PNG) |
| `--width, -w <n>` | World width in pixels | from dungeon.json |
| `--height, -h <n>` | World height in pixels | from dungeon.json |
| `--rooms, -r <n>` | Target room count | from dungeon.json |
| `--verbose, -v` | Show detailed room info | false |
| `--no-export` | Skip file export (console only) | false |

### Export Formats

| Format | Extension | Description |
|--------|-----------|-------------|
| PNG | `.png` | Color-coded dungeon image (default) |
| ASCII | `.txt` | Text-based dungeon representation |
| CSV | `.csv` | Tile data for analysis |

Default output: `Content/Debug/DungeonPreviews/dungeon_{seed}.png`

### PNG Color Legend

| Color | Meaning |
|-------|---------|
| Green | Start room |
| Blue | Exit room |
| Red | Boss room |
| Yellow | Secret room |
| Red circles | Spawners |
| Gold squares | Treasures |

### Examples
```bash
# Generate dungeon and export PNG
GameProject.DevTools dungeon-preview --seed 12345

# Verbose output with room details
GameProject.DevTools dp -s 99999 -v

# Export to ASCII art file
GameProject.DevTools dp -s 12345 -o dungeon.txt

# Custom dimensions, no file export
GameProject.DevTools dp --seed 42 --width 6000 --height 6000 --rooms 20 --no-export
```

### Output
- Stats: Generation time, map size, room counts by type, spawner/treasure/key/switch counts
- Verbose: Individual room details with bounds, types, required keys
- PNG: Color-coded visualization with room labels and entity markers
- ASCII: Text representation (# = wall, . = floor, S = start, E = exit, B = boss, ? = secret)

## Network Test

| Option | Description | Default |
|--------|-------------|---------|
| `--players <n>` | Number of game windows/clients (1-4) | 2 |
| `--local-players <n>` | Local players per client (1-4) | 1 |
| `--port <port>` | Host port | 5555 |
| `--latency <ms>` | Simulated latency in ms | 0 |
| `--packet-loss <percent>` | Simulated packet loss (0-100) | 0 |
| `--auto-start` | Host auto-starts when all ready | false |
| `--auto-ready` | Clients auto-mark ready | false |

## Key Files
- Program.cs - Command routing and help
- DungeonPreview/DungeonPreviewRunner.cs - Dungeon generation and stats
- DungeonPreview/DungeonPreviewConfig.cs - CLI argument parsing
- DungeonPreview/DungeonImageExporter.cs - PNG/ASCII/CSV export (uses SkiaSharp)
- NetworkTesting/NetworkTestRunner.cs - Multi-client network testing
"""


# =============================================================================
# Agent Registry
# =============================================================================

AGENTS = {
    "code-simplifier": {
        "name": "Code Simplifier",
        "description": "Code simplification expert for C#/MonoGame/ECS. Use when code feels complex, hard to read, or fragile. Also handles game state file refactoring (large state files >500 lines, state machine flow, UI extraction). Simplifies without breaking functionality.",
        "triggers": ["simplify", "simplification", "complex", "complicated", "refactor", "cleanup", "clean up", "readable", "readability", "maintainable", "nested", "long method", "hard to read", "confusing", "messy", "playmenustate", "hubstate", "large file", "overlay"],
        "model": "opus",
    },
    "coordinate-wizard": {
        "name": "Coordinate Wizard",
        "description": "Isometric coordinate and camera transform specialist. Use for world-to-screen conversion, isometric projections, mouse picking, entity positioning, tile rendering, camera following, UI anchoring, or ViewMode-specific behavior.",
        "triggers": ["coordinate", "screen", "camera", "isometric", "transform", "viewmode", "lightmap", "half-res", "projection", "mouse", "picking", "origin", "matrix"],
        "model": "opus",
    },
    "ecs-component-designer": {
        "name": "ECS Component Designer",
        "description": "Arch ECS specialist for designing new components, systems, and entity archetypes following existing project patterns.",
        "triggers": ["component", "system", "entity", "archetype", "query", "ecs", "factory"],
        "model": "sonnet",
    },
    "sprite-2d-artist": {
        "name": "2D Sprite Artist",
        "description": "2D sprite and animation specialist for spritesheet creation, atlas packing, animation setup, sprite integration into MonoGame content, LDtk level decoration, and placeholder asset generation.",
        "triggers": ["sprite", "atlas", "animation", "spritesheet", "frame", "ldtk", "tileset", "texture", "pack", "placeholder"],
        "model": "sonnet",
    },
    "model-3d-artist": {
        "name": "3D Model Artist",
        "description": "3D model and Meshy pipeline specialist for image-to-3D generation, retexturing, rigging, animation, and Blender sprite rendering.",
        "triggers": ["meshy", "blender", "3d", "model", "rigging", "retexture", "headless", "glb", "fbx", "mixamo"],
        "model": "sonnet",
    },
    "debugger": {
        "name": "Performance/Network Debugger",
        "description": "Performance and network debugging specialist for system profiling, performance bottlenecks, multiplayer sync issues, latency investigation, clock synchronization, damage authority debugging, and lobby/connection debugging.",
        "triggers": ["performance", "slow", "bottleneck", "latency", "sync", "network", "profiler", "fps", "debug", "lag", "damage authority", "desync"],
        "model": "opus",
    },
    "dungeon-tester": {
        "name": "Dungeon Tester",
        "description": "Dungeon generation testing specialist for seed testing, room connectivity analysis, BSP debugging, procedural content validation, and spawner/treasure distribution checks.",
        "triggers": ["dungeon", "seed", "bsp", "room", "corridor", "procedural", "generation", "spawn"],
        "model": "sonnet",
    },
    "code-reviewer-game-dev": {
        "name": "Game Dev Code Reviewer",
        "description": "Expert game engine code reviewer for C# ECS systems, physics logic, or networking code. Reviews for performance, correctness, and MonoGame best practices.",
        "triggers": ["review", "refactor", "allocations", "hot path", "performance", "patterns"],
        "model": "opus",
    },
    "network-protocol-designer": {
        "name": "Network Protocol Designer",
        "description": "Network message and protocol specialist for adding new message types, sync patterns, determinism, damage authority, multiplayer state synchronization, and MessagePack serialization.",
        "triggers": ["message", "protocol", "sync", "determinism", "spawn seed", "snapshot", "interpolation", "reconciliation", "damage report", "health sync", "death batch", "authority", "messagepack", "serialization", "serialize", "deserialize"],
        "model": "opus",
    },
    "ability-designer": {
        "name": "Ability Designer",
        "description": "End-to-end ability implementation specialist covering ECS components, systems, VFX placeholders, cooldowns, and balance considerations.",
        "triggers": ["ability", "skill", "cooldown", "projectile", "aoe", "buff", "debuff", "cast", "power-up"],
        "model": "opus",
    },
    "shader-wizard": {
        "name": "Shader Wizard",
        "description": "HLSL shader specialist for MonoGame effects, mgfxc compilation, multi-texture patterns, and graphics debugging.",
        "triggers": ["shader", "hlsl", "mgfxc", "bloom", "lighting", "multi-texture", "sampler"],
        "model": "sonnet",
    },
    "ldtk-validator": {
        "name": "LDtk Validator",
        "description": "LDtk level design validator for hub/map validation, portal connections, layer consistency, and entity placement verification.",
        "triggers": ["ldtk", "hub", "portal", "tilemap", "layer", "map"],
        "model": "sonnet",
    },
    "audio-designer": {
        "name": "Audio Designer",
        "description": "Audio implementation specialist for MonoGame. Use for sound effect creation, WAV generation, audio API integration (Freesound, ElevenLabs), ECS audio timing, performance optimization, and SoundNames organization.",
        "triggers": ["audio", "sound", "wav", "sfx", "music", "freesound", "elevenlabs", "soundeffect", "playsound", "volume", "bleep", "bloop", "click", "hover"],
        "model": "sonnet",
    },
    "ui-and-ux-agent": {
        "name": "UI/UX Designer",
        "description": "UI/UX design expert for MonoGame. Use when building menus, buttons, lists, dialogs, overlays, or debugging layout, scaling, and user interaction patterns.",
        "triggers": ["ui", "ux", "menu", "button", "dialog", "overlay", "layout", "scaling", "interaction", "widget", "panel", "screen", "interface"],
        "model": "sonnet",
    },
    "level-designer": {
        "name": "Level Designer",
        "description": "Level design specialist for dungeon config, spawning, tiles, and level balancing.",
        "triggers": ["level", "dungeon config", "spawning", "waves", "tiles", "difficulty", "balance", "enemy placement", "progression"],
        "model": "sonnet",
    },
    "game-design-brainstorm": {
        "name": "Game Design Brainstorm",
        "description": "Senior game designer and player experience critic. Use for brainstorming systems/mechanics, feature scoping, evaluating game feel, reviewing player experience, and critiquing designs from a player perspective.",
        "triggers": ["design", "brainstorm", "feature", "mechanic", "system design", "scope", "tradeoff", "complexity", "game design", "fun", "feel", "game feel", "feedback", "juice", "juicy", "satisfying", "boring", "pacing", "loop", "engagement", "player experience", "critique", "evaluate"],
        "model": "opus",
    },
    "systems-designer": {
        "name": "Systems Designer",
        "description": "MonoGame systems architecture expert. Use when designing core game systems, establishing patterns, or evaluating architectural decisions. Expert in multiplayer ARPG, FPS, and competitive game frameworks.",
        "triggers": ["systems", "architecture", "pattern", "pooling", "spatial", "physics", "ai navigation", "a*", "pathfinding", "collision", "swept", "netcode", "tick rate", "fixed timestep", "hot path", "determinism", "seeding", "rng", "procedural", "wave", "spawning", "director", "loot", "drop table", "camera system", "input buffer", "animation state", "buff system", "debuff", "targeting", "lock-on", "save system", "persistence", "accessibility", "analytics", "replay", "anti-cheat", "loading", "streaming", "data-driven", "configuration", "definition", "json data", "hot reload", "state machine", "game state", "screen stack", "lifecycle", "event bus", "pub/sub", "messaging", "debug console", "cheat", "cvar"],
        "model": "opus",
    },
}


# =============================================================================
# MCP Tools
# =============================================================================

@mcp.tool()
def suggest_agent(task_description: str) -> dict:
    """
    Suggest which specialized agent to invoke for a given task.

    Use this at the start of a task to get agent recommendations based on
    keyword matching against registered agents.

    Args:
        task_description: Description of the task you're about to perform

    Returns:
        Dictionary with recommended agent(s), matched triggers, and confidence
    """
    task_lower = task_description.lower()
    task_words = set(re.findall(r'\b\w+\b', task_lower))
    matches = []

    # Precompute trigger uniqueness: triggers in fewer agents are more informative
    trigger_agent_count: dict[str, int] = {}
    for info in AGENTS.values():
        for t in info["triggers"]:
            trigger_agent_count[t] = trigger_agent_count.get(t, 0) + 1

    for agent_id, info in AGENTS.items():
        score = 0.0
        matched_triggers = []

        for trigger in info["triggers"]:
            trigger_words = trigger.split()
            matched = False
            if len(trigger_words) == 1:
                # Single-word: exact word boundary match (not substring)
                matched = trigger in task_words
            else:
                # Multi-word phrase: check as substring (word order matters)
                matched = trigger in task_lower

            if matched:
                # Base score: multi-word triggers worth more
                base = len(trigger_words)
                # Uniqueness bonus: triggers in fewer agents score higher
                uniqueness = 1.0 / trigger_agent_count.get(trigger, 1)
                score += base * (1.0 + uniqueness)
                matched_triggers.append(trigger)

        # Also check description (weak signal)
        if any(word in info["description"].lower() for word in task_words if len(word) > 3):
            score += 0.5

        if score > 0:
            matches.append({
                "agent": agent_id,
                "name": info["name"],
                "description": info["description"],
                "model": info["model"],
                "score": score,
                "matched_triggers": matched_triggers,
            })

    # Sort by score descending
    matches.sort(key=lambda x: x["score"], reverse=True)

    # Determine confidence level
    top_score = matches[0]["score"] if matches else 0
    confidence = "high" if top_score >= 4 else "medium" if top_score >= 2 else "low" if top_score >= 1 else "none"

    result = {
        "task": task_description,
        "recommendation": matches[0]["agent"] if matches else None,
        "confidence": confidence,
        "suggested_agents": matches[:3],  # Top 3
        "should_invoke": confidence in ["high", "medium"],
    }

    # Add disambiguation hint when top agents are tied
    if len(matches) >= 2 and matches[0]["score"] == matches[1]["score"]:
        tied = [m["agent"] for m in matches if m["score"] == matches[0]["score"]]
        result["disambiguation"] = f"Tied between {', '.join(tied)}. Check which files you're modifying to decide."

    return result


@mcp.tool()
def list_agents() -> dict:
    """
    List all available specialized agents with their descriptions.

    Returns:
        Dictionary of agent names, descriptions, and models
    """
    return {
        agent_id: {
            "name": info["name"],
            "description": info["description"],
            "model": info["model"],
            "triggers": info["triggers"],
        }
        for agent_id, info in AGENTS.items()
    }


@mcp.tool()
def list_subsystems() -> dict:
    """
    List all architectural subsystems with brief descriptions.

    Returns:
        Dictionary of subsystem names and descriptions
    """
    return {
        key: {
            "name": info["name"],
            "description": info["description"],
            "keywords": info["keywords"],
        }
        for key, info in SUBSYSTEMS.items()
    }


@mcp.tool()
def get_files_for_subsystem(subsystem: str) -> dict:
    """
    Get key file paths for a specific subsystem.

    Args:
        subsystem: Subsystem key (e.g., 'ecs', 'networking', 'physics')

    Returns:
        Dictionary with subsystem info and file paths
    """
    if subsystem not in SUBSYSTEMS:
        return {
            "error": f"Unknown subsystem: {subsystem}",
            "available": list(SUBSYSTEMS.keys()),
        }

    info = SUBSYSTEMS[subsystem]
    base_path = "GameProject/src/GameProject.Engine"

    return {
        "subsystem": subsystem,
        "name": info["name"],
        "description": info["description"],
        "files": [f"{base_path}/{f}" for f in info["files"]],
    }


@mcp.tool()
def find_relevant_context(task_description: str) -> dict:
    """
    Find relevant architecture sections and files for a given task.

    Args:
        task_description: Description of the task to find context for

    Returns:
        Dictionary with relevant subsystems and suggested files
    """
    task_lower = task_description.lower()

    # Score each subsystem based on keyword matches
    matches = []
    for key, info in SUBSYSTEMS.items():
        score = 0
        matched_keywords = []

        for keyword in info["keywords"]:
            if keyword in task_lower:
                score += 1
                matched_keywords.append(keyword)

        # Also check name and description
        if info["name"].lower() in task_lower:
            score += 2

        if score > 0:
            matches.append({
                "subsystem": key,
                "name": info["name"],
                "score": score,
                "matched_keywords": matched_keywords,
                "files": info["files"],
            })

    # Sort by score descending
    matches.sort(key=lambda x: x["score"], reverse=True)

    # Build file list from top matches
    base_path = "GameProject/src/GameProject.Engine"
    suggested_files = []
    for match in matches[:3]:  # Top 3 matches
        for f in match["files"]:
            full_path = f"{base_path}/{f}"
            if full_path not in suggested_files:
                suggested_files.append(full_path)

    return {
        "task": task_description,
        "relevant_subsystems": matches[:5],  # Top 5 matches
        "suggested_files": suggested_files[:10],  # Top 10 files
        "architecture_resource": "context7://architecture",
    }


@mcp.tool()
def get_context_files() -> dict:
    """
    List all available context documents in .claude/context/.

    Returns:
        Dictionary with context file names and paths
    """
    if not CONTEXT_DIR.exists():
        return {"error": "Context directory not found"}

    files = []
    for f in CONTEXT_DIR.glob("*.md"):
        # Add description based on filename
        description = ""
        resource_uri = None
        if f.stem == "architecture":
            description = "Core architecture overview (ECS, services, networking, devtools, tiled templates)"
            resource_uri = "context7://architecture"
        elif f.stem == "dungeon-generation":
            description = "Procedural dungeon generation system (BSP, graph, rooms, corridors)"
            resource_uri = "context7://architecture/dungeon-generation"
        elif f.stem == "tiledlib-api":
            description = "TiledLib.Net 4.0 API reference for loading .tmx/.tsx files"
            resource_uri = "context7://architecture/tiled-templates"
        elif f.stem == "coordinate-systems":
            description = "Isometric rendering, coordinate conversion, depth sorting, compensation"
            resource_uri = "context7://architecture/isometric-input"
        elif f.stem == "input-system":
            description = "Input system with keyboard, mouse, and gamepad support"
            resource_uri = "context7://architecture/input-system"
        elif f.stem == "aiming-system":
            description = "Aiming system with isometric coordinate transforms, camera timing, and network determinism"
            resource_uri = "context7://architecture/aiming-system"
        elif f.stem == "boss-fight-framework":
            description = "Multi-phase boss fights with attack pools, minions, enrage, vulnerability, shield mechanics, and network sync"
            resource_uri = "context7://architecture/boss-fight-framework"
        elif f.stem == "network-operations":
            description = "Network testing, debugging, and known issues"
        elif f.stem == "art-pipeline":
            description = "3D-to-2D art pipeline (Meshy, Blender, atlas packing, content loading)"
        elif f.stem == "item-system":
            description = "Equipment system: Orbs, Mods, Cores, fusion, augment tokens, PowerLevel"

        # Note: dungeon-debug has no .md file but has MCP resource context7://architecture/dungeon-debug

        files.append({
            "name": f.stem,
            "path": str(f.relative_to(PROJECT_ROOT)),
            "description": description,
            "resource_uri": resource_uri,
        })

    return {
        "context_directory": str(CONTEXT_DIR.relative_to(PROJECT_ROOT)),
        "files": sorted(files, key=lambda x: x["name"]),
    }


@mcp.tool()
def search_context_documents(query: str) -> dict:
    """
    Search all context documents for a keyword or phrase.

    Args:
        query: Search term or phrase to find in context documents

    Returns:
        Dictionary with matching sections from context documents
    """
    if not CONTEXT_DIR.exists():
        return {"error": "Context directory not found"}

    query_lower = query.lower()
    results = []

    for doc_file in CONTEXT_DIR.glob("*.md"):
        try:
            content = doc_file.read_text(encoding="utf-8")
            lines = content.split("\n")

            # Find matching lines with context
            matches = []
            for i, line in enumerate(lines):
                if query_lower in line.lower():
                    # Get surrounding context (2 lines before and after)
                    start = max(0, i - 2)
                    end = min(len(lines), i + 3)
                    context_lines = lines[start:end]
                    matches.append({
                        "line_number": i + 1,
                        "context": "\n".join(context_lines),
                    })

            if matches:
                results.append({
                    "document": doc_file.stem,
                    "path": str(doc_file.relative_to(PROJECT_ROOT)),
                    "matches": matches[:10],  # Limit to 10 matches per doc
                    "total_matches": len(matches),
                })
        except Exception as e:
            continue

    # Also search SUBSYSTEMS keywords
    subsystem_matches = []
    for key, info in SUBSYSTEMS.items():
        if query_lower in info["name"].lower() or query_lower in info["description"].lower():
            subsystem_matches.append({
                "subsystem": key,
                "name": info["name"],
                "description": info["description"],
            })
        else:
            for keyword in info["keywords"]:
                if query_lower in keyword.lower():
                    subsystem_matches.append({
                        "subsystem": key,
                        "name": info["name"],
                        "matched_keyword": keyword,
                    })
                    break

    return {
        "query": query,
        "document_matches": results,
        "subsystem_matches": subsystem_matches,
    }


# =============================================================================
# Entry Point
# =============================================================================

def main():
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
