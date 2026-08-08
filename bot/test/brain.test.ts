import { describe, expect, it, vi } from "vitest";
import { Brain } from "../src/brain/brain.ts";
import { PERSONA } from "../src/brain/persona.ts";
import { Transcript } from "../src/brain/transcript.ts";
import { MemoryFile } from "../src/brain/memory.ts";
import { mkdtemp, writeFile } from "node:fs/promises";
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
          const iterate = async function* () {
            await done;
          };
          // Mirrors the real SDK: done() alone never starts the generator — only
          // runUntilDone() (or iterating directly) drives it to completion.
          return {
            done: () => done,
            runUntilDone: async () => {
              for await (const _ of iterate()) {
                // drain
              }
              return done;
            },
            [Symbol.asyncIterator]: iterate,
          };
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
          toolRunner: vi.fn(() => {
            const done = gate.then(() => ({ content: [] }));
            const iterate = async function* () {
              await gate;
            };
            return {
              done: () => done,
              runUntilDone: async () => {
                for await (const _ of iterate()) {
                  // drain
                }
                return done;
              },
              [Symbol.asyncIterator]: iterate,
            };
          }),
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

  it("caps the memory text included in the system prompt to the last 4000 chars", async () => {
    let capturedSystem = "";
    const anthropic = {
      beta: {
        messages: {
          toolRunner: vi.fn(
            (params: {
              system: Array<{ text: string }>;
              tools: Array<{ name: string; run: (input: never) => unknown }>;
            }) => {
              capturedSystem = params.system[0].text;
              const say = params.tools.find((t) => t.name === "say")!;
              const done = Promise.resolve(say.run({ message: "ok" } as never)).then(() => ({
                content: [],
              }));
              const iterate = async function* () {
                await done;
              };
              return {
                done: () => done,
                runUntilDone: async () => {
                  for await (const _ of iterate()) {
                    // drain
                  }
                  return done;
                },
                [Symbol.asyncIterator]: iterate,
              };
            },
          ),
        },
      },
    };
    const dir = await mkdtemp(join(tmpdir(), "brain-"));
    const memPath = join(dir, "m.md");
    // Write a 5000-char memory file directly (bypassing MemoryFile.append's own 300-char
    // per-note cap) to exercise the read-side cap on its own.
    await writeFile(memPath, "a".repeat(5000), "utf8");
    const brain = new Brain({
      anthropic: anthropic as never,
      game: { say: vi.fn(), whisper: vi.fn(), walkTo: vi.fn(), goToRoom: vi.fn() },
      memory: new MemoryFile(memPath),
      transcript: new Transcript(),
      sleep: async () => {},
    });
    await brain.respond({ username: "Ry", message: "hi claude", whisper: false });
    // system text is PERSONA + (capped) memory — isolate just the memory portion.
    const memoryPortion = capturedSystem.slice(PERSONA.length);
    expect(memoryPortion).toBe("a".repeat(4000));
  });

  it("shares 700ms spacing across separate tool calls within one respond run, not just within one say/whisper call", async () => {
    const sleepCalls: number[] = [];
    const said: string[] = [];
    const whispered: string[] = [];
    const anthropic = {
      beta: {
        messages: {
          toolRunner: vi.fn(
            (params: { tools: Array<{ name: string; run: (input: never) => unknown }> }) => {
              const say = params.tools.find((t) => t.name === "say")!;
              const whisper = params.tools.find((t) => t.name === "whisper")!;
              // Simulates the model making two separate tool calls in one turn.
              const done = (async () => {
                await say.run({ message: "hi there" } as never);
                await whisper.run({ user: "Ry", message: "psst" } as never);
                return { content: [] };
              })();
              const iterate = async function* () {
                await done;
              };
              return {
                done: () => done,
                runUntilDone: async () => {
                  for await (const _ of iterate()) {
                    // drain
                  }
                  return done;
                },
                [Symbol.asyncIterator]: iterate,
              };
            },
          ),
        },
      },
    };
    const dir = await mkdtemp(join(tmpdir(), "brain-"));
    const brain = new Brain({
      anthropic: anthropic as never,
      game: {
        say: (m: string) => void said.push(m),
        whisper: (_u: string, m: string) => void whispered.push(m),
        walkTo: vi.fn(),
        goToRoom: vi.fn(),
      },
      memory: new MemoryFile(join(dir, "m.md")),
      transcript: new Transcript(),
      sleep: async (ms: number) => void sleepCalls.push(ms),
    });
    await brain.respond({ username: "Ry", message: "hi claude", whisper: false });
    expect(said).toEqual(["hi there"]);
    expect(whispered).toEqual(["psst"]);
    // The say() call's one chunk is the very first line ever sent, so no wait. The whisper()
    // call's chunk is a *different* tool call but must still observe the 700ms spacing from
    // the say line before it — this is the cross-call spacing the fix adds.
    expect(sleepCalls).toEqual([700]);
  });
});
