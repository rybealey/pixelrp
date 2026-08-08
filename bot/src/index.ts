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
const disabledReason = !config.enabled
  ? "BOT_ENABLED=false"
  : !config.anthropicApiKey
    ? "ANTHROPIC_API_KEY is not set"
    : null;
if (disabledReason) {
  // Idle forever instead of process.exit(0): the compose service runs with
  // `restart: unless-stopped`, so exiting would just have Docker restart the container in a
  // loop for as long as the kill switch is set (or the key is left empty, as in a fresh dev
  // checkout of .env.example). Staying up with an open (no-op) event loop lets the container
  // sit healthy-but-idle until the env is fixed and it's redeployed.
  console.log(`[bot] ${disabledReason} — idling (not connecting)`);
  await new Promise<void>(() => {});
}

const pool = mysql.createPool({ ...config.db, connectionLimit: 2 });
const anthropic = new Anthropic({ apiKey: config.anthropicApiKey });
const memory = new MemoryFile(config.memoryPath);

async function session(): Promise<void> {
  const ticket = await mintTicket(pool, config.botUsername);
  const conn = new Connection();
  // Connection.connect()'s internal `ws.once("error", ...)` only settles the connect() promise
  // (and re-emits on `conn`) for the FIRST error the socket ever raises — including one that
  // happens long after `connect()` has already resolved (i.e. after login, mid-session). Node's
  // EventEmitter throws (crashing the process) if "error" is emitted with no listener attached,
  // so without this handler a post-open socket error takes the whole bot down instead of just
  // closing the connection, which the "close" handler below already turns into a reconnect.
  conn.on("error", (err) => console.error("[bot] socket error:", err));
  const game = new GameClient(conn, config.botUsername);
  const transcript = new Transcript();
  const brain = new Brain({ anthropic, game, memory, transcript });

  game.on("chat", (msg: ChatMessage) => {
    // Belt-and-braces on top of GameClient's own self-detection: UsersComposer roster parsing
    // stops as soon as it hits a bot/pet entry it doesn't fully understand (see parsers.ts), so
    // in a room where the bot's own roster entry sits behind an unparsed one, msg.self could in
    // principle come back false for our own lines. A plain username match can't be fooled by
    // that truncation, so we check it independently rather than relying on msg.self alone.
    const isSelf = msg.self || msg.username.toLowerCase() === config.botUsername.toLowerCase();
    if (isSelf) {
      // Spec: all room chat is buffered into the transcript, including our own lines — we just
      // must never treat our own lines as a trigger to respond to.
      transcript.add(msg.username, msg.message);
      return;
    }
    if (msg.userType !== 1) return; // ignore bots, pets
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
  // (SummonCommand, PurchaseGroupEvent, FollowFriendEvent, FindNewFriendsEvent,
  // ChangeUserNameEvent, FindRandomFriendingRoomEvent, SaveFloorPlanModelEvent) fires only in
  // response to some other
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
  // If login() rejects (bad/expired ticket, or the 15s timeout), the WebSocket is left open
  // with GameClient's frame/close listeners still attached and nothing left to ever close it —
  // a leaked connection per failed login, and if a very late AuthenticationOkComposer somehow
  // still arrived on it, a stray "authOk" with nothing waiting on it. The try/finally guarantees
  // conn.close() runs on that path; on the normal path it runs after the socket has already
  // closed itself (the "close" promise below only resolves once that's happened), so it's a
  // harmless no-op there.
  try {
    await game.login(ticket);
    console.log("[bot] logged in as", config.botUsername);
    game.goToRoom(config.homeRoom);

    await new Promise<void>((resolve) => game.once("close", resolve));
    console.log("[bot] disconnected");
  } finally {
    conn.close();
  }
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
