import { afterEach, describe, expect, it, vi } from "vitest";
import { createServer, type Socket } from "node:net";
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

  it("closes the connection when the stream desyncs", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    server = new WebSocketServer({ port: 0 });
    // A good frame, then a length no real frame has: the server stays up, the client must go.
    server.on("connection", (sock) =>
      sock.send(Buffer.concat([encodeFrame(2491, Buffer.alloc(0)), Buffer.from("garbage!")])),
    );
    const port = (server.address() as { port: number }).port;
    const conn = new Connection();
    const frames: number[] = [];
    conn.on("frame", (f: { id: number }) => frames.push(f.id));
    const closed = new Promise((resolve) => conn.once("close", resolve));
    await conn.connect(`ws://127.0.0.1:${port}`);
    await closed;
    expect(frames).toEqual([2491]);
    warn.mockRestore();
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

  it("closes a connection that stops answering pings", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    // autoPong off: the socket stays open but nothing ever comes back, like a dead peer.
    server = new WebSocketServer({ port: 0, autoPong: false });
    const port = (server.address() as { port: number }).port;
    const conn = new Connection({ pingIntervalMs: 25, deadAfterMs: 100 });
    const closed = new Promise((resolve) => conn.once("close", resolve));
    await conn.connect(`ws://127.0.0.1:${port}`);
    await closed;
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  it("keeps a silent connection open while the server answers pings", async () => {
    server = new WebSocketServer({ port: 0 }); // answers pings, never sends a frame
    const port = (server.address() as { port: number }).port;
    const conn = new Connection({ pingIntervalMs: 25, deadAfterMs: 100 });
    let closed = false;
    conn.once("close", () => (closed = true));
    await conn.connect(`ws://127.0.0.1:${port}`);
    await new Promise((r) => setTimeout(r, 400));
    expect(closed).toBe(false);
    conn.close();
  });

  it("fails the connect when the server never answers the handshake", async () => {
    // Accepts the TCP connection, then says nothing.
    const sockets: Socket[] = [];
    const silent = createServer((s) => void sockets.push(s));
    await new Promise<void>((r) => silent.listen(0, "127.0.0.1", r));
    const port = (silent.address() as { port: number }).port;
    const conn = new Connection({ connectTimeoutMs: 100 });
    conn.on("error", () => {});
    try {
      await expect(conn.connect(`ws://127.0.0.1:${port}`)).rejects.toThrow(/handshake has timed out/);
    } finally {
      for (const s of sockets) s.destroy();
      silent.close();
    }
  });
});
