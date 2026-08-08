# Last-Position Restore — Design Spec

**Date:** 2026-08-08
**Status:** Approved by user
**Scope:** First RP feature. Server-side (PlusEMU fork, branch `pixelrp`); no client or CMS changes.

## Goal

On login, a player skips the hotel view and loads directly into the room they
were last in, standing on the exact tile with the exact rotation they had when
they logged out or disconnected. Applies to everyone, always on (no toggle).

## Decisions (locked)

| Question | Decision |
| --- | --- |
| Fallback when saved room can't be entered (deleted, locked, full, banned) | Hotel view — today's behavior. Entry rules are never bypassed. |
| Saved tile now blocked (furni/other player) | Spawn there anyway — exact continuity wins. |
| Who / toggle | Everyone including staff; always on; no server_settings switch. |
| First login (no saved position) | Unchanged behavior (hotel view). |
| Manual room entry mid-session | Unchanged behavior (door spawn). Restore applies only to the login forward. |

## Architecture

Server-driven restore in three parts, all in the emulator:

### 1. Persistence

New `users` columns (migration on the PlusEMU schema, additive only):

- `last_room_id` int NOT NULL DEFAULT 0
- `last_x` int NOT NULL DEFAULT 0
- `last_y` int NOT NULL DEFAULT 0
- `last_rot` int NOT NULL DEFAULT 0

Written whenever a player leaves a room for any reason — normal leave, room
switch, logout, or connection drop — all of which funnel through the
room-user removal path (`RoomUserManager.RemoveUserFromRoom` and the
disconnect/disposal path that calls it). Room switches overwrite the values,
so the columns always hold "last place I stood." `last_z` is deliberately NOT
stored: Z is recomputed from the room height map at spawn so furniture changes
can't sink or float the avatar.

### 2. Login forward

After authentication completes (the packet burst around
`AuthenticationOkComposer`), if `last_room_id > 0`:

- set a per-session pending-restore marker holding `(roomId, x, y, rot)`
- send the room-forward packet (`RoomForwardComposer(last_room_id)`); Nitro
  natively enters the room on receiving it.

Normal entry validation still runs. If entry fails (room gone, locked, full,
banned), the client simply stays on hotel view and the pending marker is
cleared. Locks are never bypassed: restore changes where you land, not whether
you may enter.

### 3. Spawn override

In the room-entry placement code (where the user is placed at the door), if
the entering user has a pending restore whose roomId matches this room:

- place at `(last_x, last_y)` with rotation `last_rot` (body and head)
- Z from `GameMap.SqAbsoluteHeight(last_x, last_y)`
- clear the pending marker (single use)
- if the saved tile is outside the room model bounds (room remodeled), fall
  back to the door; otherwise place even if occupied/blocked.

Pending marker lifetime: set at forward time, cleared on first room entry (any
room), entry failure, or disconnect — it must never leak into a later manual
entry.

## Error handling

- Saved room deleted → forward not sent (room lookup fails) or entry fails →
  hotel view.
- Entry denied (lock/password/full/ban) → standard denial flow → hotel view.
- Tile out of bounds after remodel → door spawn (marker still cleared).
- Emulator crash between sessions → columns hold the previous save; worst
  case the player restores to a slightly stale position. Acceptable.

## Testing

Live browser verification against the local stack:

1. Log in → auto-enters last room on the saved tile with saved rotation
   (screenshot + `SELECT last_room_id,last_x,last_y,last_rot` assertions).
2. Walk to a different tile, disconnect (close tab), relog → restored to the
   new tile.
3. Lock then delete the room → relog lands on hotel view both times.
4. Fresh account → hotel view, unchanged.
5. Manual room entry mid-session → door spawn, unchanged.

## Out of scope

- Client/CMS changes of any kind.
- Restoring effects, dance state, or sit posture.
- Cross-hotel (prod deploy happens via the normal emulator rebuild flow).
