# Disable walking out of rooms via the door tile — design

Date: 2026-08-08
Status: approved (door tile becomes a normal tile for everyone; hotel-view exit packet staff-gated)

## Problem

Traditionally the tile a user enters a room on also acts as an exit tile:
stepping on it removes the user from the room and drops them on hotel view.
PixelRP wants players exposed to hotel view as little as possible — rooms are
connected by teleport furni, and regular players have no navigator. Walking
out the door is therefore an accidental dead end, not a feature.

## Decisions (from brainstorming)

- **Door tile becomes a normal floor tile** — walk on, stand, walk off. No
  pathfinder blocking; entry spawns (which use the same tile) are unchanged.
- **Applies to everyone, staff included.** Staff still have the navigator,
  commands, and the hotel-view packet to leave rooms.
- **The hotel-view exit packet (`GoToHotelViewEvent`) is gated to staff.**
  Non-staff in-room exit requests are silently ignored.

## Why the packet gate is safe this time

Server-side rank gates were tried before and reverted (emulator commit
`16586d89`) because they blocked packets the real client actually sends. This
gate is different:

- The client toolbar has **no leave-room button** for anyone; the only client
  flows that send `DesktopViewComposer` are error paths (room full, banned,
  doorbell cancelled, game-center fallback), all of which fire when the user
  is **not in a room**.
- `GoToHotelViewEvent` extends `RoomPacketEvent`, whose base `Parse` already
  no-ops when `CurrentRoom` is null — so those legit flows never reach the
  handler anyway.
- The gate therefore only affects a modified client trying to force an exit
  while in a room. A modified client showing hotel view while the server keeps
  the user in-room is that client's own desync.

## Changes

### Emulator: `HabboHotel/Rooms/RoomUserManager.cs`

Remove the walk-cycle check (currently lines 802–807) that adds a non-bot
user to the removal list when a step lands on `Model.DoorX/DoorY`. The code
that follows (walk-on furni triggers, `UpdateUserStatus`) already treats any
tile as a normal tile, so no replacement logic is needed.

### Emulator: `Communication/Packets/Incoming/Navigator/GoToHotelViewEvent.cs`

Early-return unless `session.GetHabbo().IsStaff` (existing property,
`Rank >= 5`). Staff behavior unchanged.

### Not touched

- `RemoveUserFromRoom` itself — still used by disconnects, kicks, room
  unloads, and staff exits.
- Bot walk logic (bots were already excluded from the door-exit check).
- Entry/spawn logic, last-position restore, idle-kick, teleports.

## Edge cases

- **Standing on the door tile** while someone enters: same collision case as
  any occupied spawn tile; existing entry logic handles it.
- **Pushed/pulled onto the door tile** (`:push`, `:pull`, super variants):
  those move users the same way walking does; with the check gone the tile is
  inert for them too.
- **Non-staff who somehow reach hotel view** (failed room entry): unchanged
  existing behavior (they re-enter via login restore / room 1 spawn); out of
  scope.

## Testing

- Build the emulator (`dotnet build`).
- Live-test on local dev with the ClaudeTest account: walk onto the door
  tile — expect to stand there with no exit; walk off again.
- Verify a staff account can still leave via the hotel-view packet, and that
  a non-staff DesktopView packet while in-room is ignored.

## Changelog

Player-facing `CHANGELOG.md` entry in the same push, per repo discipline.
