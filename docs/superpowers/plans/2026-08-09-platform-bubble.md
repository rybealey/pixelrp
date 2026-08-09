# Platform Bubble Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Spec: `docs/superpowers/specs/2026-08-09-platform-bubble-design.md`

**Goal:** `:ha` hotel alerts render as a dedicated "Platform" toast — no broken image, "Platform" badge, subtle × close, 45 s persistence, content-driven height — leaving every other notification untouched.

**Architecture:** Client-only. Route `hotel.alert` BUBBLE notifications to a new `NotificationBubbleType.PLATFORM` (no image argument, killing the synthesized-URL 404), rendered by a new `NotificationPlatformBubbleView` registered in `GetBubbleLayout`, styled via a `.platform` modifier on the existing bubble chrome.

**Tech Stack:** React/TypeScript (nitro-react fork, submodule `client/`, branch `pixelrp`), Vite build, SCSS. Emulator unchanged.

## Global Constraints

- Client commits go on `client/` branch `pixelrp`; after pushing, bump the root submodule pointer and add a player-facing `CHANGELOG.md` entry in the same push. `git pull` the root repo before the bump — another session pushed to main recently.
- No test framework in the client: test cycle is `yarn build` + live browser verification on the local stack.
- Platform bubbles: 45 s timeout, × is the ONLY dismiss control (container `onClick` overridden to null), badge text exactly "Platform", no image element ever.
- All other bubbles (INFO/moderation notice, respect, achievement, club gift) keep current behavior: 8 s, click-anywhere-to-close, existing layouts.
- The deployed client lives in `nitro/client/` (gitignored): after `yarn build`, copy `client/dist/*` over it but PRESERVE the live `renderer-config.json` and `ui-config.json` (back them up first, restore after). Prod deploy is rsync of `nitro/client/` excluding those two files.

---

### Task 1: Client changes + build + local deploy

**Files:**
- Modify: `client/src/api/notification/NotificationBubbleType.ts`
- Modify: `client/src/hooks/notification/useNotification.ts` (the `display === 'BUBBLE'` branch inside `showNotification`, ~line 95)
- Create: `client/src/components/notification-center/views/bubble-layouts/NotificationPlatformBubbleView.tsx`
- Modify: `client/src/components/notification-center/views/bubble-layouts/GetBubbleLayout.tsx`
- Modify: `client/src/components/notification-center/NotificationCenterView.scss`

**Interfaces:**
- Consumes: existing `showSingleBubble(message, type)` (imageUrl/link default null), `LayoutNotificationBubbleView` props (`timeoutMs`, `onClose`, spreads the rest onto `Flex`, so `column`/`onClick` pass through and a passed `onClick` overrides the default close-on-click), `NotificationBubbleItem` (`.message`), `Flex`'s `column` prop, `Base`/`Text` from `common`.
- Produces: `NotificationBubbleType.PLATFORM = 'platform'`; `NotificationPlatformBubbleView` (same props shape as `NotificationDefaultBubbleView`).

**Steps:**

- [ ] **Step 1: Add the type constant.** In `NotificationBubbleType.ts`, after the `INFO` line add:

```typescript
    public static PLATFORM: string = 'platform';
```

- [ ] **Step 2: Route hotel.alert in `useNotification.ts`.** Replace the existing BUBBLE branch body:

```typescript
        if(options.get('display') === 'BUBBLE')
        {
            if(type === 'hotel.alert')
            {
                // platform announcements: dedicated layout, never an image (the
                // generic path synthesizes …/hotel_alert.png which 404s)
                showSingleBubble(LocalizeText(message), NotificationBubbleType.PLATFORM);
            }
            else
            {
                showSingleBubble(LocalizeText(message), NotificationBubbleType.INFO, image, linkUrl);
            }
        }
```

- [ ] **Step 3: Create `NotificationPlatformBubbleView.tsx`:**

