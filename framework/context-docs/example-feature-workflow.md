<!--
FRAMEWORK NOTE — Example Context Doc: Feature Implementation Workflow
=====================================================================
SOURCE: Real context doc from the case study (684 lines).

PATTERN: Implementation Checklist / Process Template
- Defines a reusable 6-step pattern for implementing new features
- Each step includes code templates, file locations, and gotchas
- Serves as both documentation AND executable workflow for the AI agent

WHY THIS EXAMPLE:
This doc demonstrates how context docs can standardize *processes*, not
just describe *systems*. The case-study examples (save-system, damage-spec,
ghost-mode) document how things work. This doc documents how to BUILD things.
It's a checklist the AI agent follows when implementing new features, ensuring
consistency across the codebase.

PAIRED WITH: example-feature-builder.md (the agent that follows this
workflow when implementing new features).

KEY SECTIONS TO STUDY:
- Quick Reference 6-Step Pattern: high-level overview
- Per-step sections: detailed instructions with code templates
- Common Gotchas: mistakes the AI agent should avoid
- Network Considerations: multiplayer sync requirements per step

ANNOTATIONS: Look for "<!-- ANNOTATION: -->" comments throughout.
Remove these when adapting for your own project.
-->

<!-- v1 | last-verified: 2026-02-15 -->
# Ability Implementation Guide

This document outlines the standard workflow for implementing new player abilities in the case study project, based on the fireball ability implementation.

## Overview

Player abilities fall into two categories:
1. **Class-specific abilities** - Stomp, Fireball, future class abilities (stored in `ClassAbilityComponent`)
2. **Power-up abilities** - Missiles, Trail, Assistants (stored in `AbilitiesComponent`)

This guide focuses on class-specific abilities, which follow a consistent 5-step pattern.

## Quick Reference: 6-Step Pattern

```
1. Placeholder Art      → Generate visual assets
1.5. Visual Effects     → Add glow/particles (OPTIONAL)
2. Component Updates    → Add ability data to ClassAbilityComponent
3. Entity Factory       → Initialize ability for specific classes
4. Ability System       → Implement activation logic
5. Combat System        → Handle special projectile behavior (if needed)
```

## Shader & Visual Effects (Optional Enhancement)

The engine supports HLSL shaders and visual effects for projectile enhancement. **This is completely optional** but makes abilities feel significantly more impactful with minimal effort.

### Available Effect Systems

1. **GlowComponent** ⭐ Recommended for most abilities
   - Additive blending concentric ring glow
   - Configurable inner/outer colors
   - Pulse animation support
   - **Automatically rendered by RiftRenderSystem** (zero extra code)
   - Negligible performance cost (~3-5 draw calls)

2. **ParticleEmitterComponent** (For trails and bursts)
   - Emit particles along projectile path
   - Configurable lifetime, velocity, color fade
   - **Automatically rendered by ParticleSystem**
   - Good for fire trails, ice shards, lightning sparks
   - Cost scales with EmitRate × ParticleLifetime

3. **CircleMask.fx Shader** (Advanced - not recommended)
   - Circular masking with soft edges, swirl animation
   - Color tinting and inner glow
   - Requires custom rendering code
   - Currently used only for rift interiors

### When to Add Visual Effects

✅ **Recommended for:**
- High-impact abilities (fireballs, ice lances, lightning bolts)
- Ultimate/special abilities
- Boss projectiles
- Abilities that should feel powerful

❌ **Skip for:**
- Basic bullets (should feel lightweight)
- Melee hits (instant, no projectile)
- Performance-sensitive projectiles (100+ spawned per second)

### How to Apply (Optional Step 1.5)

After generating placeholder art in Step 1, add visual components to the projectile entity.

**Location:** `ECS/Archetypes/EntityFactory.cs` → `CreateProjectile()` method

**Pattern:** Add components after entity creation

