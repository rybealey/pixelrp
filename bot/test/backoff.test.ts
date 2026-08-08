import { describe, expect, it } from "vitest";
import { nextDelay } from "../src/backoff.ts";

describe("nextDelay", () => {
  it("starts at 10s and doubles", () => {
    expect(nextDelay(0)).toBe(10_000);
    expect(nextDelay(1)).toBe(20_000);
    expect(nextDelay(2)).toBe(40_000);
  });
  it("caps at 5 minutes", () => {
    expect(nextDelay(10)).toBe(300_000);
  });
});
