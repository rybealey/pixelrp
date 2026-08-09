import { describe, expect, it, vi } from "vitest";
import { FlagWatcher, type FlagQuery } from "../src/flag.ts";

function watcherWith(values: Array<string | null | Error>): { watcher: FlagWatcher; query: ReturnType<typeof vi.fn> } {
  let i = 0;
  const query = vi.fn<FlagQuery>(async () => {
    const v = values[Math.min(i++, values.length - 1)];
    if (v instanceof Error) throw v;
    return v;
  });
  return { watcher: new FlagWatcher(query), query };
}

describe("FlagWatcher", () => {
  it("defaults to enabled and stays enabled on '1'", async () => {
    const { watcher } = watcherWith(["1"]);
    expect(watcher.isEnabled).toBe(true);
    await watcher.pollOnce();
    expect(watcher.isEnabled).toBe(true);
  });

  it("treats a missing row as enabled", async () => {
    const { watcher } = watcherWith([null]);
    await watcher.pollOnce();
    expect(watcher.isEnabled).toBe(true);
  });

  it("fires onDisable exactly once when the flag flips off", async () => {
    const { watcher } = watcherWith(["1", "0", "0"]);
    const close = vi.fn();
    watcher.onDisable(close);
    await watcher.pollOnce();
    expect(close).not.toHaveBeenCalled();
    await watcher.pollOnce();
    expect(close).toHaveBeenCalledTimes(1);
    await watcher.pollOnce(); // still off: no repeat fire
    expect(close).toHaveBeenCalledTimes(1);
    expect(watcher.isEnabled).toBe(false);
  });

  it("waitUntilEnabled resolves immediately while enabled", async () => {
    const { watcher } = watcherWith(["1"]);
    await expect(watcher.waitUntilEnabled()).resolves.toBeUndefined();
  });

  it("waitUntilEnabled parks while off and releases when re-enabled", async () => {
    const { watcher } = watcherWith(["0", "0", "1"]);
    await watcher.pollOnce();
    expect(watcher.isEnabled).toBe(false);
    let released = false;
    const waiting = watcher.waitUntilEnabled().then(() => {
      released = true;
    });
    await watcher.pollOnce(); // still off
    expect(released).toBe(false);
    await watcher.pollOnce(); // back on
    await waiting;
    expect(released).toBe(true);
  });

  it("keeps the current state when the query throws", async () => {
    const { watcher } = watcherWith(["0", new Error("db down"), "1"]);
    await watcher.pollOnce();
    expect(watcher.isEnabled).toBe(false);
    await watcher.pollOnce(); // error: state must not flip back to default
    expect(watcher.isEnabled).toBe(false);
    await watcher.pollOnce(); // recovery applies the fresh value
    expect(watcher.isEnabled).toBe(true);
  });

  it("onDisable(null) clears the hook", async () => {
    const { watcher } = watcherWith(["1", "0"]);
    const close = vi.fn();
    watcher.onDisable(close);
    watcher.onDisable(null);
    await watcher.pollOnce();
    await watcher.pollOnce();
    expect(close).not.toHaveBeenCalled();
  });
});
