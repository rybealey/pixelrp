import { describe, expect, it } from "vitest";
import { Transcript, isAddressed } from "../src/brain/transcript.ts";

describe("isAddressed", () => {
  it("matches 'claude' case-insensitively anywhere", () => {
    expect(isAddressed("hey Claude, you there?", false)).toBe(true);
    expect(isAddressed("CLAUDE!!", false)).toBe(true);
    expect(isAddressed("what a nice day", false)).toBe(false);
  });
  it("whispers are always addressed", () => {
    expect(isAddressed("anything", true)).toBe(true);
  });
});

describe("Transcript", () => {
  it("renders as 'user: message' lines, oldest first", () => {
    const t = new Transcript();
    t.add("Ry", "hi");
    t.add("twist", "yo");
    expect(t.render()).toBe("Ry: hi\ntwist: yo");
  });
  it("caps at the configured size, dropping oldest", () => {
    const t = new Transcript(2);
    t.add("a", "1");
    t.add("b", "2");
    t.add("c", "3");
    expect(t.render()).toBe("b: 2\nc: 3");
  });
});