**IMPORTANT SIZING RULE:** Projectile visual effects should be at minimum **20% of hero visual radius** (80 units).
- Heroes: 80 units visual radius
- Minimum ability size: 16 units (20% of 80)
- Recommended: 24-36 units (30-45% of hero size) for high-impact abilities

```csharp
// In CreateProjectile() method, BEFORE creating the entity

// Fireball has larger radius (30% of hero visual radius = 24 units)
var projectileRadius = type == ProjectileType.Fireball ? 24f : (type == ProjectileType.Missile ? 10f : 8f);

var entity = _context.World.Create(
    TagComponent.Create(EntityType.Projectile, uniqueId),
    TransformComponent.Create(position, projectileRadius),  // Use calculated radius
    // ... other components
);

// AFTER creating the entity, add visual effects
if (type == ProjectileType.Fireball)
{
    // Add glow effect
    entity.Add(new GlowComponent
    {
        BaseIntensity = 1.0f,
        CurrentIntensity = 1.0f,
        RadiusMultiplier = 1.5f,          // Glow extends 50% beyond sprite (24 × 1.5 = 36 units total)
        InnerColor = new Color(255, 128, 0),    // Bright orange
        OuterColor = new Color(255, 64, 0, 0),  // Fading red (transparent)
        RingCount = 4                     // 4 concentric rings for smoother falloff
    });

    // Optional: Add particle trail
    entity.Add(new ParticleEmitterComponent
    {
        EmitRate = 20f,                   // 20 particles/second
        ParticleLifetime = 0.5f,          // Particles last 0.5 seconds
        StartColor = Color.Orange,
        EndColor = new Color(255, 0, 0, 0), // Fade to transparent red
        StartScale = 1f,
        EndScale = 0.2f,                  // Shrink as they fade
        Velocity = Vector2.Zero           // Particles stay in place (trail effect)
    });
}
```

**Required using directive:**
```csharp
using GameProject.Engine.ECS.Components.Effects; // For GlowComponent
```

**Rendering:** Components are automatically rendered by existing systems - no additional rendering code needed!

### Effect Color Presets by Element

Quick reference for common ability elements:

```csharp
// Fire abilities (fireballs, flame burst)
InnerColor = new Color(255, 128, 0);    // Bright orange
OuterColor = new Color(255, 64, 0, 0);  // Fading red

// Ice abilities (frost lance, ice nova)
InnerColor = new Color(0, 255, 255);    // Cyan
OuterColor = new Color(138, 43, 226, 0); // Fading violet

// Lightning abilities (lightning bolt, chain lightning)
InnerColor = new Color(255, 255, 0);    // Yellow
OuterColor = new Color(0, 255, 255, 0); // Fading cyan

// Dark/Shadow abilities (shadow bolt, curse)
InnerColor = new Color(148, 0, 211);    // Dark violet
OuterColor = new Color(48, 0, 96, 0);   // Fading dark purple

// Holy/Light abilities (holy bolt, smite)
InnerColor = new Color(255, 255, 255);  // White
OuterColor = new Color(255, 215, 0, 0); // Fading gold

// Poison/Toxic abilities (poison dart, acid splash)
InnerColor = new Color(0, 255, 0);      // Bright green
OuterColor = new Color(124, 252, 0, 0); // Fading lime
```

### Performance Considerations

- **GlowComponent**: ~3-5 draw calls per projectile (RingCount × directions)
- **ParticleEmitterComponent**: Particles = EmitRate × ParticleLifetime (e.g., 20/s × 0.5s = 10 particles)
- Safe for 10-20 simultaneous glowing projectiles
- For bullet hell scenarios (100+ projectiles), skip effects

### Testing Visual Effects

Add to testing checklist:
- [ ] Glow effect visible with appropriate color
- [ ] Glow follows projectile smoothly
- [ ] Particles emit correctly along path (if used)
- [ ] No frame drops with multiple projectiles
- [ ] Effects visible on both light and dark backgrounds
- [ ] Glow disappears when projectile is destroyed

## Step-by-Step Implementation

