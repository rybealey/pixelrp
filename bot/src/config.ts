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
  const required = ["WS_URL", "DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME", "ANTHROPIC_API_KEY", "BOT_USERNAME"];
  const missing = required.filter((k) => !env[k]);
  if (missing.length) throw new Error(`missing env vars: ${missing.join(", ")}`);
  return {
    enabled: env.BOT_ENABLED !== "false",
    wsUrl: env.WS_URL!,
    db: { host: env.DB_HOST!, user: env.DB_USER!, password: env.DB_PASSWORD!, database: env.DB_NAME! },
    anthropicApiKey: env.ANTHROPIC_API_KEY!,
    botUsername: env.BOT_USERNAME!,
    homeRoom: Number(env.BOT_HOME_ROOM ?? 1),
    memoryPath: env.MEMORY_PATH ?? "/data/memory.md",
  };
}
