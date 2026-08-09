# Mod Tools Toast Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Spec: `docs/superpowers/specs/2026-08-09-modtools-toast-alerts-design.md`

**Goal:** All Mod Tools alerts render as toasts: user-facing mod actions (message, caution, mute, trade-ban, kick message) as the red Moderation toast — now persistent until × — and Room Info alerts as a new blue "Information" toast.

**Architecture:** Emulator gains a `SendModerationAlert` extension (sends `RoomNotificationComposer("mod.alert", {display: BUBBLE, message})`) swapped into the five target-facing mod-action sites; `ModeratorActionEvent` broadcasts `room.alert` to the room. Client adds `INFORMATION` type + blue skin and refactors the shared toast view to a variant table (badge/skin/persistence per type); MODERATION variants pass `fadesOut={false}`.

**Tech Stack:** C#/.NET (PlusEMU fork, submodule `emulator/`, branch `pixelrp`), React/TypeScript Nitro client (submodule `client/`, branch `pixelrp`), Vite, SCSS.

## Global Constraints

- Submodule commits on their `pixelrp` branches. **Local-only deploy — do NOT touch prod** (no rsync, no VPS ssh). Root bump + player-facing CHANGELOG entry in the same push; `git pull` root before the bump.
- Persistence rule: MODERATION toasts never auto-dismiss (`fadesOut={false}`, × is the only dismiss). PLATFORM and INFORMATION keep 45 s + ×-only dismiss.
- Badge texts exactly: "Platform", "Moderation", "Information".
- Moderator-facing error whispers/popups ("Oops, you cannot…", kick "disallowed" popup) unchanged. `:ha`/`:alert` behavior unchanged except `:alert` inheriting persistence.
- No test frameworks: `docker compose build emulator` + boot READY, `yarn build`, live browser verification via the SSO flow.
- Deployed client is `nitro/client/` (gitignored): copy `client/dist/*` over it PRESERVING `renderer-config.json` and `ui-config.json`.

---

### Task 1: Emulator — SendModerationAlert + handler swaps

**Files:**
- Modify: `emulator/HabboHotel/GameClients/GameClientExtensions.cs`
- Modify: `emulator/Communication/Packets/Incoming/Moderation/ModerationMsgEvent.cs`
- Modify: `emulator/Communication/Packets/Incoming/Moderation/ModerationCautionEvent.cs`
- Modify: `emulator/Communication/Packets/Incoming/Moderation/ModerationMuteEvent.cs`
- Modify: `emulator/Communication/Packets/Incoming/Moderation/ModerationTradeLockEvent.cs`
- Modify: `emulator/Communication/Packets/Incoming/Moderation/ModerationKickEvent.cs`
- Modify: `emulator/Communication/Packets/Incoming/Moderation/ModeratorActionEvent.cs`

**Interfaces:**
- Consumes: existing `RoomNotificationComposer(string type, Dictionary<string, string> values)`.
- Produces: `SendModerationAlert(this GameClient client, string message)`; wire types `"mod.alert"` (already routed client-side) and `"room.alert"` (Task 2 routes it).

**Steps:**

- [ ] **Step 1: Extension.** In `GameClientExtensions.cs`, add `using Plus.Communication.Packets.Outgoing.Rooms.Notifications;` to the usings, and after the `SendNotification` line add:

```csharp
    // pixelrp: user-facing moderation alerts render as the client's persistent
    // red Moderation toast (mod.alert, display=BUBBLE), not the modal popup.
    public static void SendModerationAlert(this GameClient client, string message) => client.Send(new RoomNotificationComposer("mod.alert",
        new Dictionary<string, string> { { "display", "BUBBLE" }, { "message", message } }));
```

- [ ] **Step 2: Swap the four notification sites.** Replace exactly these lines (each file has one):
  - `ModerationMsgEvent.cs`: `client.SendNotification(message);` → `client.SendModerationAlert(message);`
  - `ModerationCautionEvent.cs`: `client.SendNotification(message);` → `client.SendModerationAlert(message);`
  - `ModerationMuteEvent.cs`: `habbo.Client.SendNotification($"You have been muted by a moderator for {length} seconds!");` → `habbo.Client.SendModerationAlert($"You have been muted by a moderator for {length} seconds!");`
  - `ModerationTradeLockEvent.cs`: `habbo.Client.SendNotification($"You have been trade banned for {days} day(s)!\r\rReason:\r\r{message}");` → `habbo.Client.SendModerationAlert($"You have been trade banned for {days} day(s)!\r\rReason:\r\r{message}");`

- [ ] **Step 3: Kick delivers its message.** In `ModerationKickEvent.cs`, change `packet.ReadString(); //message` to `var message = packet.ReadString();`, and immediately BEFORE the `session.GetHabbo().CurrentRoom?.GetRoomUserManager().RemoveUserFromRoom(client, true);` line insert:

```csharp
        // pixelrp: the kick message used to be read and discarded — deliver it.
        if (!string.IsNullOrWhiteSpace(message))
            client.SendModerationAlert(message);
```

  The moderator-facing `session.SendNotification(_languageManager.TryGetValue("moderation.kick.disallowed"));` stays as the popup.

