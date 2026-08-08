import { describe, expect, it, vi } from "vitest";
import { EventEmitter } from "node:events";
import { GameClient } from "../src/game/client.ts";
import { BinaryWriter } from "../src/protocol/buffer.ts";
import { sendId } from "../src/protocol/headers.ts";

class FakeConnection extends EventEmitter {
  sent: Array<{ id: number; payload: Buffer }> = [];
  send(id: number, payload: Buffer) {
    this.sent.push({ id, payload });
  }
  close() {}
}

function chatPayload(unitId: number, message: string): Buffer {
  return new BinaryWriter()
    .writeInt(unitId).writeString(message)
    .writeInt(0).writeInt(0).writeInt(0).writeInt(message.length)
    .toBuffer();
}

describe("GameClient", () => {
  it("login sends hello + sso and resolves on auth ok", async () => {
    const conn = new FakeConnection();
    const client = new GameClient(conn as never, "ClaudeTest");
    const login = client.login("ticket-1");
    expect(conn.sent.map((f) => f.id)).toContain(sendId("ClientHelloEvent"));
    expect(conn.sent.map((f) => f.id)).toContain(sendId("SsoTicketEvent"));
    conn.emit("frame", { id: 2491, payload: Buffer.alloc(0) }); // AuthenticationOkComposer
    await expect(login).resolves.toBeUndefined();
  });

  it("emits chat with username resolved from roster, flags self", () => {
    const conn = new FakeConnection();
    const client = new GameClient(conn as never, "ClaudeTest");
    // roster: unit 1 = Ry, unit 2 = ClaudeTest (self)
    const roster = new BinaryWriter().writeInt(2);
    for (const [id, name, unit] of [[100, "Ry", 1], [5, "ClaudeTest", 2]] as const) {
      roster.writeInt(id).writeString(name).writeString("").writeString("")
        .writeInt(unit).writeInt(0).writeInt(0).writeString("0").writeInt(0).writeInt(1)
        .writeString("M").writeInt(-1).writeInt(-1).writeString("").writeString("")
        .writeInt(0).writeBool(false);
    }
    conn.emit("frame", { id: 374, payload: roster.toBuffer() }); // UsersComposer id from revision.json — use recvName lookup in impl, this test uses the real id
    const events: unknown[] = [];
    client.on("chat", (e) => events.push(e));
    conn.emit("frame", { id: 1446, payload: chatPayload(1, "hi claude") });
    conn.emit("frame", { id: 1446, payload: chatPayload(2, "hello!") });
    expect(events).toEqual([
      { username: "Ry", message: "hi claude", whisper: false, self: false, userType: 1 },
      { username: "ClaudeTest", message: "hello!", whisper: false, self: true, userType: 1 },
    ]);
  });

  it("say sends a ChatEvent with the message", () => {
    const conn = new FakeConnection();
    const client = new GameClient(conn as never, "ClaudeTest");
    client.say("hello room");
    const frame = conn.sent.find((f) => f.id === sendId("ChatEvent"));
    expect(frame).toBeDefined();
    expect(frame!.payload.toString("utf8")).toContain("hello room");
  });
});
