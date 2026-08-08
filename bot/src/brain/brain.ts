import type Anthropic from "@anthropic-ai/sdk";
import { betaTool } from "@anthropic-ai/sdk/helpers/beta/json-schema.mjs";
import { PERSONA } from "./persona.ts";
import { chunkReply } from "./chunk.ts";
import type { MemoryFile } from "./memory.ts";
import type { Transcript } from "./transcript.ts";

interface GameActions {
  say(message: string): void;
  whisper(user: string, message: string): void;
  walkTo(x: number, y: number): void;
  goToRoom(roomId: number): void;
}

export class Brain {
  private busy = false;
  private sleep: (ms: number) => Promise<void>;

  constructor(
    private deps: {
      anthropic: Anthropic;
      game: GameActions;
      memory: MemoryFile;
      transcript: Transcript;
      sleep?: (ms: number) => Promise<void>;
    },
  ) {
    this.sleep = deps.sleep ?? ((ms) => new Promise((r) => setTimeout(r, ms)));
  }

  async respond(trigger: { username: string; message: string; whisper: boolean }): Promise<void> {
    if (this.busy) {
      console.log(`[brain] busy — dropping trigger from ${trigger.username}`);
      return;
    }
    this.busy = true;
    try {
      const memory = await this.deps.memory.read();
      const tools = this.buildTools();
      const runner = this.deps.anthropic.beta.messages.toolRunner({
        model: "claude-opus-5",
        max_tokens: 1000,
        output_config: { effort: "low" },
        system: [
          { type: "text", text: PERSONA + memory, cache_control: { type: "ephemeral" } },
        ],
        tools,
        messages: [
          {
            role: "user",
            content:
              `Recent room chat:\n${this.deps.transcript.render()}\n\n` +
              `${trigger.username} just ${trigger.whisper ? "whispered to you" : "said"}: ` +
              `"${trigger.message}"\nRespond using your tools.`,
          },
        ],
      });
      await runner.done();
    } catch (err) {
      console.error("[brain] respond failed:", err);
    } finally {
      this.busy = false;
    }
  }

  private buildTools() {
    const { game, memory } = this.deps;
    const speak = async (send: (line: string) => void, message: string) => {
      const chunks = chunkReply(message).slice(0, 3);
      for (const [i, chunk] of chunks.entries()) {
        if (i > 0) await this.sleep(700);
        send(chunk);
      }
      return "sent";
    };
    return [
      betaTool({
        name: "say",
        description: "Say a message in the current room (public chat bubble).",
        inputSchema: {
          type: "object",
          properties: { message: { type: "string" } },
          required: ["message"],
        },
        run: (input: { message: string }) => speak((l) => game.say(l), input.message),
      }),
      betaTool({
        name: "whisper",
        description: "Whisper privately to a user in the room.",
        inputSchema: {
          type: "object",
          properties: { user: { type: "string" }, message: { type: "string" } },
          required: ["user", "message"],
        },
        run: (input: { user: string; message: string }) =>
          speak((l) => game.whisper(input.user, l), input.message),
      }),
      betaTool({
        name: "walk_to",
        description: "Walk to a tile in the current room.",
        inputSchema: {
          type: "object",
          properties: { x: { type: "integer" }, y: { type: "integer" } },
          required: ["x", "y"],
        },
        run: (input: { x: number; y: number }) => {
          game.walkTo(input.x, input.y);
          return "walking";
        },
      }),
      betaTool({
        name: "go_to_room",
        description: "Move to another room by its numeric id.",
        inputSchema: {
          type: "object",
          properties: { roomId: { type: "integer" } },
          required: ["roomId"],
        },
        run: (input: { roomId: number }) => {
          game.goToRoom(input.roomId);
          return "moving";
        },
      }),
      betaTool({
        name: "remember",
        description: "Save a short durable note to long-term memory.",
        inputSchema: {
          type: "object",
          properties: { note: { type: "string" } },
          required: ["note"],
        },
        run: async (input: { note: string }) => {
          await memory.append(input.note);
          return "remembered";
        },
      }),
    ];
  }
}
