# Last-Position Restore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On login, a player skips hotel view and loads into their last room on the exact tile and rotation they had at logout/disconnect.

**Architecture:** Three server-side pieces in the PlusEMU fork (`emulator/`, branch `pixelrp`): (1) persist `last_room_id/last_x/last_y/last_rot` on every room-leave via the existing removal funnel; (2) after the login packet burst, send `RoomForwardComposer` and stash a short-lived pending-restore marker on the `Habbo`; (3) in room-entry placement, spawn at the saved tile/rotation instead of the door when the marker matches. No client or CMS changes.

**Tech Stack:** C#/.NET 7 (PlusEMU), MySQL 8, Dapper (`dbClient.Execute(sql, anonObject)` pattern), existing `RoomForwardComposer`.

## Global Constraints

- Applies to everyone, always on — no server_settings toggle (spec decision).
- Fallback is hotel view: entry validation is NEVER bypassed; restore only changes where you land on success.
- Blocked/occupied saved tile: spawn there anyway. Out-of-model-bounds tile (remodel): door spawn.
- Z is never persisted; recompute at spawn via `GameMap.SqAbsoluteHeight(x, y)`.
- Manual room entry (no marker) behaves exactly as today; the marker is single-use and expires 30s after login (implements the spec's "must never leak into a later manual entry" — covers denial paths without touching them).
- All emulator edits on `emulator/` branch `pixelrp`; commit trailer "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"; bump the root submodule pointer after pushing.
- No unit-test project exists in PlusEMU: each task's test cycle is compile (`docker compose build emulator`) + boot to `EMULATOR -> READY!` + live DB/browser assertions as specified.

---

### Task 1: Persist last position on room-leave

**Files:**
- Create: `emulator/Resources/SQLs/Updates/14_AddLastPositionColumns.sql`
- Modify: `emulator/HabboHotel/Rooms/RoomUserManager.cs` (inside `RemoveUserFromRoom`, which starts at line 229)

**Interfaces:**
- Consumes: `RoomUser.X`/`.Y` (int), `RoomUser.RotBody` (int), `_room.RoomId`, the existing `using (var dbClient = PlusEnvironment.DatabaseManager.Connection())` block already present in `RemoveUserFromRoom` (it updates `user_roomvisits`).
- Produces: `users.last_room_id`, `users.last_x`, `users.last_y`, `users.last_rot` — always the last tile the player stood on. Task 2 reads these columns.

- [ ] **Step 1: Write the migration file**

`emulator/Resources/SQLs/Updates/14_AddLastPositionColumns.sql` (matches the numbered style of `Updates/1_...` through `13_...`):

```sql
ALTER TABLE `users`
    ADD COLUMN `last_room_id` int UNSIGNED NOT NULL DEFAULT 0,
    ADD COLUMN `last_x` int NOT NULL DEFAULT 0,
    ADD COLUMN `last_y` int NOT NULL DEFAULT 0,
    ADD COLUMN `last_rot` int NOT NULL DEFAULT 0;
```

- [ ] **Step 2: Apply it to the local dev DB**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
PW=$(grep ^DB_PASSWORD .env | cut -d= -f2)
docker compose exec -T db mysql -upixelrp -p"$PW" pixelrp < emulator/Resources/SQLs/Updates/14_AddLastPositionColumns.sql
docker compose exec -T db mysql -upixelrp -p"$PW" pixelrp -e "SHOW COLUMNS FROM users LIKE 'last_%';"
```

Expected: four rows (`last_room_id`, `last_x`, `last_y`, `last_rot`). (`last_online`/`last_change` exist too — the LIKE also matching them is fine; verify the four new ones are present.)

- [ ] **Step 3: Write the persistence code**

In `RemoveUserFromRoom` (RoomUserManager.cs:229): the method already fetches `var user = GetRoomUserByHabbo(session.GetHabbo().Id);` and later opens a `using (var dbClient = PlusEnvironment.DatabaseManager.Connection())` block that updates `user_roomvisits`. Two edits:

(a) Immediately after `var user = GetRoomUserByHabbo(...)` and its `if (user != null)` opens — BEFORE `RemoveRoomUser(user);` executes (RemoveRoomUser wipes room state) — capture the position into locals:

```csharp
// pixelrp last-position restore: capture where the user stood before the
// room state is torn down; persisted below alongside the roomvisit update.
var lastX = user.X;
var lastY = user.Y;
var lastRot = user.RotBody;
```

(b) Inside the existing `using (var dbClient = ...)` block (same scope as the `user_roomvisits` Execute), add:

```csharp
dbClient.Execute(
    "UPDATE `users` SET `last_room_id` = @roomId, `last_x` = @x, `last_y` = @y, `last_rot` = @rot WHERE `id` = @userId LIMIT 1",
    new
    {
        userId = session.GetHabbo().Id,
        roomId = _room.RoomId,
        x = lastX,
        y = lastY,
        rot = lastRot
    });
```

Bots must not be affected (this method is for GameClient sessions only — it already is). Do not add a write anywhere else: every leave path (leave button, room switch, kick, disconnect) funnels through `RemoveUserFromRoom` — verify with `grep -rn "RemoveUserFromRoom(" emulator/ --include="*.cs" | grep -v "public void"` and confirm the disconnect/disposal path (GameClientManager or GameClient.Dispose) appears among the callers. If the disconnect path does NOT call it, report that in your task report and add the same capture+Execute to that path.

- [ ] **Step 4: Build and boot**

```bash
docker compose build emulator 2>&1 | tail -3
docker compose up -d emulator && sleep 12
docker compose logs --since 30s emulator 2>&1 | grep -E "READY|ERROR|Exception" | tail -3
```

Expected: image builds; `EMULATOR -> READY!`; no exceptions.

- [ ] **Step 5: Live verification**

Mint an SSO for ClaudeTest (`docker compose exec -T cms php artisan tinker --execute="..."` — the controller supplies the standard snippet), open `http://localhost:8080/nitro-assets/client/index.html?sso=...` in the browser, enter room 2 (`window.openroom(2)` in the JS console), click a tile to walk somewhere distinctive, then navigate the tab away (disconnect). Then:

```bash
PW=$(grep ^DB_PASSWORD .env | cut -d= -f2)
docker compose exec -T db mysql -upixelrp -p"$PW" pixelrp -e \
  "SELECT last_room_id, last_x, last_y, last_rot FROM users WHERE username='ClaudeTest';"
```

Expected: `last_room_id=2`, `last_x/last_y` = the tile walked to (non-zero), `last_rot` in 0..7.

- [ ] **Step 6: Commit (submodule then root)**

```bash
cd emulator && git add Resources/SQLs/Updates/14_AddLastPositionColumns.sql HabboHotel/Rooms/RoomUserManager.cs \
  && git commit -m "feat: persist last room/tile/rotation on room-leave

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push && cd ..
git add emulator && git commit -m "chore: bump emulator (persist last position)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Login forward + spawn override

**Files:**
- Create: `emulator/HabboHotel/Users/PendingRoomRestore.cs`
- Modify: `emulator/HabboHotel/Users/Habbo.cs` (add one property), `emulator/Communication/Packets/Incoming/Handshake/SSOTicketEvent.cs` (after the login packet burst, lines ~76-96), `emulator/HabboHotel/Rooms/RoomUserManager.cs` (`AddAvatarToRoom`, door-placement branch at ~line 147-158)

**Interfaces:**
- Consumes: Task 1's `users.last_*` columns; `RoomForwardComposer(uint roomId)` (`Communication/Packets/Outgoing/Rooms/Session/RoomForwardComposer.cs`); `IDatabase` DI as done in `UpdateFigureDataEvent` (ctor-injected `IDatabase database`, `_database.GetQueryReactor()` or `PlusEnvironment.DatabaseManager.Connection()` Dapper style); `GameMap.SqAbsoluteHeight(int x, int y)`; `RoomUser.SetPos(int, int, double)` / `SetRot(int, bool)`.
- Produces: `Habbo.PendingRestore` (type `PendingRoomRestore`) — read and cleared by `AddAvatarToRoom`.

- [ ] **Step 1: The marker type**

`emulator/HabboHotel/Users/PendingRoomRestore.cs`:

```csharp
namespace Plus.HabboHotel.Users;

/// <summary>
/// pixelrp last-position restore: set once at login when the user is
/// forwarded to their last room; consumed (and cleared) by the first room
/// entry. Expires 30s after login so it can never leak into a later manual
/// entry if the forward is denied (locked/full/banned room).
/// </summary>
public sealed class PendingRoomRestore
{
    public uint RoomId { get; }
    public int X { get; }
    public int Y { get; }
    public int Rot { get; }
    public DateTime SetAt { get; }

    public PendingRoomRestore(uint roomId, int x, int y, int rot)
    {
        RoomId = roomId;
        X = x;
        Y = y;
        Rot = rot;
        SetAt = DateTime.Now;
    }

    public bool IsFresh => (DateTime.Now - SetAt).TotalSeconds <= 30;
}
```

On `Habbo.cs`, near `public uint HomeRoom { get; set; }` (line ~82), add:

```csharp
public PendingRoomRestore PendingRestore { get; set; }
```

- [ ] **Step 2: Login forward in SSOTicketEvent**

In `SSOTicketEvent.cs`, after the existing login packet burst (after the last `session.Send(...)` of the burst that starts with `AuthenticationOkComposer` at line ~76 — place it at the very end of the method's success path, after any MOTD/motd-style sends so the forward is the final packet):

```csharp
// pixelrp last-position restore: forward the user into the room they were
// last in. Entry validation still runs server-side; on denial the client
// simply stays on hotel view. Spawn position is applied in AddAvatarToRoom.
using (var dbClient = PlusEnvironment.DatabaseManager.Connection())
{
    var last = dbClient.QuerySingleOrDefault<(uint RoomId, int X, int Y, int Rot)>(
        "SELECT `last_room_id`, `last_x`, `last_y`, `last_rot` FROM `users` WHERE `id` = @userId LIMIT 1",
        new { userId = session.GetHabbo().Id });
    if (last.RoomId > 0)
    {
        session.GetHabbo().PendingRestore = new PendingRoomRestore(last.RoomId, last.X, last.Y, last.Rot);
        session.Send(new RoomForwardComposer(last.RoomId));
    }
}
```

Adjust mechanics to the file's reality: check how this event/class accesses the DB elsewhere (`PlusEnvironment.DatabaseManager.Connection()` Dapper is used in `RoomUserManager`; `IDatabase`+`GetQueryReactor` in `UpdateFigureDataEvent` — use whichever this file can reach with the least ceremony, injecting `IDatabase` via constructor if needed). If Dapper tuple-mapping of `QuerySingleOrDefault<(...)>` is awkward, map to a small private record or use `QuerySingleOrDefault<dynamic>`. Add the `using Plus.Communication.Packets.Outgoing.Rooms.Session;` import for `RoomForwardComposer`.

- [ ] **Step 3: Spawn override in AddAvatarToRoom**

In `RoomUserManager.AddAvatarToRoom` (~line 147), the non-teleport/non-hopping branch currently reads:

```csharp
user.SetPos(model.DoorX, model.DoorY, model.DoorZ);
user.SetRot(model.DoorOrientation, false);
```

Replace with:

```csharp
// pixelrp last-position restore: if this entry is the login forward to the
// user's last room, spawn on the saved tile/rotation instead of the door.
// Blocked/occupied tiles are allowed (exact continuity); a tile outside the
// current model (room remodeled) falls back to the door. The marker is
// single-use: cleared below on ANY room entry.
var restore = session.GetHabbo().PendingRestore;
if (restore != null && restore.IsFresh && restore.RoomId == _room.RoomId
    && restore.X >= 0 && restore.X < model.MapSizeX
    && restore.Y >= 0 && restore.Y < model.MapSizeY)
{
    user.SetPos(restore.X, restore.Y, _room.GetGameMap().SqAbsoluteHeight(restore.X, restore.Y));
    user.SetRot(restore.Rot, false);
}
else
{
    user.SetPos(model.DoorX, model.DoorY, model.DoorZ);
    user.SetRot(model.DoorOrientation, false);
}
session.GetHabbo().PendingRestore = null;
```

Also add `session.GetHabbo().PendingRestore = null;` at the END of the teleport/hopping `else if` branch (a user who logs out inside a teleporter re-enters via teleport; the marker must still be consumed). Verify the model bounds property names with `grep -n "MapSizeX\|MapSizeY" emulator/HabboHotel/Rooms/RoomModel.cs` (if they differ, e.g. `MapSize`, use the real names and note it in the report).

- [ ] **Step 4: Build and boot**

```bash
docker compose build emulator 2>&1 | tail -3
docker compose up -d emulator && sleep 12
docker compose logs --since 30s emulator 2>&1 | grep -E "READY|ERROR|Exception" | tail -3
```

Expected: builds; READY; no exceptions.

- [ ] **Step 5: Live E2E — the spec's five scenarios**

Using the browser against `http://localhost:8080` (controller mints SSO tickets as in Task 1):

1. **Restore:** ClaudeTest already has `last_room_id=2` + a tile from Task 1's test. Log in with a fresh SSO. Expected: client auto-enters room 2 with the avatar on that exact tile with that rotation — NO hotel view interlude. Screenshot + `SELECT` to compare tile.
2. **Re-walk + disconnect:** walk to a different tile, close the tab, relog. Expected: restored to the NEW tile.
3. **Denied entry:** lock room 2 (`UPDATE rooms SET state='locked' WHERE id=2;` then restart nothing — state is read per-entry; if the emulator caches loaded rooms, `docker compose restart emulator` to be safe). Relog. Expected: client stays on hotel view (doorbell/denial — no crash), avatar not in room. Unlock after (`state='open'`).
4. **Fresh account:** `UPDATE users SET last_room_id=0 WHERE username='ClaudeTest';` relog. Expected: hotel view, exactly today's behavior.
5. **Manual entry:** after scenario 4's login, enter room 2 via `window.openroom(2)`. Expected: door spawn (marker absent).

Record each scenario's outcome (screenshot descriptions + SQL output) in the task report.

- [ ] **Step 6: Commit (submodule then root)**

```bash
cd emulator && git add HabboHotel/Users/PendingRoomRestore.cs HabboHotel/Users/Habbo.cs \
  Communication/Packets/Incoming/Handshake/SSOTicketEvent.cs HabboHotel/Rooms/RoomUserManager.cs \
  && git commit -m "feat: restore last room/tile/rotation on login

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push && cd ..
git add emulator && git commit -m "chore: bump emulator (last-position restore)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Production deploy + changelog

**Files:**
- Modify: `CHANGELOG.md` (root repo)

**Interfaces:**
- Consumes: Tasks 1-2 landed on `emulator/pixelrp` and the root pointer committed; the prod deploy flow (pull → submodule update → build emulator → up -d) used for every prior emulator change; `/root`-reachable prod DB creds in `/opt/pixelrp/.env`.

- [ ] **Step 1: Apply the migration on prod**

```bash
ssh root@67.219.109.182 'cd /opt/pixelrp && git pull -q origin main && git submodule update --init emulator && \
  PW=$(grep ^DB_PASSWORD .env | cut -d= -f2) && \
  docker compose -f compose.yaml -f compose.prod.yaml exec -T db mysql -upixelrp -p"$PW" pixelrp < emulator/Resources/SQLs/Updates/14_AddLastPositionColumns.sql && \
  docker compose -f compose.yaml -f compose.prod.yaml exec -T db mysql -upixelrp -p"$PW" pixelrp -e "SHOW COLUMNS FROM users LIKE \"last_room_id\";"'
```

Expected: the column row prints. NOTE the heredoc/quoting: the `<` redirection happens on the VPS side — run the whole thing inside the ssh single-quoted command as written.

- [ ] **Step 2: Rebuild + restart the prod emulator**

```bash
ssh root@67.219.109.182 'cd /opt/pixelrp && docker compose -f compose.yaml -f compose.prod.yaml build emulator 2>&1 | tail -2 && \
  docker compose -f compose.yaml -f compose.prod.yaml up -d emulator && sleep 12 && \
  docker compose -f compose.yaml -f compose.prod.yaml logs --since 30s emulator 2>&1 | grep -E "READY|ERROR|Exception" | tail -3'
```

Expected: `EMULATOR -> READY!`, no exceptions. (Players in rooms are disconnected by the restart; they reconnect — and now restore. Deploy is the same interruption every emulator change has had.)

- [ ] **Step 3: Changelog entry**

Prepend to `CHANGELOG.md` under a new dated section, player-facing voice per the file's house rules:

```markdown
## 2026-08-08 — Pick up where you left off

### Added

- **You now log back in right where you were.** Closing the game — or losing
  connection — no longer sends you back to the hotel screen. On your next
  login you'll be standing in the same room, on the same tile, facing the
  same way as when you left. If that room has since been locked or removed,
  you'll land on the hotel screen like before.
```

- [ ] **Step 4: Commit and push root**

```bash
git add CHANGELOG.md && git commit -m "docs: changelog for last-position restore

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push origin main
```

- [ ] **Step 5: Prod smoke test**

Log a test account into https://pixelrp.co (controller/user does this in a browser), enter a room, disconnect, relog. Expected: lands back in the room on the same tile. If the user prefers, this can be their own manual check — report it as pending-user-verification rather than blocking.

---

## Self-review notes

- Spec coverage: persistence (T1), forward + marker + spawn override + all five locked decisions (T2), the five test scenarios verbatim (T2 Step 5), deploy + player-facing note (T3). Fallback-to-hotel-view needs no code — it is the absence of bypasses, tested by scenario 3.
- The 30s TTL implements the spec's marker-lifetime rule ("cleared on entry failure, or disconnect") without instrumenting every denial path; single-use clearing on ANY entry is explicit in both placement branches.
- Type consistency: `PendingRoomRestore(uint, int, int, int)` matches both the SSOTicketEvent construction and the AddAvatarToRoom reads; `RoomForwardComposer(uint)` matches its existing signature; column names `last_room_id/last_x/last_y/last_rot` are identical across T1 SQL, T1 Execute, and T2 SELECT.
