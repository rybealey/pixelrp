export function encodeFrame(id: number, payload: Buffer): Buffer {
  const frame = Buffer.alloc(4 + 2 + payload.length);
  frame.writeInt32BE(2 + payload.length, 0);
  frame.writeUInt16BE(id, 4);
  payload.copy(frame, 6);
  return frame;
}

export class FrameAssembler {
  private pending = Buffer.alloc(0);

  push(chunk: Buffer): Array<{ id: number; payload: Buffer }> {
    this.pending = this.pending.length
      ? Buffer.concat([this.pending, chunk])
      : chunk;
    const frames: Array<{ id: number; payload: Buffer }> = [];
    while (this.pending.length >= 6) {
      const length = this.pending.readInt32BE(0); // bytes after the length field
      if (this.pending.length < 4 + length) break;
      const id = this.pending.readUInt16BE(4);
      const payload = this.pending.subarray(6, 4 + length);
      frames.push({ id, payload: Buffer.from(payload) });
      this.pending = this.pending.subarray(4 + length);
    }
    return frames;
  }
}
