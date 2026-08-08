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
//     userType 2 (pet) and userType 4 (bot) share the exact same 10-field common prefix
//     above (baseId/name/motto/look/virtualId/x/y/z/dir/userType — WriteUser() writes these
//     in the same order and types for every branch), then diverge into different, longer
//     tails that we don't need for the bot's own purposes but must still consume field-by-
//     field to keep the stream aligned for whatever roster entry comes after — including,
//     potentially, the bot's own entry (roster order is not guaranteed to put the bot last).
//
//     userType 2 (pet) tail, WriteUser() L133-141:
//       WriteInteger(user.PetData.Type)        -> pet type
//       WriteInteger(user.PetData.OwnerId)     -> owner userId
//       WriteString(user.PetData.OwnerName)    -> owner username
//       WriteInteger(1)                        -> hardcoded constant
//       WriteBoolean(user.PetData.Saddle > 0)  -> has saddle
//       WriteBoolean(user.RidingHorse)         -> is being ridden
//       WriteInteger(0)                        -> hardcoded constant
//       WriteInteger(0)                        -> hardcoded constant
//       WriteString("")                        -> hardcoded constant
//
//     userType 4 (bot) tail, WriteUser() L155-163:
//       WriteString(user.BotData.Gender.ToLower())              -> gender
//       WriteInteger(user.BotData.OwnerId)                      -> owner userId
//       WriteString(PlusEnvironment.GetUsernameById(OwnerId))   -> owner username
//       WriteInteger(5)                                         -> hardcoded action count
//       WriteShort(1) / WriteShort(2) / WriteShort(3) / WriteShort(4) / WriteShort(5)
//                                                                -> 5 hardcoded preset-action shorts
//
//     Any other userType has no known tail shape in this composer, so for that case only we
//     stop and return the entries decoded so far rather than risk misaligning the stream on
//     an assumption we can't verify.

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
      if (userType === 1) {
        // Type-1 (user) tail — see UsersComposer.cs L60-75 cited above.
        r.readString(); // gender
        r.readInt(); // group id
        r.readInt(); // group status
        r.readString(); // group name
        r.readString(); // swim figure
        r.readInt(); // achievement score
        r.readBool(); // is moderator
      } else if (userType === 2) {
        // Type-2 (pet) tail — UsersComposer.cs WriteUser() L133-141, cited above.
        r.readInt(); // pet type
        r.readInt(); // owner userId
        r.readString(); // owner username
        r.readInt(); // hardcoded constant (1)
        r.readBool(); // has saddle
        r.readBool(); // is being ridden
        r.readInt(); // hardcoded constant (0)
        r.readInt(); // hardcoded constant (0)
        r.readString(); // hardcoded constant ("")
      } else if (userType === 4) {
        // Type-4 (bot) tail — UsersComposer.cs WriteUser() L155-163, cited above.
        r.readString(); // gender
        r.readInt(); // owner userId
        r.readString(); // owner username
        r.readInt(); // hardcoded action count (5)
        r.readShort(); // preset action 1
        r.readShort(); // preset action 2
        r.readShort(); // preset action 3
        r.readShort(); // preset action 4
        r.readShort(); // preset action 5
      } else {
        // No known tail shape for this userType — stop rather than misalign the stream,
        // returning what we've decoded so far.
        users.push({ userId, username, unitId, userType });
        break;
      }
      users.push({ userId, username, unitId, userType });
    }
    return users;
  } catch {
    return [];
  }
}
