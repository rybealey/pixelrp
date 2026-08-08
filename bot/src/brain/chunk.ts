export function chunkReply(text: string, max = 100): string[] {
  const chunks: string[] = [];
  for (const line of text.split("\n")) {
    const words = line.trim();
    if (!words) continue;
    let current = "";
    for (const word of words.split(/\s+/)) {
      if (word.length > max) {
        if (current) {
          chunks.push(current);
          current = "";
        }
        for (let i = 0; i < word.length; i += max) chunks.push(word.slice(i, i + max));
        continue;
      }
      const candidate = current ? `${current} ${word}` : word;
      if (candidate.length > max) {
        chunks.push(current);
        current = word;
      } else {
        current = candidate;
      }
    }
    if (current) chunks.push(current);
  }
  return chunks;
}
