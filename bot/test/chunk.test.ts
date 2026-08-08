import { describe, expect, it } from "vitest";
import { chunkReply } from "../src/brain/chunk.ts";

describe("chunkReply", () => {
  it("passes short messages through", () => {
    expect(chunkReply("hi there")).toEqual(["hi there"]);
  });
  it("splits on word boundaries at 100 chars", () => {
    const text = Array(30).fill("word").join(" "); // 149 chars
    const chunks = chunkReply(text);
    expect(chunks.length).toBe(2);
    for (const c of chunks) expect(c.length).toBeLessThanOrEqual(100);
    expect(chunks.join(" ")).toBe(text);
  });
  it("hard-splits a single over-long word", () => {
    const chunks = chunkReply("x".repeat(250));
    expect(chunks.map((c) => c.length)).toEqual([100, 100, 50]);
  });
  it("strips newlines into separate bubbles", () => {
    expect(chunkReply("line one\nline two")).toEqual(["line one", "line two"]);
  });
});
