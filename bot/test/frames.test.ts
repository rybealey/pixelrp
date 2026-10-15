import { describe, expect, it, vi } from "vitest";
import { encodeFrame, FrameAssembler, MAX_FRAME_LENGTH } from "../src/protocol/frames.ts";
import { BinaryWriter } from "../src/protocol/buffer.ts";

describe("frames", () => {
  it("encodes length = 2 + payload bytes", () => {
    const payload = new BinaryWriter().writeString("hi").toBuffer(); // 4 bytes
    const frame = encodeFrame(1314, payload);
    expect(frame.readInt32BE(0)).toBe(2 + 4);
    expect(frame.readUInt16BE(4)).toBe(1314);
    expect(frame.length).toBe(4 + 2 + 4);
  });

  it("reassembles two frames from one chunk", () => {
    const a = encodeFrame(1, Buffer.from([9]));
    const b = encodeFrame(2, Buffer.alloc(0));
    const out = new FrameAssembler().push(Buffer.concat([a, b]));
    expect(out.map((f) => f.id)).toEqual([1, 2]);
    expect(out[0].payload).toEqual(Buffer.from([9]));
  });

  it("reassembles one frame split across chunks", () => {
    const frame = encodeFrame(7, Buffer.from("payload"));
    const asm = new FrameAssembler();
    expect(asm.push(frame.subarray(0, 3))).toEqual([]);
    const out = asm.push(frame.subarray(3));
    expect(out).toHaveLength(1);
    expect(out[0].id).toBe(7);
    expect(out[0].payload.toString()).toBe("payload");
  });

  it("treats a malformed length (<2) as stream desync: returns frames decoded so far, then nothing", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const good = encodeFrame(1, Buffer.from([9]));
    // A hand-built "frame" with length=1, which no real encodeFrame() output can produce (the
    // minimum valid length is 2: the packet id alone, with an empty payload).
    const malformed = Buffer.alloc(4 + 2);
    malformed.writeInt32BE(1, 0);
    malformed.writeUInt16BE(99, 4);
    const trailingGarbage = Buffer.from([1, 2, 3]);
    const asm = new FrameAssembler();
    const out = asm.push(Buffer.concat([good, malformed, trailingGarbage]));
    // The good frame before the malformed one is still returned.
    expect(out).toEqual([{ id: 1, payload: Buffer.from([9]) }]);
    expect(warn).toHaveBeenCalled();
    expect(asm.desynced).toBe(true);
    // The stream is finished (Connection closes it): later bytes are neither decoded nor kept.
    expect(asm.push(encodeFrame(2, Buffer.from([5])))).toEqual([]);
    warn.mockRestore();
  });

  it("treats a huge length as stream desync instead of buffering every chunk while it waits", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    // What a desynced stream sees when it lands on text: "{\"us" read as a length is ~2 GB.
    const asm = new FrameAssembler();
    expect(asm.push(Buffer.from('{"user":"x"}'))).toEqual([]);
    expect(asm.desynced).toBe(true);
    expect(warn).toHaveBeenCalled();
    // Just over the cap is refused the same way.
    const overCap = new FrameAssembler();
    const header = Buffer.alloc(6);
    header.writeInt32BE(MAX_FRAME_LENGTH + 1, 0);
    expect(overCap.push(header)).toEqual([]);
    expect(overCap.desynced).toBe(true);
    warn.mockRestore();
  });

  it("still assembles a large real frame (a full room's furni list) split across chunks", () => {
    const payload = Buffer.alloc(1024 * 1024, 7); // past the emulator's own incoming cap
    const frame = encodeFrame(3, payload);
    const asm = new FrameAssembler();
    expect(asm.push(frame.subarray(0, 100_000))).toEqual([]);
    const out = asm.push(frame.subarray(100_000));
    expect(asm.desynced).toBe(false);
    expect(out).toHaveLength(1);
    expect(out[0].payload.equals(payload)).toBe(true);
  });
});
