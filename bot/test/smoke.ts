// Usage: WS_URL=ws://localhost:2096 SSO=<ticket for a second account> node --experimental-strip-types test/smoke.ts
//
// Not part of `vitest run` — this is a manual, live-stack smoke test. It opens a second raw
// protocol connection (separate from the bot under test), logs in as another account, joins
// room 2, and says "hi claude, say the word banana" to trigger the bot's respond() path. Watch
// stdout for a `chat` event echoed back from the bot's username.
import { Connection } from "../src/protocol/connection.ts";
import { GameClient } from "../src/game/client.ts";

const conn = new Connection();
const game = new GameClient(conn, "SmokeTester");
game.on("chat", (m) => console.log("[smoke] chat:", m));

await conn.connect(process.env.WS_URL!);
await game.login(process.env.SSO!);
console.log("[smoke] logged in; joining room 2");
game.goToRoom(2);
setTimeout(() => game.say("hi claude, say the word banana"), 3000);
setTimeout(() => {
  console.log("[smoke] done (check output above for the bot's reply)");
  process.exit(0);
}, 25_000);