- [ ] **Step 4: Room alert.** In `ModeratorActionEvent.cs`, replace the four lines

```csharp
        var alertMode = packet.ReadInt();
        var alertMessage = packet.ReadString();
        var isCaution = alertMode != 3;
        alertMessage = isCaution ? $"Caution from Moderator:\n\n{alertMessage}" : $"Message from Moderator:\n\n{alertMessage}";
        session.GetHabbo().CurrentRoom.SendPacket(new BroadcastMessageAlertComposer(alertMessage));
```

  with:

```csharp
        packet.ReadInt(); // alert mode (caution/message) — same toast either way
        var alertMessage = packet.ReadString();
        // pixelrp: room alerts render as the blue Information toast for everyone
        // in the room; the badge replaces the old "from Moderator" prefixes.
        currentRoom.SendPacket(new RoomNotificationComposer("room.alert",
            new Dictionary<string, string> { { "display", "BUBBLE" }, { "message", alertMessage } }));
```

  Replace `using Plus.Communication.Packets.Outgoing.Moderation;` with `using Plus.Communication.Packets.Outgoing.Rooms.Notifications;` (BroadcastMessageAlertComposer is no longer referenced in this file).

- [ ] **Step 5: Build + boot:**

```bash
docker compose build emulator 2>&1 | tail -3
docker compose up -d emulator
```

Expected: clean build; `docker compose logs emulator | tail -5` shows `EMULATOR -> READY!`.

- [ ] **Step 6: Commit (emulator submodule, branch `pixelrp`):**

```bash
git -C emulator add HabboHotel/GameClients/GameClientExtensions.cs Communication/Packets/Incoming/Moderation/
git -C emulator commit -m "feat(moderation): mod-tools alerts as toasts - mod.alert to targets, room.alert to rooms, kick message delivered"
```

### Task 2: Client — INFORMATION skin + persistent Moderation

**Files:**
- Modify: `client/src/api/notification/NotificationBubbleType.ts`
- Modify: `client/src/hooks/notification/useNotification.ts`
- Modify: `client/src/components/notification-center/views/bubble-layouts/NotificationPlatformBubbleView.tsx`
- Modify: `client/src/components/notification-center/views/bubble-layouts/GetBubbleLayout.tsx`
- Modify: `client/src/components/notification-center/NotificationCenterView.scss`

**Interfaces:**
- Consumes: wire types `hotel.alert`/`mod.alert`/`room.alert`; `LayoutNotificationBubbleView`'s existing `fadesOut` prop (its timeout effect early-returns when `fadesOut` is false).
- Produces: `NotificationBubbleType.INFORMATION = 'information'`; variant-table toast view.

**Steps:**

- [ ] **Step 1: Type constant.** In `NotificationBubbleType.ts` after the `MODERATION` line:

```typescript
    public static INFORMATION: string = 'information';
```

- [ ] **Step 2: Routing.** In `useNotification.ts`, in the BUBBLE branch, after the `mod.alert` else-if block add:

```typescript
            else if(type === 'room.alert')
            {
                // room-wide moderation info: same layout, blue skin, no image
                showSingleBubble(LocalizeText(message), NotificationBubbleType.INFORMATION);
            }
```

- [ ] **Step 3: Variant-table view.** Replace `NotificationPlatformBubbleView.tsx` entirely with:

```tsx
import { FC } from 'react';
import { NotificationBubbleItem, NotificationBubbleType } from '../../../../api';
import { Base, Flex, LayoutNotificationBubbleView, LayoutNotificationBubbleViewProps, Text } from '../../../../common';

interface ToastVariant
{
    badge: string;
    classNames: string[];
    persistent: boolean;
}

const TOAST_VARIANTS: { [key: string]: ToastVariant } = {
    [NotificationBubbleType.PLATFORM]: { badge: 'Platform', classNames: [ 'platform' ], persistent: false },
    [NotificationBubbleType.MODERATION]: { badge: 'Moderation', classNames: [ 'platform', 'moderation' ], persistent: true },
    [NotificationBubbleType.INFORMATION]: { badge: 'Information', classNames: [ 'platform', 'information' ], persistent: false }
};

export interface NotificationPlatformBubbleViewProps extends LayoutNotificationBubbleViewProps
{
    item: NotificationBubbleItem;
}

export const NotificationPlatformBubbleView: FC<NotificationPlatformBubbleViewProps> = props =>
{
    const { item = null, onClose = null, ...rest } = props;

    const variant = (TOAST_VARIANTS[item.notificationType] || TOAST_VARIANTS[NotificationBubbleType.PLATFORM]);
    const htmlText = item.message.replace(/\r\n|\r|\n/g, '<br />');

    return (
        <LayoutNotificationBubbleView onClose={ onClose } fadesOut={ !variant.persistent } timeoutMs={ 45000 } column gap={ 1 } classNames={ variant.classNames } onClick={ null } { ...rest }>
            <Flex justifyContent="between" alignItems="center" fullWidth>
                <Base className="platform-badge no-select">{ variant.badge }</Base>
                <Base pointer className="platform-close no-select" onClick={ event => onClose() }>×</Base>
            </Flex>
            <Text wrap fullWidth variant="white" dangerouslySetInnerHTML={ { __html: htmlText } } />
        </LayoutNotificationBubbleView>
    );
}
```

