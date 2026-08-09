# `:alert` Moderation Toast Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Spec: `docs/superpowers/specs/2026-08-09-moderation-alert-bubble-design.md`

**Goal:** Staff (rank ≥ 5) type `:alert <user> <message>` and that single user sees a red-tinted "Moderation" toast — same chrome, 45 s persistence, ×-only dismiss, and dynamic height as the `:ha` Platform toast.

**Architecture:** Repoint the stock `AlertCommand` from the `SendNotification` popup to a single-client `RoomNotificationComposer("mod.alert", {display: BUBBLE, message})`. Client routes `mod.alert` to a new `MODERATION` bubble type rendered by the existing `NotificationPlatformBubbleView` with a `moderation` modifier (red skin, "Moderation" badge). SQL 18 raises the permission to rank group 5.

**Tech Stack:** C#/.NET (PlusEMU fork, submodule `emulator/`, branch `pixelrp`), React/TypeScript Nitro client (submodule `client/`, branch `pixelrp`), MySQL 8, Vite, SCSS.

## Global Constraints

- Submodule commits on their `pixelrp` branches; root submodule bump + player-facing `CHANGELOG.md` entry in the same push; `git pull` the root repo before the bump.
- No test frameworks: test cycles are `docker compose build emulator` + boot to `EMULATOR -> READY!`, `yarn build`, and live browser verification via the SSO flow.
- Moderation toast: badge text exactly "Moderation", red tint subtle (danger red mixed into the dark base, same .95 opacity), 45 s timeout, ×-only dismiss — all inherited from the shared component; sent only to the target user.
- Stock behaviors kept: self-alert → "Get a life." whisper; sender confirmation whisper; `MustBeInSameRoom => false`; `ITargetChatCommand` target resolution (offline-user whisper handled by `CommandManager`).
- `:ha` Platform toast and all other bubbles unchanged.
- Deployed client lives in `nitro/client/` (gitignored): after `yarn build`, copy `client/dist/*` over it, PRESERVING the live `renderer-config.json` and `ui-config.json`. Prod client deploy is rsync excluding those two files.

---

### Task 1: Emulator — repoint AlertCommand + SQL 18

**Files:**
- Modify: `emulator/HabboHotel/Rooms/Chat/Commands/Moderator/AlertCommand.cs`
- Create: `emulator/Resources/SQLs/Updates/18_AlertUserRank5.sql`

