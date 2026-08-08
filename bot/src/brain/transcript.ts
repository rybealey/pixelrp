export function isAddressed(message: string, whisper: boolean): boolean {
  return whisper || message.toLowerCase().includes("claude");
}

export class Transcript {
  private lines: string[] = [];
  private cap: number;

  constructor(cap = 30) {
    this.cap = cap;
  }

  add(username: string, message: string): void {
    this.lines.push(`${username}: ${message}`);
    if (this.lines.length > this.cap) this.lines.shift();
  }

  render(): string {
    return this.lines.join("\n");
  }
}
