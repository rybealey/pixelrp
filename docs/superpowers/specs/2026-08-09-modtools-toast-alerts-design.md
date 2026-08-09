# Mod Tools alerts on the toast system — design

Date: 2026-08-09
Status: approved (mod.alert reuse for user-facing mod actions; new room.alert/INFORMATION blue toast; Moderation toasts persistent; kick message delivered; local-only deploy)

## Problem

Mod Tools alerts still use the modal popup (`SendNotification` →
`BroadcastMessageAlertComposer`): User Info send-message
(`ModerationMsgEvent`), caution (`ModerationCautionEvent`), the mute and
trade-ban notices, and the Room Info alert (`ModeratorActionEvent`, which
also prefixes "Caution/Message from Moderator:"). Kick reads the
moderator's message and discards it. These should all use the toast system
built for `:ha`/`:alert`.

## Decisions (from brainstorming)

- **User-facing mod alerts → the red Moderation toast** (type `mod.alert`),
  via a new `SendModerationAlert` extension. Sites: mod message, caution,
  mute notice, trade-ban notice, and (new) the kick message when non-empty,
  delivered before the kick.
- **Moderation toasts become persistent** until the × is clicked — one
  rule: red = stays until closed. This includes `:alert`.
- **Room alerts → new blue "Information" toast** (type `room.alert`,
  client `NotificationBubbleType.INFORMATION`), 45 s like Platform, ×-only
  dismiss. The "Caution/Message from Moderator:" prefixes are dropped — the
  badge carries the meaning.
- Deploy local only; prod ships later on request.

## Changes

### Emulator (branch `pixelrp`)

- `HabboHotel/GameClients/GameClientExtensions.cs`: add
  `SendModerationAlert(this GameClient client, string message)` →
  `client.Send(new RoomNotificationComposer("mod.alert", { display: BUBBLE, message }))`.
- `Communication/Packets/Incoming/Moderation/ModerationMsgEvent.cs` and
  `ModerationCautionEvent.cs`: `client.SendNotification(message)` →
  `client.SendModerationAlert(message)`.
- `ModerationMuteEvent.cs` (line ~42) and `ModerationTradeLockEvent.cs`
  (line ~47): same swap for the target-facing notices (moderator-facing
  error whispers/popups untouched).
- `ModerationKickEvent.cs`: capture the message (currently discarded); if
  non-empty, `client.SendModerationAlert(message)` before
  `RemoveUserFromRoom`. The moderator-facing "disallowed" popup stays.
- `ModeratorActionEvent.cs`: drop the prefix wrapping; send
  `currentRoom.SendPacket(new RoomNotificationComposer("room.alert", { display: BUBBLE, message }))`.

### Client (branch `pixelrp`)

- `NotificationBubbleType.ts`: add `INFORMATION = 'information'`.
- `useNotification.ts` BUBBLE branch: `room.alert` →
  `showSingleBubble(LocalizeText(message), NotificationBubbleType.INFORMATION)`
  (no image), alongside `hotel.alert`/`mod.alert`.
- `NotificationPlatformBubbleView.tsx`: refactor to a variant table keyed
  by `item.notificationType` — `{ badge, classNames, persistent }`:
  PLATFORM `('Platform', ['platform'], false)`, MODERATION
  `('Moderation', ['platform','moderation'], true)`, INFORMATION
  `('Information', ['platform','information'], false)`. Persistent →
  `fadesOut={ false }` on `LayoutNotificationBubbleView` (existing prop);
  non-persistent keep `timeoutMs={ 45000 }`.
- `GetBubbleLayout.tsx`: INFORMATION case → `NotificationPlatformBubbleView`.
- `NotificationCenterView.scss`: `.platform.information` block mirroring
  the moderation one with `$info` in place of `$danger`.

## Testing (local live, Admin + ClaudeTest sessions)

- User Info → send message and caution to ClaudeTest → red persistent
  Moderation toasts (still present after >50 s; × closes).
- Mod action mute (e.g. 300 s) → target gets persistent red toast; unmute
  after. Trade lock similarly if convenient. Kick with a message → target
  gets the toast and is removed from the room.
- Room Info → send alert → everyone in the room gets the blue
  "Information" toast (45 s, ×-only dismiss), no prefix text.
- Regressions: `:ha` Platform toast 45 s; `:alert` now persistent;
  moderator-facing error popups unchanged; logs clean.

## Changelog

Player-facing entry in the same push. No prod deploy in this change.
