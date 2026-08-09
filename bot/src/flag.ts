// In-game kill switch: staff toggle server_settings.`bot.enabled` with the
// emulator's :bot command; this watcher polls the row and the main loop /
// active session react to it. BOT_ENABLED in the env stays the hard override —
// when it's false the process idles before this module is ever constructed.

/** Returns the flag row's value, or null when the row doesn't exist. */
export type FlagQuery = () => Promise<string | null>;

export class FlagWatcher {
  private enabled = true;
  private waiters: Array<() => void> = [];
  private onDisableFn: (() => void) | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private errorStreak = 0;
  // Plain fields, not constructor parameter properties: the container runs
  // this file through Node's strip-only TS loader, which rejects them.
  private readonly query: FlagQuery;
  private readonly intervalMs: number;

  constructor(query: FlagQuery, intervalMs = 10_000) {
    this.query = query;
    this.intervalMs = intervalMs;
  }

  /** Starts polling. The returned promise settles after the first poll, so
   * callers can know the initial state before connecting. */
  async start(): Promise<void> {
    await this.pollOnce();
    this.timer = setInterval(() => void this.pollOnce(), this.intervalMs);
    // Never keep the process alive just to poll a kill switch.
    this.timer.unref?.();
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }

  get isEnabled(): boolean {
    return this.enabled;
  }

  /** Resolves immediately when enabled; otherwise parks until a poll flips the
   * flag back on. */
  waitUntilEnabled(): Promise<void> {
    if (this.enabled) return Promise.resolve();
    return new Promise((resolve) => this.waiters.push(resolve));
  }

  /** At most one listener — the active session's "close my connection" hook.
   * Pass null when the session ends. */
  onDisable(fn: (() => void) | null): void {
    this.onDisableFn = fn;
  }

  async pollOnce(): Promise<void> {
    let value: string | null;
    try {
      value = await this.query();
    } catch (err) {
      // A DB blip must never flip the switch or spam the log: keep the last
      // known state and report once per error streak.
      if (this.errorStreak === 0) console.error("[bot] bot.enabled poll error (keeping current state):", err);
      this.errorStreak++;
      return;
    }
    this.errorStreak = 0;
    // Missing row = enabled: matches behavior before the toggle existed.
    this.setEnabled(value === null || value === "1");
  }

  private setEnabled(next: boolean): void {
    if (next === this.enabled) return;
    this.enabled = next;
    if (next) {
      console.log("[bot] enabled via :bot — reconnecting");
      const waiters = this.waiters;
      this.waiters = [];
      for (const release of waiters) release();
    } else {
      console.log("[bot] disabled via :bot — disconnecting");
      this.onDisableFn?.();
    }
  }
}
