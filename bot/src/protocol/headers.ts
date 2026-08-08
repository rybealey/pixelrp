import revision from "./revision.json" with { type: "json" };

// revision.json terminology is from the SERVER's point of view:
//   IncomingHeaders = client -> server  (packets the bot SENDS)
//   OutgoingHeaders = server -> client  (packets the bot RECEIVES)
const sendMap: Record<string, number> = revision.IncomingHeaders;
const recvMap = new Map<number, string>(
  Object.entries(revision.OutgoingHeaders as Record<string, number>).map(
    ([name, id]) => [id, name],
  ),
);

export const revisionName: string = revision.Name;

export function sendId(name: string): number {
  const id = sendMap[name];
  if (id === undefined) throw new Error(`unknown send packet name: ${name}`);
  return id;
}

export function recvName(id: number): string | undefined {
  return recvMap.get(id);
}
