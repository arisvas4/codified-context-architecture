<!-- v1 | last-verified: 2026-02-15 -->
# Enemy Combat System

Comprehensive guide to the enemy attack system with multi-phase attacks, telegraphs, and network-safe deterministic timing.

## Overview

The enemy combat system supports 7 attack types with visual telegraph warnings. All attacks follow a state machine pattern (Idle → Windup → Execute → Recovery) and are network-synchronized using deterministic timing.

**Key Features:**
- Multi-phase attack state machine with telegraphs
- Zero-bandwidth network model (client-predicted, damage-only sync)
- 7 attack types: Melee, WindupMelee, Projectile, Cone, GroundAOE, Beam, Burst
- Data-driven JSON configuration
- Visual telegraph warnings with pulsing effects

## Architecture

### Component Split Pattern

The system uses a config/state split for performance and network safety:

| Component | Type | Purpose |
|-----------|------|---------|
| `EnemyAttackConfigComponent` | Immutable | Attack configuration from JSON (range, damage, timing) |
| `EnemyAttackStateComponent` | Mutable | Runtime attack state (phase, timing, locked targets) |
| `EnemyTelegraphComponent` | Mutable | Visual telegraph warnings (optional, added during Windup) |

**Why split?** Immutable config can be safely shared, mutable state tracks runtime progress.

### State Machine

```
[Idle] → cooldown complete + in range → [Windup]
[Windup] → WindupDuration elapsed → [Execute]
[Execute] → apply damage/spawn projectile → [Recovery]
[Recovery] → RecoveryDuration elapsed → [Idle]
```

**Timing:** All transitions use `context.GetSyncedTime()` for network determinism.

**Interruption:**
- **Death**: Immediately remove telegraph and stop attack
- **Freeze**: Pause timers (not implemented yet)
- **Knockback**: Cancel to Idle phase if force > threshold

### Network Synchronization

**Zero-Bandwidth Model:**
- Attack phases are client-predicted from synced time
- Telegraphs render locally on all clients
- Only damage results sync via `DamageReportMessage` → `HealthSyncBatch`

**Deterministic Requirements:**
- Use `context.GetSyncedTime()` (NOT `context.TotalTime`)
- Lock direction/position at Windup start
- All timing calculations based on config values (no randomness in timing)

## Attack Types

### 1. Melee (Instant)

Simple melee attack with no windup. Backward compatible with original system.

**Config:**
```csharp
EnemyAttackConfigComponent.CreateMelee(
    range: 30f,
    damage: 10f,
    attackInterval: 1.0f
)
```

**Behavior:**
- No telegraph
- Instant damage when in range
- Cooldown-based

### 2. WindupMelee

Melee attack with telegraph warning. Players can dodge during windup.

**Config:**
```csharp
EnemyAttackConfigComponent.CreateWindupMelee(
    range: 35f,
    damage: 15f,
    attackInterval: 2.0f,
    windupDuration: 0.5f,
    recoveryDuration: 0.4f,
    attackSpeedMultiplier: 1.0f,
    damageType: DamageType.Physical
)
```

**Telegraph:** Circle at enemy position, radius = attack range

**JSON Example:**
```json
{
  "ai": {
    "attackType": "windup_melee",
    "attackRange": 35,
    "attackCooldown": 2.0,
    "attackWindupDuration": 0.5,
    "attackRecoveryDuration": 0.4,
    "attackDamageType": "physical"
  }
}
```

### 3. Projectile

Spawns a single projectile toward locked target direction.

**Config:**
```csharp
EnemyAttackConfigComponent.CreateProjectile(
    range: 350f,
    damage: 10f,
    projectileSpeed: 7.0f,
    attackInterval: 2.0f,
    windupDuration: 0.4f,
    recoveryDuration: 0.3f,
    attackSpeedMultiplier: 1.0f,
    damageType: DamageType.Physical
)
```

**Telegraph:** Line from enemy toward target, length = attack range

**Direction Locking:** Direction is locked at Windup start for fairness (allows dodging)