### Step 1: Generate Placeholder Art

**When to do this:** First step - visual assets needed for testing

**Command:**
```bash
python -m tools.asset_pipeline.placeholder_generator \
    --create "projectiles/ice_lance" \
    --type projectile \
    --color "#00BFFF" \
    --description "Ice mage lance projectile"
```

**Asset type selection:**
- `projectile` - Directional (8 dirs × 4 frames), 64×64, for bullets/fireballs/arrows
- `ability` - Non-directional (8 frames), 128×128, for AoE effects
- `effect` - Non-directional (8 frames), 128×128, for explosions/particles

**Output:**
- Individual frame PNGs: `Content/Sprites/projectiles/ice_lance/ice_lance_S_0.png` through `ice_lance_SE_3.png`
- Atlas texture: `ice_lance_atlas.png`
- Atlas metadata: `ice_lance_atlas.json`
- Manifest entry in `Content/Data/asset_manifest.json`

**In code reference:**
```csharp
textureName: "projectiles/ice_lance/ice_lance_atlas"
```

### Step 2: Component Updates

**File:** `ECS/Components/Player/ClassAbilityComponent.cs`

**Pattern:** Add fields for the new ability following existing naming conventions

```csharp
public struct ClassAbilityComponent
{
    // Existing abilities...

    // IceLance (IceMage)
    public float IceLanceCooldown;
    public float IceLanceLastUsed;
    public float IceLanceSpeed;
    public float IceLanceDamageMultiplier;
    public float IceLancePierceCount;  // Ability-specific property

    /// <summary>
    /// Gets whether ice lance is ready to use.
    /// </summary>
    public readonly bool CanIceLance(float currentTime)
        => currentTime - IceLanceLastUsed >= IceLanceCooldown;

    /// <summary>
    /// Creates a ClassAbilityComponent for IceMage.
    /// </summary>
    public static ClassAbilityComponent ForIceMage(float cooldownMultiplier = 1f)
        => new()
        {
            // IceMage has ice lance, no stomp
            StompCooldown = 0f,
            StompLastUsed = 0f,
            // ... set other unused abilities to 0

            // Ice lance settings
            IceLanceCooldown = 8f * cooldownMultiplier,
            IceLanceLastUsed = -8f, // Ready immediately
            IceLanceSpeed = 15f,
            IceLanceDamageMultiplier = 1.5f,
            IceLancePierceCount = 3f // Pierces 3 enemies
        };
}
```

**If the ability uses a new projectile type:**

File: `ECS/Components/Combat/ProjectileComponent.cs`

```csharp
// Add to enum
public enum ProjectileType
{
    Bullet,
    Missile,
    Melee,
    Fireball,
    IceLance  // New
}

// Add factory method
public static ProjectileComponent IceLance(float damage, int ownerId, Color color)
    => new()
    {
        Type = ProjectileType.IceLance,
        Damage = damage,
        OwnerId = ownerId,
        BouncesLeft = 3, // Pierces 3 enemies
        Color = color,
        TargetId = -1,
        HomingStrength = 0f,
        ExplosionRadius = 0f,
        Knockback = 20f
    };
```

### Step 3: Entity Factory Updates

**File:** `ECS/Archetypes/EntityFactory.cs`

**Method:** `CreatePlayer`

**Pattern:** Update class ability initialization to handle new class

```csharp
// Create class-specific ability component
var classAbility = heroClass switch
{
    HeroClass.Sharpshooter => ClassAbilityComponent.ForSharpshooter(stats.CooldownMultiplier),
    HeroClass.IceMage => ClassAbilityComponent.ForIceMage(stats.CooldownMultiplier),
    _ => ClassAbilityComponent.ForOtherClass(stats.CooldownMultiplier)
};

var entity = _context.World.Create(
    // ... other components
    classAbility,
    // ... rest
);
```

### Step 4: Ability System Logic

**File:** `ECS/Systems/AbilitySystem.cs`

**Four sub-steps:**

