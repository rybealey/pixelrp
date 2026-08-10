# Changing-Booth-Gated Avatar Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The "Change Your Looks" window opens only while standing in a changing booth (`boutique_changing1/2/3`) and closes on stepping out; all other entry points are removed.

**Architecture:** New emulator interaction type `DressingBooth` hooks the existing step-commit walk-on/walk-off path and drives the client via a new `InClientLinkComposer` (wire id 2023, already parsed by nitro-renderer as a link-event dispatch). Client work is pure deletion of the two existing entry points.

**Tech Stack:** C# (.NET, Plus Emulator) in `emulator/`, React + TypeScript (Nitro) in `client/`, MySQL in Docker.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-10-changing-booth-avatar-editor-design.md` (approved). One deviation: the SQL update file is numbered **21** (20 already exists: `20_HideWallsByDefault.sql`).
- `emulator/` and `client/` are their own git repositories. Commit feature work inside them; the parent repo gets a final `feat: bump client+emulator - ...` commit plus the CHANGELOG entry, matching existing history (e.g. `f0f0d13`).
- Neither codebase has automated tests. Every task's verify step is a build: emulator = `docker compose build emulator`, client = `cd client && yarn eslint src --ext .ts,.tsx` (build happens once in Task 5 via `docker/nitro/build-client.sh`). Final acceptance is live in-game verification (Task 5).
- New server packet headers use the project's custom 4100+ range; header const name must exactly match the composer class name (reflection wiring).
- CHANGELOG.md entry required (player-facing change).

---

### Task 1: `InClientLinkComposer` (emulator → client link dispatch)

**Files:**
- Create: `emulator/Communication/Packets/Outgoing/Avatar/InClientLinkComposer.cs`
- Modify: `emulator/Communication/Packets/Outgoing/ServerPacketHeader.cs` (append after line 323, the `//Camera` block)
- Modify: `emulator/Resources/Revisions/1.6.6.json` (last entry is `"CameraPublishStatusMessageComposer": 2057` at line 544)

**Interfaces:**
- Consumes: nothing new.
- Produces: `new InClientLinkComposer(string link)` — sends the link string on wire id 2023; nitro-renderer's `SessionDataManager.onInClientLinkEvent` dispatches it as a client link event (e.g. `"avatar-editor/show"`). Used by Tasks 2.

- [ ] **Step 1: Create the composer**

`emulator/Communication/Packets/Outgoing/Avatar/InClientLinkComposer.cs`:

```csharp
using Plus.Communication.Packets;
using Plus.HabboHotel.GameClients;

namespace Plus.Communication.Packets.Outgoing.Avatar;

public class InClientLinkComposer : IServerPacket
{
    private readonly string _link;

    public uint MessageId => ServerPacketHeader.InClientLinkComposer;

    public InClientLinkComposer(string link)
    {
        _link = link;
    }

    public void Compose(IOutgoingPacket packet)
    {
        packet.WriteString(_link);
    }
}
```

(Match the `IServerPacket`/`IOutgoingPacket` shape of `InitCameraMessageComposer.cs` in `Outgoing/Camera/` — if the interface there differs from the above, copy its exact shape.)

- [ ] **Step 2: Register the internal header**

In `emulator/Communication/Packets/Outgoing/ServerPacketHeader.cs`, after the `//Camera` block (line 323):

```csharp
    //Dressing booth
    public const uint InClientLinkComposer = 4106;
```

- [ ] **Step 3: Map to the Nitro wire id**

In `emulator/Resources/Revisions/1.6.6.json`, the current last entry (line 544) is `"CameraPublishStatusMessageComposer": 2057` followed by the closing brace. Add a comma and append:

```json
    "InClientLinkComposer": 2023
```

Verify the file is valid JSON: `python3 -m json.tool emulator/Resources/Revisions/1.6.6.json > /dev/null && echo OK`

- [ ] **Step 4: Verify emulator builds**

Run: `docker compose build emulator`
Expected: image builds with no compiler errors.

- [ ] **Step 5: Commit (emulator repo)**

```bash
cd emulator && git add Communication/Packets/Outgoing/Avatar/InClientLinkComposer.cs Communication/Packets/Outgoing/ServerPacketHeader.cs Resources/Revisions/1.6.6.json && git commit -m "feat: InClientLinkComposer (wire 2023) for server-driven client link events"
```

