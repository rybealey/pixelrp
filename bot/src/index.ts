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
  // SSOTicketEvent.Parse sends RoomForwardComposer(last_room_id) unconditionally on every login
  // (emulator/Communication/Packets/Incoming/Handshake/SSOTicketEvent.cs L130-161: reads
  // users.last_room_id, falling back to room 1) — the server restoring where the account was
  // last seen, same as any real client reconnecting. If we auto-follow that forward (as a real
  // client does) *and* then also send our own home-room entry, the two
  // OpenFlatConnectionEvent/GetRoomEntryDataEvent sequences land on the same session for two
  // different rooms; live testing showed this desyncs the session's room membership — our own
  // roster correctly shows us in the home room, but the room's broadcast list never gets chat
  // from other occupants delivered to us. So the login-restore forward must never be followed.
  //
  // It can't be filtered by "arrived before our own goToRoom(homeRoom) call", though: per the
  // same file (L80-146), a genuine async gap — a rewards check plus a DB query — sits between
  // AuthenticationOkComposer and this RoomForwardComposer server-side, and GameClient.Send
  // flushes per-composer with no batching, so it can just as easily arrive as a *later* WebSocket
  // message, after our synchronous post-login code (including any "have we sent our own entry
  // yet" flag) has already run. Ordering relative to our own call is not guaranteed either way.
  //
  // What *is* guaranteed, independent of arrival order, is that this is the only unprompted
  // RoomForwardComposer a fresh connection ever receives: every other call site in the emulator
  // (SummonCommand, PurchaseGroupEvent, FollowFriendEvent, ChangeUserNameEvent,
  // FindRandomFriendingRoomEvent, SaveFloorPlanModelEvent) fires only in response to some other
  // action — an admin command or a packet this bot doesn't send — that can't happen before our
  // first login completes. So the very first RoomForwardComposer this connection ever receives
  // is always the login-restore one, whenever it happens to arrive, and gets ignored; every
  // later one is a genuine mid-session redirect (e.g. an admin /summon) and is followed.
  let seenLoginRestoreForward = false;
  game.on("roomForward", ({ roomId }: { roomId: number }) => {
    if (!seenLoginRestoreForward) {
      seenLoginRestoreForward = true;
      return;
    }
    game.goToRoom(roomId);
  });

  await conn.connect(config.wsUrl);
  await game.login(ticket);
  console.log("[bot] logged in as", config.botUsername);
  game.goToRoom(config.homeRoom);

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