#### 4a. Update Query (if needed)
```csharp
public override void Initialize(GameContext context)
{
    _playerQuery = new QueryDescription()
        .WithAll<TransformComponent, PlayerComponent, AbilitiesComponent,
                 ClassAbilityComponent, CombatComponent, HeroStatsComponent>();
    // ClassAbilityComponent already included from fireball implementation
}
```

#### 4b. Add Activation Logic
```csharp
// In Update method, inside the query callback:
if (input.Action) // Or input.Special, input.Ultimate, etc.
{
    if (player.HeroClass == HeroClass.Sharpshooter && classAbility.CanFireball(context.TotalTime))
    {
        var newClassAbility = PerformFireball(context, entity, ref transform, classAbility,
                                              ref combat, ref stats, ref input, player.PlayerColor);
        entity.Set(newClassAbility);
    }
    else if (player.HeroClass == HeroClass.IceMage && classAbility.CanIceLance(context.TotalTime))
    {
        var newClassAbility = PerformIceLance(context, entity, ref transform, classAbility,
                                              ref combat, ref stats, ref input, player.PlayerColor);
        entity.Set(newClassAbility);
    }
    else if (classAbility.CanStomp(context.TotalTime))
    {
        // Default ability for other classes
        var newClassAbility = PerformStomp(context, ref transform, classAbility,
                                          ref combat, ref stats, player.PlayerColor, enemies);
        entity.Set(newClassAbility);
    }
}
```

#### 4c. Add Perform Method

**Pattern:** Follow this signature and structure

```csharp
private ClassAbilityComponent PerformIceLance(
    GameContext context,
    Entity entity,
    ref TransformComponent transform,
    ClassAbilityComponent classAbility,
    ref CombatComponent combat,
    ref HeroStatsComponent stats,
    ref PlayerInput input,
    Color playerColor)
{
    // 1. Update cooldown timestamp
    classAbility.IceLanceLastUsed = context.TotalTime;

    // 2. Get aim direction from input
    var aimDir = new Vector2(input.AimX, input.AimY);
    if (aimDir.LengthSquared() < 0.01f)
        aimDir = new Vector2(0, 1); // Default south
    else
        aimDir = Vector2.Normalize(aimDir);

    // 3. Calculate damage (scale with appropriate stat)
    var damage = combat.Damage * classAbility.IceLanceDamageMultiplier * stats.Special;

    // 4. Create projectile
    var projectile = context.EntityFactory.CreateProjectile(
        ProjectileType.IceLance,
        transform.Position + aimDir * (transform.Radius + 10f),
        aimDir,
        classAbility.IceLanceSpeed,
        damage,
        entity.Id,
        playerColor,
        duration: 2f,
        textureName: "projectiles/ice_lance/ice_lance_atlas"
    );

    // 5. Apply ability-specific properties
    ref var proj = ref projectile.Get<ProjectileComponent>();
    proj = ProjectileComponent.IceLance(damage, entity.Id, playerColor);

    // 6. Return updated component
    return classAbility;
}
```

#### 4d. Add Using Directive (if needed)
```csharp
using GameProject.Engine.Input; // For PlayerInput type
```

### Step 5: Combat System (Optional)

**File:** `ECS/Systems/CombatSystem.cs`

**When needed:** Only if projectile has special collision/damage behavior

**Examples:**
- Explosions (Fireball, Missile)
- Piercing (IceLance)
- Chain effects
- Status effects

**Pattern for explosions:**
```csharp
// In projectile-enemy collision handling:
if ((proj.type == ProjectileType.Missile || proj.type == ProjectileType.Fireball)
    && proj.explosionRadius > 0)
{
    ProcessMissileExplosionSpatial(context, proj.pos, proj.damage,
                                   proj.explosionRadius, spatialService, gameState);
    projTag.MarkedForDeletion = true;
    break; // Explodes once
}
```

