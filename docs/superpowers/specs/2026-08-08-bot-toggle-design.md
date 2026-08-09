# In-game Claude bot toggle — design

Date: 2026-08-08
Status: approved (disconnect semantics, `:bot on/off/status` command, DB-persisted)

## Problem

The Claude game bot's only kill switch is `BOT_ENABLED` in `.env`, read once at
container start. Turning the bot off (or back on) requires shell access to the
VPS and a container restart. Staff need a way to do it from inside the game.

## Decisions (from brainstorming)

- **Off = disconnect.** Claude visibly leaves the hotel within the poll
  interval and stays gone; no API spend while off.
- **Command:** `:bot on` / `:bot off`, staff-gated like other moderator
  commands; bare `:bot` whispers the current state.
- **Persistence:** the state lives in the `server_settings` table and survives
  restarts of any component.

## Architecture

Two independent pieces communicate through one `server_settings` row,
`bot.enabled` = `'1'` / `'0'` (seeded by SQL update
`16_AddBotEnabledSetting.sql`, idempotent):

### Emulator: `:bot` command

- New `BotCommand` in `HabboHotel/Rooms/Chat/Commands/Moderator/`, registered
  in `CommandManager` with the same permission pattern as sibling moderator
  commands.
- `on`/`off` write the row with a plain parameterized query (the pattern other
  commands use); no arg reads and whispers the state. Feedback via whisper.
- The emulator never consumes the flag itself — the command is purely a
  control plane for the bot process.

### Bot: flag watcher

- Polls `SELECT value FROM server_settings WHERE \`key\` = 'bot.enabled'`
  every 10 s on the existing MySQL pool.
- Off mid-session → log, close the connection cleanly, keep polling in idle.
- On → the existing session/reconnect loop takes over (bot returns ≤ 10 s).
- Checked on boot before the first connect.
- `BOT_ENABLED=false` in the environment remains a hard override: the DB flag
  is only consulted when the env switch allows the bot to run at all.
- Missing row → enabled (matches today's behavior).

## Failure modes

- **Missing grant / SELECT error:** log the error, keep the current state
  (never crash-loop, never treat as "off"). DB blips use the existing backoff
  helper; a failed poll never tears down a healthy session.
- **Concurrent toggles:** last write wins; `:bot` reports the settled state.

## Access control

The bot's dedicated MySQL user gains `SELECT (\`key\`, \`value\`)` on
`server_settings`:
- `docker/db/create-bot-user.sh` (first-init path) updated.
- Existing volumes/prod: grant applied by hand, documented in `bot/README.md`.
- Fallback behavior when the bot runs as the app user (no dedicated user
  configured) is unchanged — the app user can already read the table.

## Testing

- vitest units for the watcher: on→off closes the session, off→on releases
  the idle wait, missing row = enabled, query error = no state change.
- Live on local dev: `:bot off` as staff → Claude leaves; `:bot on` →
  returns; `:bot` whispers status.

## Deploy

SQL 16 on both DBs, prod grant (only if prod uses the dedicated bot user),
emulator + bot image rebuilds, player-facing changelog entry.

## Out of scope

- Instant-off kick from the command (≤10 s latency is fine for a kill
  switch; easy later addition).
- CMS housekeeping toggle.