---

### Task 2: `DressingBooth` interaction type + walk/exit/pickup behavior

**Files:**
- Modify: `emulator/HabboHotel/Items/InteractionType.cs` (enum, before closing brace ~line 119)
- Modify: `emulator/HabboHotel/Items/InteractionTypes.cs` (string switch, before `default` ~line 216)
- Create: `emulator/HabboHotel/Items/Interactor/InteractorDressingBooth.cs`
- Modify: `emulator/HabboHotel/Items/Item.cs` (`Interactor` switch line 197-254; `UserWalksOnFurni` line 1109-1123; `UserWalksOffFurni` line 1125-1136)
- Modify: `emulator/HabboHotel/Rooms/RoomUserManager.cs` (`RemoveUserFromRoom`, inside `if (user != null)` block, before `RemoveRoomUser(user)` at line 304)

**Interfaces:**
- Consumes: `InClientLinkComposer(string)` from Task 1; existing `Item.LegacyDataString`, `Item.UpdateState(bool inDb, bool inRoom)`, `GameMap.GetRoomUsers(Point)`, `GameMap.GetCoordinatedItems(Point)`.
- Produces: `InteractionType.DressingBooth`, DB string `"dressing_booth"` (used by Task 3's SQL).

- [ ] **Step 1: Add the enum member**

In `emulator/HabboHotel/Items/InteractionType.cs`, after `Exchange` (last member):

```csharp
    Exchange,
    DressingBooth
}
```

- [ ] **Step 2: Add the string mapping**

In `emulator/HabboHotel/Items/InteractionTypes.cs`, before the `default:` case:

```csharp
            case "dressing_booth":
                return InteractionType.DressingBooth;
```

- [ ] **Step 3: Create the interactor (click no-op, pickup closes editor)**

`emulator/HabboHotel/Items/Interactor/InteractorDressingBooth.cs`:

```csharp
using System.Drawing;
using Plus.Communication.Packets.Outgoing.Avatar;
using Plus.HabboHotel.GameClients;

namespace Plus.HabboHotel.Items.Interactor;

public class InteractorDressingBooth : IFurniInteractor
{
    public void OnPlace(GameClient session, Item item) { }

    public void OnRemove(GameClient session, Item item)
    {
        // Booth picked up from under a standing user: close their editor.
        var room = item.GetRoom();
        if (room == null)
            return;
        foreach (var user in room.GetGameMap().GetRoomUsers(new Point(item.GetX, item.GetY)))
            user.GetClient()?.Send(new InClientLinkComposer("avatar-editor/hide"));
    }

    public void OnTrigger(GameClient session, Item item, int request, bool hasRights) { }

    public void OnWiredTrigger(Item item) { }
}
```

(`IFurniInteractor` has default no-op implementations, but keep the explicit no-ops for clarity alongside the real `OnRemove`. If `item.GetX`/`item.GetY` don't resolve, check the property names used at `RoomUserManager.cs:1192` — `item.GetX`/`item.GetY`.)

- [ ] **Step 4: Wire the interactor**

In `emulator/HabboHotel/Items/Item.cs`, in the `Interactor` switch before `case InteractionType.None:` (line 251):

```csharp
                case InteractionType.DressingBooth:
                    return new InteractorDressingBooth();
```

- [ ] **Step 5: Walk-on opens, walk-off closes**

In `emulator/HabboHotel/Items/Item.cs`, add a `using Plus.Communication.Packets.Outgoing.Avatar;` to the file's usings if absent.

In `UserWalksOnFurni`, after the tent line (1120), before the wired trigger:

```csharp
        if (Definition.InteractionType == InteractionType.DressingBooth)
        {
            LegacyDataString = "1";
            UpdateState(false, true);
            user.GetClient().Send(new InClientLinkComposer("avatar-editor/show"));
        }
```

In `UserWalksOffFurni`, after the tent removal (1134), before the wired trigger:

```csharp
        if (Definition.InteractionType == InteractionType.DressingBooth)
        {
            LegacyDataString = "0";
            UpdateState(false, true);
            user.GetClient().Send(new InClientLinkComposer("avatar-editor/hide"));
        }
```

- [ ] **Step 6: Room exit while inside a booth closes the editor**

In `emulator/HabboHotel/Rooms/RoomUserManager.cs`, inside `RemoveUserFromRoom`, in the `if (user != null)` block **before** `RemoveRoomUser(user);` (line 304):

```csharp
                // Dressing booth: the avatar editor is global client UI and would
                // survive the room change; close it and reopen the curtain.
                foreach (var tileItem in _room.GetGameMap().GetCoordinatedItems(new(user.X, user.Y)))
                {
                    if (tileItem.Definition.InteractionType != InteractionType.DressingBooth)
                        continue;
                    tileItem.LegacyDataString = "0";
                    tileItem.UpdateState(false, true);
                    session.Send(new InClientLinkComposer("avatar-editor/hide"));
                }
```

Add `using Plus.Communication.Packets.Outgoing.Avatar;` to the file's usings if absent (`Plus.HabboHotel.Items` is already used there).

- [ ] **Step 7: Verify emulator builds**

Run: `docker compose build emulator`
Expected: builds clean.

- [ ] **Step 8: Commit (emulator repo)**

```bash
cd emulator && git add HabboHotel/Items/InteractionType.cs HabboHotel/Items/InteractionTypes.cs HabboHotel/Items/Interactor/InteractorDressingBooth.cs HabboHotel/Items/Item.cs HabboHotel/Rooms/RoomUserManager.cs && git commit -m "feat: dressing_booth interaction - avatar editor gated to changing booths"
```

---

### Task 3: SQL update + apply to local DB

**Files:**
- Create: `emulator/Resources/SQLs/Updates/21_DressingBooths.sql`

**Interfaces:**
- Consumes: DB string `"dressing_booth"` from Task 2.
- Produces: the three booths (`boutique_changing1/2/3`) carry `interaction_type = 'dressing_booth'` locally; the numbered file is the prod replay artifact.

- [ ] **Step 1: Write the SQL update file**

`emulator/Resources/SQLs/Updates/21_DressingBooths.sql`:

```sql
-- Changing booths (Builders > Corporations > Clothing) become dressing booths:
-- standing in one auto-opens the Change Your Looks window (closes on step-off).
-- Previous value was 'pressure_tile', which the emulator never mapped (fell
-- back to None / generic switch).
-- Idempotent: safe to re-run.

UPDATE furniture SET interaction_type = 'dressing_booth'
WHERE item_name IN ('boutique_changing1', 'boutique_changing2', 'boutique_changing3');
```

- [ ] **Step 2: Apply to the local dev DB**

```bash
docker compose exec -T db sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" pixelrp' < emulator/Resources/SQLs/Updates/21_DressingBooths.sql
```

- [ ] **Step 3: Verify the rows**

```bash
docker compose exec -T db sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" pixelrp -e "SELECT item_name, interaction_type FROM furniture WHERE item_name LIKE \"boutique_changing%\";"'
```

Expected: all three rows show `dressing_booth`.

- [ ] **Step 4: Commit (emulator repo)**

```bash
cd emulator && git add Resources/SQLs/Updates/21_DressingBooths.sql && git commit -m "feat: SQL update 21 - boutique changing booths use dressing_booth interaction"
```

---

### Task 4: Remove client entry points

**Files:**
- Modify: `client/src/components/room/widgets/avatar-info/menu/AvatarInfoWidgetOwnAvatarView.tsx` (delete lines 54-56 and 133-135)
- Modify: `client/src/components/toolbar/ToolbarMeView.tsx` (delete line 47)

**Interfaces:**
- Consumes: nothing.
- Produces: no client-side way to open the avatar editor; the `avatar-editor/` `ILinkEventTracker` in `AvatarEditorView.tsx` remains untouched (the server packet drives it).

- [ ] **Step 1: Delete the context-menu item**

In `AvatarInfoWidgetOwnAvatarView.tsx` remove the action case (lines 54-56):

```tsx
                    case 'change_looks':
                        CreateLinkEvent('avatar-editor/show');
                        break;
```

and the menu entry (lines 133-135):

```tsx
                    <ContextMenuListItemView onClick={ event => processAction('change_looks') }>
                        { LocalizeText('widget.memenu.myclothes') }
                    </ContextMenuListItemView>
```

If `CreateLinkEvent` is now unreferenced in this file, remove it from the imports.

- [ ] **Step 2: Delete the toolbar clothing icon**

In `ToolbarMeView.tsx` remove line 47:

```tsx
            <Base pointer className="navigation-item icon icon-me-clothing" onClick={ event => CreateLinkEvent('avatar-editor/toggle') } />
```

`CreateLinkEvent` stays imported there (still used by lines 41, 46, 48).

- [ ] **Step 3: Lint**

Run: `cd client && yarn eslint src --ext .ts,.tsx`
Expected: no new errors (unused-import errors mean Step 1's import cleanup was missed).

- [ ] **Step 4: Commit (client repo)**

```bash
cd client && git add src/components/room/widgets/avatar-info/menu/AvatarInfoWidgetOwnAvatarView.tsx src/components/toolbar/ToolbarMeView.tsx && git commit -m "feat: remove My clothes menu item and toolbar clothing icon - editor is booth-driven"
```

---

### Task 5: Build, restart, in-game verification, changelog, parent bump

**Files:**
- Modify: `CHANGELOG.md` (parent repo — follow the existing entry format at the top of the file)

**Interfaces:**
- Consumes: everything above.
- Produces: verified feature; parent repo commit bumping both subrepos.

- [ ] **Step 1: Build the client bundle**

Run: `docker/nitro/build-client.sh`
Expected: exits 0 (read the script first if it takes arguments).

- [ ] **Step 2: Restart the stack pieces**

```bash
docker compose up -d --build emulator && docker compose restart web
```

(`web` restart is mandatory: nginx keeps proxying /ws to the old emulator container IP otherwise and clients hang at 100%.)

- [ ] **Step 3: In-game verification (as ClaudeTest)**

Mint a fresh SSO ticket and open the client (browser pane):
`docker compose exec -T cms php artisan tinker --execute='$u = \App\Models\User::where("username","ClaudeTest")->first(); echo $u->ssoTicket();'`
→ `http://localhost:8080/nitro-assets/client/index.html?sso=<ticket>`

Verify each, with screenshots:
1. Own-avatar context menu has no "My clothes" (Decorate Room / Dance / Actions / Signs remain).
2. Toolbar "Me" flyout has no clothing icon.
3. Place a changing booth (catalog: Builders > Corporations > Clothing — ClaudeTest is rank 7 so catalog is visible). Walk onto it: "Change Your Looks" opens, curtain closes (extradata state 1 — if the visual reads inverted, swap the `"1"`/`"0"` values in Item.cs Step 5 and RoomUserManager Step 6).
4. Walk off: window closes, curtain reopens.
5. Click the booth: nothing happens.
6. Stand in booth, pick it up (owner tools): window closes.
7. Stand in booth, leave the room (navigator): window closes.

- [ ] **Step 4: CHANGELOG entry (parent repo)**

Add under a `2026-08-10` heading, matching the file's existing style:

```markdown
- Changing booths (Builders > Corporations > Clothing) now open the Change Your
  Looks window automatically while you stand in them, and close it when you step
  out. The "My clothes" context-menu item and the toolbar clothing button are
  removed — booths are now the only way to change your look.
```

- [ ] **Step 5: Parent bump commit**

```bash
git add CHANGELOG.md client emulator && git commit -m "feat: bump client+emulator - avatar editor gated to changing booths"
```

(Include the plan/spec files if the repo convention is to commit them with the feature; the spec is already committed.)

- [ ] **Step 6: Prod note**

Do NOT deploy. Report to the user: deploy goes via `gh workflow run deploy.yml`, and `21_DressingBooths.sql` must be replayed against the prod DB at deploy time (data changes don't ship via git).

---

## Self-Review

- **Spec coverage:** context-menu removal (T4), toolbar removal (T4), auto open/close (T2 walk hooks), booth pickup (T2 interactor OnRemove), room exit (T2 Step 6), click no-op (T2 interactor), SQL + local apply + prod replay note (T3, T5), changelog (T5), testing list (T5) — all covered.
- **Deviation from spec:** SQL file number 21 (spec said 20; 20 was taken). Header 4106 confirmed free (camera ends at 4105).
- **Type consistency:** `InClientLinkComposer(string link)` used identically in T1/T2; `InteractionType.DressingBooth` / `"dressing_booth"` consistent across T2/T3.
- **Known accepted limitations (from spec):** forced repositioning bypassing `ProcessUserMovement` may skip walk-off; X-closing the window mid-booth requires re-entry.