**JSON Example:**
```json
{
  "ai": {
    "attackType": "projectile",
    "attackRange": 350,
    "attackCooldown": 2.0,
    "attackWindupDuration": 0.4,
    "attackRecoveryDuration": 0.3,
    "attackDamageType": "physical",
    "projectileSpeed": 7.0
  }
}
```

**Test Enemy:** GoblinArcher (kite behavior + projectile)

### 4. Cone

Damage all players in cone shape. Good for breath weapons.

**Config:**
```csharp
EnemyAttackConfigComponent.CreateCone(
    range: 100f,
    damage: 15f,
    coneAngleDegrees: 60f,
    attackInterval: 3.0f,
    windupDuration: 0.6f,
    recoveryDuration: 0.4f,
    attackSpeedMultiplier: 1.0f,
    damageType: DamageType.Magic
)
```

**Telegraph:** Cone shape from enemy in locked direction

**Hit Detection:** Angle-based check (see `IsInCone()` helper)

**JSON Example:**
```json
{
  "ai": {
    "attackType": "cone",
    "attackRange": 100,
    "attackCooldown": 3.0,
    "attackWindupDuration": 0.8,
    "attackRecoveryDuration": 1.0,
    "attackDamageType": "magic",
    "coneAngleDegrees": 60
  }
}
```

**Test Enemy:** DragonWhelp (chase + cone breath)

### 5. GroundAOE

Damage at target's locked position after delay. Players can move out of the circle.

**Config:**
```csharp
EnemyAttackConfigComponent.CreateGroundAOE(
    range: 300f,
    damage: 15f,
    aoeRadius: 80f,
    attackInterval: 3.5f,
    windupDuration: 1.2f,
    recoveryDuration: 1.0f,
    attackSpeedMultiplier: 1.0f,
    damageType: DamageType.Magic
)
```

**Telegraph:** GroundCircle at locked target position (not enemy position)

**Hit Detection:** Distance check from locked position

**JSON Example:**
```json
{
  "ai": {
    "attackType": "ground_aoe",
    "attackRange": 300,
    "attackCooldown": 3.5,
    "attackWindupDuration": 1.2,
    "attackRecoveryDuration": 1.0,
    "attackDamageType": "magic",
    "aoeRadius": 80
  }
}
```

**Test Enemy:** FireMage (circlestrafe + ground AOE)

### 6. Beam

Continuous damage in line over Execute duration. Ticks at `BeamTickInterval`.

**Config:**
```csharp
EnemyAttackConfigComponent.CreateBeam(
    range: 400f,
    damagePerTick: 8f,
    beamWidth: 30f,
    attackInterval: 5.0f,
    windupDuration: 0.8f,
    executeDuration: 1.5f,
    recoveryDuration: 0.5f,
    beamTickInterval: 0.2f,
    attackSpeedMultiplier: 1.0f,
    damageType: DamageType.Magic
)
```

**Telegraph:** Line from enemy in locked direction, stays visible during Execute

**Hit Detection:** Capsule collision (see `IsInBeam()` helper)

**Tick-Based Damage:** Uses `LastBeamTickTime` to ensure damage at intervals, not every frame

**JSON Example:**
```json
{
  "ai": {
    "attackType": "beam",
    "attackRange": 400,
    "attackCooldown": 5.0,
    "attackWindupDuration": 0.8,
    "executeDuration": 1.5,
    "attackRecoveryDuration": 0.5,
    "attackDamageType": "magic",
    "beamWidth": 30,
    "beamTickInterval": 0.2
  }
}
```

**Test Enemy:** EyeBeam (circlestrafe + beam)

### 7. Burst

Multiple projectiles in spread pattern simultaneously.

**Config:**
```csharp
EnemyAttackConfigComponent.CreateBurst(
    range: 250f,
    damagePerProjectile: 6f,
    projectileSpeed: 6.0f,
    projectileCount: 3,
    spreadAngleDegrees: 30f,
    attackInterval: 2.5f,
    windupDuration: 0.5f,
    recoveryDuration: 0.4f,
    attackSpeedMultiplier: 1.0f,
    damageType: DamageType.Physical
)
```

**Telegraph:** Cone showing spread pattern

