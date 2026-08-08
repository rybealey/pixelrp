import { describe, expect, it, vi } from "vitest";
import { Brain } from "../src/brain/brain.ts";
import { Transcript } from "../src/brain/transcript.ts";
import { MemoryFile } from "../src/brain/memory.ts";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

function fakeAnthropic(reply: string) {
  return {
    beta: {
      messages: {
        toolRunner: vi.fn((params: { tools: Array<{ name: string; run: (input: never) => unknown }> }) => {
          const say = params.tools.find((t) => t.name === "say")!;
          // simulate the runner executing one tool call then finishing
          const done = Promise.resolve(say.run({ message: reply } as never)).then(() => ({
            content: [],
          }));
          return { done: () => done, [Symbol.asyncIterator]: async function* () { await done; } };
        }),
      },
    },
  };
}

describe("Brain", () => {
  it("responds to a trigger by saying chunked reply via the game client", async () => {
    const said: string[] = [];
    const game = {
      say: (m: string) => void said.push(m),
      whisper: vi.fn(),
      walkTo: vi.fn(),
      goToRoom: vi.fn(),
    };
    const dir = await mkdtemp(join(tmpdir(), "brain-"));
    const brain = new Brain({
      anthropic: fakeAnthropic("hello Ry! good to see you") as never,
      game,
      memory: new MemoryFile(join(dir, "m.md")),
      transcript: new Transcript(),
      sleep: async () => {},
    });
    await brain.respond({ username: "Ry", message: "hi claude", whisper: false });
    expect(said).toEqual(["hello Ry! good to see you"]);
  });

  it("drops overlapping triggers instead of queuing", async () => {
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    const anthropic = {
      beta: {
        messages: {
          toolRunner: vi.fn(() => ({
            done: () => gate.then(() => ({ content: [] })),
            [Symbol.asyncIterator]: async function* () { await gate; },
          })),
        },
      },
    };
    const dir = await mkdtemp(join(tmpdir(), "brain-"));
    const brain = new Brain({
      anthropic: anthropic as never,
      game: { say: vi.fn(), whisper: vi.fn(), walkTo: vi.fn(), goToRoom: vi.fn() },
      memory: new MemoryFile(join(dir, "m.md")),
      transcript: new Transcript(),
      sleep: async () => {},
    });
    const first = brain.respond({ username: "a", message: "claude", whisper: false });
    await brain.respond({ username: "b", message: "claude", whisper: false }); // dropped
    release();
    await first;
    // Only "a" ever reached toolRunner — "b" was dropped while busy, not queued.
    expect(anthropic.beta.messages.toolRunner).toHaveBeenCalledTimes(1);
  });
});
