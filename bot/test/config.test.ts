import { describe, expect, it } from "vitest";
import { loadConfig } from "../src/config.ts";

const baseEnv = {
  WS_URL: "ws://emulator:2096",
  DB_HOST: "db",
  DB_USER: "pixelrp",
  DB_PASSWORD: "pw",
  DB_NAME: "pixelrp",
  ANTHROPIC_API_KEY: "sk-test",
  BOT_USERNAME: "ClaudeTest",
};

describe("loadConfig", () => {
  it("loads a full config", () => {
    const config = loadConfig({ ...baseEnv });
    expect(config.enabled).toBe(true);
    expect(config.anthropicApiKey).toBe("sk-test");
  });

  it("treats a missing ANTHROPIC_API_KEY as disabled rather than fatal", () => {
    const config = loadConfig({ ...baseEnv, ANTHROPIC_API_KEY: "" });
    expect(config.enabled).toBe(true);
    expect(config.anthropicApiKey).toBe("");
  });

  it("still throws on other missing env vars", () => {
    expect(() => loadConfig({ ...baseEnv, WS_URL: "" })).toThrow(/WS_URL/);
  });

  it("respects the BOT_ENABLED kill switch", () => {
    expect(loadConfig({ ...baseEnv, BOT_ENABLED: "false" }).enabled).toBe(false);
  });
});