**Projectile Pattern:** All spawn simultaneously at Execute start

**JSON Example:**
```json
{
  "ai": {
    "attackType": "burst",
    "attackRange": 250,
    "attackCooldown": 2.5,
    "attackWindupDuration": 0.5,
    "attackRecoveryDuration": 0.4,
    "attackDamageType": "physical",
    "projectileSpeed": 6.0,
    "projectileCount": 3,
    "projectileSpreadAngle": 30
  }
}
```

**Test Enemy:** ImpSwarm (chase + burst projectiles)

## Telegraph System

Visual warnings rendered by `TelegraphRenderSystem` (priority 490, before sprites).

### Telegraph Shapes

| Shape | Use For | Position |
|-------|---------|----------|
| Circle | Melee range, WindupMelee | Enemy position |
| Line | Projectile path, Beam | Enemy position, locked direction |
| Cone | Cone attacks, Burst pattern | Enemy position, locked direction |
| GroundCircle | Ground AOE | Locked target position |

### Visual Effects

**Pulsing Alpha:**
```csharp
var pulseRate = 2f + progress * 8f;  // Faster as attack approaches
var pulseAmount = 0.3f + progress * 0.4f;  // More intense at end
var pulse = (MathF.Sin(totalTime * pulseRate * MathF.PI * 2f) + 1f) * 0.5f;
var alpha = telegraph.Color.A / 255f * (0.5f + pulse * pulseAmount);
```

**Fill Growth:**
```csharp
var fillProgress = progress * 0.8f;  // 0% to 80% filled over windup
```

**Colors:** Red for physical, purple for magic (configurable per attack)

### Telegraph Lifecycle

1. **Windup Start**: `EnemyAttackSystem` adds `EnemyTelegraphComponent`
2. **Windup Phase**: `TelegraphRenderSystem` renders with pulsing effect
3. **Execute Start**: Telegraph removed (except Beam, which stays visible)
4. **Death**: Immediately remove telegraph to prevent visual bugs

## Enemy Projectiles

Enemy projectiles use the same `ProjectileComponent` as player projectiles but with `IsEnemyProjectile = true`.

**Key Differences:**

| Aspect | Player Projectile | Enemy Projectile |
|--------|-------------------|------------------|
| `IsEnemyProjectile` flag | false | true |
| Collision Layer | PlayerProjectile | EnemyProjectile |
| Damages | Enemies | Players |
| Critical hits | Yes | No (simpler) |
| Core procs | Yes | No |
| Penetration | Yes | No |

**Factory Method:**
```csharp
ProjectileComponent.EnemyProjectile(
    damage: 10f,
    ownerEntityId: enemyTag.UniqueId,
    damageType: DamageType.Physical,
    color: Color.Red
)
```

**Collision Handling:**
```csharp
// In CombatSystem
private void ProcessEnemyProjectilePlayerCollisionsSpatial(...)
{
    // Check IsEnemyProjectile flag
    // Apply damage to players
    // Handle shield blocking
    // Handle Earth Thorns reflection (50% damage back)
}
```

## Adding a New Attack Type

### Step 1: Add to EnemyAttackType Enum

```csharp
// In EnemyAttackComponent.cs
public enum EnemyAttackType : byte
{
    None = 0,
    Melee = 1,
    WindupMelee = 2,
    Projectile = 3,
    Cone = 4,
    GroundAOE = 5,
    Beam = 6,
    Burst = 7,
    YourNewType = 8  // Add here
}
```

### Step 2: Extend EnemyAttackConfigComponent

Add any new config fields needed:

```csharp
// In EnemyAttackConfigComponent.cs
public readonly struct EnemyAttackConfigComponent
{
    // ... existing fields ...

    // Your new attack config
    public readonly float YourNewField;
}
```

Add factory method:

