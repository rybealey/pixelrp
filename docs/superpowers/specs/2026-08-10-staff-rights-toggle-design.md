# Staff Rights Toggle + Rights-Gated Furni Infostand

**Date:** 2026-08-10
**Status:** Approved

## Problem

Staff (rank 4+) currently receive owner-level room rights automatically in every
room via the `room_any_owner` / `room_any_rights` permissions checked in
`Room.CheckRights`. In an RP hotel, staff walking around with rights everywhere
(flatctrl badge, furni manipulation, owner tools) breaks immersion. Separately,
every player can click any furni and read its infostand (name, owner, ID for
staff), which leaks build information to players with no rights in the room.

## Requirements

1. Room rights are **disabled by default for all staff (rank ≥ 4)**, in every
   room — including rooms the staff member personally owns.
2. A new staff command `:rights on` / `:rights off` enables or disables room
   rights **in the room they are currently standing in**.
3. The toggle **resets to off** when the session ends or the user leaves the
   room (room change, disconnect, hotel view).
4. Players who do not hold room rights in a room cannot view the furni
   infostand when clicking furniture. **Staff follow the same gate**: with
   `:rights off` they see no infostand either. A player who owns the clicked
   furni item, or owns the room, keeps visibility.
5. `:rights on` restores exactly the rights staff get today on room entry
   (owner-level, controller level 4/5 per `room_item_save_branding_items`).

## Design

### 1. Emulator — default-off gate in `Room.CheckRights`

New transient property on `Habbo` (`HabboHotel/Users/Habbo.cs`, alongside the
other session-scoped fields):

```csharp
public bool RoomRightsEnabled { get; set; }   // staff :rights toggle, session-transient
```

At the top of `CheckRights(GameClient, bool, bool)`
(`HabboHotel/Rooms/Room.cs:265`), after the null guard:

```csharp
if (session.GetHabbo().Rank >= 4 && !session.GetHabbo().RoomRightsEnabled)
    return false;
```

This runs before the owner-name check, so it covers staff-owned rooms, the
`room_any_owner` / `room_any_rights` bypasses, explicit `room_rights` rows, and
group-admin rights — all rights-derived behavior flows through this one method.
Explicit permission checks that sit next to `CheckRights` (`mod_tool`,
`room_enter_locked`, `room_unload_any`, command permissions, etc.) are
deliberately untouched: staff moderation tooling keeps working.

The rank-4 threshold matches who holds the `:rights` command, so nobody is
locked out of rights without also having the toggle.

### 2. Emulator — `:rights` command

New `RightsCommand : IChatCommand` in
`HabboHotel/Rooms/Chat/Commands/Moderator/` (auto-registered by assembly
scanning):

- `Key => "rights"`, `PermissionRequired => "command_rights"`,
  `Parameters => "%on/off%"`.
- Argument parsing follows `BotCommand`: no arg / bad arg → whisper current
  state and usage; `on` / `off` → set `RoomRightsEnabled` and refresh.
- Refresh = re-run the rights push for the current room (see §3). On `off`,
  the user receives `YouAreNotControllerComposer`, the `flatctrl` status is
  removed, and a user-status update is broadcast so the rights badge disappears
  for everyone in the room.

### 3. Emulator — shared rights-push helper

The rights block in `RoomUserManager.AddAvatarToRoom`
(`HabboHotel/Rooms/RoomUserManager.cs:226-246`) is extracted into a public
helper on `RoomUserManager` (e.g. `RefreshRights(GameClient session,
RoomUser user)`) that computes and pushes
`YouAreOwnerComposer` / `YouAreControllerComposer(n)` /
`YouAreNotControllerComposer` and sets/clears the `flatctrl` status. Called
from both `AddAvatarToRoom` (unchanged behavior) and `RightsCommand`.

### 4. Emulator — reset semantics

`RoomUserManager.RemoveUserFromRoom` sets
`session.GetHabbo().RoomRightsEnabled = false`. This single hook covers room
change, hotel view, kick, and disconnect (`Habbo.Dispose` routes through it).
Session end is inherently covered: the field is in-memory only, never
persisted.

### 5. Database — command permission row

```sql
INSERT INTO permissions_commands (command, group_id, subscription_id)
VALUES ('command_rights', 4, 0);
```

Command gating is cumulative (`player.Rank >= GroupId`), so this grants
rank 4+. Data-only change: must be applied to local dev and replayed manually
on prod, and gets a CHANGELOG entry.

### 6. Client — rights-gated furni infostand

In `client/src/components/room/widgets/avatar-info/AvatarInfoWidgetView.tsx`,
`getInfostandView()` FURNI case: return `null` unless

```ts
avatarInfo.roomControllerLevel >= RoomControllerLevel.GUEST
    || avatarInfo.isRoomOwner
    || avatarInfo.isOwner   // clicked furni belongs to the clicker
```

No `isAnyRoomController` / moderator bypass — staff with `:rights off` see
nothing, consistent with the server. These fields are captured from the room
session at click time in `AvatarInfoUtilities.getFurniInfo`, so the gate stays
correct when rights change mid-session; since the server no longer pushes
`YouAreOwner`/`YouAreController` to staff by default, `controllerLevel` and
`isRoomOwner` are already authoritative. Selection side effects (wired picker,
decorate menu) are unchanged — only the infostand render is gated.

## Error handling / edge cases

- `:rights` outside a room: command manager already resolves the room; if no
  room, whisper a no-op message.
- `:rights on` twice / `off` twice: idempotent — refresh re-pushes the same
  state.
- Toggling `off` while a furni-move UI is open: acceptable; the server rejects
  the subsequent action via `CheckRights`.
- Non-staff (rank < 4) typing `:rights`: no `command_rights` permission → the
  text falls through as normal chat, matching every other staff command.

## Testing

Manual verification on local dev:

1. ClaudeTest (staff rank) enters own room and another player's room → no
   flatctrl badge, cannot move furni, no infostand on furni click.
2. `:rights on` → badge appears, furni manipulation works, infostand visible;
   `:rights off` → all revoked live.
3. Room change and re-login after `:rights on` → rights are off again.
4. Low-rank account with explicit room rights (room_rights row) → still has
   rights and sees infostand (gate only applies to rank ≥ 4).
5. Regular player in a room they own → sees infostand; in someone else's room
   → does not.

## Out of scope

- The pre-existing `flatctrl` status-key inconsistency
  (`SetStatus("flatctrl", "1")` vs `SetStatus("flatctrl 1")`) beyond what the
  shared helper fixes in its own path — flagged as a separate task.
- Persisting the toggle across sessions (explicitly unwanted).
- Gating avatar/pet/bot infostands — furni only.
