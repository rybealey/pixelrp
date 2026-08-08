export function nextDelay(attempt: number): number {
  return Math.min(10_000 * 2 ** attempt, 300_000);
}