**Interfaces:**
- Consumes: existing `RoomNotificationComposer(string type, Dictionary<string, string> values)`, `ITargetChatCommand` (CommandManager strips the username from `parameters` before `Execute`, so `CommandManager.MergeParams(parameters)` is the message only).
- Produces: server sends type `"mod.alert"` with `display=BUBBLE` + `message` to the target client only (Task 2's client routing depends on the exact string `mod.alert`).

**Steps:**

- [ ] **Step 1: Rewrite `AlertCommand.cs`** so the file reads exactly:

```csharp
using Plus.Communication.Packets.Outgoing.Rooms.Notifications;
using Plus.HabboHotel.GameClients;
using Plus.HabboHotel.Users;

namespace Plus.HabboHotel.Rooms.Chat.Commands.Moderator;

internal class AlertCommand : ITargetChatCommand
{
    public string Key => "alert";
    public string PermissionRequired => "command_alert_user";

    public string Parameters => "%username% %Messages%";

    public string Description => "Alert a user with a bubble notification.";

    public bool MustBeInSameRoom => false;

    public Task Execute(GameClient session, Room room, Habbo habbo, string[] parameters)
    {
        if (habbo.Username == session.GetHabbo().Username)
        {
            session.SendWhisper("Get a life.");
            return Task.CompletedTask;
        }
        var message = CommandManager.MergeParams(parameters);
        // pixelrp: delivered as the client's Moderation toast (red-tinted
        // Platform bubble), not the modal popup.
        habbo.Client.Send(new RoomNotificationComposer("mod.alert",
            new Dictionary<string, string> { { "display", "BUBBLE" }, { "message", message } }));
        session.SendWhisper($"Alert successfully sent to {habbo.Username}");
        return Task.CompletedTask;
    }
}
```

- [ ] **Step 2: Create `emulator/Resources/SQLs/Updates/18_AlertUserRank5.sql`:**

```sql
-- :alert single-user moderation toast restricted to staff (rank >= 5),
-- matching the project's staff convention. Stock mapping was 2.
UPDATE `permissions_commands` SET `group_id` = '5' WHERE `command` = 'command_alert_user';
```

- [ ] **Step 3: Build, apply SQL, restart** (permissions load at boot):

```bash
docker compose build emulator 2>&1 | tail -3
docker compose up -d emulator
docker compose exec -T db mysql -upixelrp -p"changeme-local" pixelrp < emulator/Resources/SQLs/Updates/18_AlertUserRank5.sql
docker compose exec -T db mysql -upixelrp -p"changeme-local" pixelrp -e "SELECT command, group_id FROM permissions_commands WHERE command='command_alert_user';"
docker compose restart emulator
```

Expected: clean build; SELECT shows `group_id = 5`; `docker compose logs emulator | tail -5` shows `EMULATOR -> READY!` after restart.

- [ ] **Step 4: Commit on the emulator submodule (branch `pixelrp`):**

```bash
git -C emulator add HabboHotel/Rooms/Chat/Commands/Moderator/AlertCommand.cs Resources/SQLs/Updates/18_AlertUserRank5.sql
git -C emulator commit -m "feat(commands): :alert sends single-user Moderation bubble; staff rank 5+"
```

### Task 2: Client — MODERATION skin

**Files:**
- Modify: `client/src/api/notification/NotificationBubbleType.ts`
- Modify: `client/src/hooks/notification/useNotification.ts` (BUBBLE branch of `showNotification`)
- Modify: `client/src/components/notification-center/views/bubble-layouts/NotificationPlatformBubbleView.tsx`
- Modify: `client/src/components/notification-center/views/bubble-layouts/GetBubbleLayout.tsx`
- Modify: `client/src/components/notification-center/NotificationCenterView.scss`

**Interfaces:**
- Consumes: `NotificationBubbleType.PLATFORM` and the platform view/styles from the `:ha` work; server type string `"mod.alert"` from Task 1.
- Produces: `NotificationBubbleType.MODERATION = 'moderation'`; `NotificationPlatformBubbleView` renders both PLATFORM and MODERATION items.

**Steps:**

- [ ] **Step 1: Add the type constant** in `NotificationBubbleType.ts`, after the `PLATFORM` line:

```typescript
    public static MODERATION: string = 'moderation';
```

- [ ] **Step 2: Route `mod.alert` in `useNotification.ts`.** Replace the BUBBLE branch body so it reads:

```typescript
        if(options.get('display') === 'BUBBLE')
        {
            if(type === 'hotel.alert')
            {
                // platform announcements: dedicated layout, never an image (the
                // generic path synthesizes …/hotel_alert.png which 404s)
                showSingleBubble(LocalizeText(message), NotificationBubbleType.PLATFORM);
            }
            else if(type === 'mod.alert')
            {
                // single-user moderation alerts: same layout, red skin, no image
                showSingleBubble(LocalizeText(message), NotificationBubbleType.MODERATION);
            }
            else
            {
                showSingleBubble(LocalizeText(message), NotificationBubbleType.INFO, image, linkUrl);
            }
        }
```

- [ ] **Step 3: Generalize `NotificationPlatformBubbleView.tsx`** so the file reads exactly:

```tsx
import { FC } from 'react';
import { NotificationBubbleItem, NotificationBubbleType } from '../../../../api';
import { Base, Flex, LayoutNotificationBubbleView, LayoutNotificationBubbleViewProps, Text } from '../../../../common';

export interface NotificationPlatformBubbleViewProps extends LayoutNotificationBubbleViewProps
{
    item: NotificationBubbleItem;
}

export const NotificationPlatformBubbleView: FC<NotificationPlatformBubbleViewProps> = props =>
{
    const { item = null, onClose = null, ...rest } = props;

    const isModeration = (item.notificationType === NotificationBubbleType.MODERATION);
    const htmlText = item.message.replace(/\r\n|\r|\n/g, '<br />');

    return (
        <LayoutNotificationBubbleView onClose={ onClose } timeoutMs={ 45000 } column gap={ 1 } classNames={ isModeration ? [ 'platform', 'moderation' ] : [ 'platform' ] } onClick={ null } { ...rest }>
            <Flex justifyContent="between" alignItems="center" fullWidth>
                <Base className="platform-badge no-select">{ isModeration ? 'Moderation' : 'Platform' }</Base>
                <Base pointer className="platform-close no-select" onClick={ event => onClose() }>×</Base>
            </Flex>
            <Text wrap fullWidth variant="white" dangerouslySetInnerHTML={ { __html: htmlText } } />
        </LayoutNotificationBubbleView>
    );
}
```

- [ ] **Step 4: Register the case** in `GetBubbleLayout.tsx`, below the PLATFORM case:

```tsx
        case NotificationBubbleType.MODERATION:
            return <NotificationPlatformBubbleView { ...props } />
```

- [ ] **Step 5: SCSS.** In `NotificationCenterView.scss`, after the `.nitro-notification-bubble.platform { … }` block add:

```scss
.nitro-notification-bubble.platform.moderation {
    background-color: rgba(mix($danger, $dark, 25%), .95);

    .platform-badge {
        color: rgba(mix($danger, $white, 40%), .9);
        border-color: rgba(mix($danger, $white, 40%), .45);
    }
}
```

- [ ] **Step 6: Build and deploy locally** (backups in the SDD workspace directory):

```bash
cd client && yarn build 2>&1 | tail -2 && cd ..
cp nitro/client/renderer-config.json nitro/client/ui-config.json <workspace-dir>/
cp -R client/dist/* nitro/client/
cp <workspace-dir>/renderer-config.json <workspace-dir>/ui-config.json nitro/client/
```

- [ ] **Step 7: Commit on the client submodule (branch `pixelrp`):**

```bash
git -C client add src/api/notification/NotificationBubbleType.ts src/hooks/notification/useNotification.ts src/components/notification-center/views/bubble-layouts/NotificationPlatformBubbleView.tsx src/components/notification-center/views/bubble-layouts/GetBubbleLayout.tsx src/components/notification-center/NotificationCenterView.scss
git -C client commit -m "feat(notifications): Moderation skin for single-user alerts on the Platform toast"
```

### Task 3: Live verification (local dev)

**Files:** none.

SSO login mechanic and the reliable chat-send snippet are as in the previous plan: mint `auth_ticket` in the DB, open `http://localhost:8080/nitro-assets/client/index.html?sso=<ticket>`, set the chat input value via the native setter + `input` event, then dispatch `new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })` on the input.

**Steps:**

- [ ] **Step 1: Targeted delivery.** Session A: Admin (rank 9). Session B (second tab): ClaudeTest. From A: `:alert ClaudeTest Please review the room rules`. Expected: B shows a toast with class `nitro-notification-bubble platform moderation`, badge text "Moderation", red-tinted background (assert `getComputedStyle(...).backgroundColor` differs from a `:ha` bubble's), no `<img>`; A shows NO toast but receives the whisper "Alert successfully sent to ClaudeTest". Screenshot B.
- [ ] **Step 2: Self-alert guard.** From A: `:alert Admin hi` → whisper "Get a life.", no toast anywhere.
- [ ] **Step 3: Rank gate.** From B (ClaudeTest, rank 1): `:alert Admin hey` → no toast on A; message falls through to normal chat (rank 1 lacks `command_alert_user` at group 5).
- [ ] **Step 4: Platform regression.** From A: `:ha Regression check` → BOTH sessions show the untinted Platform toast (badge "Platform", no `moderation` class).
- [ ] **Step 5: Logs.** `docker compose logs emulator --tail 30` — no exceptions.

### Task 4: Changelog, bumps, push, prod deploy

**Files:**
- Modify: `CHANGELOG.md`
- Modify: root submodule pointers for `emulator/` and `client/`

**Steps:**

- [ ] **Step 1: Push both submodules:**

```bash
git -C emulator push origin pixelrp
git -C client push origin pixelrp
```

- [ ] **Step 2: Changelog.** In the `## 2026-08-09 — The hotel found its tannoy` section's `### Added` list, append:

```markdown
- **Personal alerts from the team.** Staff can now send a notice to a single
  player. It shows up as the same corner toast as hotel announcements, but
  tinted red with a "Moderation" label so you know it's meant just for you.
```

- [ ] **Step 3: Pull, bump, push main:**

```bash
git pull -q
git add emulator client CHANGELOG.md
git commit -m "chore: bump emulator + client (:alert as single-user Moderation toast)"
git push
```

- [ ] **Step 4: Prod deploy** (client rsync, emulator rebuild, SQL 18):

```bash
rsync -az --exclude 'renderer-config.json' --exclude 'ui-config.json' nitro/client/ root@67.219.109.182:/opt/pixelrp/nitro/client/
ssh root@67.219.109.182 'cd /opt/pixelrp && git pull -q origin main && git submodule update --init emulator && git -C emulator log --oneline -1'
ssh root@67.219.109.182 'cd /opt/pixelrp && . ./.env 2>/dev/null; docker compose -f compose.yaml -f compose.prod.yaml exec -T db mysql -upixelrp -p"$DB_PASSWORD" pixelrp < emulator/Resources/SQLs/Updates/18_AlertUserRank5.sql && docker compose -f compose.yaml -f compose.prod.yaml exec -T db mysql -upixelrp -p"$DB_PASSWORD" pixelrp -e "SELECT command, group_id FROM permissions_commands WHERE command=\"command_alert_user\";"'
ssh root@67.219.109.182 'cd /opt/pixelrp && docker compose -f compose.yaml -f compose.prod.yaml build emulator 2>&1 | tail -2 && docker compose -f compose.yaml -f compose.prod.yaml up -d emulator'
```

Expected: prod SELECT shows `group_id = 5`; prod logs show `EMULATOR -> READY!`. Note the emulator restart briefly disconnects online players.

- [ ] **Step 5: Prod spot-check.** Fresh prod client load (confirm the new bundle hash in index.html changed from `index-37656d01.js`); staff sends `:alert <someone> test` when convenient — or confirm receive-side by having the user alert the Claude account while a session is open.
