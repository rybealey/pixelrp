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
});
