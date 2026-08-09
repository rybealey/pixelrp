# `:alert <user> <message>` as Moderation toast — design

Date: 2026-08-09
Status: approved (repoint stock `:alert`; MODERATION bubble skin on the Platform toast; rank ≥ 5; SQL 18)

## Problem

Staff need to alert a single player. The stock `:alert` command
(`AlertCommand`, key `alert`, `ITargetChatCommand`, permission
`command_alert_user` at rank group 2) sends a modal popup via
`SendNotification`. PixelRP wants it delivered as the Platform-style toast
introduced for `:ha`, tinted subtle red with a **Moderation** badge instead
of **Platform**.

## Decisions (from brainstorming)

- Reuse the stock `:alert` command; popup replaced, target resolution,
  self-alert guard ("Get a life."), and the sender confirmation whisper
  ("Alert successfully sent to X") all stay.
- Permission raised to rank group 5 via SQL 18 (was 2), matching the staff
  convention used for `:ha`.
- Client reuses `NotificationPlatformBubbleView` for both skins — no
  duplicate component. Same 45 s persistence, ×-only dismiss,
  content-driven height.
- Skin: `moderation` modifier class → dark-red-tinted background (danger
  red mixed into the dark base, same opacity) and red-hued badge border;
  badge text **Moderation**.

## Changes

### Emulator (branch `pixelrp`)

- `HabboHotel/Rooms/Chat/Commands/Moderator/AlertCommand.cs`: replace the
  `SendNotification` line with a single-client send of
  `RoomNotificationComposer("mod.alert", { display: BUBBLE, message })`.
- `Resources/SQLs/Updates/18_AlertUserRank5.sql`: idempotent
  `UPDATE permissions_commands SET group_id = '5' WHERE command = 'command_alert_user';`

### Client (branch `pixelrp`)

- `src/api/notification/NotificationBubbleType.ts`: add
  `MODERATION = 'moderation'`.
- `src/hooks/notification/useNotification.ts`: in the BUBBLE branch, route
  `type === 'mod.alert'` to
  `showSingleBubble(LocalizeText(message), NotificationBubbleType.MODERATION)`
  (no image), alongside the existing `hotel.alert` → PLATFORM case.
- `src/components/notification-center/views/bubble-layouts/NotificationPlatformBubbleView.tsx`:
  derive `isModeration` from `item.notificationType`; badge text
  `Moderation`/`Platform`; classNames `[ 'platform', 'moderation' ]` when
  moderation.
- `GetBubbleLayout.tsx`: `MODERATION` case → `NotificationPlatformBubbleView`.
- `NotificationCenterView.scss`: `.nitro-notification-bubble.platform.moderation`
  overrides (red-tinted background, red-hued badge border).

## Testing

Local live (SSO flow, two sessions): staff `:alert ClaudeTest <msg>` →
red Moderation toast on ClaudeTest only, sender gets confirmation whisper
and no toast; `:alert` on self → "Get a life." whisper; rank-1 sender
denied (falls to chat); `:ha` still renders the untinted Platform toast
(regression); logs clean. Deploy: client rsync (preserve prod config
JSONs), emulator rebuild, SQL 18 on both DBs, prod boot check.

## Changelog

Player-facing entry in the same push.
