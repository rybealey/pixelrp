import { EventEmitter } from "node:events";
import WebSocket from "ws";
import { encodeFrame, FrameAssembler } from "./frames.ts";

export interface ConnectionOptions {
  /** A connect that hasn't finished its opening handshake by then fails. */
  connectTimeoutMs?: number;
  /** How often an open connection sends a WebSocket ping. */
  pingIntervalMs?: number;
  /** An open connection that has sent nothing at all — no frame, no pong — for this long is dead. */
  deadAfterMs?: number;
}

export class Connection extends EventEmitter {
  private ws?: WebSocket;
  private assembler = new FrameAssembler();
  // Plain fields, not constructor parameter properties: the container runs
  // this file through Node's strip-only TS loader, which rejects them.
  private readonly connectTimeoutMs: number;
  private readonly pingIntervalMs: number;
  private readonly deadAfterMs: number;

  constructor(options: ConnectionOptions = {}) {
    super();
    this.connectTimeoutMs = options.connectTimeoutMs ?? 15_000;
    this.pingIntervalMs = options.pingIntervalMs ?? 30_000;
    this.deadAfterMs = options.deadAfterMs ?? 90_000;
  }

  connect(url: string): Promise<void> {
    // A fresh stream gets a fresh assembler: a desynced one stays desynced.
    this.assembler = new FrameAssembler();
    return new Promise((resolve, reject) => {
      // handshakeTimeout covers both the TCP connect and the HTTP upgrade (ws passes it to
      // http.request as `timeout`), so a server that never answers fails the connect instead
      // of leaving it — and the reconnect loop waiting on it — pending for good.
      const ws = new WebSocket(url, { perMessageDeflate: false, handshakeTimeout: this.connectTimeoutMs });
      ws.binaryType = "nodebuffer";
      // Keep-alive. A connection can die without ever closing — the far end drops off the
      // network, a NAT or firewall forgets the flow — and a socket that is only read from may
      // never notice, leaving the bot offline with no "close" to reconnect on. The emulator's
      // NetCoreServer WsSession answers every WebSocket ping with a pong (WsSession.OnWsPing ->
      // SendPongAsync; WsSessionProxy doesn't override it), so a live connection always
      // answers, even in a silent room. Hearing nothing at all — no frame, no pong — for
      // deadAfterMs (three missed pings, room for a slow server) means it's gone.
      let lastHeard = Date.now();
      let keepAlive: ReturnType<typeof setInterval> | undefined;
      const heard = () => {
        lastHeard = Date.now();
      };
      ws.once("open", () => {
        this.ws = ws;
        heard();
        keepAlive = setInterval(() => {
          const silentMs = Date.now() - lastHeard;
          if (silentMs > this.deadAfterMs) {
            console.warn(`[connection] nothing heard for ${Math.round(silentMs / 1000)}s — closing a dead connection`);
            // terminate(), not close(): a closing handshake would wait on a peer that isn't there.
            ws.terminate();
            return;
          }
          ws.ping();
        }, this.pingIntervalMs);
        resolve();
      });
      ws.once("error", (err) => {
        this.emit("error", err);
        reject(err);
      });
      ws.on("pong", heard);
      ws.on("message", (data) => {
        heard();
        for (const frame of this.assembler.push(data as Buffer)) {
          this.emit("frame", frame);
        }
        // A broken stream can't be resynced (see FrameAssembler.push): close the socket, so
        // "close" below hands over to the reconnect loop in index.ts. terminate(), not
        // close(): nothing more is wanted from this stream, so no closing handshake to wait on.
        if (this.assembler.desynced) ws.terminate();
      });
      ws.once("close", () => {
        clearInterval(keepAlive);
        this.emit("close");
      });
    });
  }

  send(id: number, payload: Buffer): void {
    this.ws?.send(encodeFrame(id, payload));
  }

  close(): void {
    this.ws?.close();
  }
}
