import { afterEach, describe, expect, it } from "vitest";
import { WebSocketServer, WebSocket } from "ws";
import { Connection } from "../src/protocol/connection.ts";
import { encodeFrame } from "../src/protocol/frames.ts";

describe("Connection", () => {
  let server: WebSocketServer;
  afterEach(() => server?.close());

  it("sends frames and emits received frames", async () => {
    const received: Buffer[] = [];
    server = new WebSocketServer({ port: 0 });
    server.on("connection", (sock: WebSocket) => {
      sock.on("message", (data: Buffer) => {
        received.push(Buffer.from(data as Buffer));
        sock.send(encodeFrame(2491, Buffer.alloc(0))); // pretend auth ok
      });
    });
    const port = (server.address() as { port: number }).port;

    const conn = new Connection();
    const gotFrame = new Promise<{ id: number }>((resolve) =>
      conn.once("frame", resolve),
    );
    await conn.connect(`ws://127.0.0.1:${port}`);
    conn.send(4000, Buffer.from([1, 2]));

    const frame = await gotFrame;
    expect(frame.id).toBe(2491);
    expect(received[0].readUInt16BE(4)).toBe(4000);
    conn.close();
  });

  it("emits close when the server drops the socket", async () => {
    server = new WebSocketServer({ port: 0 });
    server.on("connection", (sock) => sock.close());
    const port = (server.address() as { port: number }).port;
    const conn = new Connection();
    const closed = new Promise((resolve) => conn.once("close", resolve));
    await conn.connect(`ws://127.0.0.1:${port}`);
    await closed; // resolves = pass
  });
});
