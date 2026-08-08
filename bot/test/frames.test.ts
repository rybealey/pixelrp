import { describe, expect, it, vi } from "vitest";
import { encodeFrame, FrameAssembler } from "../src/protocol/frames.ts";
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

  it("treats a malformed length (<2) as stream desync: drops pending bytes and returns frames decoded so far", () => {
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
    // The desync wipes the pending buffer, so more bytes arriving afterward start a clean
    // parse rather than being misread against the garbage that was dropped.
    const next = encodeFrame(2, Buffer.from([5]));
    expect(asm.push(next)).toEqual([{ id: 2, payload: Buffer.from([5]) }]);
    warn.mockRestore();
  });
});
