import { describe, expect, it } from "vitest";
import { BinaryReader, BinaryWriter } from "../src/protocol/buffer.ts";

describe("binary codec", () => {
  it("round-trips int, short, string, bool", () => {
    const buf = new BinaryWriter()
      .writeInt(-42)
      .writeShort(1314)
      .writeString("héllo wörld")
      .writeBool(true)
      .writeBool(false)
      .toBuffer();
    const r = new BinaryReader(buf);
    expect(r.readInt()).toBe(-42);
    expect(r.readShort()).toBe(1314);
    expect(r.readString()).toBe("héllo wörld");
    expect(r.readBool()).toBe(true);
    expect(r.readBool()).toBe(false);
    expect(r.remaining()).toBe(0);
  });

  it("string length prefix is byte length, not char length", () => {
    const buf = new BinaryWriter().writeString("é").toBuffer();
    expect(buf.readUInt16BE(0)).toBe(2); // 'é' is 2 UTF-8 bytes
  });

  it("throws when reading past the end", () => {
    const r = new BinaryReader(Buffer.alloc(2));
    expect(() => r.readInt()).toThrow();
  });
});