```csharp
public static EnemyAttackConfigComponent CreateYourNewType(
    float range,
    float damage,
    float yourNewField,
    float attackInterval = 2.0f,
    float windupDuration = 0.5f,
    float recoveryDuration = 0.4f,
    float attackSpeedMultiplier = 1.0f,
    DamageType damageType = DamageType.Physical)
    => new()
    {
        AttackType = EnemyAttackType.YourNewType,
        AttackRange = range,
        AttackDamage = damage,
        BaseAttackInterval = attackInterval,
        WindupDuration = windupDuration / attackSpeedMultiplier,
        ExecuteDuration = 0.1f,
        RecoveryDuration = recoveryDuration / attackSpeedMultiplier,
        DamageType = damageType,
        YourNewField = yourNewField,
        // Set defaults for unused fields
        ProjectileSpeed = 0f,
        ProjectileCount = 0,
        ProjectileSpreadAngle = 0f,
        ConeAngleDegrees = 0f,
        AOERadius = 0f,
        BeamWidth = 0f,
        BeamTickInterval = 0f
    };
```

### Step 3: Add Handler to EnemyAttackSystem

```csharp
// In EnemyAttackSystem.cs Update() method
switch (attackConfig.AttackType)
{
    // ... existing cases ...
    case EnemyAttackType.YourNewType:
        UpdateYourNewType(context, enemy, ref transform, ref enemyComp,
            in attackConfig, ref attackState, players);
        break;
}
```

Implement handler method:

```csharp
private void UpdateYourNewType(
    GameContext context,
    Entity enemy,
    ref TransformComponent transform,
    ref EnemyComponent enemyComp,
    in EnemyAttackConfigComponent attackConfig,
    ref EnemyAttackStateComponent attackState,
    List<(Entity entity, Vector2 pos, float radius, int playerId)> players)
{
    var currentTime = context.GetSyncedTime();

    switch (attackState.CurrentPhase)
    {
        case AttackPhase.Idle:
            // Check if can attack
            if (!attackState.CanAttack(currentTime, GetEffectiveAttackInterval(attackConfig)))
                return;

            // Find target
            var target = FindNearestPlayer(transform.Position, attackConfig.AttackRange, players);
            if (target == null)
                return;

            // Lock direction and start windup
            var direction = Vector2.Normalize(target.Value.pos - transform.Position);
            attackState.BeginAttack(currentTime, target.Value.pos, target.Value.playerId, direction);

            // Create telegraph
            if (enemy.Has<EnemyTelegraphComponent>())
                enemy.Remove<EnemyTelegraphComponent>();

            enemy.Add(new EnemyTelegraphComponent
            {
                Shape = TelegraphShape.Circle,  // Or your shape
                Position = transform.Position,
                Direction = direction,
                Radius = attackConfig.AttackRange,
                Color = Color.Red,
                StartTime = currentTime,
                Duration = attackConfig.WindupDuration,
                OwnerEntityId = enemy.Get<TagComponent>().UniqueId,
                IsActive = true
            });
            break;

        case AttackPhase.Windup:
            // Wait for windup to complete
            if (!attackState.IsPhaseComplete(currentTime, attackConfig.WindupDuration))
                return;

            // Transition to Execute
            attackState.TransitionTo(AttackPhase.Execute, currentTime);
            break;

        case AttackPhase.Execute:
            // Apply your attack effect (only once!)
            if (!attackState.HasExecuted)
            {
                attackState.HasExecuted = true;

                // Your damage/projectile/effect code here
                // ...

                // Remove telegraph
                if (enemy.Has<EnemyTelegraphComponent>())
                    enemy.Remove<EnemyTelegraphComponent>();
            }

            // Wait for execute duration
            if (!attackState.IsPhaseComplete(currentTime, attackConfig.ExecuteDuration))
                return;

            // Transition to Recovery
            attackState.TransitionTo(AttackPhase.Recovery, currentTime);
            break;

        case AttackPhase.Recovery:
            // Wait for recovery to complete
            if (!attackState.IsPhaseComplete(currentTime, attackConfig.RecoveryDuration))
                return;

            // Complete attack
            attackState.CompleteAttack(currentTime);
            break;
    }
}
```

### Step 4: Extend JSON Schema

Add fields to `AIDefinition` class:

```csharp
// In EnemyDefinition.cs
public class AIDefinition
{
    // ... existing fields ...

    /// <summary>Your new field description.</summary>
    public float YourNewField { get; set; } = 100f;
}
```

