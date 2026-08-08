import { describe, expect, it } from "vitest";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { MemoryFile } from "../src/brain/memory.ts";

describe("MemoryFile", () => {
  it("reads empty string when file missing, appends notes", async () => {
    const dir = await mkdtemp(join(tmpdir(), "botmem-"));
    const mem = new MemoryFile(join(dir, "memory.md"));
    expect(await mem.read()).toBe("");
    await mem.append("kat is Jake's girl");
    await mem.append("twist rebuilt his testt room");
    expect(await mem.read()).toBe(
      "- kat is Jake's girl\n- twist rebuilt his testt room\n",
    );
  });
});
