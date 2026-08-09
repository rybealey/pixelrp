# `:ha` hotel alert as notification bubble — design

Date: 2026-08-09
Status: approved (repoint stock `:ha` at the bubble packet; rank ≥ 5; message only)

## Problem

Staff need a way to message every online player. The stock `:ha` command
exists but sends `BroadcastMessageAlertComposer` — a modal popup dialog.
PixelRP wants alerts in the small dark corner bubble instead: the exact
format of the moderation disclaimer ("Discussions in PixelRP rooms may be
monitored…"), which is the client's standard INFO notification bubble.

## Decisions (from brainstorming)

- **Reuse the stock `:ha` command** (`HotelAlertCommand`, key `ha`,
  permission `command_hotel_alert`); the popup behavior is replaced, not
  duplicated under a second key.
- **Rank ≥ 5** may use it (project staff convention), via a one-row
  permission update — the stock mapping was rank group 8.
- **Message only** — no "— Username" attribution suffix.

## How the bubble is produced

No client changes. The client's `useNotification` hook handles
`NotificationDialogMessageEvent` → `showNotification(type, parameters)`;
when parameters include `display=BUBBLE` it calls
`showSingleBubble(LocalizeText(message), NotificationBubbleType.INFO)` —
the same call that renders the moderation disclaimer, so the format is
pixel-identical. The emulator already has the matching outgoing packet,
`RoomNotificationComposer(type, Dictionary<string,string>)`.

Free text passes through the client's `LocalizeText`, which returns unknown
keys unchanged — the established Nitro pattern for server-sent bubble text.

## Changes

### Emulator: `HabboHotel/Rooms/Chat/Commands/Moderator/HotelAlertCommand.cs`

Replace the `BroadcastMessageAlertComposer` send with a hotel-wide
`RoomNotificationComposer("hotel.alert", { display: BUBBLE, message })`
broadcast via the existing `_gameClientManager.SendPacket`. Keep the
empty-message whisper guard. Update the `Description` string to mention the
bubble.

### Emulator: `Resources/SQLs/Updates/17_HotelAlertRank5.sql`

Idempotent: `UPDATE permissions_commands SET group_id = '5' WHERE command =
'command_hotel_alert';` Applied to local and prod DBs at deploy.

## Testing

- Compile (`docker compose build emulator`), boot to `EMULATOR -> READY!`,
  apply SQL 17 locally.
- Live: two sessions (Admin rank 9 + a second account in a different room).
  `:ha Test message` from Admin → bubble appears on both sessions in the
  notification-bubble format; empty `:ha` → usage whisper.
- Rank gate: non-staff account cannot invoke `:ha` (unknown/denied command).

## Changelog

Player-facing `CHANGELOG.md` entry in the same push.
