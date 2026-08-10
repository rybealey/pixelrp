# Staff Rights Toggle + Rights-Gated Furni Infostand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Staff (rank ≥ 4) have no room rights anywhere by default, toggle them per-room with `:rights on/off` (reset on room exit / session end), and the furni infostand is hidden from anyone without room rights.

**Architecture:** One server-side gate at the top of `Room.CheckRights` keyed on a transient `Habbo.RoomRightsEnabled` flag; a shared `RefreshRights` helper extracted from `RoomUserManager.AddAvatarToRoom` so the new `:rights` chat command can re-push controller state mid-session; a client-side render gate in `AvatarInfoWidgetView` using the rights snapshot already captured at click time.

**Tech Stack:** Plus Emulator (C# / .NET, `emulator/` git submodule on branch `pixelrp`), Nitro React client (TypeScript, `client/` git submodule), MySQL 8 via docker compose.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-10-staff-rights-toggle-design.md`.
- "Staff" for the rights lockout = `Rank >= 4` (matches `command_rights` grant, `group_id = 4`).
- `RoomRightsEnabled` is **never persisted** — in-memory on `Habbo` only.
- No moderator/staff bypass in the client infostand gate.
- The emulator has **no automated test project** (`emulator/Tests/` contains only build artifacts). Verification per task = `dotnet build` with zero new warnings/errors; behavior verification is Task 6 (manual, local dev).
- CHANGELOG.md is player-facing: describe what players see, no file paths or internals.
- `emulator/` and `client/` are submodules: commit inside each submodule first, then bump pointers in the parent repo (Task 6). Before committing in a submodule, check `git -C <submodule> status` / current branch (emulator uses `pixelrp`).
- A separate session (background task) may be fixing the pre-existing `flatctrl` status-key mismatch in this same area. If you hit unexpected conflicts in `RoomUserManager.cs` or rights-change packet handlers, stop and surface it rather than force-merging.
- All emulator builds: run `dotnet build "Plus Emulator.sln"` from `emulator/`.

---

### Task 1: `RoomRightsEnabled` flag + `CheckRights` gate

**Files:**
- Modify: `emulator/HabboHotel/Users/Habbo.cs` (~line 206, after `SessionClothingBlocked`)
- Modify: `emulator/HabboHotel/Rooms/Room.cs:265-300` (`CheckRights`)

**Interfaces:**
- Consumes: existing `Habbo.Rank` (uint), `GameClient.GetHabbo()`.
- Produces: `public bool RoomRightsEnabled { get; set; }` on `Habbo` (default `false`) — Tasks 2 and 3 read/write this exact name.

- [ ] **Step 1: Add the transient flag to `Habbo`**

In `emulator/HabboHotel/Users/Habbo.cs`, directly after `public bool SessionClothingBlocked { get; set; }`:

```csharp
// Staff :rights toggle — rank 4+ have no room rights (any room, own rooms
// included) until they enable them per-room. Reset on room exit; never persisted.
public bool RoomRightsEnabled { get; set; }
```

- [ ] **Step 2: Gate `CheckRights`**

In `emulator/HabboHotel/Rooms/Room.cs`, `CheckRights(GameClient session, bool requireOwnership, bool checkForGroups = false)`, insert immediately after the null guard (`if (session == null || session.GetHabbo() == null) return false;`):

```csharp
if (session.GetHabbo().Rank >= 4 && !session.GetHabbo().RoomRightsEnabled)
    return false;
```

This must run **before** the `OwnerName` check so staff-owned rooms are covered.

- [ ] **Step 3: Build**

Run from `emulator/`: `dotnet build "Plus Emulator.sln"`
Expected: Build succeeded, no new errors.

- [ ] **Step 4: Commit (emulator submodule)**

```bash
git -C emulator add HabboHotel/Users/Habbo.cs HabboHotel/Rooms/Room.cs
git -C emulator commit -m "feat: disable room rights for staff (rank 4+) by default"
```

---

### Task 2: Extract `RefreshRights` helper + reset on room exit

**Files:**
- Modify: `emulator/HabboHotel/Rooms/RoomUserManager.cs:225-247` (`AddAvatarToRoom` rights block) and `:261+` (`RemoveUserFromRoom`)

**Interfaces:**
- Consumes: `Habbo.RoomRightsEnabled` (Task 1).
- Produces: `public void RefreshRights(GameClient session, RoomUser user)` on `RoomUserManager` — Task 3 calls it via `room.GetRoomUserManager().RefreshRights(session, user)`.

- [ ] **Step 1: Extract the rights-push block into a helper**

In `RoomUserManager.cs`, replace lines 226-247 (the `if (_room.CheckRights(session, true))` chain through `user.UpdateNeeded = true;`) with:

```csharp
        RefreshRights(session, user);
```

and add this method to the class (near `AddAvatarToRoom`):

```csharp
    public void RefreshRights(GameClient session, RoomUser user)
    {
        // Clear any previous rights badge; re-added below if still entitled.
        user.RemoveStatus("flatctrl");
        if (_room.CheckRights(session, true))
        {
            user.SetStatus("flatctrl", "useradmin");
            session.Send(new YouAreOwnerComposer());
            // Nitro only shows the branding (ads_background) editor at controller
            // level 5 ("moderator"); level 4 caps out at plain owner tools.
            session.Send(new YouAreControllerComposer(
                session.GetHabbo().Permissions.HasRight("room_item_save_branding_items") ? 5 : 4));
        }
        else if (_room.CheckRights(session, false) && _room.Group == null)
        {
            user.SetStatus("flatctrl", "1");
            session.Send(new YouAreControllerComposer(1));
        }
        else if (_room.Group != null && _room.CheckRights(session, false, true))
        {
            user.SetStatus("flatctrl", "3");
            session.Send(new YouAreControllerComposer(3));
        }
        else
            session.Send(new YouAreNotControllerComposer());
        user.UpdateNeeded = true;
    }
```

Note: the composer chain is byte-for-byte the code removed from `AddAvatarToRoom`; the only additions are the leading `RemoveStatus("flatctrl")` (no-op on first entry, required when the command downgrades rights mid-session) and folding in the trailing `user.UpdateNeeded = true;` from old line 247. Do **not** change the status keys beyond this — the wider `flatctrl` key mismatch is a separate task.

- [ ] **Step 2: Reset the toggle on room exit**

In `RemoveUserFromRoom`, directly after `session.GetHabbo().CurrentRoom = null;` (line 275):

```csharp
            // Staff :rights toggle is per-room-visit; covers room change,
            // hotel view, kick, and disconnect (Habbo.Dispose routes here).
            session.GetHabbo().RoomRightsEnabled = false;
```

- [ ] **Step 3: Build**

Run from `emulator/`: `dotnet build "Plus Emulator.sln"`
Expected: Build succeeded.

- [ ] **Step 4: Commit (emulator submodule)**

```bash
git -C emulator add HabboHotel/Rooms/RoomUserManager.cs
git -C emulator commit -m "refactor: extract RefreshRights helper, reset staff rights toggle on room exit"
```

---

### Task 3: `:rights` chat command

**Files:**
- Create: `emulator/HabboHotel/Rooms/Chat/Commands/Moderator/RightsCommand.cs`

**Interfaces:**
- Consumes: `Habbo.RoomRightsEnabled` (Task 1), `RoomUserManager.RefreshRights(GameClient, RoomUser)` (Task 2), `GameClientExtensions.SendWhisper(this GameClient, string, int colour = 0)`.
- Produces: chat command keyed `rights`, permission `command_rights` (DB row in Task 4). Auto-registered by the `[Singleton]` assembly scan — no manual registration.

- [ ] **Step 1: Create the command**

`emulator/HabboHotel/Rooms/Chat/Commands/Moderator/RightsCommand.cs` (whole file):

```csharp
using Plus.HabboHotel.GameClients;

namespace Plus.HabboHotel.Rooms.Chat.Commands.Moderator;

internal class RightsCommand : IChatCommand
{
    public string Key => "rights";
    public string PermissionRequired => "command_rights";

    public string Parameters => "%on/off%";

    public string Description => "Enable or disable your room rights in the room you are standing in.";

    public void Execute(GameClient session, Room room, string[] parameters)
    {
        var argument = parameters.Length > 0 ? parameters[0].ToLower() : "";
        if (argument != "on" && argument != "off")
        {
            session.SendWhisper($"Your room rights are currently {(session.GetHabbo().RoomRightsEnabled ? "ON" : "OFF")}. Use :rights on or :rights off to change them.");
            return;
        }
        session.GetHabbo().RoomRightsEnabled = argument == "on";
        var user = room.GetRoomUserManager().GetRoomUserByHabbo(session.GetHabbo().Id);
        if (user != null)
            room.GetRoomUserManager().RefreshRights(session, user);
        session.SendWhisper(session.GetHabbo().RoomRightsEnabled
            ? "Room rights enabled - they reset when you leave the room or log out."
            : "Room rights disabled.");
    }
}
```

(`Room` resolves without a using — the namespace nests under `Plus.HabboHotel.Rooms`. Match `BotCommand.cs` in the same folder for style.)

- [ ] **Step 2: Build**

Run from `emulator/`: `dotnet build "Plus Emulator.sln"`
Expected: Build succeeded.

- [ ] **Step 3: Commit (emulator submodule)**

```bash
git -C emulator add HabboHotel/Rooms/Chat/Commands/Moderator/RightsCommand.cs
git -C emulator commit -m "feat: add :rights on/off staff command"
```

---

### Task 4: `command_rights` DB row + CHANGELOG

**Files:**
- Modify: local dev database (data-only; prod replay happens at deploy time)
- Modify: `CHANGELOG.md` (parent repo)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `permissions_commands` row (`command_rights`, `group_id = 4`, `subscription_id = 0`) that gates Task 3's command.

- [ ] **Step 1: Insert the permission row into local dev DB**

The compose service is `db` (MySQL 8, creds in `.env` at repo root). From the repo root:

```bash
set -a; source .env; set +a
docker compose exec db mysql -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" \
  -e "INSERT INTO permissions_commands (command, group_id, subscription_id) VALUES ('command_rights', 4, 0);"
```

- [ ] **Step 2: Verify the row and restart the emulator**

`PermissionManager` loads `permissions_commands` once at startup, so the emulator must restart to see it:

```bash
docker compose exec db mysql -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" \
  -e "SELECT * FROM permissions_commands WHERE command = 'command_rights';"
docker compose restart emulator
```

Expected: one row (`command_rights`, 4, 0).

- [ ] **Step 3: CHANGELOG entry (parent repo)**

Add at the top of `CHANGELOG.md`, below the maintainer comment block (player-facing wording, no internals):

```markdown
## 2026-08-10 — Staff blend in

### Changed

- **Staff no longer have automatic rights in every room.** The rights badge is
  gone from staff by default — they walk, sit, and chat like any other player,
  even in rooms they own. Staff can switch their tools on in a specific room
  when they need to build, and it switches off again the moment they leave.
- **Clicking furniture only shows the info panel if you have rights in that
  room.** No rights, no infostand — the room's builds keep their secrets.
```

- [ ] **Step 4: Commit (parent repo — CHANGELOG only for now)**

```bash
git add CHANGELOG.md
git commit -m "docs: changelog for staff rights toggle + infostand gating"
```

Note for deploy (record in the final report, not in CHANGELOG): the same `INSERT` must be replayed manually on prod before/with the emulator deploy.

---

### Task 5: Client — rights-gated furni infostand

**Files:**
- Modify: `client/src/components/room/widgets/avatar-info/AvatarInfoWidgetView.tsx:1,100-128`

**Interfaces:**
- Consumes: `AvatarInfoFurni` fields already populated at click time by `AvatarInfoUtilities.getFurniInfo` — `roomControllerLevel: number`, `isRoomOwner: boolean`, `isOwner: boolean`; `RoomControllerLevel` enum from `@nitrots/nitro-renderer` (`GUEST = 1`).
- Produces: nothing consumed by other tasks.

- [ ] **Step 1: Add the gate**

In `AvatarInfoWidgetView.tsx`:

a. Add `RoomControllerLevel` to the renderer import (line 1):

```ts
import { RoomControllerLevel, RoomEngineEvent, RoomEnterEffect, RoomSessionDanceEvent } from '@nitrots/nitro-renderer';
```

b. Replace the `AvatarInfoFurni.FURNI` case in `getInfostandView()` (line 106-107):

```tsx
            case AvatarInfoFurni.FURNI: {
                const furniInfo = (avatarInfo as AvatarInfoFurni);

                // Rights-gated: no infostand without rights in this room. No staff
                // bypass — the server drives controllerLevel via the :rights toggle.
                if(!(furniInfo.isOwner || furniInfo.isRoomOwner || (furniInfo.roomControllerLevel >= RoomControllerLevel.GUEST))) return null;

                return <InfoStandWidgetFurniView avatarInfo={ furniInfo } onClose={ () => setAvatarInfo(null) } />;
            }
```

c. Avoid rendering an empty `nitro-infostand-container` when the gate returns null. In the component's JSX return (lines 120-128), hoist the call: immediately before `return (`, add

```tsx
    const infostandView = getInfostandView();
```

and change the wrapper

```tsx
            { avatarInfo &&
                <Column alignItems="end" className="nitro-infostand-container">
                    { getInfostandView() }
                </Column> }
```

to

```tsx
            { infostandView &&
                <Column alignItems="end" className="nitro-infostand-container">
                    { infostandView }
                </Column> }
```

- [ ] **Step 2: Build the client**

```bash
cd client && yarn build
```

Expected: vite build completes with no TypeScript errors (pre-existing warnings are fine).

- [ ] **Step 3: Commit (client submodule)**

First check state: `git -C client status --short --branch` (note which branch; create/switch consistent with prior client commits if detached).

```bash
git -C client add src/components/room/widgets/avatar-info/AvatarInfoWidgetView.tsx
git -C client commit -m "feat: hide furni infostand from users without room rights"
```

---

### Task 6: Manual verification + submodule pointer bump

**Files:**
- Modify: parent repo `emulator` + `client` submodule pointers

**Interfaces:**
- Consumes: everything above, running on local dev (docker compose stack + client dev server or built client).

- [ ] **Step 1: Bring up local dev with the new emulator build**

Rebuild/restart the emulator container so it runs the new code (follow the project's existing compose workflow, e.g. `docker compose up -d --build emulator`), and serve the client (`yarn start` dev server, or however the stack serves the built client).

- [ ] **Step 2: Manual test matrix**

Using ClaudeTest (staff rank ≥ 4) via the SSO-ticket flow, plus a low-rank account:

1. ClaudeTest enters a room they own and a room they don't → no `flatctrl` badge, cannot move/rotate/pick up furni, clicking furni shows **no** infostand.
2. `:rights` (no arg) → whisper reports OFF. `:rights on` → whisper confirms; badge appears; furni move works; infostand appears on click; room settings accessible.
3. `:rights off` → all of it revoked live (badge gone for other users in room too).
4. With rights on, walk to another room → rights are off again there. Re-login → off.
5. Low-rank account with a `room_rights` row in a room → still has rights, sees infostand. Same account in a room with no rights → no infostand. In a room they own → infostand visible.
6. Non-staff types `:rights on` → appears as plain chat, no effect.

Any failure: stop, diagnose with superpowers:systematic-debugging before touching code.

- [ ] **Step 3: Bump submodule pointers (parent repo)**

```bash
git add emulator client
git commit -m "feat: bump emulator + client - staff rights toggle (:rights), rights-gated furni infostand"
```

- [ ] **Step 4: Report**

Summarize: what changed, test results, and the outstanding prod steps (replay the `permissions_commands` INSERT on prod; deploy via `gh workflow run deploy.yml`, never manual SSH).
