# Changing-Booth-Gated Avatar Editor — Design

**Date:** 2026-08-10
**Status:** Approved

## Goal

The "Change Your Looks" (avatar editor) window must only appear while a player is
standing in a changing booth (the three `boutique_changing*` furni sold on the
catalog page Builders > Corporations > Clothing, page id 912370). It opens
automatically on stepping into a booth and closes automatically on stepping out.
All other ways of opening it are removed.

## Current state (verified)

- Client entry points to the editor: the avatar context-menu item "My clothes"
  (`client/src/components/room/widgets/avatar-info/menu/AvatarInfoWidgetOwnAvatarView.tsx:133`,
  action `change_looks` → `CreateLinkEvent('avatar-editor/show')`) and the
  toolbar clothing icon
  (`client/src/components/toolbar/ToolbarMeView.tsx:47`, `avatar-editor/toggle`).
  No hotkeys, chat commands, or purchase hooks exist.
- The editor window (`client/src/components/avatar-editor/AvatarEditorView.tsx`)
  is toggled by `avatar-editor/show|hide|toggle` link events via an
  `ILinkEventTracker`.
- The nitro-renderer already parses server packet `InClientLink` (wire id
  **2023**) and dispatches its string payload as a link event
  (`SessionDataManager.onInClientLinkEvent`). The emulator has no composer for
  it yet.
- The three booths (`boutique_changing1/2/3`, furniture ids 710001996,
  710001997, 710002003) have `interaction_type = 'pressure_tile'`, which is
  **unmapped** in the emulator (`InteractionTypes.GetTypeFromString` only knows
  `pressure_pad`) and silently falls back to `InteractionType.None` /
  `InteractorGenericSwitch`. Standing on a booth currently does nothing;
  clicking cycles its 2 extradata states (curtain open/closed). There is no
  client-side pressure logic for these items.
- Emulator walk hooks: `RoomUserManager.ProcessUserMovement` calls
  `Item.UserWalksOffFurni(user)` for items on the old tile and
  `Item.UserWalksOnFurni(user)` for items on the new tile
  (`emulator/HabboHotel/Items/Item.cs:1109-1136`).
  `IFurniInteractor.OnWalkOn/OnWalkOff` are dead code — never called.

## Design

### Emulator

1. **New interaction type** `DressingBooth`, DB string `"dressing_booth"`
   (`InteractionType.cs`, `InteractionTypes.cs`).
2. **New composer** `InClientLinkComposer(string link)` under
   `Communication/Packets/Outgoing/` following the camera-packet recipe:
   - `ServerPacketHeader.InClientLinkComposer = 4106` (project custom range;
     camera used 4101–4105).
   - `Resources/Revisions/1.6.6.json`: `"InClientLinkComposer": 2023`.
   - Payload: single string.
3. **Walk hooks** in `Item.UserWalksOnFurni` / `UserWalksOffFurni`
   (alongside the existing tent handling):
   - On: if `Definition.InteractionType == DressingBooth` → set extradata
     `"1"`, broadcast the item update to the room, send
     `InClientLinkComposer("avatar-editor/show")` to the walking user only.
   - Off: extradata `"0"`, broadcast update, send
     `InClientLinkComposer("avatar-editor/hide")`.
4. **Click is a no-op** for `DressingBooth` (map to a do-nothing interactor in
   `Item.Interactor`) so players can't desync the curtain state.
5. **Edge cases:**
   - Booth picked up / removed while a user stands on it → send that user
     `avatar-editor/hide` (hook the room-item removal path).
   - User leaves the room while standing in a booth → send
     `avatar-editor/hide` on room exit (the editor is global UI and survives
     room changes otherwise).
   - Stepping directly from booth A onto adjacent booth B is safe: walk-off
     (hide) runs before walk-on (show) within the same step commit.
   - Forced repositioning that bypasses `ProcessUserMovement` (e.g. staff
     teleport commands) may skip the walk-off; accepted limitation.

### Client

- Delete the "My clothes" `ContextMenuListItemView` and the `change_looks`
  case in `AvatarInfoWidgetOwnAvatarView.tsx`.
- Delete the toolbar clothing icon in `ToolbarMeView.tsx` (removed for
  everyone, including staff — per user decision).
- No other client changes: the `avatar-editor/` link tracker and the window
  stay as-is; the server packet drives them.
- Accepted quirk: closing the window with X while still in the booth requires
  stepping off and back on to reopen it (classic Habbo behavior).

### Data

- New idempotent SQL update `emulator/Resources/SQLs/Updates/20_DressingBooths.sql`:
  `UPDATE furniture SET interaction_type = 'dressing_booth' WHERE item_name IN
  ('boutique_changing1','boutique_changing2','boutique_changing3');`
- Apply to the local dev DB immediately (furniture definitions are boot-time
  loaded → emulator restart required).
- Prod: replay the same SQL at deploy time (data changes don't ship via git);
  CHANGELOG.md entry required.

## Testing

Rebuild client and emulator images, restart the stack (including
`pixelrp-web-1`, else the ws proxy points at the dead emulator container),
log in as ClaudeTest and verify:

1. Avatar context menu has no "My clothes"; toolbar has no clothing icon.
2. Place a changing booth (buy from Builders > Corporations > Clothing);
   stepping on opens "Change Your Looks" and closes the curtain.
3. Stepping off closes the window and opens the curtain.
4. Clicking the booth does nothing.
5. Picking up the booth while standing on it closes the window.
6. Leaving the room while in the booth closes the window.
