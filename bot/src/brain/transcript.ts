export function isAddressed(message: string, whisper: boolean): boolean {
  return whisper || message.toLowerCase().includes("claude");
}

export class Transcript {
  private lines: string[] = [];
  constructor(private cap = 30) {}

  add(username: string, message: string): void {
    this.lines.push(`${username}: ${message}`);
    if (this.lines.length > this.cap) this.lines.shift();
  }

  render(): string {
    return this.lines.join("\n");
  }
}
