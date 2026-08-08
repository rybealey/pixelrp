import Anthropic from "@anthropic-ai/sdk";
import mysql from "mysql2/promise";
import { loadConfig } from "./config.ts";
import { Connection } from "./protocol/connection.ts";
import { GameClient, type ChatMessage } from "./game/client.ts";
import { Brain } from "./brain/brain.ts";
import { Transcript, isAddressed } from "./brain/transcript.ts";
import { MemoryFile } from "./brain/memory.ts";
import { mintTicket } from "./sso.ts";
import { nextDelay } from "./backoff.ts";

const config = loadConfig();
if (!config.enabled) {
  console.log("[bot] BOT_ENABLED=false — exiting");
  process.exit(0);
}

const pool = mysql.createPool({ ...config.db, connectionLimit: 2 });
const anthropic = new Anthropic({ apiKey: config.anthropicApiKey });
const memory = new MemoryFile(config.memoryPath);

async function session(): Promise<void> {
  const ticket = await mintTicket(pool, config.botUsername);
  const conn = new Connection();
  const game = new GameClient(conn, config.botUsername);
  const transcript = new Transcript();
  const brain = new Brain({ anthropic, game, memory, transcript });

  game.on("chat", (msg: ChatMessage) => {
    if (msg.self || msg.userType !== 1) return; // ignore own lines, bots, pets
    transcript.add(msg.username, msg.message);
    if (isAddressed(msg.message, msg.whisper)) {
      void brain
        .respond({ username: msg.username, message: msg.message, whisper: msg.whisper })
        .catch((err) => console.error("[bot] respond error:", err));
    }
  });
  // SSOTicketEvent.Parse sends RoomForwardComposer(last_room_id) unconditionally right after
  // AuthenticationOkComposer (emulator/Communication/Packets/Incoming/Handshake/SSOTicketEvent.cs
  // L130-161: reads users.last_room_id, falling back to room 1) — this is the server restoring
  // where the user was last seen, same as any real client reconnecting. If we auto-follow that
  // forward (as a real client does) *and* then immediately also send our own home-room entry
  // right after login resolves, the two OpenFlatConnectionEvent/GetRoomEntryDataEvent sequences
  // fire back-to-back (single-digit ms apart) for two different rooms on the same session. Live
  // testing against the emulator showed this leaves the session's room membership desynced: our
  // own UsersComposer roster correctly shows us in the home room, but the room's broadcast list
  // never gets chat from other occupants delivered to us. Ignoring the pre-startup forward and
  // only following ones that arrive *after* our own initial entry (e.g. a real mid-session
  // redirect, like an admin teleport) avoids the race and matches what we actually verified live.
  let settled = false;
  game.on("roomForward", ({ roomId }: { roomId: number }) => {
    if (!settled) return;
    game.goToRoom(roomId);
  });

  await conn.connect(config.wsUrl);
  await game.login(ticket);
  console.log("[bot] logged in as", config.botUsername);
  game.goToRoom(config.homeRoom);
  settled = true;

  await new Promise<void>((resolve) => game.once("close", resolve));
  console.log("[bot] disconnected");
}

let attempt = 0;
for (;;) {
  try {
    const started = Date.now();
    await session();
    if (Date.now() - started > 60_000) attempt = 0; // healthy session resets backoff
  } catch (err) {
    console.error("[bot] session error:", err);
  }
  const delay = nextDelay(attempt++);
  console.log(`[bot] reconnecting in ${delay / 1000}s`);
  await new Promise((r) => setTimeout(r, delay));
}
