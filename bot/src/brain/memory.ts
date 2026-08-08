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
    // Prompt-injection hardening: `note` is written by the `remember` tool, whose input can be
    // steered by anything a player says in chat, and the file is read back verbatim into the
    // system prompt on every future response (see Brain.respond / PERSONA). A note containing
    // embedded newlines could forge additional "- " bullet lines that read as new memory
    // entries — or, worse, as instructions — so newlines are collapsed to spaces to keep every
    // note a single bullet line. Length is also capped so one note can't balloon the memory
    // file (and the prompt built from it) unboundedly.
    const singleLine = note.replace(/\r\n|\r|\n/g, " ");
    const capped = singleLine.length > 300 ? singleLine.slice(0, 300) : singleLine;
    await appendFile(this.path, `- ${capped}\n`, "utf8");
  }
}
