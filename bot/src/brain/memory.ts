import { appendFile, readFile, rename, stat, writeFile } from "node:fs/promises";

// Nothing else ever shortens the file: one line per `remember` call, for as long as the bot
// runs. Brain only puts the last 4000 chars of it into the prompt (MAX_MEMORY_CHARS in
// brain.ts), so once the file passes MAX_FILE_BYTES it is cut back to its newest
// KEEP_CHARS, on a line boundary. That is more than the prompt sees, so a trim never drops a
// note the bot could still read, and the gap between the two means it trims every few dozen
// notes rather than on every one.
const MAX_FILE_BYTES = 8 * 1024;
const KEEP_CHARS = 6000;

export class MemoryFile {
  private path: string;
  // Appends run one at a time: the tool runner runs a turn's tool calls in parallel, and a
  // trim that read the file before another note was appended would write that note away.
  private writes: Promise<void> = Promise.resolve();

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

  append(note: string): Promise<void> {
    // Prompt-injection hardening: `note` is written by the `remember` tool, whose input can be
    // steered by anything a player says in chat, and the file is read back verbatim into the
    // system prompt on every future response (see Brain.respond / PERSONA). A note containing
    // embedded newlines could forge additional "- " bullet lines that read as new memory
    // entries — or, worse, as instructions — so newlines are collapsed to spaces to keep every
    // note a single bullet line. Length is also capped so one note can't balloon the memory
    // file (and the prompt built from it) unboundedly.
    const singleLine = note.replace(/\r\n|\r|\n/g, " ");
    const capped = singleLine.length > 300 ? singleLine.slice(0, 300) : singleLine;
    const done = this.writes.then(() => this.write(`- ${capped}\n`));
    this.writes = done.catch(() => {}); // one failed write must not block the next
    return done;
  }

  private async write(line: string): Promise<void> {
    await appendFile(this.path, line, "utf8");
    if ((await stat(this.path)).size <= MAX_FILE_BYTES) return;
    const text = await readFile(this.path, "utf8");
    if (text.length <= KEEP_CHARS) return;
    // Keep from the first line start inside the last KEEP_CHARS: whole notes only.
    const cut = text.indexOf("\n", text.length - KEEP_CHARS - 1);
    // Written beside the file and renamed over it, so a crash mid-write can't leave the
    // memory file empty or half written.
    const tmp = `${this.path}.tmp`;
    await writeFile(tmp, text.slice(cut + 1), "utf8");
    await rename(tmp, this.path);
  }
}
