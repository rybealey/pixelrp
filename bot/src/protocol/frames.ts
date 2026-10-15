export function encodeFrame(id: number, payload: Buffer): Buffer {
  const frame = Buffer.alloc(4 + 2 + payload.length);
  frame.writeInt32BE(2 + payload.length, 0);
  frame.writeUInt16BE(id, 4);
  payload.copy(frame, 6);
  return frame;
}

// Upper bound on one incoming frame's length field. The biggest packet the server sends the
// bot is a room's floor furni (ObjectsComposer): at most room.item.placement_limit (7500)
// items at roughly 60-90 bytes each, so well under 1 MB. The emulator caps its own incoming
// frames at 1 MB (GameClient.MaxPacketLength); outgoing ones have no cap, so this leaves
// headroom - a real room must never trip it, or the bot would reconnect into the same room
// in a loop. A desynced stream reads whatever 4 bytes it lands on as the length, and text
// or a large number reads as hundreds of MB, far past this.
export const MAX_FRAME_LENGTH = 4 * 1024 * 1024;

export class FrameAssembler {
  // Explicitly typed `Buffer` (== Buffer<ArrayBufferLike>, the default type param) rather than
  // left to widen from `Buffer.alloc(0)`'s inferred `Buffer<ArrayBuffer>`: without this
  // annotation, reassigning from `chunk` (a plain `Buffer`-typed parameter, i.e.
  // `Buffer<ArrayBufferLike>`) doesn't satisfy the narrower inferred field type under strict
  // mode — the pre-existing `npx tsc --noEmit` error at this file.
  private pending: Buffer = Buffer.alloc(0);
  /** Set for good once the stream is out of step; the owner must close the connection. */
  desynced = false;

  push(chunk: Buffer): Array<{ id: number; payload: Buffer }> {
    // Nothing that arrives on a broken stream can be trusted, or buffered.
    if (this.desynced) return [];
    this.pending = this.pending.length
      ? Buffer.concat([this.pending, chunk])
      : chunk;
    const frames: Array<{ id: number; payload: Buffer }> = [];
    while (this.pending.length >= 6) {
      const length = this.pending.readInt32BE(0); // bytes after the length field
      if (length < 2 || length > MAX_FRAME_LENGTH) {
        // A well-formed frame's length is always >= 2 (the 2-byte packet id, even with a
        // zero-byte payload) and never more than MAX_FRAME_LENGTH. Anything else means the
        // stream is desynced — e.g. we misparsed a previous frame and are no longer reading
        // from a real frame boundary — and continuing to trust `length` as a byte count would
        // misparse everything after it too, or, for a huge one, buffer every chunk that
        // arrives while waiting for bytes that never come, with the bot hearing nothing.
        // There is no frame boundary to resync on, so the stream is finished: drop the
        // pending buffer, mark it desynced (Connection closes the socket, and the reconnect
        // gets a clean stream) and return the complete frames decoded before this point.
        console.warn(
          `[frames] impossible frame length ${length} — dropping ${this.pending.length} pending byte(s), stream desync`,
        );
        this.pending = Buffer.alloc(0);
        this.desynced = true;
        break;
      }
      if (this.pending.length < 4 + length) break;
      const id = this.pending.readUInt16BE(4);
      const payload = this.pending.subarray(6, 4 + length);
      frames.push({ id, payload: Buffer.from(payload) });
      this.pending = this.pending.subarray(4 + length);
    }
    return frames;
  }
}