```tsx
import { FC } from 'react';
import { NotificationBubbleItem } from '../../../../api';
import { Base, Flex, LayoutNotificationBubbleView, LayoutNotificationBubbleViewProps, Text } from '../../../../common';

export interface NotificationPlatformBubbleViewProps extends LayoutNotificationBubbleViewProps
{
    item: NotificationBubbleItem;
}

export const NotificationPlatformBubbleView: FC<NotificationPlatformBubbleViewProps> = props =>
{
    const { item = null, onClose = null, ...rest } = props;

    const htmlText = item.message.replace(/\r\n|\r|\n/g, '<br />');

    return (
        <LayoutNotificationBubbleView onClose={ onClose } timeoutMs={ 45000 } column gap={ 1 } classNames={ [ 'platform' ] } onClick={ null } { ...rest }>
            <Flex justifyContent="between" alignItems="center" fullWidth>
                <Base className="platform-badge no-select">Platform</Base>
                <Base pointer className="platform-close no-select" onClick={ event => onClose() }>×</Base>
            </Flex>
            <Text wrap fullWidth variant="white" dangerouslySetInnerHTML={ { __html: htmlText } } />
        </LayoutNotificationBubbleView>
    );
}
```

  (`onClick={ null }` overrides the layout's default close-on-any-click because the spread comes after the default; the × is then the only dismiss control. `column` makes height content-driven.)

- [ ] **Step 4: Register the layout.** In `GetBubbleLayout.tsx` add the import and a case above `default`:

```tsx
import { NotificationPlatformBubbleView } from './NotificationPlatformBubbleView';
```

```tsx
        case NotificationBubbleType.PLATFORM:
            return <NotificationPlatformBubbleView { ...props } />
```

- [ ] **Step 5: SCSS.** In `NotificationCenterView.scss`, after the `.nitro-notification-bubble { … }` block add:

```scss
.nitro-notification-bubble.platform {
    .platform-badge {
        font-size: 9px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: .08em;
        color: rgba($white, .75);
        border: 1px solid rgba($white, .35);
        border-radius: 3px;
        padding: 1px 5px;
    }

    .platform-close {
        color: rgba($white, .5);
        font-size: 14px;
        line-height: 1;
        padding: 0 2px;

        &:hover {
            color: $white;
        }
    }
}
```

- [ ] **Step 6: Build and deploy locally** (from the repo root):

```bash
cd client && yarn build 2>&1 | tail -2 && cd ..
cp nitro/client/renderer-config.json nitro/client/ui-config.json /tmp-scratch-or-workspace/
cp -R client/dist/* nitro/client/
cp /tmp-scratch-or-workspace/renderer-config.json /tmp-scratch-or-workspace/ui-config.json nitro/client/
```

  (Use the session scratchpad or the SDD workspace directory for the two backups — any writable temp dir. Expected: `✓ built in …s`, then `nitro/client/index.html` mtime is now.)

- [ ] **Step 7: Commit on the client submodule (branch `pixelrp`):**

```bash
git -C client add src/api/notification/NotificationBubbleType.ts src/hooks/notification/useNotification.ts src/components/notification-center/views/bubble-layouts/NotificationPlatformBubbleView.tsx src/components/notification-center/views/bubble-layouts/GetBubbleLayout.tsx src/components/notification-center/NotificationCenterView.scss
git -C client commit -m "feat(notifications): Platform bubble for hotel alerts - badge, 45s, x-only close, no image"
```

### Task 2: Live verification (local dev)

**Files:** none.

Login mechanic (NEVER type passwords): mint an SSO ticket
(`docker compose exec -T db mysql -upixelrp -p"changeme-local" pixelrp -e "UPDATE users SET auth_ticket='<fresh-random>' WHERE username='Admin';"`), open `http://localhost:8080/nitro-assets/client/index.html?sso=<ticket>`. To send chat reliably from the browser tools, set the input value natively and dispatch a synthetic Enter:

```js
const input = document.querySelector('input[placeholder="Click here to chat..."]');
const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
setter.call(input, ':ha <message>');
input.dispatchEvent(new Event('input', { bubbles: true }));
input.focus();
input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
```

**Steps:**

- [ ] **Step 1: Hard-reload the client tab** (cache-bust: navigate to the URL again with a fresh SSO ticket) and log in as Admin.
- [ ] **Step 2: Short alert.** `:ha Short test` → within ~1 s a `.nitro-notification-bubble.platform` element exists containing a "Platform" badge, a × control, the text — and NO `<img>` element inside the bubble. Screenshot it.
- [ ] **Step 3: Long alert.** `:ha` + a ~200-character sentence → bubble height grows to fit (compare `getBoundingClientRect().height` vs the short one), text wraps, no horizontal overflow. Screenshot.
- [ ] **Step 4: Persistence + dismiss.** Confirm the bubble is still present 20 s after sending (`document.querySelector('.nitro-notification-bubble.platform')` non-null), clicking the bubble BODY does not close it, clicking × closes it immediately.
- [ ] **Step 5: Other bubbles unchanged.** Re-enter a room to trigger the moderation disclaimer → it renders WITHOUT the badge/×, and auto-dismisses in ~8 s.
- [ ] **Step 6: Console clean.** No new JS errors in the tab console (pre-existing image 404s for `c_images/Habbo-Stories` are known noise).

### Task 3: Changelog, submodule bump, push, prod deploy

**Files:**
- Modify: `CHANGELOG.md`
- Modify: root submodule pointer for `client/`

**Steps:**

- [ ] **Step 1: Push client:**

```bash
git -C client push origin pixelrp
```

- [ ] **Step 2: Changelog.** Under the existing `## 2026-08-09 — The hotel found its tannoy` section's `### Added` list (the hotel-announcements entry), append:

```markdown
- **Announcements got a proper look.** Hotel-wide messages now arrive as a
  tidy "Platform" toast — labeled so you know it's official, sized to fit
  the message, sticking around for 45 seconds, and dismissible with a small
  × in the corner. (An earlier version showed a broken picture and squashed
  the text sideways.)
```

- [ ] **Step 3: Pull, bump submodule, push main** (root repo moved recently — pull first):

```bash
git pull -q
git add client CHANGELOG.md
git commit -m "chore: bump client (Platform bubble for hotel alerts)"
git push
```

- [ ] **Step 4: Deploy client assets to prod** (static rsync — no container rebuild; prod configs preserved):

```bash
rsync -az --exclude 'renderer-config.json' --exclude 'ui-config.json' nitro/client/ root@67.219.109.182:/opt/pixelrp/nitro/client/
```

- [ ] **Step 5: Prod spot-check.** Load the prod client fresh (hard reload); as a prod staff account send `:ha Platform toast test` and confirm the badge/×/no-image rendering. If no staff login is practical from this side, confirm at minimum the deployed `nitro/client/index.html` on the VPS has the new build's mtime/hash and ask the user to eyeball their next `:ha`.
