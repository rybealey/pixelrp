import { BinaryReader } from "../protocol/buffer.ts";

// Field orders verified against emulator sources on 2026-08-08:
//
//   emulator/Communication/Packets/Outgoing/Rooms/Chat/ChatComposer.cs (Compose, L21-29)
//     WriteInteger(virtualId)   -> unitId
//     WriteString(message)     -> message
//     WriteInteger(emotion)
//     WriteInteger(colour)     -> "bubble"
//     WriteInteger(0)          -> hardcoded constant, not a url count field
//     WriteInteger(-1)         -> hardcoded constant, not message.length
//   Only the first two fields are consumed here; the rest are fixed/unused.
//   Same prefix is shared by ShoutComposer/WhisperComposer (not separately verified,
//   per task brief they share ChatComposer's shape).
//
//   emulator/Communication/Packets/Outgoing/Rooms/Session/RoomForwardComposer.cs (Compose, L15)
//     WriteUInteger(roomId)    -> roomId
//   BinaryWriter/BinaryReader (Task 2) only expose signed int32 read/write; room ids fit well
//   under 2^31 so readInt()/writeInt() round-trip the same bits as the emulator's uint.
//
//   emulator/Communication/Packets/Outgoing/Rooms/Engine/UsersComposer.cs (WriteUser, L31-165)
//     Compose():  WriteInteger(count), then WriteUser() per entry.
//     WriteUser() branches by user.IsPet / user.IsBot / neither (regular user, userType 1):
//
//     userType 1 (regular user), L50-75:
//       WriteInteger(habbo.Id)          -> userId
//       WriteString(habbo.Username)     -> username
//       WriteString(habbo.Motto)        -> motto
//       WriteString(habbo.Look)         -> figure
//       WriteInteger(user.VirtualId)    -> unitId
//       WriteInteger(user.X)            -> x
//       WriteInteger(user.Y)            -> y
//       WriteString(user.Z)             -> z
//       WriteInteger(user.RotBody)      -> dir
//       WriteInteger(1)                 -> userType (1 = user)
//       -- type-1 tail --
//       WriteString(habbo.Gender)       -> gender
//       WriteInteger(group.Id or 0)     -> groupId
//       WriteInteger(0)                 -> groupStatus (always 0 in source)
//       WriteString(group.Name or "")   -> groupName
//       WriteString("")                 -> swimFigure (always "" in source)
//       WriteInteger(achievementPoints) -> achievementScore
//       WriteBoolean(false)             -> isModerator (always false in source)
//
//     userType 2 (pet, L117-141) and userType 4 (bot, L143-164) have different, longer
//     tails (pet type/owner/saddle/riding flags; bot owner/action-count/5 shorts of
//     preset actions) that we do not need for the bot's purposes. We do not attempt to
//     parse them field-by-field: once we hit a non-1 userType we stop, returning the
//     entries decoded so far, rather than risk misaligning the stream on an assumption
//     about a tail we don't consume.

export function parseChat(payload: Buffer): { unitId: number; message: string } {
  const r = new BinaryReader(payload);
  return { unitId: r.readInt(), message: r.readString() };
}

export function parseRoomForward(payload: Buffer): { roomId: number } {
  return { roomId: new BinaryReader(payload).readInt() };
}

export interface RoomUser {
  userId: number;
  username: string;
  unitId: number;
  userType: number;
}

export function parseUsers(payload: Buffer): RoomUser[] {
  try {
    const r = new BinaryReader(payload);
    const count = r.readInt();
    const users: RoomUser[] = [];
    for (let i = 0; i < count; i++) {
      const userId = r.readInt();
      const username = r.readString();
      r.readString(); // motto
      r.readString(); // figure
      const unitId = r.readInt();
      r.readInt(); // x
      r.readInt(); // y
      r.readString(); // z
      r.readInt(); // dir
      const userType = r.readInt();
      if (userType !== 1) {
        // Bots/pets (userType 2/4) have different tails we don't parse — stop rather
        // than misalign the stream, returning what we've decoded so far.
        users.push({ userId, username, unitId, userType });
        break;
      }
      // Type-1 (user) tail — see UsersComposer.cs L60-75 cited above.
      r.readString(); // gender
      r.readInt(); // group id
      r.readInt(); // group status
      r.readString(); // group name
      r.readString(); // swim figure
      r.readInt(); // achievement score
      r.readBool(); // is moderator
      users.push({ userId, username, unitId, userType });
    }
    return users;
  } catch {
    return [];
  }
}
