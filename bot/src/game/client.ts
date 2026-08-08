import { EventEmitter } from "node:events";
import type { Connection } from "../protocol/connection.ts";
import { BinaryWriter } from "../protocol/buffer.ts";
import { recvName, revisionName, sendId } from "../protocol/headers.ts";
import { parseChat, parseRoomForward, parseUsers } from "./parsers.ts";

export interface ChatMessage {
  username: string;
  message: string;
  whisper: boolean;
  self: boolean;
  userType: number;
}

export class GameClient extends EventEmitter {
  private roster = new Map<number, { username: string; userType: number }>();
  botUnitId: number | undefined;
  private conn: Connection;
  private botUsername: string;

  constructor(conn: Connection, botUsername: string) {
    super();
    this.conn = conn;
    this.botUsername = botUsername;
    conn.on("frame", (f: { id: number; payload: Buffer }) => this.onFrame(f));
    conn.on("close", () => this.emit("close"));
  }

  login(ssoTicket: string): Promise<void> {
    // ClientHelloEvent.Parse (emulator/Communication/Packets/Incoming/Handshake/ClientHelloEvent.cs
    // L22-25) reads: string build, string clientType, int clientPlatform, int clientDeviceType.
    // `build` is looked up in IRevisionsCache.Revisions, whose keys are Revision.Name — i.e. our
    // revisionName (bot/src/protocol/revision.json "Name" == "NITRO-1-6-6"). clientType/platform/
    // device match the real Nitro client's ClientHelloMessageComposer (nitro-renderer
    // src/nitro/communication/messages/outgoing/handshake/ClientHelloMessageComposer.ts), which
    // always sends ["HTML5", ClientPlatformEnum.HTML5 (2), ClientDeviceCategoryEnum.BROWSER (1)]
    // regardless of constructor args.
    this.conn.send(
      sendId("ClientHelloEvent"),
      new BinaryWriter().writeString(revisionName).writeString("HTML5").writeInt(2).writeInt(1).toBuffer(),
    );
    // SsoTicketEvent.Parse (Handshake/SSOTicketEvent.cs L76) reads only: string sso.
    // No trailing int — the real client's SSOTicketMessageComposer also sends a second `time`
    // field, but the server never reads it, so we omit it to match what Parse() actually consumes.
    this.conn.send(sendId("SsoTicketEvent"), new BinaryWriter().writeString(ssoTicket).toBuffer());
    return new Promise((resolve, reject) => {
      const cleanup = () => {
        clearTimeout(timer);
        this.off("authOk", onAuthOk);
        this.off("close", onClose);
      };
      const onAuthOk = () => {
        cleanup();
        resolve();
      };
      // SSOTicketEvent.cs's failure branch (L163-178) sends no error packet — it just calls
      // session.Disconnect() (bad/expired/reused ticket, account not found, login prohibited).
      // Without this, a rejected ticket would silently hang the whole 15s timeout instead of
      // failing fast when the socket actually closes.
      const onClose = () => {
        cleanup();
        reject(new Error("connection closed before login completed"));
      };
      const timer = setTimeout(() => {
        cleanup();
        reject(new Error("login timeout (15s)"));
      }, 15_000);
      this.once("authOk", onAuthOk);
      this.once("close", onClose);
    });
  }

  say(message: string): void {
    // ChatEvent.Parse (Rooms/Chat/ChatEvent.cs L53,56) reads: string message, int colour(bubble).
    this.conn.send(sendId("ChatEvent"), new BinaryWriter().writeString(message).writeInt(0).toBuffer());
  }

  whisper(user: string, message: string): void {
    // WhisperEvent.Parse (Rooms/Chat/WhisperEvent.cs L57-60) reads a single combined string
    // "<user> <message>" (split on the first space via @params.Split(' ')[0]/.Substring), then
    // int colour. There is no separate WhisperEvent in Rooms/Connection — this is the
    // Rooms/Chat one; the wire name "WhisperEvent" matches revision.json IncomingHeaders.
    this.conn.send(
      sendId("WhisperEvent"),
      new BinaryWriter().writeString(`${user} ${message}`).writeInt(0).toBuffer(),
    );
  }

  goToRoom(roomId: number): void {
    // Room entry is a two-packet sequence, verified across emulator/Communication/Packets/Incoming/Rooms/Connection/
    // and Rooms/Engine/GetRoomEntryDataEvent.cs:
    //
    // 1. OpenFlatConnectionEvent.Parse (Rooms/Connection/OpenFlatConnectionEvent.cs L9-11) reads
    //    uint roomId, string password, then calls Habbo.PrepareRoom(roomId, password), which (via
    //    Habbo.EnterRoom) sends RoomReadyComposer etc. but does NOT yet add the avatar to the room
    //    or broadcast UsersComposer.
    // 2. GetRoomEntryDataEvent.Parse (Rooms/Engine/GetRoomEntryDataEvent.cs L19-56) reads no
    //    payload at all; it calls RoomUserManager.AddAvatarToRoom(session), which is what actually
    //    places the avatar and triggers the UsersComposer broadcast. Without this follow-up, the
    //    bot would never appear in the roster.
    //
    // (Rooms/Connection/GoToFlatEvent.cs also takes no payload, but only re-enters the client's
    // *already-current* room — Habbo.EnterRoom(CurrentRoom) — so it's irrelevant to fresh entry
    // and is not part of this sequence.)
    this.conn.send(
      sendId("OpenFlatConnectionEvent"),
      new BinaryWriter().writeInt(roomId).writeString("").toBuffer(),
    );
    this.conn.send(sendId("GetRoomEntryDataEvent"), Buffer.alloc(0));
  }

  walkTo(x: number, y: number): void {
    // MoveAvatarEvent.Parse (Rooms/Engine/MoveAvatarEvent.cs L17-18) reads: int moveX, int moveY.
    this.conn.send(sendId("MoveAvatarEvent"), new BinaryWriter().writeInt(x).writeInt(y).toBuffer());
  }

  usernameFor(unitId: number): string | undefined {
    return this.roster.get(unitId)?.username;
  }

  private onFrame({ id, payload }: { id: number; payload: Buffer }): void {
    const name = recvName(id);
    try {
      switch (name) {
        case "AuthenticationOkComposer":
          this.emit("authOk");
          break;
        case "RoomForwardComposer":
          this.emit("roomForward", parseRoomForward(payload));
          break;
        case "UsersComposer":
          for (const u of parseUsers(payload)) {
            this.roster.set(u.unitId, { username: u.username, userType: u.userType });
            if (u.username.toLowerCase() === this.botUsername.toLowerCase()) {
              this.botUnitId = u.unitId;
            }
          }
          break;
        case "ChatComposer":
        case "ShoutComposer":
        case "WhisperComposer": {
          const { unitId, message } = parseChat(payload);
          const entry = this.roster.get(unitId);
          this.emit("chat", {
            username: entry?.username ?? "someone",
            message,
            whisper: name === "WhisperComposer",
            self: unitId === this.botUnitId,
            userType: entry?.userType ?? 1,
          } satisfies ChatMessage);
          break;
        }
        default:
          break; // every other packet: ignored by design
      }
    } catch (err) {
      console.warn(`[game] failed to handle ${name ?? id}:`, err);
    }
  }
}
