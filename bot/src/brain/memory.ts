import { appendFile, readFile } from "node:fs/promises";

export class MemoryFile {
  private path: string;

  constructor(path: string) {
    this.path = path;
  }

  async read(): Promise<string> {
    try {
      return await readFile(this.path, "utf8");
    } catch {
      return "";
    }
  }

  async append(note: string): Promise<void> {
    await appendFile(this.path, `- ${note}\n`, "utf8");
  }
}