**Pattern for piercing:**
```csharp
// After applying damage:
if (proj.type == ProjectileType.IceLance)
{
    // Reduce pierce count
    projComp.BouncesLeft--;

    // Delete if no pierces left
    if (projComp.BouncesLeft <= 0)
    {
        projTag.MarkedForDeletion = true;
    }
    // Don't break - continue checking other enemies this frame
}
else
{
    // Regular projectile - delete on first hit
    projTag.MarkedForDeletion = true;
    break;
}
```

## Common Patterns

### Aim Direction
```csharp
// From input (player controlled)
var aimDir = new Vector2(input.AimX, input.AimY);
if (aimDir.LengthSquared() < 0.01f)
    aimDir = new Vector2(0, 1); // Default direction
else
    aimDir = Vector2.Normalize(aimDir);

// Towards nearest enemy (auto-aim)
var target = FindNearestEnemy(transform.Position, enemies, maxRange);
if (target.HasValue)
{
    var aimDir = target.Value.pos - transform.Position;
    aimDir = Vector2.Normalize(aimDir);
}
```

### Damage Scaling
```csharp
// Standard damage scaling by stat
var damage = combat.Damage * abilityMultiplier * stats.Special;  // Magic abilities
var damage = combat.Damage * abilityMultiplier * stats.Strength; // Physical abilities
var damage = combat.Damage * abilityMultiplier * stats.Agility;  // Finesse abilities
```

### Cooldown Management
```csharp
// Check if ready
if (classAbility.CanAbilityName(context.TotalTime))
{
    // Perform ability
    classAbility.AbilityNameLastUsed = context.TotalTime;
    // ... rest of logic
}
```

### Projectile Spawning
```csharp
// Spawn offset from player (avoids self-collision)
var spawnPos = transform.Position + direction * (transform.Radius + 10f);

// Duration based on intended range
var duration = maxRange / speed; // e.g., 1200 units / 10 speed = 120 seconds
```

## Testing Checklist

After implementation, verify:

- [ ] Ability activates with correct input
- [ ] Cooldown works correctly
- [ ] Damage scales with appropriate stat
- [ ] Projectile visual appears (placeholder or final art)
- [ ] Projectile moves in correct direction
- [ ] Special behavior works (explosion, piercing, etc.)
- [ ] Other classes still have their abilities
- [ ] Ability doesn't damage player who used it
- [ ] Visual effects appear (if applicable)
- [ ] Damage numbers show correctly
- [ ] Network sync works (if multiplayer)

## Build Verification

```bash
cd GameProject
dotnet build
```

Should complete with 0 errors. Warnings from other files are acceptable.

## Common Mistakes to Avoid

### ❌ Wrong: Using readonly struct with object initializers
```csharp
public readonly struct ClassAbilityComponent  // Wrong!
{
    public readonly float Cooldown;  // Wrong!
}
```

### ✅ Correct: Regular struct with mutable fields
```csharp
public struct ClassAbilityComponent
{
    public float Cooldown;  // Mutable field
}
```

### ❌ Wrong: Forgetting to return updated component
```csharp
private void PerformAbility(...)  // Returns void - won't update!
{
    classAbility.LastUsed = time;
    // Missing: return classAbility;
}
```

### ✅ Correct: Return and set component
```csharp
private ClassAbilityComponent PerformAbility(...)
{
    classAbility.LastUsed = time;
    return classAbility;
}

// In caller:
var newClassAbility = PerformAbility(...);
entity.Set(newClassAbility);
```

### ❌ Wrong: Missing using directive
```csharp
// Error: PlayerInput type not found
private ClassAbilityComponent PerformAbility(..., ref PlayerInput input, ...)
```

### ✅ Correct: Add using directive
```csharp
using GameProject.Engine.Input;
```

### ❌ Wrong: Using transform.Entity.Id
```csharp
// Error: TransformComponent doesn't have Entity property
var projectile = CreateProjectile(..., transform.Entity.Id, ...);
```

