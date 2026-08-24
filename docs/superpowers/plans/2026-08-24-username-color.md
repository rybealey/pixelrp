# Username Color Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let players pick a username color (20-color palette, black default) in Settings → Social → Username → Color that colors their username in everyone's chat bubbles and the chat-history panel, persisted per user.

**Architecture:** Two data paths. (1) Persistence/ownership reuses the existing chrome UI-settings pipeline (`user_ui_settings` table + `RpSaveUiSettings`/`RpUiSettings` packets) — self only, for the picker's selected state. (2) Display rides the chat packet: the emulator stamps the speaker's saved color onto Chat/Shout/Whisper, and every client colors that user's bubble/history username. `""` and `#000000` both mean default (no override).

**Tech Stack:** PlusEMU emulator (C#, `emulator/` submodule), nitro-react client (React/TS, `client/` submodule, pixelrp branch), @nitrots/nitro-renderer patched via Yarn 4 `yarn patch`, MariaDB, Docker.

## Global Constraints

- **Submodules:** client code lives in the `client/` submodule; emulator code in `emulator/` (currently on branch `pixelrp`). `.gitmodules` pins the client to branch `pixelrp`, but the working tree may currently be on another branch (e.g. `chat-bubbles`) — **before the Task 6–8 commits, confirm the client submodule is on the branch you intend to ship from and that Task 9 pushes that same branch.** Commit + push in the submodule, then bump the parent pointer. Never edit `nitro/client/` (git-ignored build output).
- **Wire-format rule:** append every new packet field at the **end** of its composer and read it at the **end** of the matching parser. The server must always write a **defined** string (default `""`) so the parser never desyncs (EvaWire writes `undefined` as 2 bytes and shifts every later field).
- **No new message IDs:** these are field additions to existing packets — do not touch `ClientPacketHeader.cs` / `ServerPacketHeader.cs`.
- **Default sentinel:** black = `#000000`; the client sends `""` for black, and the emulator/client treat `""` and `#000000` identically as "no color override".
- **Testing style:** the client/renderer have no unit-test harness; the per-task gate is a successful compile/build, and end-to-end behavior is verified manually in-game (Task 9). Do not screenshot-drive the Nitro client.
- **Palette (20, order = swatch order):** `#000000` Black (default), `#4b5563` Slate, `#b91c1c` Red, `#be123c` Crimson, `#d35400` Orange, `#b45309` Amber, `#a16207` Gold, `#4d7c0f` Olive, `#2e7d32` Green, `#0f766e` Teal, `#0e7490` Cyan, `#0369a1` Ocean, `#1d4ed8` Blue, `#3730a3` Indigo, `#6d28d9` Violet, `#7e22ce` Purple, `#a21caf` Magenta, `#be185d` Pink, `#6d4c41` Brown, `#374151` Charcoal.

---

### Task 1: DB column `username_color`

**Files:**
- Create: `docs/sql/2026-08-24-username-color.sql` (migration record, committed to parent repo)

**Interfaces:**
- Produces: column `user_ui_settings.username_color VARCHAR(7) NOT NULL DEFAULT ''`, consumed by Task 2.

- [ ] **Step 1: Write the migration SQL**

Create `docs/sql/2026-08-24-username-color.sql`:

```sql
-- Username color (Settings > Social > Username > Color). Empty = default (black).
ALTER TABLE `user_ui_settings`
  ADD COLUMN `username_color` VARCHAR(7) NOT NULL DEFAULT '' AFTER `header_color`;
```

- [ ] **Step 2: Apply to the local dev DB**

Run (adjust container/service name to match `compose.yaml`'s db service):

```bash
docker compose exec -T db mariadb -uroot -p"$(grep -m1 MYSQL_ROOT_PASSWORD .env | cut -d= -f2)" pixelrp < docs/sql/2026-08-24-username-color.sql
```

Expected: no error. (DB name is `pixelrp` per `.env`'s `DB_NAME`.)

- [ ] **Step 3: Verify the column exists**

```bash
docker compose exec -T db mariadb -uroot -p"$(grep -m1 MYSQL_ROOT_PASSWORD .env | cut -d= -f2)" pixelrp -e "SHOW COLUMNS FROM user_ui_settings LIKE 'username_color';"
```

Expected: one row naming `username_color`, type `varchar(7)`.

- [ ] **Step 4: Commit**

```bash
git add docs/sql/2026-08-24-username-color.sql
git commit -m "chore: username_color migration for user_ui_settings"
```

Note: this ALTER is a manual prod/beta-DB step (schema changes don't ship via deploy) — it is applied to the beta DB in Task 9.

---

### Task 2: Emulator — persist username color on Habbo

**Files:**
- Modify: `emulator/HabboHotel/Users/Habbo.cs` (RpUi settings region ~L251-283)

**Interfaces:**
- Consumes: `user_ui_settings.username_color` (Task 1).
- Produces: `Habbo.RpUiUsernameColor` (string), loaded by `EnsureRpUiSettingsLoaded()` and saved by `SaveRpUiSettings()`; consumed by Tasks 3 and 4.

- [ ] **Step 1: Add the property**

In `Habbo.cs`, next to the existing RpUi properties (after `public string RpUiHeaderColor { get; set; } = "";`):

```csharp
public string RpUiUsernameColor { get; set; } = "";
```

- [ ] **Step 2: Load it in `EnsureRpUiSettingsLoaded`**

Change the SELECT and add the assignment:

```csharp
dbClient.SetQuery("SELECT `chrome_color`,`chrome_opacity`,`header_color`,`username_color` FROM `user_ui_settings` WHERE `user_id` = @id LIMIT 1");
```

After `RpUiHeaderColor = Convert.ToString(row["header_color"]) ?? "";` add:

```csharp
RpUiUsernameColor = Convert.ToString(row["username_color"]) ?? "";
```

- [ ] **Step 3: Save it in `SaveRpUiSettings`**

Change the REPLACE and add the parameter:

```csharp
dbClient.SetQuery("REPLACE INTO `user_ui_settings` (`user_id`,`chrome_color`,`chrome_opacity`,`header_color`,`username_color`) VALUES (@id,@color,@opacity,@header,@username)");
dbClient.AddParameter("id", Id);
dbClient.AddParameter("color", RpUiChromeColor);
dbClient.AddParameter("opacity", RpUiChromeOpacity);
dbClient.AddParameter("header", RpUiHeaderColor);
dbClient.AddParameter("username", RpUiUsernameColor);
```

- [ ] **Step 4: Compile**

```bash
cd emulator && dotnet build "Plus Emulator.sln" -clp:ErrorsOnly
```

Expected: Build succeeded, 0 errors.

- [ ] **Step 5: Commit (in the emulator submodule)**

```bash
cd emulator && git add HabboHotel/Users/Habbo.cs && git commit -m "feat: persist RpUiUsernameColor on Habbo"
```

---

### Task 3: Emulator — carry username color on the UI-settings packets

**Files:**
- Modify: `emulator/Communication/Packets/Incoming/Users/RpSaveUiSettingsEvent.cs`
- Modify: `emulator/Communication/Packets/Outgoing/Users/RpUiSettingsComposer.cs`
- Modify: `emulator/Communication/Packets/Incoming/Handshake/SSOTicketEvent.cs:116`

**Interfaces:**
- Consumes: `Habbo.RpUiUsernameColor` (Task 2).
- Produces: save packet reads a 4th trailing string; login composer writes a 4th trailing string. Mirrored by renderer Task 5 (`RpSaveUiSettingsComposer` writes it / `RpUiSettingsParser` reads it).

- [ ] **Step 1: Read the 4th field in `RpSaveUiSettingsEvent.Parse`**

After `var header = packet.ReadString() ?? "";` add:

```csharp
var usernameColor = packet.ReadString() ?? "";
```

After the existing header validation and before `var habbo = session.GetHabbo();`, validate username color (reuse the `HexColor()` regex; allow empty):

```csharp
if (usernameColor != "" && !HexColor().IsMatch(usernameColor))
    return Task.CompletedTask;
```

After `habbo.RpUiHeaderColor = header;` add:

```csharp
habbo.RpUiUsernameColor = usernameColor;
```

- [ ] **Step 2: Write the 4th field in `RpUiSettingsComposer`**

Add a constructor param and field, and write it last:

```csharp
private readonly string _usernameColor;

public RpUiSettingsComposer(string chromeColor, int chromeOpacity, string headerColor, string usernameColor)
{
    _chromeColor = chromeColor ?? "";
    _chromeOpacity = chromeOpacity;
    _headerColor = headerColor ?? "";
    _usernameColor = usernameColor ?? "";
}

public void Compose(IOutgoingPacket packet)
{
    packet.WriteString(_chromeColor);
    packet.WriteInteger(_chromeOpacity);
    packet.WriteString(_headerColor);
    packet.WriteString(_usernameColor);
}
```

- [ ] **Step 3: Pass it at the login send site**

In `SSOTicketEvent.cs`, update the send (currently line 116) to pass the 4th arg:

```csharp
session.Send(new RpUiSettingsComposer(session.GetHabbo().RpUiChromeColor, session.GetHabbo().RpUiChromeOpacity, session.GetHabbo().RpUiHeaderColor, session.GetHabbo().RpUiUsernameColor));
```

(`EnsureRpUiSettingsLoaded()` is already called on the line above, so the value is populated.)

- [ ] **Step 4: Compile**

```bash
cd emulator && dotnet build "Plus Emulator.sln" -clp:ErrorsOnly
```

Expected: Build succeeded, 0 errors.

- [ ] **Step 5: Commit**

```bash
cd emulator && git add Communication/Packets/Incoming/Users/RpSaveUiSettingsEvent.cs Communication/Packets/Outgoing/Users/RpUiSettingsComposer.cs Communication/Packets/Incoming/Handshake/SSOTicketEvent.cs && git commit -m "feat: username color on RpUiSettings save/login packets"
```

---

### Task 4: Emulator — stamp username color onto chat packets

**Files:**
- Modify: `emulator/Communication/Packets/Outgoing/Rooms/Chat/ChatComposer.cs`
- Modify: `emulator/Communication/Packets/Outgoing/Rooms/Chat/ShoutComposer.cs`
- Modify: `emulator/Communication/Packets/Outgoing/Rooms/Chat/WhisperComposer.cs`
- Modify: `emulator/HabboHotel/Rooms/RoomUser.cs` (`OnChat`, ~L383-396, 424-429)
- Modify: `emulator/Communication/Packets/Incoming/Rooms/Chat/WhisperEvent.cs` (~L102-121)

**Interfaces:**
- Consumes: `Habbo.RpUiUsernameColor` (Task 2).
- Produces: Chat/Shout/Whisper packets write a trailing `usernameColor` string (default `""` for all non-user senders). Read by renderer `RoomUnitChatParser` (Task 5).

- [ ] **Step 1: Add trailing param to all three composers**

In each of `ChatComposer.cs`, `ShoutComposer.cs`, `WhisperComposer.cs`: add an optional field/param and write it last. Example for `ChatComposer.cs` (apply the same shape to the other two, keeping their existing param names `message`/`text`):

```csharp
private readonly int _colour;
private readonly string _usernameColor;
public uint MessageId => ServerPacketHeader.ChatComposer;

public ChatComposer(int virtualId, string message, int emotion, int colour, string usernameColor = "")
{
    _virtualId = virtualId;
    _message = message;
    _emotion = emotion;
    _colour = colour;
    _usernameColor = usernameColor ?? "";
}

public void Compose(IOutgoingPacket packet)
{
    packet.WriteInteger(_virtualId);
    packet.WriteString(_message);
    packet.WriteInteger(_emotion);
    packet.WriteInteger(_colour);
    packet.WriteInteger(0);
    packet.WriteInteger(-1);
    packet.WriteString(_usernameColor);
}
```

The default `= ""` keeps every existing call site (pets, bots, wired, commands, tent-notify, `GameClientExtensions`) compiling unchanged and emitting `""`.

- [ ] **Step 2: Pass the speaker's color in `RoomUser.OnChat`**

At the top of `OnChat`, right after the `GetClient() == null ...` guard, capture:

```csharp
var usernameColor = GetClient().GetHabbo().RpUiUsernameColor ?? "";
```

Then add `usernameColor` as the last argument to the four speaker-side composers in this method:

```csharp
packet = new ShoutComposer(VirtualId, message, emotion, colour, usernameColor);
// ...
packet = new ChatComposer(VirtualId, message, emotion, colour, usernameColor);
// mention variant:
mentionPacket = shout
    ? new ShoutComposer(VirtualId, message, emotion, 25, usernameColor)
    : (IServerPacket)new ChatComposer(VirtualId, message, emotion, 25, usernameColor);
// tent chat whisper:
packet = new WhisperComposer(VirtualId, $"[Tent Chat] {message}", 0, colour, usernameColor);
```

(Leave the pet/bot `ChatComposer` calls at ~L334/L346 untouched — those are pet/bot senders, not the player.)

- [ ] **Step 3: Pass the speaker's color in `WhisperEvent.Parse`**

After `var user = room.GetRoomUserManager().GetRoomUserByHabbo(session.GetHabbo().Id);` (and its null check), capture:

```csharp
var usernameColor = session.GetHabbo().RpUiUsernameColor ?? "";
```

Add `usernameColor` as the last argument to the four `new WhisperComposer(...)` calls in this handler (the echo to sender, the send to target, and the mod-notify), e.g.:

```csharp
user.GetClient().Send(new WhisperComposer(user.VirtualId, message, 0, user.LastBubble, usernameColor));
```

- [ ] **Step 4: Compile**

```bash
cd emulator && dotnet build "Plus Emulator.sln" -clp:ErrorsOnly
```

Expected: Build succeeded, 0 errors.

- [ ] **Step 5: Commit**

```bash
cd emulator && git add Communication/Packets/Outgoing/Rooms/Chat/ChatComposer.cs Communication/Packets/Outgoing/Rooms/Chat/ShoutComposer.cs Communication/Packets/Outgoing/Rooms/Chat/WhisperComposer.cs HabboHotel/Rooms/RoomUser.cs Communication/Packets/Incoming/Rooms/Chat/WhisperEvent.cs && git commit -m "feat: stamp username color onto user chat/shout/whisper packets"
```

---

### Task 5: Renderer patch — read username color on chat + settings packets

**Files:**
- Modify (via `yarn patch`): `@nitrots/nitro-renderer` →
  - `src/nitro/communication/messages/parser/room/unit/chat/RoomUnitChatParser.ts`
  - `src/events/session/RoomSessionChatEvent.ts`
  - `src/nitro/session/handler/RoomChatHandler.ts`
  - the patched `RpUiSettingsParser` and `RpSaveUiSettingsComposer` (added by the existing patch)
- Result files: `client/.yarn/patches/@nitrots-nitro-renderer-npm-1.6.6-*.patch`, `client/package.json`, `client/yarn.lock`

**Interfaces:**
- Consumes: emulator chat packet trailing string (Task 4) and login packet trailing string (Task 3).
- Produces: `RoomSessionChatEvent.usernameColor: string`, `RpUiSettingsParser.usernameColor: string`, and `RpSaveUiSettingsComposer(chromeColor, chromeOpacity, headerColor, usernameColor)` — consumed by client Tasks 6–8.

- [ ] **Step 1: Open the package for patching**

```bash
cd client && yarn patch @nitrots/nitro-renderer
```

Note the temp dir it prints (call it `$P`). Make the edits below inside `$P` (same relative paths as `node_modules/@nitrots/nitro-renderer`).

- [ ] **Step 2: `RoomUnitChatParser.ts` — read trailing username color**

Add a private field, flush default, and read after `messageLength`:

```typescript
private _usernameColor: string;
```

In `flush()` add `this._usernameColor = '';`. In `parse()`, after `this._messageLength = wrapper.readInt();` add:

```typescript
this._usernameColor = wrapper.readString();
```

Add the getter:

```typescript
public get usernameColor(): string
{
    return this._usernameColor;
}
```

- [ ] **Step 3: `RoomSessionChatEvent.ts` — carry username color**

Add `private _usernameColor: string;`, a constructor param `usernameColor: string = ''` (append at the end of the parameter list), assign `this._usernameColor = usernameColor;`, and:

```typescript
public get usernameColor(): string
{
    return this._usernameColor;
}
```

- [ ] **Step 4: `RoomChatHandler.ts` — pass it through**

In `onRoomUnitChatEvent`, change the construction to pass the parser value as the final arg:

```typescript
const chatEvent = new RoomSessionChatEvent(RoomSessionChatEvent.CHAT_EVENT, session, parser.roomIndex, parser.message, chatType, parser.bubble, null, -1, parser.usernameColor);
```

(Confirm the `RoomSessionChatEvent` constructor arg order is `(type, session, objectId, message, chatType, style, links, extraParam, usernameColor)` after Step 3, and that `links`/`extraParam` defaults are preserved — pass `null, -1` explicitly so `usernameColor` lands in the right slot.)

- [ ] **Step 5: `RpUiSettingsParser` — read the 4th field**

In the patched `RpUiSettingsParser` (search the temp dir for `class RpUiSettingsParser`), add `private _usernameColor: string;`, flush `this._usernameColor = '';`, read after `this._headerColor = wrapper.readString();`:

```typescript
this._usernameColor = wrapper.readString();
```

and add a `get usernameColor(): string` getter returning it.

- [ ] **Step 6: `RpSaveUiSettingsComposer` — write the 4th field**

In the patched `RpSaveUiSettingsComposer`, extend the constructor to `(chromeColor: string, chromeOpacity: number, headerColor: string, usernameColor: string)` and store all four in `this._data` in that order (the composer's `getMessageArray()`/data array must emit `usernameColor` last so it maps to the emulator's `packet.ReadString()` in Task 3 Step 1).

- [ ] **Step 7: Commit the patch**

```bash
cd client && yarn patch-commit -s "$P"
```

Expected: `.yarn/patches/...patch`, `package.json`, and `yarn.lock` update. If the patch filename hash changed, that's expected.

- [ ] **Step 8: Build the client to prove the patch applies and types resolve**

```bash
cd client && yarn install && npx tsc --noEmit -p tsconfig.json
```

Expected: no errors from the renderer types. (A full `vite build` runs in Task 9.)

- [ ] **Step 9: Commit (client submodule)**

```bash
cd client && git add .yarn/patches package.json yarn.lock && git commit -m "feat: renderer patch - username color on chat + UI-settings packets"
```

---

### Task 6: Client — palette module + message/history color fields

**Files:**
- Create: `client/src/components/rp-settings/UsernameColors.ts`
- Modify: `client/src/api/room/widgets/ChatBubbleMessage.ts`
- Modify: `client/src/api/chat-history/IChatEntry.ts`

**Interfaces:**
- Produces: `USERNAME_COLORS`, `DEFAULT_USERNAME_COLOR`, `IsValidUsernameColor` (from `UsernameColors.ts`); `ChatBubbleMessage.usernameColor: string`; `IChatEntry.usernameColor?: string` — consumed by Tasks 7 and 8.

- [ ] **Step 1: Create `UsernameColors.ts`**

```typescript
// PixelRP username color palette (Settings > Social > Username > Color).
// Black (#000000) is the default; selecting it persists as '' server-side.
// Colors are chosen to stay legible on the light chat-bubble background.

export interface UsernameColor
{
    key: string;
    name: string;
    color: string;
}

export const USERNAME_COLORS: UsernameColor[] = [
    { key: 'black', name: 'Black', color: '#000000' },
    { key: 'slate', name: 'Slate', color: '#4b5563' },
    { key: 'red', name: 'Red', color: '#b91c1c' },
    { key: 'crimson', name: 'Crimson', color: '#be123c' },
    { key: 'orange', name: 'Orange', color: '#d35400' },
    { key: 'amber', name: 'Amber', color: '#b45309' },
    { key: 'gold', name: 'Gold', color: '#a16207' },
    { key: 'olive', name: 'Olive', color: '#4d7c0f' },
    { key: 'green', name: 'Green', color: '#2e7d32' },
    { key: 'teal', name: 'Teal', color: '#0f766e' },
    { key: 'cyan', name: 'Cyan', color: '#0e7490' },
    { key: 'ocean', name: 'Ocean', color: '#0369a1' },
    { key: 'blue', name: 'Blue', color: '#1d4ed8' },
    { key: 'indigo', name: 'Indigo', color: '#3730a3' },
    { key: 'violet', name: 'Violet', color: '#6d28d9' },
    { key: 'purple', name: 'Purple', color: '#7e22ce' },
    { key: 'magenta', name: 'Magenta', color: '#a21caf' },
    { key: 'pink', name: 'Pink', color: '#be185d' },
    { key: 'brown', name: 'Brown', color: '#6d4c41' },
    { key: 'charcoal', name: 'Charcoal', color: '#374151' },
];

export const DEFAULT_USERNAME_COLOR: string = USERNAME_COLORS[0].color; // '#000000'

export const IsValidUsernameColor = (color: string): boolean => USERNAME_COLORS.some(entry => (entry.color === color));
```

- [ ] **Step 2: Add `usernameColor` to `ChatBubbleMessage`**

Append a constructor param (after `color`):

```typescript
public color: string = null,
public usernameColor: string = null
```

- [ ] **Step 3: Add `usernameColor` to `IChatEntry`**

Add to the interface (near `color?`):

```typescript
usernameColor?: string;
```

- [ ] **Step 4: Type-check**

```bash
cd client && npx tsc --noEmit -p tsconfig.json
```

Expected: no new errors.

- [ ] **Step 5: Commit**

```bash
cd client && git add src/components/rp-settings/UsernameColors.ts src/api/room/widgets/ChatBubbleMessage.ts src/api/chat-history/IChatEntry.ts && git commit -m "feat: username color palette + message/history color fields"
```

---

### Task 7: Client — apply username color when rendering chat

**Files:**
- Modify: `client/src/hooks/rooms/widgets/useChatWidget.ts` (~L211-227)
- Modify: `client/src/components/room/widgets/chat/ChatWidgetMessageView.tsx:88`
- Modify: `client/src/components/chat-history/ChatHistoryView.tsx:80`

**Interfaces:**
- Consumes: `RoomSessionChatEvent.usernameColor` (Task 5); `ChatBubbleMessage.usernameColor`, `IChatEntry.usernameColor` (Task 6).

- [ ] **Step 1: Thread the color through `useChatWidget`**

In the `RoomSessionChatEvent.CHAT_EVENT` handler, derive the color from the event and normalize the default to `null` (so no inline style is applied for black/empty). Immediately before `const chatMessage = new ChatBubbleMessage(`:

```typescript
const usernameColor = (event.usernameColor && (event.usernameColor !== '#000000')) ? event.usernameColor : null;
```

Pass it as the final arg to `new ChatBubbleMessage(...)`:

```typescript
        color,
        usernameColor);
```

And add it to the `addChatEntry({ ... })` object (append `, usernameColor`).

- [ ] **Step 2: Color the bubble username in `ChatWidgetMessageView.tsx`**

Change the username `<b>` (line ~88) to apply the color:

```tsx
<b className="username mr-1" style={ chat.usernameColor ? { color: chat.usernameColor } : undefined } dangerouslySetInnerHTML={ { __html: `${ chat.username }: ` } } />
```

- [ ] **Step 3: Color the history username in `ChatHistoryView.tsx`**

Change the `TYPE_CHAT` username `<b>` (line ~80) — leave the `TYPE_ROOM_INFO` `<Text>{ row.name }` untouched:

```tsx
<b className="username mr-1" style={ row.usernameColor ? { color: row.usernameColor } : undefined } dangerouslySetInnerHTML={ { __html: `${ row.name }: ` } } />
```

- [ ] **Step 4: Type-check**

```bash
cd client && npx tsc --noEmit -p tsconfig.json
```

Expected: no new errors.

- [ ] **Step 5: Commit**

```bash
cd client && git add src/hooks/rooms/widgets/useChatWidget.ts src/components/room/widgets/chat/ChatWidgetMessageView.tsx src/components/chat-history/ChatHistoryView.tsx && git commit -m "feat: color username in chat bubbles and history"
```

---

### Task 8: Client — Settings UI (remove Roleplay Color/Tag; add Social → Username → Color)

**Files:**
- Modify: `client/src/components/rp-settings/RpSettingsView.tsx`
- Modify (if needed): `client/src/components/rp-settings/RpSettingsView.scss`

**Interfaces:**
- Consumes: `USERNAME_COLORS`, `DEFAULT_USERNAME_COLOR`, `IsValidUsernameColor` (Task 6); `RpUiSettingsEvent.usernameColor`, `RpSaveUiSettingsComposer(...4 args)` (Task 5).

- [ ] **Step 1: Imports + page lists**

Add to the `UiChrome` import line a new import:

```typescript
import { DEFAULT_USERNAME_COLOR, IsValidUsernameColor, USERNAME_COLORS } from './UsernameColors';
```

Change the Roleplay pages and add Social pages:

```typescript
const ROLEPLAY_PAGES: string[] = [ 'Macros', 'Messages' ];
const SOCIAL_PAGES: string[] = [ 'Username' ];
```

- [ ] **Step 2: State**

Add alongside the other settings state:

```typescript
const [ usernameColor, setUsernameColor ] = useState<string>(DEFAULT_USERNAME_COLOR);
const [ socialPage, setSocialPage ] = useState<string>(SOCIAL_PAGES[0]);
```

- [ ] **Step 3: Apply from the login event**

In the `RpUiSettingsEvent` handler, after the header handling, add:

```typescript
const uname = (IsValidUsernameColor(parser.usernameColor) ? parser.usernameColor : DEFAULT_USERNAME_COLOR);
setUsernameColor(uname);
```

- [ ] **Step 4: Unify the save to carry all four fields**

Rename `saveChrome` to `saveSettings` and add the username arg; update its three existing callers (`selectChrome`, `selectOpacity`, `selectHeader`) to call `saveSettings(...)` with `usernameColor` as the 4th value:

```typescript
const saveSettings = (color: string, opacity: number, header: string, uname: string) =>
{
    SendMessageComposer(new RpSaveUiSettingsComposer(
        (color === DEFAULT_CHROME_COLOR) ? '' : color,
        opacity,
        (header === DEFAULT_HEADER_KEY) ? '' : header,
        (uname === DEFAULT_USERNAME_COLOR) ? '' : uname));
}
```

Example updated caller:

```typescript
const selectChrome = (color: string) =>
{
    setChromeColor(color);
    ApplyUiChrome(color, chromeOpacity, headerKey);
    saveSettings(color, chromeOpacity, headerKey, usernameColor);
}
```

(Do the same for `selectOpacity` and `selectHeader`, passing the current `usernameColor`.)

- [ ] **Step 5: Username selector**

Add:

```typescript
const selectUsernameColor = (color: string) =>
{
    setUsernameColor(color);
    saveSettings(chromeColor, chromeOpacity, headerKey, color);
}
```

- [ ] **Step 6: Render the Social sub-nav + Username page**

Add a `Social` tab block mirroring the Roleplay/Interface `rp-settings-subnav-layout`, before or after the Roleplay block:

```tsx
{ (currentTab === 'Social') &&
    <div className="rp-settings-subnav-layout">
        <div className="rp-settings-subnav">
            { SOCIAL_PAGES.map(page => (
                <div key={ page }
                    className={ `rp-settings-subnav-item ${ (socialPage === page) ? 'is-active' : '' }` }
                    onClick={ () => setSocialPage(page) }>
                    { page }
                </div>
            )) }
        </div>
        <Column gap={ 2 } className="rp-settings-subpage">
            { (socialPage === 'Username') &&
                <div className="rp-settings-section">
                    <div className="rp-settings-section-info">
                        <Text bold>Color</Text>
                        <Text small className="text-muted">The color of your username in your chat bubbles. Everyone in the room sees it.</Text>
                    </div>
                    <div className="rp-settings-swatches">
                        { USERNAME_COLORS.map(entry => (
                            <div key={ entry.key } title={ entry.name }
                                className={ `rp-settings-swatch ${ (usernameColor === entry.color) ? 'is-selected' : '' }` }
                                style={ { backgroundColor: entry.color } }
                                onClick={ () => selectUsernameColor(entry.color) } />
                        )) }
                    </div>
                </div> }
        </Column>
    </div> }
```

- [ ] **Step 7: Fix the catch-all branch**

Update the final fallthrough condition so `Social` no longer shows "Nothing here yet":

```tsx
{ (currentTab !== 'Interface') && (currentTab !== 'Roleplay') && (currentTab !== 'Social') &&
    <Column center fullHeight gap={ 1 } className="rp-settings-placeholder">
        <Text bold>{ currentTab }</Text>
        <Text className="text-muted">Nothing here yet.</Text>
    </Column> }
```

- [ ] **Step 8: SCSS — no change expected**

`.rp-settings-swatches` is already `display: grid; grid-template-columns: repeat(4, 34px); gap: 8px;`, which auto-flows 20 swatches into 5 rows of 4. No CSS change is needed (swatch background is inline). Only touch the SCSS if the grid visibly overflows the sub-page.

- [ ] **Step 9: Type-check**

```bash
cd client && npx tsc --noEmit -p tsconfig.json
```

Expected: no new errors.

- [ ] **Step 10: Commit**

```bash
cd client && git add src/components/rp-settings/RpSettingsView.tsx src/components/rp-settings/RpSettingsView.scss && git commit -m "feat: Settings Social > Username > Color; drop Roleplay Color/Tag"
```

---

### Task 9: Build, verify in-game, changelog, and ship to beta

**Files:**
- Modify: `CHANGELOG.md` (parent repo)
- Parent repo submodule pointers: `client`, `emulator`

**Interfaces:**
- Consumes: all prior tasks.

- [ ] **Step 1: Build client + emulator locally**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
docker/nitro/build-client.sh
cd emulator && dotnet build "Plus Emulator.sln" -clp:ErrorsOnly
```

Expected: client bundle builds and installs to `nitro/client/`; emulator builds with 0 errors.

- [ ] **Step 2: Run the stack and verify in-game (manual)**

Bring up the local stack (`docker compose up -d --build` or the usual dev flow), log in with the local test account (`ClaudeTest`), and confirm:
  1. Settings → Roleplay shows only `Macros`, `Messages` (no `Color`, no `Tag`).
  2. Settings → Social shows a `Username` sub-nav; its `Color` section shows 20 swatches, black selected.
  3. Pick a non-black color and speak → own bubble username is colored; the color also shows in the chat-history panel.
  4. With a second account in the room, the second client sees the same color on the first user's bubble username.
  5. Relog → the picker still shows the chosen swatch and new bubbles stay colored.
  6. Pick Black → username returns to default everywhere; DB `username_color` for that user is `''`.
  7. A bot/pet message still renders with the default (uncolored) username.

- [ ] **Step 3: Changelog**

Add an entry to `CHANGELOG.md` (top of the current section):

```markdown
- **Username colors** — players can now pick a username color (20-color palette) in Settings → Social → Username → Color. The color shows on your username in chat bubbles and the chat-history panel for everyone in the room, and persists across sessions. (Removed the unused Roleplay → Color/Tag pages.) Requires the `user_ui_settings.username_color` DB migration.
```

- [ ] **Step 4: Push the submodules first**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus/client && git push origin "$(git rev-parse --abbrev-ref HEAD)"
cd /Users/rybealey/Documents/Personal/pixelrp/plus/emulator && git push origin pixelrp
```

(Emulator tracks branch `pixelrp`. For the client, push whatever branch you committed on — confirm it's the intended ship branch per the Global Constraints note.)

- [ ] **Step 5: Apply the DB migration to the beta DB**

Apply `docs/sql/2026-08-24-username-color.sql` to the **beta** database before deploying (schema changes don't ship via deploy). Use the beta DB credentials/host.

- [ ] **Step 6: Bump pointers, commit, push to beta**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
git add client emulator CHANGELOG.md docs/superpowers/plans/2026-08-24-username-color.md
git commit -m "feat: username color in chat bubbles (Settings > Social > Username)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git push origin beta
```

- [ ] **Step 7: Confirm the beta deploy**

Watch the Deploy Beta workflow for the pushed SHA and confirm `conclusion: success`:

```bash
gh run list --branch beta --limit 3 --json displayTitle,status,conclusion,headSha
```

Expected: the new commit's run completes successfully. Then spot-check on beta.pixelrp.co that the migration is applied and the feature works.

---

## Self-Review

**Spec coverage:**
- Remove Roleplay Color/Tag → Task 8 Step 1. ✓
- Social sub-nav (same style) + Username page → Task 8 Step 6. ✓
- First Username option = Color → Task 8 Step 6 (only section). ✓
- 20 colors, same swatch implementation, black first/default → Task 6 Step 1 + Task 8 Step 6. ✓
- Changes username color in chat bubbles → Tasks 4, 5, 7. ✓
- Viewable by all users → chat-packet transport (Tasks 4, 5, 7). ✓
- Persist across sessions → DB + Habbo + login packet (Tasks 1, 2, 3). ✓
- Bubbles + chat history scope → Task 7 Steps 2–3. ✓
- Push to beta → Task 9. ✓

**Placeholder scan:** No TBD/TODO; all code steps carry concrete code. Deploy-only environment specifics (emulator branch name, beta DB creds) are intentionally parameterized and resolved at run time.

**Type consistency:** `usernameColor` string is the field name across emulator (`RpUiUsernameColor`), renderer (`usernameColor` getters, `RpSaveUiSettingsComposer` 4th arg), and client (`ChatBubbleMessage.usernameColor`, `IChatEntry.usernameColor`, `event.usernameColor`). `RpSaveUiSettingsComposer` arg order (chromeColor, chromeOpacity, headerColor, usernameColor) matches the emulator read order in Task 3. `''`/`#000000` default handling is consistent (client normalizes to `null` before rendering; sends `''` for black).