### Step 5: Update EntityFactory

Add case to attack config creation:

```csharp
// In EntityFactory.cs CreateEnemy()
var attackConfig = attackType switch
{
    // ... existing cases ...
    "your_new_type" => EnemyAttackConfigComponent.CreateYourNewType(
        range: aiConfig.AttackRange,
        damage: stats.Damage * 0.5f,
        yourNewField: enemyDef?.AI?.YourNewField ?? 100f,
        attackInterval: attackInterval,
        windupDuration: enemyDef?.AI?.AttackWindupDuration ?? 0.5f,
        recoveryDuration: enemyDef?.AI?.AttackRecoveryDuration ?? 0.4f,
        attackSpeedMultiplier: attackSpeedMultiplier,
        damageType: damageType
    ),
    // ...
};
```

### Step 6: Add Test Enemy

```json
{
  "YourTestEnemy": {
    "displayName": "Test Enemy",
    "sprite": "",
    "fallbackEmoji": "💀",
    "hp": 15,
    "speed": 2.0,
    "damage": 12,
    "radius": 20,
    "visualRadius": 30,
    "weight": 1.0,
    "armor": 0,
    "resist": 0,
    "xp": 50,
    "ai": {
      "behavior": "chase",
      "aggroRange": 400,
      "attackRange": 200,
      "attackCooldown": 2.5,
      "attackType": "your_new_type",
      "attackWindupDuration": 0.6,
      "attackRecoveryDuration": 0.5,
      "attackDamageType": "physical",
      "yourNewField": 150
    }
  }
}
```

### Step 7: Test

```bash
# In-game console (press ` or F12)
spawn YourTestEnemy
```

## Best Practices

### Timing

✅ **DO:**
- Use `context.GetSyncedTime()` for all timing calculations
- Lock direction/position at Windup start
- Use `HasExecuted` flag to prevent duplicate execution

❌ **DON'T:**
- Use `context.TotalTime` (not synced across clients)
- Check phase duration repeatedly (framerate-dependent)
- Spawn projectiles every frame in Execute phase

### Network Safety

✅ **DO:**
- Make all state transitions deterministic from synced time
- Use config values for all timing (no randomness)
- Let `DamageAuthoritySystem` handle damage validation

❌ **DON'T:**
- Add new network messages for attacks (zero-bandwidth model)
- Use spatial queries during Execute (may differ on clients)
- Apply damage directly (use `DamageService.ApplyDamage()`)

### Performance

✅ **DO:**
- Reuse `SystemGatherBuffers` for player list
- Remove telegraphs when no longer needed
- Use helper methods to avoid code duplication

❌ **DON'T:**
- Allocate new `List<>()` in hot paths
- Query all enemies every frame
- Create temporary vectors in loops

## Testing

### Console Commands

```bash
# Test individual attack types
spawn GoblinArcher        # Projectile
spawn FireMage            # Ground AOE
spawn DragonWhelp         # Cone
spawn EyeBeam             # Beam
spawn ImpSwarm            # Burst

# Test in groups
spawn GoblinArcher 5
spawn FireMage 3

# Enter immortal training arena
test-arena

# Kill all non-boss enemies
kill
```

### Network Testing

```bash
# Terminal 1 (Host)
dotnet run -- --host --auto-ready --auto-start

