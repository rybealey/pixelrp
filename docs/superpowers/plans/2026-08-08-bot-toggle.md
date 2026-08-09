# In-game Bot Toggle Implementation Plan

> Spec: `docs/superpowers/specs/2026-08-08-bot-toggle-design.md`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Staff type `:bot off` / `:bot on` in-game; the Claude bot disconnects (visibly leaves) or reconnects within ~10 s. Bare `:bot` whispers the current state. State persists in `server_settings` (`bot.enabled`).

**Tech Stack:** C#/.NET 7 (PlusEMU, branch `pixelrp`), TypeScript bot (`bot/`, vitest), MySQL 8.

## Global Constraints

- `BOT_ENABLED=false` env stays a hard override; DB flag consulted only when env allows.
- Missing row or unreadable flag → keep current state; default enabled. Never crash-loop, never hammer the DB (10 s cadence, reuse `backoff.ts` on errors only).
- Emulator commits on `emulator/` branch `pixelrp`; bump the root submodule after pushing; player-facing CHANGELOG entry in the same push (project discipline).

---

### Task 1: SQL seed + emulator `:bot` command

**Files:**
- Create: `emulator/Resources/SQLs/Updates/16_AddBotEnabledSetting.sql`
- Create: `emulator/HabboHotel/Rooms/Chat/Commands/Moderator/BotCommand.cs`
- Modify: `emulator/HabboHotel/Rooms/Chat/Commands/CommandManager.cs` (Register call)

**Steps:**
- [ ] SQL 16: idempotent `INSERT IGNORE INTO server_settings` seeding `bot.enabled` = `'1'` with a description.
- [ ] `BotCommand`: follow a sibling Moderator command's shape (`PermissionRequired`, `Parameters`, `Description`, `Execute`). `on`/`off` → parameterized UPDATE of the row (INSERT if absent); no arg → SELECT and whisper `Bot is currently ON/OFF`. Whisper confirmation on change.
- [ ] Register as `bot` with the same permission gate its Moderator siblings use (verify the exact permission string from a neighbor, e.g. DisconnectCommand).
- [ ] Compile via `docker compose build emulator`; boot clean.

### Task 2: Bot flag watcher

**Files:**
- Create: `bot/src/flag.ts` (watcher; injectable poll interval + query fn for tests)
- Modify: `bot/src/index.ts` (gate session loop on the watcher)
- Create: `bot/test/flag.test.ts`

**Steps:**
- [ ] `flag.ts`: `FlagWatcher` exposing `enabled` (current bool), `waitUntilEnabled()`, and an `onDisable` callback hook; polls `SELECT value FROM server_settings WHERE \`key\`='bot.enabled'` via injected query fn. Missing row → true. Query error → log once per streak, keep last value.
- [ ] `index.ts`: before each `session()` attempt, `await watcher.waitUntilEnabled()`; on `onDisable`, close the active connection (reuse the path the reconnect loop already handles) and log `[bot] disabled via :bot — disconnecting`.
- [ ] vitest: on→off closes session (spy on close), off→on releases waiter, missing row = enabled, query error = no state change.
- [ ] `npm test` green; `docker compose build bot` clean.

### Task 3: Grants, docs, changelog

**Files:**
- Modify: `docker/db/create-bot-user.sh` (+ `GRANT SELECT (\`key\`,\`value\`) ON server_settings`)
- Modify: `bot/README.md` (grant statement for existing volumes/prod; `:bot` usage)
- Modify: `CHANGELOG.md` (player-facing entry)

### Task 4: Verify locally, push, deploy

- [ ] Apply SQL 16 + grant locally; rebuild emulator + bot; `:bot off` as ClaudeTest → bot logs disconnect and leaves room; `:bot on` → returns; bare `:bot` whispers state.
- [ ] Push `PlusEMU` `pixelrp` and `pixelrp` main (submodule bump + changelog).
- [ ] VPS: pull, apply SQL 16, apply grant only if prod uses the dedicated bot user (check `.env`), rebuild emulator + bot, verify logs + live `:bot` round-trip.