### ✅ Correct: Use entity parameter from query
```csharp
private ClassAbilityComponent PerformAbility(
    GameContext context,
    Entity entity,  // Entity from query callback
    ...)
{
    var projectile = CreateProjectile(..., entity.Id, ...);
}
```

## File Modification Summary

For a typical new class ability, expect to modify:

| File | Changes | Typical Line Count |
|------|---------|-------------------|
| `ClassAbilityComponent.cs` | Add fields + helper + factory | +20-30 lines |
| `ProjectileComponent.cs` | Add enum value + factory (if new type) | +15-20 lines |
| `EntityFactory.cs` | Update class switch | +2-3 lines |
| `AbilitySystem.cs` | Add activation + perform method | +40-60 lines |
| `CombatSystem.cs` | Special behavior (if needed) | +10-30 lines |
| **Total** | | **~87-143 lines** |

Plus auto-generated placeholder art (32 frames + atlas + JSON).

## Advanced: Multiple Abilities per Class

If a class has multiple abilities (e.g., Q, E, R keys):

```csharp
// In ClassAbilityComponent
public struct ClassAbilityComponent
{
    // IceMage abilities
    public float IceLance_Cooldown;
    public float IceLance_LastUsed;
    public float FrostNova_Cooldown;
    public float FrostNova_LastUsed;
    public float Blizzard_Cooldown;
    public float Blizzard_LastUsed;
}

// In AbilitySystem.Update
if (input.Action && classAbility.CanIceLance(context.TotalTime))
{
    // Primary ability (SPACE)
}
else if (input.Special && classAbility.CanFrostNova(context.TotalTime))
{
    // Secondary ability (Q key)
}
else if (input.Ultimate && classAbility.CanBlizzard(context.TotalTime))
{
    // Ultimate ability (R key)
}
```

Note: `input.Special` and `input.Ultimate` would need to be added to `PlayerInput` struct first.

## Related Files

- **Main implementation guide:** This file
- **Placeholder art workflow:** `.claude/agents/asset-placeholder/AGENT.md`
- **ECS patterns:** `.claude/context/architecture.md`
- **Sprite workflow:** `.claude/agents/sprite-2d-artist/AGENT.md`

## Example Implementations

- **Fireball (Sharpshooter):** Straight projectile with explosion AOE damage
  - Component: `ClassAbilityComponent.ForSharpshooter()`
  - System: `AbilitySystem.PerformFireball()`
  - Special behavior: Explosion on impact (CombatSystem)

- **Stomp (Brute, Soldier):** Melee AOE instant damage
  - Component: `ClassAbilityComponent.ForOtherClass()`
  - System: `AbilitySystem.PerformStomp()`
  - Special behavior: Immediate radius damage (no projectile)

## Future Ability Ideas

Based on the established pattern, these would be straightforward to implement:

- **IceLance** - Piercing projectile (3 enemies)
- **LightningChain** - Projectile that chains between enemies
- **ShadowStep** - Teleport + damage at destination
- **HealingNova** - AOE heal for allies
- **TimeStop** - Slow enemies in radius
- **SummonTurret** - Spawns allied entity

Each follows the same 5-step pattern outlined above.

## References

### Source Files
- `ECS/Systems/CombatSystem.cs` — Ability activation and damage application
- `ECS/Systems/ProjectileSystem.cs` — Projectile firing and collision
- `ECS/Components/Player/AbilitiesComponent.cs` — Power-up ability state
- `ECS/Components/Player/ComputedStatsComponent.cs` — Stat scaling for abilities
- `ECS/Archetypes/EntityFactory.cs` — Projectile and effect entity creation
- `ECS/Data/AbilityContext.cs` — Multi-component calculation helper

### Related Context Docs
- [turbo-system.md](turbo-system.md) — Hold-to-charge turbo abilities (dodge + turbo shot/stomp/ball)
- [network-determinism-architecture.md](network-determinism-architecture.md) — CombatRng determinism for proc effects
- [vfx-particle-system.md](vfx-particle-system.md) — VFX rendering for ability effects
