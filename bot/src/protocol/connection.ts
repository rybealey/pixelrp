import { EventEmitter } from "node:events";
import WebSocket from "ws";
import { encodeFrame, FrameAssembler } from "./frames.ts";

export class Connection extends EventEmitter {
  private ws?: WebSocket;
  private assembler = new FrameAssembler();

  connect(url: string): Promise<void> {
    // A fresh stream gets a fresh assembler: a desynced one stays desynced.
    this.assembler = new FrameAssembler();
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(url, { perMessageDeflate: false });
      ws.binaryType = "nodebuffer";
      ws.once("open", () => {
        this.ws = ws;
        resolve();
      });
      ws.once("error", (err) => {
        this.emit("error", err);
        reject(err);
      });
      ws.on("message", (data) => {
        for (const frame of this.assembler.push(data as Buffer)) {
          this.emit("frame", frame);
        }
        // A broken stream can't be resynced (see FrameAssembler.push): close the socket, so
        // "close" below hands over to the reconnect loop in index.ts. terminate(), not
        // close(): nothing more is wanted from this stream, so no closing handshake to wait on.
        if (this.assembler.desynced) ws.terminate();
      });
      ws.once("close", () => this.emit("close"));
    });
  }

  send(id: number, payload: Buffer): void {
    this.ws?.send(encodeFrame(id, payload));
  }

  close(): void {
    this.ws?.close();
  }
}
