# Claude Game Bot — Design

**Date:** 2026-08-08
**Status:** Approved

## Purpose

A headless, always-on bot that plays PixelRP as the **Claude** account: it hangs
out in rooms, listens to chat, and replies in character when addressed. Powered
by the Claude API (`claude-opus-5`) instead of a browser-driven client.

Day-one scope is **chat companion only**. Staff duties, scheduled smoke tests,
and bug reporting are explicitly out of scope (they layer onto the same
foundation later).

## Decisions

| Decision | Choice |
|---|---|
| Connection approach | Minimal headless packet client (no nitro-renderer, no emulator changes) |
| Chattiness | Replies only when addressed ("claude" in message, or whispered) |
| Model | `claude-opus-5`, `effort: low`, `max_tokens` ~1000 |
| Memory | Single markdown memory file, append via tool, volume-mounted |
| Language / runtime | TypeScript, Node 22, `@anthropic-ai/sdk` + `ws` |
| Hosting | `bot` service in compose; dev-first, then VPS |
| Account | Existing **Claude** user (prod) / **ClaudeTest** (dev), selected by env |

## Architecture

New top-level `bot/` directory in the plus repo (plain directory, not a
submodule), running as a `bot` compose service. Three modules with hard
boundaries:

### `protocol/` — wire layer

- Frame codec: `int32 length` + `uint16 packet id` + payload; strings are
  length-prefixed UTF-8 (standard Habbo encoding, as implemented in the
  emulator's `GameClient.cs` / `PacketFactory`).
- Connection wrapper over `ws` with connect/close/send/frame events.
- Packet ids come from a checked-in copy of the emulator's
  `Resources/Revisions/1.6.6.json` (273 incoming / 266 outgoing ids). The
  revision is frozen — we control the server — so drift is not a concern; a
  comment records the source path.
- Knows nothing about game semantics.

### `game/` — GameClient

- `login(ssoTicket)` — ClientHello (4000) + SsoTicketEvent (2419) handshake.
- Actions: `say()` (ChatEvent 1314), `shout()`, `whisper()`, `goToRoom(id)`,
  `walkTo(x, y)`.
- Event emitter for the packets we parse: auth OK, room user list
  (unit-id → username mapping, required because chat packets carry unit ids),
  chat/shout/whisper (ChatComposer 1446 etc.), room forward, disconnect.
- **Every other packet is skipped by frame length, unparsed.** This is the
  core simplification that keeps the client ~small.
- Degrades gracefully: if a user-list parse fails, speaker maps to
  "someone" rather than crashing.

### `brain/` — Claude integration

- Persona system prompt (stable text, `cache_control: ephemeral`).
- Rolling room-transcript buffer, capped at ~30 messages; all room chat is
  buffered regardless of addressing so replies are context-aware.
- Addressed-detector: case-insensitive "claude" substring, or whisper to the
  bot.
- Tool runner (`client.beta.messages.toolRunner`) with tools:
  `say(message)`, `whisper(user, message)`, `walk_to(x, y)`,
  `go_to_room(id)`, `remember(note)`.
- Memory file: markdown at a volume-mounted path; `remember` appends; full
  file is included in the prompt (it stays small; revisit if it grows).

### Wiring (`index.ts`)

Config from env (`BOT_ENABLED`, `WS_URL`, `DB_*`, `ANTHROPIC_API_KEY`,
`BOT_USERNAME`, `BOT_HOME_ROOM`, `MEMORY_PATH`), connect → login → join the
configured home room (default: room 1) → event loop.

## Login / account

The bot mints its own SSO ticket at startup and on every reconnect by writing
`users.auth_ticket` directly over the compose network (same MySQL the stack
uses). No manual step.

Consequence of sharing the Claude account: a browser login as Claude bumps the
bot's session. The bot treats it as an ordinary disconnect and reclaims the
account via backoff once the browser session ends.

## Reply flow

1. Chat packet → `game` emits `{username, message, whisper}` → buffered.
2. If addressed: one tool-runner call (persona + memory + transcript).
3. Claude responds via tools — typically one or two `say` calls.
4. Replies over the ~100-char chat limit are split across bubbles with ~700ms
   spacing (emulator flood filter).
5. Bot ignores its own messages and Plus bots/pets (filtered by user type).

## Resilience

- Websocket drop / login bump → exponential backoff 10s → 5min cap, fresh
  ticket each attempt.
- Claude API errors → typed exception chain; on final failure the bot stays
  silent (logged), never crashes.
- Packet parse errors skip the frame, never the process.
- `BOT_ENABLED=false` is the kill switch; container `restart: unless-stopped`.

## Cost profile

Addressed-only + capped transcript + cached persona ≈ 1–2K input / ~100 output
tokens per reply on `claude-opus-5` ($5/$25 per MTok) — roughly a hundredth of
a cent per reply; well under $1/day at plausible activity.

## Testing

- **TDD (vitest)** for the deterministic core: frame codec round-trips, string
  encoding, chat packet parse/build, addressed-detection, reply chunking —
  with recorded byte fixtures.
- **Integration (local stack):** bot logs in as ClaudeTest; a smoke script
  opens a second raw connection, says "hi claude", asserts a chat packet
  returns.
- **Manual:** watch it converse in the dev client via browser before any prod
  deploy.

## Out of scope (deliberately)

- Staff/QA duties, scheduled smoke tests, bug reports (future phases).
- Per-player memory profiles (evolve from the memory file if wanted).
- Interjecting un-addressed (revisit chattiness later).
- Parsing room furniture/heightmap; pathfinding beyond `walkTo` click-target.
