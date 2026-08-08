export function encodeFrame(id: number, payload: Buffer): Buffer {
  const frame = Buffer.alloc(4 + 2 + payload.length);
  frame.writeInt32BE(2 + payload.length, 0);
  frame.writeUInt16BE(id, 4);
  payload.copy(frame, 6);
  return frame;
}

export class FrameAssembler {
  // Explicitly typed `Buffer` (== Buffer<ArrayBufferLike>, the default type param) rather than
  // left to widen from `Buffer.alloc(0)`'s inferred `Buffer<ArrayBuffer>`: without this
  // annotation, reassigning from `chunk` (a plain `Buffer`-typed parameter, i.e.
  // `Buffer<ArrayBufferLike>`) doesn't satisfy the narrower inferred field type under strict
  // mode — the pre-existing `npx tsc --noEmit` error at this file.
  private pending: Buffer = Buffer.alloc(0);

  push(chunk: Buffer): Array<{ id: number; payload: Buffer }> {
    this.pending = this.pending.length
      ? Buffer.concat([this.pending, chunk])
      : chunk;
    const frames: Array<{ id: number; payload: Buffer }> = [];
    while (this.pending.length >= 6) {
      const length = this.pending.readInt32BE(0); // bytes after the length field
      if (length < 2) {
        // A well-formed frame's length is always >= 2 (the 2-byte packet id, even with a
        // zero-byte payload). A smaller value means the stream is desynced — e.g. we
        // misparsed a previous frame and are no longer reading from a real frame boundary —
        // and continuing to trust `length` as a byte count would misparse everything after
        // it too. Treat it as unrecoverable: drop the pending buffer and return whatever
        // complete frames were decoded before this point, rather than loop forever or throw
        // away a working connection over one bad frame.
        console.warn(
          `[frames] malformed frame length ${length} — dropping ${this.pending.length} pending byte(s), stream desync`,
        );
        this.pending = Buffer.alloc(0);
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
