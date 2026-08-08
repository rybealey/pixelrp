import { describe, expect, it } from "vitest";
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
});
