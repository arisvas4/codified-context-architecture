<!-- v1 | last-verified: 2026-02-15 -->
# UI Sync Patterns

How UI state is synchronized across networked clients. Use this guide when adding new menus, overlays, or interactive UI that needs to be visible to remote players.

## Three Routing Topologies

### 1. Hub-Relay (Client -> Host -> BroadcastToAll)

Host validates and relays. Used when the state transition has gameplay implications or needs authority.

| Message | ID | Description |
|---------|----|-------------|
| `HeroSelectedMessage` | 23 | Hero class selection in lobby |
| `PlayerReadyMessage` | 24 | Ready toggle in lobby |
| `HeroCreationOverlayMessage` | 25 | Overlay open/close in hub |
| `ProfileSelectedMessage` | 29 | Profile switch in lobby |
| `VictoryPageTransitionMessage` | 51 | Host commands page change |

**Pattern:** Client sends to host (`SendToHost`), host validates then rebroadcasts (`BroadcastToAll`). All use `ReliableOrdered`.

### 2. Direct-Broadcast (Any Peer -> BroadcastToAll)

No host validation. Used for cosmetic-only UI state that doesn't affect gameplay.

| Message | ID | Delivery | Description |
|---------|----|---------|----|
| `ShopFocusChanged` | 45 | UnreliableSequenced | Cursor position in shop |
| `RadialDialSyncMessage` | 39 | Dual (see below) | Radial dial open/select/close |
| `ShopReadyChanged` | 49 | ReliableOrdered | Shop ready toggle |
| `ShopPurchase` | 46 | ReliableOrdered | Item purchased notification |

**Pattern:** Any peer calls `BroadcastToAll` directly. Handler filters own messages with `IsLocalPlayer()`.

### 3. Client-to-Host Only (Client -> Host)

Host consumes data; never rebroadcasts to other clients.

| Message | ID | Description |
|---------|----|-------------|
| `PlayerDisplaySyncMessage` | 38 | Level/Gold/XP% for HUD widgets |
| `HeroStatsUpdateMessage` | 34 | Combat stats for damage validation |

**Pattern:** Client sends to host (`SendToHost`). Host stores data locally for its own use.

## Delivery Mode Decision Tree

```
Is it a critical state transition (open/close/confirm/purchase)?
  YES -> ReliableOrdered
  NO -> Is it a frequent cursor/selection update?
    YES -> UnreliableSequenced (only latest matters)
    NO -> ReliableOrdered (default safe choice)
```

**Dual delivery (RadialDialSync pattern):** Same message struct, different delivery mode based on context:
- Open/close: `ReliableOrdered` (must arrive)
- Selection changes: `UnreliableSequenced` (high frequency, only latest matters)

```csharp
void SendRadialDialSync(RadialDialSyncMessage message, bool reliable);
// reliable=true  -> DeliveryMode.ReliableOrdered
// reliable=false -> DeliveryMode.UnreliableSequenced
```

## Handler Boilerplate

Every UI sync handler must:

1. **Filter own messages** — prevent processing your own broadcasts:
   ```csharp
   private void HandleRadialDialSync(RadialDialSyncMessage msg)
   {
       if (IsLocalPlayer(msg.PlayerId)) return;  // Always filter first
       OnRadialDialSync?.Invoke(msg);
   }
   ```

2. **Subscribe in initialization, unsubscribe in cleanup:**
   ```csharp
   // In Initialize()
   _networkService.OnRadialDialSync += HandleRemoteDialSync;

   // In Dispose()
   _networkService.OnRadialDialSync -= HandleRemoteDialSync;
   ```

3. **Use event pattern** — NetworkService fires events, subscribers handle domain logic.

## When to Create a New Message vs Extend Existing

| Scenario | Action |
|----------|--------|
| Different field structure | New message type |
| Different routing topology | New message type |
| Same domain, new context (e.g., RadialDial adds ShopPurchase mode) | Same message, new enum value |
| Unrelated UI element | New message type |

## Naming Convention

`{Domain}{Action}Message` or `{Domain}{State}`:
- `RadialDialSyncMessage` — syncs radial dial state
- `ShopFocusChanged` — shop cursor position changed
- `ShopReadyChanged` — shop ready state changed

## Adding a New UI Sync Message (Checklist)

1. Create message struct in `Network/Messages/{Domain}Messages.cs` with `[MessagePackObject]` + `[Key(n)]` + `[SerializationConstructor]`
2. Add enum value to `NetworkMessageType.cs`
3. Add serialize method to `NetworkMessageSerializer.cs`
4. Add event + send method to `INetworkService.cs`
5. Add event field + send implementation + dispatch case + handler to `NetworkService.cs`
6. Subscribe to event in the consuming service/overlay
7. Build verify: `cd GameProject && dotnet build`

## Key Files

| File | Role |
|------|------|
| `Network/Messages/NetworkMessageType.cs` | Message type enum (byte IDs) |
| `Network/Messages/NetworkMessageSerializer.cs` | Serialize/deserialize helpers |
| `Network/INetworkService.cs` | Events and send method declarations |
| `Network/NetworkService.cs` | Event fields, send implementations, dispatch switch, handlers |
| `Network/Messages/RadialDialMessages.cs` | Radial dial sync message |
| `Network/Messages/ShopMessages.cs` | Shop UI messages |

## References

### Source Files
- `Network/Messages/NetworkMessageType.cs` — Message type enum (byte IDs)
- `Network/Messages/NetworkMessageSerializer.cs` — Serialize/deserialize helpers
- `Network/INetworkService.cs` — Events and send method declarations
- `Network/NetworkService.cs` — Event fields, send implementations, dispatch, handlers
- `Network/Messages/RadialDialMessages.cs` — Radial dial sync message
- `Network/Messages/ShopMessages.cs` — Shop UI messages

### Related Context Docs
- [network-multiplayer-system.md](network-multiplayer-system.md) — Full network architecture and MessagePack patterns
- [hud-blueprint.md](hud-blueprint.md) — HUD layout requiring sync data
