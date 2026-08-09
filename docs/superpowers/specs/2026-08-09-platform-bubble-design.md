# Platform bubble for hotel alerts — design

Date: 2026-08-09
Status: approved (client-only; PLATFORM bubble type; 45 s; ×-only dismiss; "Platform" badge)

## Problem

`:ha` hotel alerts render through the client's generic INFO bubble path,
which synthesizes an image URL from the notification type when none is sent
(`hotel.alert` → `…/hotel_alert.png`). The file doesn't exist, so the toast
shows a broken image in a fixed 50 px slot with the text pushed right. The
toast also auto-dismisses in 8 s, has no close affordance, and nothing
identifies it as an official platform message.

## Decisions (from brainstorming)

- Fix at the routing layer: `hotel.alert` bubbles never carry an image.
- New `NotificationBubbleType.PLATFORM` with its own layout view; all other
  notification types are untouched.
- Look: same dark bubble chrome as the moderation notice; small uppercase
  **Platform** badge top-left; subtle **×** top-right; wrapping message
  below; height fully content-driven.
- Persistence: 45 s (default bubbles stay 8 s).
- Dismiss: the × is the only close control — platform bubbles do not close
  on body clicks (deliberate deviation from default bubble behavior, so a
  stray click can't dismiss an announcement).

## Changes (client only, branch `pixelrp`)

### `src/hooks/notification/useNotification.ts`

In `showNotification`, when `options.get('display') === 'BUBBLE'` and
`type === 'hotel.alert'`, call
`showSingleBubble(LocalizeText(message), NotificationBubbleType.PLATFORM)`
— no image argument. Other BUBBLE notifications keep the existing call.

### `src/api/notification/NotificationBubbleType.ts`

Add `public static PLATFORM: string = 'platform';`.

### `src/components/notification-center/views/bubble-layouts/NotificationPlatformBubbleView.tsx` (new)

Column-layout bubble: header row with "Platform" badge + × button
(`onClose`), message text (`Text wrap`, newline → `<br />` like the default
view). Passes `timeoutMs={ 45000 }` and overrides the container `onClick`
to null so only the × closes. Registered in `GetBubbleLayout` under
`NotificationBubbleType.PLATFORM`.

### `src/components/notification-center/NotificationCenterView.scss`

`.nitro-notification-bubble.platform` styles: badge (small, uppercase,
letter-spaced, subtle border or tinted background), × (muted, brightens on
hover, cursor pointer), spacing between header and message.

## Not touched

Emulator (already sends type `hotel.alert` + `display=BUBBLE`), all other
bubble/alert layouts, the moderation disclaimer (stays INFO/8 s).

## Testing

- `yarn build`; deploy to `nitro/client/` preserving live
  `renderer-config.json`/`ui-config.json`; verify locally as Admin:
  `:ha` short and long messages → badge, ×, no image element, height grows
  with text, toast persists ~45 s, body click does NOT close, × does.
- Confirm a non-platform bubble (moderation notice on room entry) is
  unchanged (8 s, no badge).
- Deploy: rsync `nitro/client/` to prod excluding the two config JSONs.

## Changelog

Player-facing entry in the same push.
