export interface Config {
  enabled: boolean;
  wsUrl: string;
  db: { host: string; user: string; password: string; database: string };
  anthropicApiKey: string;
  botUsername: string;
  homeRoom: number;
  memoryPath: string;
}

export function loadConfig(env = process.env): Config {
  // ANTHROPIC_API_KEY is deliberately not in this list: .env.example ships it empty, and a
  // throw here would just make the compose service (restart: unless-stopped) crash-loop on a
  // fresh dev checkout. An empty key instead idles the bot — index.ts treats it like the
  // BOT_ENABLED kill switch, with its own log line.
  const required = ["WS_URL", "DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME", "BOT_USERNAME"];
  const missing = required.filter((k) => !env[k]);
  if (missing.length) throw new Error(`missing env vars: ${missing.join(", ")}`);
  return {
    enabled: env.BOT_ENABLED !== "false",
    wsUrl: env.WS_URL!,
    db: { host: env.DB_HOST!, user: env.DB_USER!, password: env.DB_PASSWORD!, database: env.DB_NAME! },
    anthropicApiKey: env.ANTHROPIC_API_KEY ?? "",
    botUsername: env.BOT_USERNAME!,
    homeRoom: Number(env.BOT_HOME_ROOM ?? 1),
    memoryPath: env.MEMORY_PATH ?? "/data/memory.md",
  };
}