- [ ] **Step 4: Layout case.** In `GetBubbleLayout.tsx`, below the MODERATION case:

```tsx
        case NotificationBubbleType.INFORMATION:
            return <NotificationPlatformBubbleView { ...props } />
```

- [ ] **Step 5: SCSS.** After the `.nitro-notification-bubble.platform.moderation { … }` block:

```scss
.nitro-notification-bubble.platform.information {
    background-color: rgba(mix($info, $dark, 25%), .95);

    .platform-badge {
        color: rgba(mix($info, $white, 40%), .9);
        border-color: rgba(mix($info, $white, 40%), .45);
    }
}
```

- [ ] **Step 6: Build + local deploy** (backups in the SDD workspace dir):

```bash
cd client && yarn build 2>&1 | tail -2 && cd ..
cp nitro/client/renderer-config.json nitro/client/ui-config.json <workspace-dir>/
cp -R client/dist/* nitro/client/
cp <workspace-dir>/renderer-config.json <workspace-dir>/ui-config.json nitro/client/
```

- [ ] **Step 7: Commit (client submodule, branch `pixelrp`):**

```bash
git -C client add src/api/notification/NotificationBubbleType.ts src/hooks/notification/useNotification.ts src/components/notification-center/views/bubble-layouts/NotificationPlatformBubbleView.tsx src/components/notification-center/views/bubble-layouts/GetBubbleLayout.tsx src/components/notification-center/NotificationCenterView.scss
git -C client commit -m "feat(notifications): Information skin, variant table, persistent Moderation toasts"
```

### Task 3: Live verification (local dev)

**Files:** none.

SSO login + reliable chat/UI driving as in prior plans (mint `auth_ticket`, native value setter + synthetic Enter for chat; the Mod Tools panels are driven by clicking the toolbar mod-tools icon then the panel buttons — read_page/computer tools).

**Steps:**

- [ ] **Step 1: Setup.** Session A: Admin (rank 9). Session B: ClaudeTest. Both in the same room (ClaudeTest spawns in the landing room with Admin).
- [ ] **Step 2: Mod message.** A: open Mod Tools → user info for ClaudeTest (click ClaudeTest's avatar → mod action / or the mod-tools user search) → send message "Please behave". Expected: B shows red `platform moderation` toast, badge "Moderation"; toast STILL PRESENT after 50 s (persistence); × closes it.
- [ ] **Step 3: Caution.** A: send caution "Formal caution" → same persistent red toast on B; `user_info.cautions` incremented for ClaudeTest (`SELECT cautions FROM user_info WHERE user_id = (SELECT id FROM users WHERE username='ClaudeTest');`).
- [ ] **Step 4: Mute.** A: mod-action mute ClaudeTest (shortest option) → B gets persistent red toast "You have been muted by a moderator for N seconds!". Unmute: `UPDATE users SET time_muted=0 WHERE username='ClaudeTest';` then `docker compose restart` NOT needed (in-memory: have B relog if chat needed later).
- [ ] **Step 5: Kick with message.** A: kick ClaudeTest with message "Kick reason test" → B gets the persistent red toast AND is removed from the room. Relog B afterwards.
- [ ] **Step 6: Room alert.** A: Mod Tools → room info (current room) → send alert "Room information test". Expected: BOTH sessions show a BLUE `platform information` toast, badge "Information", message verbatim (no "Caution from Moderator:" prefix), auto-dismisses ~45 s, background differs from both the dark Platform and red Moderation values (compare `getComputedStyle` backgroundColor).
- [ ] **Step 7: Regressions.** `:ha Reg check` → Platform toast (45 s). `:alert ClaudeTest reg` → red toast now PERSISTENT (>50 s). Moderator-facing guards intact (e.g. `:alert` from rank 1 still falls to chat). `docker compose logs emulator --tail 30` clean.

### Task 4: Changelog + push (NO prod deploy)

**Files:**
- Modify: `CHANGELOG.md`
- Modify: root submodule pointers for `emulator/` and `client/`

**Steps:**

- [ ] **Step 1: Push submodules:**

```bash
git -C emulator push origin pixelrp
git -C client push origin pixelrp
```

- [ ] **Step 2: Changelog.** In the `## 2026-08-09 — The hotel found its tannoy` section's `### Added` list, append:

```markdown
- **Moderation caught up with the new toasts.** Messages, cautions, mute and
  trade-ban notices from the moderation team — and the reason when you're
  kicked from a room — now arrive as the red "Moderation" toast, which stays
  on screen until you close it. Room-wide notices appear as a blue
  "Information" toast for everyone in the room.
```

- [ ] **Step 3: Pull, bump, push main:**

```bash
git pull -q
git add emulator client CHANGELOG.md
git commit -m "chore: bump emulator + client (mod-tools alerts as toasts)"
git push
```

- [ ] **Step 4: Confirm NO prod changes** — do not rsync, do not ssh to the VPS. Prod ships later on request.
