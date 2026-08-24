# Username Icon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Icon + Icon Color picker below Settings → Social → Username → Color that renders `[ <icon> ]` (FontAwesome kit) before the player's username in chat bubbles and history for everyone, persisted per user.

**Architecture:** Same two-path shape as the shipped username-color feature. Persistence reuses the chrome UI-settings pipeline (`user_ui_settings` + a new migration); display rides the chat packet (two more trailing fields). The X swatch = "none" (empty value → no prefix). Icons render via the embedded FA kit (`<i class="…">` → SVG); the X in the picker is react-icons `<FaTimes/>`.

**Tech Stack:** PlusEMU (C#, `emulator/` submodule), nitro-react (React/TS, `client/` submodule branch `pixelrp`), @nitrots/nitro-renderer via `yarn patch`, FontAwesome kit `19221c1121`, MariaDB/MySQL 8.0, Docker.

## Global Constraints

- **Submodules:** client code in `client/` (branch `pixelrp`), emulator in `emulator/` (branch `pixelrp`). Commit + push in the submodule, then bump the parent pointer. Never edit `nitro/client/` (build output).
- **Wire-format rule:** append each new field at the **end** of its composer and read it at the **end** of the parser; the server always writes a **defined** string (default `""`). Field order per packet: chat = `…, usernameColor, icon, iconColor`; UI settings = `…, usernameColor, icon, iconColor`.
- **No new message IDs** — field additions only; do not touch `*PacketHeader.cs`.
- **Defaults:** icon `''` = none (no prefix, X selected). Icon color `''`/`#000000` = default (black). Client normalizes both to `null` before rendering; sends `''` for none/black.
- **Migrations ship via deploy:** put DDL in `emulator/Resources/SQLs/Updates/` (next number is **25**); the deploy's "Apply database patches" step applies it once (tracked in `_applied_sql_updates`). No manual DB step. MySQL 8.0 has no `ADD COLUMN IF NOT EXISTS`.
- **Icon color reuses `USERNAME_COLORS`** from `UsernameColors.ts` — no new palette.
- **Testing style:** no client unit-test harness; per-task gate is a clean compile/build (`dotnet build` / `tsc --noEmit`), end-to-end verified manually in-game. Do not screenshot-drive the client.
- **Current renderer baseline (post username-color):** `RoomUnitChatParser` reads `usernameColor` last; `RoomSessionChatEvent` ctor ends `…, usernameColor: string = ''`; `RpSaveUiSettingsComposer(chromeColor, chromeOpacity, headerColor, usernameColor)`; `RpUiSettingsParser` reads `usernameColor` last.

---

### Task 1: Emulator — persist icon + icon color, and the migration

**Files:**
- Create: `emulator/Resources/SQLs/Updates/25_AddUsernameIcon.sql`
- Modify: `emulator/HabboHotel/Users/Habbo.cs` (RpUi settings region)

**Interfaces:**
- Produces: `user_ui_settings.username_icon` (VARCHAR 64) + `username_icon_color` (VARCHAR 7); `Habbo.RpUiUsernameIcon` / `Habbo.RpUiUsernameIconColor` (strings) loaded by `EnsureRpUiSettingsLoaded` and saved by `SaveRpUiSettings`. Consumed by Tasks 2 and 3.

- [ ] **Step 1: Write the migration**

Create `25_AddUsernameIcon.sql`:

```sql
-- PixelRP username icon: an optional FontAwesome-kit icon rendered as
-- [ <icon> ] before the player's name in chat, plus its color. Empty icon =
-- none (no prefix); empty color = default (black). Loaded at login and carried
-- on the chat packet so everyone in the room sees it.
ALTER TABLE `user_ui_settings`
  ADD COLUMN `username_icon` VARCHAR(64) NOT NULL DEFAULT '' AFTER `username_color`,
  ADD COLUMN `username_icon_color` VARCHAR(7) NOT NULL DEFAULT '' AFTER `username_icon`;
```

- [ ] **Step 2: Add properties + load + save in `Habbo.cs`**

After `public string RpUiUsernameColor { get; set; } = "";` add:

```csharp
public string RpUiUsernameIcon { get; set; } = "";
public string RpUiUsernameIconColor { get; set; } = "";
```

Change the SELECT in `EnsureRpUiSettingsLoaded`:

```csharp
dbClient.SetQuery("SELECT `chrome_color`,`chrome_opacity`,`header_color`,`username_color`,`username_icon`,`username_icon_color` FROM `user_ui_settings` WHERE `user_id` = @id LIMIT 1");
```

After `RpUiUsernameColor = Convert.ToString(row["username_color"]) ?? "";` add:

```csharp
RpUiUsernameIcon = Convert.ToString(row["username_icon"]) ?? "";
RpUiUsernameIconColor = Convert.ToString(row["username_icon_color"]) ?? "";
```

Change the REPLACE in `SaveRpUiSettings`:

```csharp
dbClient.SetQuery("REPLACE INTO `user_ui_settings` (`user_id`,`chrome_color`,`chrome_opacity`,`header_color`,`username_color`,`username_icon`,`username_icon_color`) VALUES (@id,@color,@opacity,@header,@username,@icon,@iconcolor)");
```

After `dbClient.AddParameter("username", RpUiUsernameColor);` add:

```csharp
dbClient.AddParameter("icon", RpUiUsernameIcon);
dbClient.AddParameter("iconcolor", RpUiUsernameIconColor);
```

- [ ] **Step 3: Compile**

Run (host has no dotnet; use a clean copy to avoid the nested-worktree glob):

```bash
SRC=/Users/rybealey/Documents/Personal/pixelrp/plus/emulator
TMP=/private/tmp/claude-emu-build
rm -rf "$TMP"; mkdir -p "$TMP"
rsync -a --exclude='.claude/' --exclude='bin/' --exclude='obj/' --exclude='.git' "$SRC"/ "$TMP"/
docker run --rm -v "$TMP":/src -w /src mcr.microsoft.com/dotnet/sdk:7.0 bash -c "dotnet build 'Plus Emulator.csproj' -clp:ErrorsOnly -nologo 2>&1 | tail -20"
```

Expected: `Build succeeded. 0 Error(s)`.

- [ ] **Step 4: Commit (emulator submodule)**

```bash
cd emulator && git add Resources/SQLs/Updates/25_AddUsernameIcon.sql HabboHotel/Users/Habbo.cs && git commit -m "feat: persist username icon + icon color on Habbo (migration 25)"
```

---

### Task 2: Emulator — icon + icon color on the UI-settings packets

**Files:**
- Modify: `emulator/Communication/Packets/Incoming/Users/RpSaveUiSettingsEvent.cs`
- Modify: `emulator/Communication/Packets/Outgoing/Users/RpUiSettingsComposer.cs`
- Modify: `emulator/Communication/Packets/Incoming/Handshake/SSOTicketEvent.cs`

**Interfaces:**
- Consumes: `Habbo.RpUiUsernameIcon` / `RpUiUsernameIconColor` (Task 1).
- Produces: save packet reads 5th/6th trailing strings; login composer writes them. Mirrored by renderer Task 4.

- [ ] **Step 1: Read + validate in `RpSaveUiSettingsEvent.Parse`**

After `var usernameColor = packet.ReadString() ?? "";` add:

```csharp
var icon = packet.ReadString() ?? "";
var iconColor = packet.ReadString() ?? "";
```

After the existing `usernameColor` hex check, add validation (empty allowed; icon is fa-style classes only — blocks injection):

```csharp
if (iconColor != "" && !HexColor().IsMatch(iconColor))
    return Task.CompletedTask;
if (icon != "" && !IconClass().IsMatch(icon))
    return Task.CompletedTask;
```

Add the icon regex next to `HexColor()`:

```csharp
[GeneratedRegex("^[a-z0-9][a-z0-9 -]{0,63}$")]
private static partial Regex IconClass();
```

After `habbo.RpUiUsernameColor = usernameColor;` add:

```csharp
habbo.RpUiUsernameIcon = icon;
habbo.RpUiUsernameIconColor = iconColor;
```

- [ ] **Step 2: Write in `RpUiSettingsComposer`**

Add fields + ctor params (append last) + writes (append last):

```csharp
private readonly string _icon;
private readonly string _iconColor;

public RpUiSettingsComposer(string chromeColor, int chromeOpacity, string headerColor, string usernameColor, string icon, string iconColor)
{
    _chromeColor = chromeColor ?? "";
    _chromeOpacity = chromeOpacity;
    _headerColor = headerColor ?? "";
    _usernameColor = usernameColor ?? "";
    _icon = icon ?? "";
    _iconColor = iconColor ?? "";
}
```

In `Compose`, after `packet.WriteString(_usernameColor);`:

```csharp
packet.WriteString(_icon);
packet.WriteString(_iconColor);
```

- [ ] **Step 3: Pass at the login send site (`SSOTicketEvent.cs`)**

```csharp
session.Send(new RpUiSettingsComposer(session.GetHabbo().RpUiChromeColor, session.GetHabbo().RpUiChromeOpacity, session.GetHabbo().RpUiHeaderColor, session.GetHabbo().RpUiUsernameColor, session.GetHabbo().RpUiUsernameIcon, session.GetHabbo().RpUiUsernameIconColor));
```

- [ ] **Step 4: Compile** (same command as Task 1 Step 3). Expected: 0 errors.

- [ ] **Step 5: Commit**

```bash
cd emulator && git add Communication/Packets/Incoming/Users/RpSaveUiSettingsEvent.cs Communication/Packets/Outgoing/Users/RpUiSettingsComposer.cs Communication/Packets/Incoming/Handshake/SSOTicketEvent.cs && git commit -m "feat: username icon + color on RpUiSettings save/login packets"
```

---

### Task 3: Emulator — stamp icon + icon color onto chat packets

**Files:**
- Modify: `emulator/Communication/Packets/Outgoing/Rooms/Chat/ChatComposer.cs`, `ShoutComposer.cs`, `WhisperComposer.cs`
- Modify: `emulator/HabboHotel/Rooms/RoomUser.cs` (`OnChat`)
- Modify: `emulator/Communication/Packets/Incoming/Rooms/Chat/WhisperEvent.cs`

**Interfaces:**
- Consumes: `Habbo.RpUiUsernameIcon` / `RpUiUsernameIconColor` (Task 1).
- Produces: Chat/Shout/Whisper packets write trailing `icon`, `iconColor` (after `_usernameColor`). Read by renderer Task 4.

- [ ] **Step 1: Add trailing params to all three composers**

In each composer add two fields + two ctor params (default `""`) after `usernameColor`, and two writes after `packet.WriteString(_usernameColor);`. Example (`ChatComposer.cs`):

```csharp
private readonly string _usernameColor;
private readonly string _icon;
private readonly string _iconColor;

public ChatComposer(int virtualId, string message, int emotion, int colour, string usernameColor = "", string icon = "", string iconColor = "")
{
    _virtualId = virtualId;
    _message = message;
    _emotion = emotion;
    _colour = colour;
    _usernameColor = usernameColor ?? "";
    _icon = icon ?? "";
    _iconColor = iconColor ?? "";
}
```

In `Compose`, after `packet.WriteString(_usernameColor);`:

```csharp
packet.WriteString(_icon);
packet.WriteString(_iconColor);
```

Apply the same shape to `ShoutComposer.cs` and `WhisperComposer.cs` (keep their `text`/`message` param names).

- [ ] **Step 2: `RoomUser.OnChat` — pass the speaker's icon + color**

Where `usernameColor` is captured, add:

```csharp
var usernameIcon = GetClient().GetHabbo().RpUiUsernameIcon ?? "";
var usernameIconColor = GetClient().GetHabbo().RpUiUsernameIconColor ?? "";
```

Add `usernameIcon, usernameIconColor` as the last two args to the four speaker-side composers (the `shout`/`else` Chat/Shout, the two mention variants, and the tent `WhisperComposer`), e.g.:

```csharp
packet = new ShoutComposer(VirtualId, message, emotion, colour, usernameColor, usernameIcon, usernameIconColor);
// ...
packet = new ChatComposer(VirtualId, message, emotion, colour, usernameColor, usernameIcon, usernameIconColor);
// mention:
mentionPacket = shout
    ? new ShoutComposer(VirtualId, message, emotion, 25, usernameColor, usernameIcon, usernameIconColor)
    : (IServerPacket)new ChatComposer(VirtualId, message, emotion, 25, usernameColor, usernameIcon, usernameIconColor);
// tent:
packet = new WhisperComposer(VirtualId, $"[Tent Chat] {message}", 0, colour, usernameColor, usernameIcon, usernameIconColor);
```

- [ ] **Step 3: `WhisperEvent.Parse` — pass the whisperer's icon + color**

Where `usernameColor` is captured, add:

```csharp
var usernameIcon = session.GetHabbo().RpUiUsernameIcon ?? "";
var usernameIconColor = session.GetHabbo().RpUiUsernameIconColor ?? "";
```

Add `usernameIcon, usernameIconColor` as the last two args to the four `new WhisperComposer(...)` calls (the two `user.LastBubble, usernameColor` ones — note there are three identical `message` calls plus the mod-notify). Since three are identical, update each occurrence:

- the two identical `new WhisperComposer(user.VirtualId, message, 0, user.LastBubble, usernameColor)` → append `, usernameIcon, usernameIconColor` (there are 3 of these; update all);
- the mod-notify `new WhisperComposer(user.VirtualId, $"[Whisper to {toUser}] {message}", 0, user.LastBubble, usernameColor)` → append `, usernameIcon, usernameIconColor`.

- [ ] **Step 4: Compile** (Task 1 Step 3 command). Expected: 0 errors.

- [ ] **Step 5: Commit**

```bash
cd emulator && git add Communication/Packets/Outgoing/Rooms/Chat/ChatComposer.cs Communication/Packets/Outgoing/Rooms/Chat/ShoutComposer.cs Communication/Packets/Outgoing/Rooms/Chat/WhisperComposer.cs HabboHotel/Rooms/RoomUser.cs Communication/Packets/Incoming/Rooms/Chat/WhisperEvent.cs && git commit -m "feat: stamp username icon + color onto user chat/shout/whisper packets"
```

---

### Task 4: Renderer patch — read icon + icon color

**Files (via `yarn patch @nitrots/nitro-renderer`):**
- `RoomUnitChatParser.ts`, `RoomSessionChatEvent.ts`, `RoomChatHandler.ts`, `RpUiSettingsEvent.ts` (holds `RpUiSettingsParser`), `RpSaveUiSettingsComposer.ts`

**Interfaces:**
- Consumes: emulator trailing chat fields (Task 3) + login fields (Task 2).
- Produces: `RoomSessionChatEvent.icon` / `.iconColor`; `RpUiSettingsParser.icon` / `.iconColor`; `RpSaveUiSettingsComposer(chromeColor, chromeOpacity, headerColor, usernameColor, icon, iconColor)`. Consumed by client Tasks 5–7.

- [ ] **Step 1: Open the package + apply the existing patch to the temp dir**

```bash
cd client && yarn patch @nitrots/nitro-renderer
```

Note the temp dir `$P`. The extraction is the **unpatched** base — apply the current patch first so you layer on top (else the username-color + all prior additions are lost):

```bash
git apply -p1 --directory="$P" .yarn/patches/@nitrots-nitro-renderer-npm-1.6.6-c15ae4be91.patch
```

Verify: `grep -rl usernameColor "$P/src" | head` shows the parser/event/composer.

- [ ] **Step 2: Edit the five files in `$P`** (append after the `usernameColor` slots)

`RoomUnitChatParser.ts`: add `private _icon: string;` + `private _iconColor: string;`; in `flush()` add `this._icon = ''; this._iconColor = '';`; in `parse()` after `this._usernameColor = wrapper.readString();` add `this._icon = wrapper.readString(); this._iconColor = wrapper.readString();`; add getters `get icon()` and `get iconColor()`.

`RoomSessionChatEvent.ts`: add `private _icon: string;` + `private _iconColor: string;`; ctor params append `, icon: string = '', iconColor: string = ''`; assign `this._icon = icon; this._iconColor = iconColor;`; add `get icon()` + `get iconColor()`.

`RoomChatHandler.ts`: in `onRoomUnitChatEvent`, change the construction to pass them last:

```typescript
const chatEvent = new RoomSessionChatEvent(RoomSessionChatEvent.CHAT_EVENT, session, parser.roomIndex, parser.message, chatType, parser.bubble, null, -1, parser.usernameColor, parser.icon, parser.iconColor);
```

`RpUiSettingsEvent.ts` (`RpUiSettingsParser`): add `_icon` + `_iconColor` fields, flush `''`, read after `this._usernameColor = wrapper.readString();`, add getters.

`RpSaveUiSettingsComposer.ts`: ctor → `(chromeColor: string, chromeOpacity: number, headerColor: string, usernameColor: string, icon: string, iconColor: string)`; `this._data = [chromeColor, chromeOpacity, headerColor, usernameColor, icon, iconColor];`.

- [ ] **Step 3: Commit the patch + reinstall**

```bash
cd client && yarn patch-commit -s "$P" && yarn install
```

- [ ] **Step 4: Verify node_modules reflects it**

```bash
cd client && grep -c "iconColor" node_modules/@nitrots/nitro-renderer/src/nitro/communication/messages/parser/room/unit/chat/RoomUnitChatParser.ts
grep -c "usernameColor" .yarn/patches/@nitrots-nitro-renderer-npm-1.6.6-*.patch
```

Expected: `iconColor` present in the parser; `usernameColor` still present in the patch (nothing clobbered). A full `tsc` will fail until the client caller is updated (Task 7) — that is expected.

- [ ] **Step 5: Commit (client submodule)**

```bash
cd client && git add .yarn/patches package.json yarn.lock && git commit -m "feat: renderer patch - username icon + icon color on chat + UI-settings packets"
```

---

### Task 5: Client — kit embed, palette module, glyph, message/history fields

**Files:**
- Modify: `client/index.html`
- Create: `client/src/components/rp-settings/IconChoices.ts`
- Create: `client/src/components/rp-settings/UsernameIconGlyph.tsx`
- Modify: `client/src/api/room/widgets/ChatBubbleMessage.ts`
- Modify: `client/src/api/chat-history/IChatEntry.ts`

**Interfaces:**
- Produces: `USERNAME_ICONS`, `DEFAULT_USERNAME_ICON`, `IsValidUsernameIcon` (from `IconChoices.ts`); `UsernameIconGlyph`; `ChatBubbleMessage.usernameIcon` + `.usernameIconColor`; `IChatEntry.usernameIcon?` + `.usernameIconColor?`. Consumed by Tasks 6 and 7.

- [ ] **Step 1: Embed the kit in `index.html`**

In `<head>` (e.g. after the fonts stylesheet line), add:

```html
<script src="https://kit.fontawesome.com/19221c1121.js" crossorigin="anonymous"></script>
```

- [ ] **Step 2: Create `IconChoices.ts`** (seeded with only the "none" X for now; the custom list is filled in Task 8)

```typescript
// PixelRP username icon choices (Settings > Social > Username > Icon).
// The first entry (iconClass: null) is "None" — the target-HUD X — and stores
// '' server-side, rendering no prefix. Every other entry is a FontAwesome kit
// custom icon class rendered as [ <icon> ] before the username.

export interface IconChoice
{
    key: string;
    name: string;
    iconClass: string | null; // null = none (the X / clear state)
}

export const USERNAME_ICONS: IconChoice[] = [
    { key: 'none', name: 'None', iconClass: null },
    // Custom kit icons populated in Task 8 (discovered live from the kit), e.g.:
    // { key: 'star', name: 'Star', iconClass: 'fa-kit fa-kit-star' },
];

export const DEFAULT_USERNAME_ICON: string = ''; // none / X selected

export const IsValidUsernameIcon = (value: string): boolean =>
    (value === '') || USERNAME_ICONS.some(entry => (entry.iconClass === value));
```

- [ ] **Step 3: Create `UsernameIconGlyph.tsx`**

```tsx
import { FC } from 'react';
import { FaTimes } from 'react-icons/fa';

// Renders a username icon uniformly for the picker and the chat views. A null
// iconClass is the "none" state, drawn as the target-HUD X (react-icons); a
// non-null class is a FontAwesome kit icon (<i> swapped to SVG by the kit).
export const UsernameIconGlyph: FC<{ iconClass: string | null; color?: string }> = ({ iconClass, color }) =>
    iconClass
        ? <i className={ iconClass } style={ color ? { color } : undefined } />
        : <FaTimes style={ color ? { color } : undefined } />;
```

- [ ] **Step 4: Extend `ChatBubbleMessage.ts`** — append two ctor fields after `usernameColor`:

```typescript
        public usernameColor: string = null,
        public usernameIcon: string = null,
        public usernameIconColor: string = null
    )
```

- [ ] **Step 5: Extend `IChatEntry.ts`** — after `usernameColor?`:

```typescript
    usernameIcon?: string;
    usernameIconColor?: string;
```

- [ ] **Step 6: Type-check** (renderer types now resolve for these files)

```bash
cd client && npx tsc --noEmit -p tsconfig.json 2>&1 | grep -v "motto" | head
```

Expected: no new errors beyond the pre-existing `motto` ones (which are unrelated). Task 7 removes the RpSettingsView caller mismatch.

- [ ] **Step 7: Commit**

```bash
cd client && git add index.html src/components/rp-settings/IconChoices.ts src/components/rp-settings/UsernameIconGlyph.tsx src/api/room/widgets/ChatBubbleMessage.ts src/api/chat-history/IChatEntry.ts && git commit -m "feat: FA kit embed, icon choices, glyph, message/history icon fields"
```

---

### Task 6: Client — render the `[ <icon> ]` prefix

**Files:**
- Modify: `client/src/hooks/rooms/widgets/useChatWidget.ts`
- Modify: `client/src/components/room/widgets/chat/ChatWidgetMessageView.tsx`
- Modify: `client/src/components/chat-history/ChatHistoryView.tsx`

**Interfaces:**
- Consumes: `RoomSessionChatEvent.icon` / `.iconColor` (Task 4); `ChatBubbleMessage` + `IChatEntry` icon fields (Task 5).

- [ ] **Step 1: Thread through `useChatWidget`**

Where `usernameColor` is derived, add:

```typescript
const usernameIcon = (event.icon && event.icon.length) ? event.icon : null;
const usernameIconColor = (event.iconColor && (event.iconColor !== '#000000')) ? event.iconColor : null;
```

Pass `usernameIcon, usernameIconColor` as the final two args to `new ChatBubbleMessage(...)`, and add `usernameIcon, usernameIconColor` to the `addChatEntry({...})` object.

- [ ] **Step 2: Bubble prefix in `ChatWidgetMessageView.tsx`**

Import the glyph at the top:

```tsx
import { UsernameIconGlyph } from '../../../rp-settings/UsernameIconGlyph';
```

Immediately before the username `<b>` (inside `chat-content`), add:

```tsx
{ chat.usernameIcon &&
    <b className="username mr-1">{ '[ ' }<UsernameIconGlyph iconClass={ chat.usernameIcon } color={ chat.usernameIconColor || undefined } />{ ' ]' }</b> }
```

- [ ] **Step 3: History prefix in `ChatHistoryView.tsx`**

Import the glyph:

```tsx
import { UsernameIconGlyph } from '../../rp-settings/UsernameIconGlyph';
```

Before the `TYPE_CHAT` username `<b>`, add:

```tsx
{ row.usernameIcon &&
    <b className="username mr-1">{ '[ ' }<UsernameIconGlyph iconClass={ row.usernameIcon } color={ row.usernameIconColor || undefined } />{ ' ]' }</b> }
```

- [ ] **Step 4: Type-check**

```bash
cd client && npx tsc --noEmit -p tsconfig.json 2>&1 | grep -v "motto" | head
```

Expected: no new errors (RpSettingsView caller updated in Task 7; if run before Task 7 it will flag the 4-arg `RpSaveUiSettingsComposer` call — acceptable mid-task).

- [ ] **Step 5: Commit**

```bash
cd client && git add src/hooks/rooms/widgets/useChatWidget.ts src/components/room/widgets/chat/ChatWidgetMessageView.tsx src/components/chat-history/ChatHistoryView.tsx && git commit -m "feat: render [ <icon> ] prefix in chat bubbles and history"
```

---

### Task 7: Client — Settings Icon + Icon Color pickers

**Files:**
- Modify: `client/src/components/rp-settings/RpSettingsView.tsx`

**Interfaces:**
- Consumes: `USERNAME_ICONS`, `DEFAULT_USERNAME_ICON`, `IsValidUsernameIcon`, `UsernameIconGlyph` (Task 5); `USERNAME_COLORS` / `DEFAULT_USERNAME_COLOR` / `IsValidUsernameColor` (existing); `RpUiSettingsEvent.icon` / `.iconColor` + 6-arg `RpSaveUiSettingsComposer` (Task 4).

- [ ] **Step 1: Imports**

```tsx
import { DEFAULT_USERNAME_ICON, IsValidUsernameIcon, USERNAME_ICONS } from './IconChoices';
import { UsernameIconGlyph } from './UsernameIconGlyph';
```

- [ ] **Step 2: State**

```tsx
const [ usernameIcon, setUsernameIcon ] = useState<string>(DEFAULT_USERNAME_ICON);
const [ usernameIconColor, setUsernameIconColor ] = useState<string>(DEFAULT_USERNAME_COLOR);
```

- [ ] **Step 3: Apply from `RpUiSettingsEvent`**

After the username color apply, add:

```tsx
const uicon = (IsValidUsernameIcon(parser.icon) ? parser.icon : DEFAULT_USERNAME_ICON);
const uiconColor = (IsValidUsernameColor(parser.iconColor) ? parser.iconColor : DEFAULT_USERNAME_COLOR);
setUsernameIcon(uicon);
setUsernameIconColor(uiconColor);
```

- [ ] **Step 4: Extend the unified save to 6 values**

```tsx
const saveSettings = (color: string, opacity: number, header: string, uname: string, icon: string, iconColor: string) =>
{
    SendMessageComposer(new RpSaveUiSettingsComposer(
        (color === DEFAULT_CHROME_COLOR) ? '' : color,
        opacity,
        (header === DEFAULT_HEADER_KEY) ? '' : header,
        (uname === DEFAULT_USERNAME_COLOR) ? '' : uname,
        icon,
        (iconColor === DEFAULT_USERNAME_COLOR) ? '' : iconColor));
}
```

Update the existing callers (`selectChrome`, `selectOpacity`, `selectHeader`, `selectUsernameColor`) to pass `usernameIcon, usernameIconColor` as the last two args. Add the two new selectors:

```tsx
const selectUsernameIcon = (icon: string) =>
{
    setUsernameIcon(icon);
    saveSettings(chromeColor, chromeOpacity, headerKey, usernameColor, icon, usernameIconColor);
}

const selectUsernameIconColor = (color: string) =>
{
    setUsernameIconColor(color);
    saveSettings(chromeColor, chromeOpacity, headerKey, usernameColor, usernameIcon, color);
}
```

- [ ] **Step 5: Render the Icon + Icon Color sections**

Inside the Social → Username subpage, below the existing Color `rp-settings-section`, add:

```tsx
<div className="rp-settings-section">
    <div className="rp-settings-section-info">
        <Text bold>Icon</Text>
        <Text small className="text-muted">An icon shown before your name in chat. Everyone in the room sees it. The X means none.</Text>
    </div>
    <div className="rp-settings-swatches">
        { USERNAME_ICONS.map(entry => (
            <div key={ entry.key } title={ entry.name }
                className={ `rp-settings-swatch rp-settings-swatch--icon ${ (usernameIcon === (entry.iconClass ?? '')) ? 'is-selected' : '' }` }
                onClick={ () => selectUsernameIcon(entry.iconClass ?? '') }>
                <UsernameIconGlyph iconClass={ entry.iconClass } />
            </div>
        )) }
    </div>
</div>
<div className="rp-settings-section">
    <div className="rp-settings-section-info">
        <Text bold>Icon Color</Text>
        <Text small className="text-muted">The color of your chat icon.</Text>
    </div>
    <div className="rp-settings-swatches">
        { USERNAME_COLORS.map(entry => (
            <div key={ entry.key } title={ entry.name }
                className={ `rp-settings-swatch ${ (usernameIconColor === entry.color) ? 'is-selected' : '' }` }
                style={ { backgroundColor: entry.color } }
                onClick={ () => selectUsernameIconColor(entry.color) } />
        )) }
    </div>
</div>
```

- [ ] **Step 6: SCSS — center the icon glyph in its swatch**

In `RpSettingsView.scss`, add a small rule so icon swatches show the glyph centered on the swatch background (they carry no `background-color`):

```scss
.rp-settings-swatch--icon {
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, .15);
    color: #000;
    font-size: 16px;

    svg { width: 16px; height: 16px; }
}
```

- [ ] **Step 7: Type-check + eslint**

```bash
cd client && npx tsc --noEmit -p tsconfig.json 2>&1 | grep -v "motto" | head
```

Expected: no new errors.

- [ ] **Step 8: Commit**

```bash
cd client && git add src/components/rp-settings/RpSettingsView.tsx src/components/rp-settings/RpSettingsView.scss && git commit -m "feat: Settings Social > Username > Icon + Icon Color pickers"
```

---

### Task 8: Discover the kit's custom icons and populate the list

**Files:**
- Modify: `client/src/components/rp-settings/IconChoices.ts`

**Interfaces:**
- Consumes: the embedded kit (Task 5 Step 1).
- Produces: the real `USERNAME_ICONS` entries.

- [ ] **Step 1: Build + run locally, load the client**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus && docker/nitro/build-client.sh
```

Bring up the local stack and open the served client in the in-app browser (the kit loads on the login page — no login needed). If the kit is domain-locked and refuses `localhost`, do this step on beta after Task 9's first deploy instead.

- [ ] **Step 2: Enumerate the custom icons in the console**

In the browser console for the client tab, run:

```js
// Custom (kit) icon prefixes are usually "fak"/"fa-kit". List what's loaded:
(() => {
  const fa = window.FontAwesome;
  const defs = fa?.library?.definitions ?? {};
  const out = {};
  for (const prefix of Object.keys(defs)) out[prefix] = Object.keys(defs[prefix]);
  return out;
})()
```

Record the custom family prefix (e.g. `fak`) and the icon names. The usable class for a custom icon `foo` is typically `fa-kit fa-kit-foo` (verify by rendering one and confirming the kit swaps it to SVG). If `window.FontAwesome` does not expose the custom set, get the class names from the kit dashboard (ask the user to paste) — architecture is unaffected.

- [ ] **Step 3: Populate `USERNAME_ICONS`**

Replace the placeholder comment with the discovered entries, keeping `none` first:

```typescript
export const USERNAME_ICONS: IconChoice[] = [
    { key: 'none', name: 'None', iconClass: null },
    { key: '<name>', name: '<Name>', iconClass: '<verified class>' },
    // …one per discovered custom icon
];
```

- [ ] **Step 4: Rebuild + spot-check a swatch renders as SVG**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus && docker/nitro/build-client.sh
```

Reload the client, open Settings → Social → Username, confirm the Icon grid shows glyphs (not bare boxes). If bubbles later show a bare `<i>`, add the FA fallback nudge (a `useEffect` calling `window.FontAwesome.dom.i2svg({ node })` on the bubble ref) — only if verification shows a gap.

- [ ] **Step 5: Commit**

```bash
cd client && git add src/components/rp-settings/IconChoices.ts && git commit -m "feat: populate username icon list from the FontAwesome kit"
```

---

### Task 9: Build, ship to beta, verify, changelog

**Files:**
- Modify: `CHANGELOG.md` (parent)
- Parent submodule pointers: `client`, `emulator`

- [ ] **Step 1: Final builds**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
docker/nitro/build-client.sh
# emulator compile via the clean-copy docker command from Task 1 Step 3
```

Expected: client bundle builds; emulator 0 errors.

- [ ] **Step 2: Changelog**

Add a dated section at the top of `CHANGELOG.md` (player-facing):

```markdown
## 2026-08-24 — A badge for your name

### Added

- **Put an icon before your name in chat.** Settings → Social → Username now
  has an Icon picker (and an Icon Color to match). Pick one and it shows as
  `[ icon ]` in front of your name in chat bubbles and history for everyone in
  the room; pick the X to remove it. It sticks between visits.
```

- [ ] **Step 3: Push submodules**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus/client && git push origin "$(git rev-parse --abbrev-ref HEAD)"
cd /Users/rybealey/Documents/Personal/pixelrp/plus/emulator && git push origin pixelrp
```

- [ ] **Step 4: Bump pointers, commit, push to beta**

First `git fetch origin beta` and rebase local `beta` onto it if it advanced (parallel work is likely); resolve any submodule-pointer conflict to your newest commits, re-verifying `git merge-base --is-ancestor origin/beta beta`. Then:

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
git add client emulator CHANGELOG.md docs/superpowers/plans/2026-08-24-username-icon.md
git commit -m "feat: username icon in chat (Settings > Social > Username > Icon)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git push origin beta
```

(Migration 25 auto-applies via the deploy's "Apply database patches" step — no manual beta DB step.)

- [ ] **Step 5: Confirm the deploy**

```bash
gh run list --branch beta --limit 3 --json displayTitle,status,conclusion,headSha
```

Watch the run for the pushed SHA to `conclusion: success` and confirm the emulator comes up healthy (the "Wait for the beta emulator" step). If Task 8's discovery had to be done on beta, do it now against beta.pixelrp.co, then redeploy with the populated list.

- [ ] **Step 6: Hand off for manual in-game testing**

Verify in-game (two accounts, relog, X = none, icon color, bubbles + history, bot/pet unaffected).

---

## Self-Review

**Spec coverage:**
- Icon picker below Color under Social → Username → Task 7 Step 5. ✓
- `[ <icon> ]` before username, all viewers → Tasks 3, 4, 6. ✓
- Icon color, reuse 20 username colors → Task 7 (Icon Color grid uses `USERNAME_COLORS`). ✓
- FA kit embed → Task 5 Step 1. ✓
- Default X = none = no prefix → `IconChoices` (`iconClass: null` → stores `''`), render guards on `chat.usernameIcon` truthy (Task 6). ✓
- Brackets black, icon colored → Task 6 (brackets in `<b>`, icon in colored glyph). ✓
- Bubbles + history → Task 6 Steps 2–3. ✓
- Persist across sessions → Tasks 1, 2 + migration 25. ✓
- Styled like the color swatches → Task 7 (same `rp-settings-swatches`), Step 6 icon-swatch SCSS. ✓
- Push to beta → Task 9. ✓

**Placeholder scan:** The only intentional deferred content is the discovered icon list (Task 8), which is a live-discovery data step, explicitly flagged, with a paste fallback. No `TBD` in architecture/code.

**Type consistency:** `usernameIcon` (string, `''`=none) and `usernameIconColor` (string, `''`/`#000000`=default) are the field names across emulator (`RpUiUsernameIcon`/`RpUiUsernameIconColor`), renderer (`icon`/`iconColor` getters; `RpSaveUiSettingsComposer` 5th/6th args), and client (`ChatBubbleMessage.usernameIcon`/`.usernameIconColor`, `IChatEntry`, `event.icon`/`event.iconColor`). Composer arg order (…, usernameColor, icon, iconColor) matches the emulator read order in Task 2 and the chat read order in Task 4. `saveSettings` now takes 6 values in the order (chromeColor, opacity, header, usernameColor, icon, iconColor), matching `RpSaveUiSettingsComposer`.