# Terminal 2 (Client with latency)
dotnet run -- --join 127.0.0.1:5555 --latency 100 --auto-ready
```

**Verify:**
- Telegraphs appear simultaneously on both clients (±100ms)
- Projectiles spawn at same time
- Damage syncs via HealthSyncBatch
- No rubber-banding from position corrections

## Files Reference

| File | Purpose |
|------|---------|
| [EnemyAttackComponent.cs](../../GameProject/src/GameProject.Engine/ECS/Components/Enemy/EnemyAttackComponent.cs) | `EnemyAttackType` enum |
| [EnemyAttackConfigComponent.cs](../../GameProject/src/GameProject.Engine/ECS/Components/Enemy/EnemyAttackConfigComponent.cs) | Immutable attack config, factory methods |
| [EnemyAttackStateComponent.cs](../../GameProject/src/GameProject.Engine/ECS/Components/Enemy/EnemyAttackStateComponent.cs) | Mutable attack state, phase tracking |
| [EnemyTelegraphComponent.cs](../../GameProject/src/GameProject.Engine/ECS/Components/Enemy/EnemyTelegraphComponent.cs) | Telegraph visual data |
| [EnemyAttackSystem.cs](../../GameProject/src/GameProject.Engine/ECS/Systems/EnemyAttackSystem.cs) | Attack state machine, handlers, helpers |
| [TelegraphRenderSystem.cs](../../GameProject/src/GameProject.Engine/ECS/Systems/TelegraphRenderSystem.cs) | Telegraph rendering with pulsing effects |
| [ProjectileComponent.cs](../../GameProject/src/GameProject.Engine/ECS/Components/Combat/ProjectileComponent.cs) | `IsEnemyProjectile` flag, factory |
| [CombatSystem.cs](../../GameProject/src/GameProject.Engine/ECS/Systems/CombatSystem.cs) | Enemy projectile → player collision |
| [EntityFactory.cs](../../GameProject/src/GameProject.Engine/ECS/Archetypes/EntityFactory.cs) | `CreateEnemy()`, `CreateEnemyProjectile()` |
| [EnemyDefinition.cs](../../GameProject/src/GameProject.Engine/Content/Definitions/EnemyDefinition.cs) | JSON schema (`AIDefinition` class) |
| [enemies.json](../../GameProject/Content/Data/enemies.json) | Enemy definitions with attack configs |

## Common Issues

### Telegraph doesn't appear
- Check `IsActive = true` when adding component
- Verify `TelegraphRenderSystem` priority (490, before sprites)
- Ensure `context.GetSyncedTime()` is used for timing

### Projectile doesn't spawn
- Check `HasExecuted` flag is reset in `BeginAttack()`
- Verify `ExecuteDuration` is long enough (at least 1 frame)
- Confirm `SpawnEnemyProjectile()` is called with correct UniqueId

### Beam damages too fast
- Verify `BeamTickInterval` is set correctly (default 0.2s)
- Check `LastBeamTickTime` is updated after each tick
- Ensure tick check happens before damage application

### Network desync
- Replace `context.TotalTime` with `context.GetSyncedTime()`
- Verify all timing uses synced time
- Check direction is locked at Windup start (not updated every frame)

### SpriteBatch error
- Don't call `Begin()`/`End()` in render systems
- Use the already-active SpriteBatch from `GameProjectGame.DrawWithVirtualFramebuffer()`
- Follow pattern in `SpriteRenderSystem` or `TelegraphRenderSystem`

## References

### Source Files
- `ECS/Systems/EnemyAttackSystem.cs` — Attack state machine, handlers, helpers
- `ECS/Systems/TelegraphRenderSystem.cs` — Telegraph rendering with pulsing effects
- `ECS/Components/Enemy/EnemyAttackComponent.cs` — EnemyAttackType enum
- `ECS/Components/Enemy/EnemyAttackConfigComponent.cs` — Immutable attack config, factory methods
- `ECS/Components/Enemy/EnemyAttackStateComponent.cs` — Mutable attack state, phase tracking
- `ECS/Components/Enemy/EnemyTelegraphComponent.cs` — Telegraph visual data
- `ECS/Components/Combat/ProjectileComponent.cs` — IsEnemyProjectile flag
- `ECS/Systems/CombatSystem.cs` — Enemy projectile to player collision
- `ECS/Archetypes/EntityFactory.cs` — CreateEnemy, CreateEnemyProjectile
- `Content/Definitions/EnemyDefinition.cs` — JSON schema (AIDefinition class)

### Related Context Docs
- [enemy-archetypes.md](enemy-archetypes.md) — 40 enemy archetype definitions
- [boss-fight-framework.md](boss-fight-framework.md) — Boss attack patterns and phase system
- [enemy-collision-physics.md](enemy-collision-physics.md) — Enemy-to-enemy collision physics
