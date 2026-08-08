# Claude — The Hotel Bot

Claude is an AI bot that lives in PixelRP's hotel. It hangs out in Moody's Pointe and chats with players who call out its name. It remembers conversations, follows the hotel gossip, and walks around like anyone else.

## Running Locally

The bot runs as a Docker Compose service:

```bash
docker compose up -d
```

In dev, the bot runs as `ClaudeTest` in room 2. You can test it by SSO logging into the local client, standing in room 2, and saying "claude" in chat.

To disable it without stopping the container, set `BOT_ENABLED=false` in your `.env`:

```bash
# .env
BOT_ENABLED=false
docker compose up -d
```

Or stop the service directly:

```bash
docker compose stop bot
```

## Environment Variables

| Variable | Default | Required | Notes |
|----------|---------|----------|-------|
| `BOT_ENABLED` | `true` | No | Set to `"false"` (string) to disable the bot without stopping the container. |
| `WS_URL` | — | Yes | WebSocket URL to the emulator. In compose, this is `ws://emulator:2096`. |
| `DB_HOST` | — | Yes | MySQL host (`db` in compose). |
| `DB_USER` | — | Yes | MySQL username. |
| `DB_PASSWORD` | — | Yes | MySQL password. |
| `DB_NAME` | — | Yes | MySQL database name. |
| `ANTHROPIC_API_KEY` | — | Yes | Claude API key for AI responses. |
| `BOT_USERNAME` | — | Yes | Bot's in-game username. |
| `BOT_HOME_ROOM` | `1` | No | Room ID where the bot spawns. Dev: `2` (Moody's Pointe). Prod: `1`. |
| `MEMORY_PATH` | `/data/memory.md` | No | Path to the bot's persistent memory file. In compose, mounted from the `bot-memory` volume. |

## How SSO Minting Works

At each session start, the bot writes an `auth_ticket` to the MySQL `users` table for its account. This ticket is used by the client to authenticate without a password. The bot generates a unique `bot-UUID` token and stores it in `users.auth_ticket`, allowing the client to SSO in as the bot's user.

## Memory

The bot remembers conversations in a Markdown file at `MEMORY_PATH` (default `/data/memory.md`). This file is mounted as a Docker volume (`bot-memory`) and persists across restarts.

Check the memory file:

```bash
docker compose exec bot cat /data/memory.md
```

## Account Sharing Note

If a player logs into the client as the bot's user (e.g., manually or through SSO), the bot's session will be bumped. The bot detects this and reclaims its session after a backoff delay (starting at 10 seconds, capping at 5 minutes). This is intentional — the bot yields to human players but comes back.

## Build & Development

The bot runs on Node 22 with `--experimental-strip-types`, so there's no build step. Source files in `bot/src/` are executed directly.

Run tests:

```bash
cd bot && npx vitest run
```
