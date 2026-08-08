import { describe, expect, it } from "vitest";
import { BinaryWriter } from "../src/protocol/buffer.ts";
import { parseChat, parseRoomForward, parseUsers } from "../src/game/parsers.ts";

// Field order verified against emulator source:
//   emulator/Communication/Packets/Outgoing/Rooms/Chat/ChatComposer.cs (Compose, lines 21-29)
// WriteInteger(virtualId), WriteString(message), WriteInteger(emotion),
// WriteInteger(colour/bubble), WriteInteger(0) [hardcoded], WriteInteger(-1) [hardcoded].
// parseChat only needs the first two fields; the rest are fixed/irrelevant.
function chatFixture(unitId: number, message: string): Buffer {
  return new BinaryWriter()
    .writeInt(unitId)
    .writeString(message)
    .writeInt(0) // emotion
    .writeInt(0) // bubble/colour
    .writeInt(0) // hardcoded 0 in source
    .writeInt(-1) // hardcoded -1 in source
    .toBuffer();
}

// Field order verified against emulator source:
//   emulator/Communication/Packets/Outgoing/Rooms/Engine/UsersComposer.cs
//   (WriteUser, lines 31-76, non-pet/non-bot branch, i.e. userType 1)
// WriteInteger(userId), WriteString(username), WriteString(motto), WriteString(figure/look),
// WriteInteger(unitId), WriteInteger(x), WriteInteger(y), WriteString(z), WriteInteger(dir),
// WriteInteger(userType=1), then the type-1 tail:
// WriteString(gender), WriteInteger(groupId), WriteInteger(groupStatus, always 0),
// WriteString(groupName), WriteString(swimFigure, always ""), WriteInteger(achievementScore),
// WriteBoolean(isModerator, always false).
function userEntry(w: BinaryWriter, userId: number, username: string, unitId: number) {
  w.writeInt(userId)
    .writeString(username)
    .writeString("motto")
    .writeString("figure")
    .writeInt(unitId)
    .writeInt(5) // x
    .writeInt(6) // y
    .writeString("0.0") // z
    .writeInt(2) // dir
    .writeInt(1); // userType 1 = user
  // type-1 tail (UsersComposer.cs lines 60-75):
  w.writeString("m") // gender
    .writeInt(0) // group id
    .writeInt(0) // group status (always 0 in source)
    .writeString("") // group name
    .writeString("") // swim figure (always "" in source)
    .writeInt(0) // achievement score
    .writeBool(false); // is moderator (always false in source)
}

// Field order verified against emulator source:
//   emulator/Communication/Packets/Outgoing/Rooms/Engine/UsersComposer.cs
//   (WriteUser, bot branch, userType 4, lines 143-164)
// Shares the same 10-field common prefix as userEntry() above, then diverges into the
// bot-specific tail: WriteString(gender), WriteInteger(ownerId), WriteString(ownerName),
// WriteInteger(actionCount=5), then 5x WriteShort (preset actions 1-5).
function botEntry(w: BinaryWriter, baseId: number, name: string, unitId: number) {
  w.writeInt(baseId)
    .writeString(name)
    .writeString("motto")
    .writeString("figure")
    .writeInt(unitId)
    .writeInt(5) // x
    .writeInt(6) // y
    .writeString("0.0") // z
    .writeInt(0) // dir (hardcoded 0 for bots)
    .writeInt(4); // userType 4 = bot
  // bot tail (UsersComposer.cs lines 155-163):
  w.writeString("m") // gender
    .writeInt(1) // owner userId
    .writeString("Ry") // owner username
    .writeInt(5) // hardcoded action count
    .writeShort(1)
    .writeShort(2)
    .writeShort(3)
    .writeShort(4)
    .writeShort(5);
}

describe("parsers", () => {
  it("parses chat unitId + message, ignoring the tail", () => {
    expect(parseChat(chatFixture(42, "hey claude"))).toEqual({
      unitId: 42,
      message: "hey claude",
    });
  });

  it("parses room forward", () => {
    const buf = new BinaryWriter().writeInt(10).toBuffer();
    expect(parseRoomForward(buf)).toEqual({ roomId: 10 });
  });

  it("parses a two-user roster", () => {
    const w = new BinaryWriter().writeInt(2);
    userEntry(w, 100, "Ry", 1);
    userEntry(w, 101, "twist", 2);
    const users = parseUsers(w.toBuffer());
    expect(users).toEqual([
      { userId: 100, username: "Ry", unitId: 1, userType: 1 },
      { userId: 101, username: "twist", unitId: 2, userType: 1 },
    ]);
  });

  it("returns [] instead of throwing on malformed roster", () => {
    expect(parseUsers(Buffer.from([0, 0, 0, 5, 1]))).toEqual([]);
  });

  it("parses past a bot's tail to keep reading the users behind it (regression: truncation broke self-detection when the bot's own entry sat behind another bot/pet)", () => {
    const w = new BinaryWriter().writeInt(3);
    userEntry(w, 100, "Ry", 1);
    botEntry(w, 999, "Rentcop", 2);
    userEntry(w, 101, "ClaudeTest", 3);
    const users = parseUsers(w.toBuffer());
    expect(users).toEqual([
      { userId: 100, username: "Ry", unitId: 1, userType: 1 },
      { userId: 999, username: "Rentcop", unitId: 2, userType: 4 },
      { userId: 101, username: "ClaudeTest", unitId: 3, userType: 1 },
    ]);
  });
});
