# Username Color — Design

Date: 2026-08-24
Status: Approved design, pending spec review

## Summary

Give players a **username color** for their chat bubbles, chosen from a
20-color palette in **Settings → Social → Username → Color**. The chosen
color is:

- **visible to all users** — everyone in the room sees the sender's chosen
  color on the username in that sender's chat bubble (and in the chat
  history panel), and
- **persistent across sessions** — stored server-side per user.

As part of the same change, the **Roleplay** tab loses its `Color` and `Tag`
sub-pages, and **Social** gains a sub-nav (matching the Interface/Roleplay
sub-nav style) whose first page is `Username`, whose first section is `Color`.

## Scope decisions (confirmed)

- **Transport:** the sender's username color rides on the **chat packet**
  (Chat / Shout / Whisper). No per-user registry, no room-entry lifecycle,
  no client-side cache. A color change simply applies on the sender's next
  message.
- **Palette:** 20 colors, chosen in this spec, **black first = default**.
- **Where it applies:** live chat bubbles **and** the chat history panel.

## Non-goals

- No effect on the room's floating name tag, the HUD, or anywhere other than
  the chat bubble username and the chat-history username.
- No per-room or staff-only gating — every player may set it.
- The `Tag` and `Macros`/`Messages` Roleplay pages are not built here; `Color`
  and `Tag` are simply removed from Roleplay (Tag is dropped entirely for now).

## Why the chat packet (vs. the alternatives)

Username color is intrinsically a property of a chat message: the username
only ever renders inside a bubble/log entry, which the client builds from the
chat event. The client already receives the sender's identity in that event,
so adding one field there means **zero caching and no lifecycle bugs** —
unlike a per-user broadcast (needs a room-entry hook + a synced cache) or
extending core `RoomUnitData` (modifies a fundamental packet parser). The
per-message cost is one string, written on both sides in a fixed position.

## Architecture

Two independent data paths, deliberately kept separate:

1. **Persistence / ownership (self only).** The player's chosen color is
   saved to and loaded from the DB via the existing UI-settings pipeline
   (the same one the chrome color uses). This path only ever tells the
   *owner* their own color — used to show the selected swatch in the picker.

2. **Display (all users).** When any user speaks, the emulator stamps that
   user's saved username color onto the outgoing Chat/Shout/Whisper packet,
   so every recipient's client can color the username. This is how other
   players learn a user's color; it needs no login-time broadcast.

```
Picker (Social▸Username▸Color)
  │  select swatch
  ▼
RpSaveUiSettingsComposer (chrome…, usernameColor)  ── client → server
  ▼
RpSaveUiSettingsEvent → Habbo.RpUiUsernameColor → user_ui_settings.username_color (DB)

login:
user_ui_settings → Habbo → RpUiSettingsComposer(chrome…, usernameColor) ── server → owner
  ▼
RpUiSettingsEvent → picker shows selected swatch

any user speaks:
Habbo.RpUiUsernameColor → ChatComposer/ShoutComposer/WhisperComposer(…, usernameColor)
  ▼ (server → every client in room)
RoomUnitChatParser.usernameColor → RoomSessionChatEvent.usernameColor
  ▼
useChatWidget → ChatBubbleMessage.usernameColor / IChatEntry.usernameColor
  ▼
ChatWidgetMessageView + ChatHistoryView  ── color the <b class="username">
```

`""` (empty) and `#000000` both mean **default** (no color override), exactly
mirroring how the chrome color treats `""` as "client default".

## The palette

20 entries; `#000000` first and treated as the default. Chosen for
legibility on the light chat-bubble background and the history panel (all
mid-to-dark lightness). Order is the swatch-grid order.

| # | Name | Hex | # | Name | Hex |
|---|------|-----|---|------|-----|
| 1 | Black (default) | `#000000` | 11 | Cyan | `#0e7490` |
| 2 | Slate | `#4b5563` | 12 | Ocean | `#0369a1` |
| 3 | Red | `#b91c1c` | 13 | Blue | `#1d4ed8` |
| 4 | Crimson | `#be123c` | 14 | Indigo | `#3730a3` |
| 5 | Orange | `#d35400` | 15 | Violet | `#6d28d9` |
| 6 | Amber | `#b45309` | 16 | Purple | `#7e22ce` |
| 7 | Gold | `#a16207` | 17 | Magenta | `#a21caf` |
| 8 | Olive | `#4d7c0f` | 18 | Pink | `#be185d` |
| 9 | Green | `#2e7d32` | 19 | Brown | `#6d4c41` |
| 10 | Teal | `#0f766e` | 20 | Charcoal | `#374151` |

The picker swatch shows the **literal** hex (unlike the chrome picker, which
shows a vibrant proxy of a near-black surface). Selecting Black sends `""`.

## Components & changes

### A. Client — nitro-react (`client/`)

1. **`src/components/rp-settings/UsernameColors.ts`** (new). Mirrors
   `UiChrome.ts`'s data half: `USERNAME_COLORS: {key,name,color}[]` (the 20
   above), `DEFAULT_USERNAME_COLOR = '#000000'`,
   `IsValidUsernameColor(color)` = exact membership test.

2. **`src/components/rp-settings/RpSettingsView.tsx`**
   - `ROLEPLAY_PAGES` → `['Macros','Messages']` (drop `Color`, `Tag`).
   - Add `SOCIAL_PAGES = ['Username']` and `socialPage` state.
   - Add `usernameColor` state; initialize from `RpUiSettingsEvent`
     (validate; fall back to default) alongside the existing chrome fields.
   - Render a `rp-settings-subnav-layout` block for the `Social` tab (same
     markup as Interface/Roleplay), with a `Username` page containing a
     `Color` section: a `rp-settings-swatches` grid of the 20 colors, each a
     `rp-settings-swatch` with `backgroundColor: color`, `is-selected` when
     it matches, `onClick` → `selectUsernameColor(color)`.
   - `selectUsernameColor(color)`: set state, then persist. Persistence
     reuses the single save call (see §4) so chrome + username go together.
   - Remove the `Social` case from the catch-all "Nothing here yet" branch.

3. **`src/api/room/widgets/ChatBubbleMessage.ts`** — add
   `public usernameColor: string = null` constructor param (appended last).

4. **Save/apply wiring for username color** — extend the existing chrome
   packets rather than add new ones (minimal wire surface):
   - Persist via `RpSaveUiSettingsComposer(chrome, opacity, header,
     usernameColor)`. `RpSettingsView` holds all four in state and always
     passes the current `usernameColor` in `saveChrome(...)` (rename to
     `saveSettings`), so saving a chrome change never clears the username
     color and vice-versa. Black → send `''`.

5. **`src/hooks/rooms/widgets/useChatWidget.ts`** — read
   `event.usernameColor`; pass it to `new ChatBubbleMessage(...)` and include
   `usernameColor` in the `addChatEntry({...})` object.

6. **`src/api/chat-history/IChatEntry.ts`** — add
   `usernameColor?: string;`.

7. **`src/components/room/widgets/chat/ChatWidgetMessageView.tsx`** — on the
   `<b className="username">` (line ~88), apply
   `style={{ color: chat.usernameColor || undefined }}` (undefined when empty
   / default → inherits today's look).

8. **`src/components/chat-history/ChatHistoryView.tsx`** — apply the same
   `style={{ color: row.usernameColor || undefined }}` to the username `<b>`
   (line ~80) and, where the compact layout renders `row.name` via `<Text>`
   (line ~88), wrap/style it consistently so both history layouts match.

9. **`src/components/rp-settings/RpSettingsView.scss`** — the existing
   `.rp-settings-swatches` / `.rp-settings-swatch` should already flex-wrap;
   confirm 20 swatches wrap to a tidy grid and add a modifier only if needed.

### B. Renderer — nitro-react yarn patch (`client/.yarn/patches/...`)

Extend the existing patch. **Append every new field at the end** of its
packet, read at the end on the client — matching the fixed EvaWire field
order both sides already share.

1. **`RoomUnitChatParser`** — after `this._messageLength = wrapper.readInt();`
   read `this._usernameColor = wrapper.readString();`; add the private field,
   flush default `''`, and a `get usernameColor()`. (Chat, Shout, and Whisper
   all share this one parser.)
2. **`RoomSessionChatEvent`** — add a `usernameColor` constructor param
   (default `''`) + getter.
3. **`RoomChatHandler.onRoomUnitChatEvent`** — pass `parser.usernameColor`
   into the `new RoomSessionChatEvent(...)`.
4. **`RpUiSettingsParser`** — after `this._headerColor = wrapper.readString();`
   read `this._usernameColor = wrapper.readString();` (+ field, flush, getter).
5. **`RpSaveUiSettingsComposer`** — constructor takes a 4th `usernameColor`
   arg and writes it last.

### C. Emulator — PlusEMU (`emulator/`)

1. **`HabboHotel/Users/Habbo.cs`**
   - Add `public string RpUiUsernameColor { get; set; } = "";`.
   - `EnsureRpUiSettingsLoaded`: `SELECT` also `username_color`; assign.
   - `SaveRpUiSettings`: `REPLACE INTO user_ui_settings (...,username_color)`
     and add the parameter.
2. **`Communication/Packets/Incoming/Users/RpSaveUiSettingsEvent.cs`** — read
   a 4th string `usernameColor`; validate against the hex regex (allow `""`);
   assign `habbo.RpUiUsernameColor` before `SaveRpUiSettings()`.
3. **`Communication/Packets/Outgoing/Users/RpUiSettingsComposer.cs`** — take a
   4th `usernameColor` arg and `WriteString` it last; update the login send
   site to pass `habbo.RpUiUsernameColor`.
4. **Chat composers** (`ChatComposer.cs`, `ShoutComposer.cs`,
   `WhisperComposer.cs`) — add a trailing constructor param
   `string usernameColor = ""` and `WriteString(_usernameColor)` **after** the
   existing final `WriteInteger(-1)`. The default keeps all ~13 existing call
   sites (pets, bots, wired, commands, system) compiling unchanged and
   emitting `""`.
5. **`HabboHotel/Rooms/RoomUser.cs`** — the real user speak/shout/whisper
   paths pass `GetClient()?.GetHabbo()?.RpUiUsernameColor ?? ""` into the
   composer. This is the only call site that supplies a real color.

### D. Data / deploy (non-git)

DB schema change — apply to prod manually (schema changes don't ship via
deploy):

```sql
ALTER TABLE `user_ui_settings`
  ADD COLUMN `username_color` VARCHAR(7) NOT NULL DEFAULT '' AFTER `header_color`;
```

Beta first (auto-deploys beta.pixelrp.co): apply the ALTER on the beta DB
before/with the deploy. Then prod when promoting.

## Wire-format safety

- The chat field is appended after each composer's existing trailing `-1`
  and read after `messageLength` in `RoomUnitChatParser` — a fixed position
  both sides agree on. The server **always** writes a defined string (default
  `""`), so the parser never desyncs (avoids the "undefined = 2 bytes" trap).
- The UI-settings field is appended last in both `RpUiSettingsComposer`
  (server→client) and `RpSaveUiSettingsComposer` (client→server) and read
  last in `RpUiSettingsParser`.
- No `ClientPacketHeader` / `ServerPacketHeader` changes — these are field
  additions to existing packets, not new message IDs.

## Testing / verification

Manual in-game (per project preference — no screenshot-driving the client):

1. Build renderer patch → build client → build emulator; apply the ALTER on
   the beta DB.
2. In Settings: confirm Roleplay no longer shows `Color`/`Tag`; Social shows
   a `Username` sub-nav with a `Color` grid of 20 swatches, black selected by
   default.
3. Pick a non-black color; speak — own bubble username is colored. A second
   account in the room sees the same color on your bubble and in its chat
   history. Relog — the swatch is still selected and new bubbles stay colored.
4. Pick Black — username returns to default for everyone; DB row stores `''`.
5. Pets/bots/wired/system chat still render normally (default color).

## CHANGELOG

Add a player-facing entry (username colors in chat bubbles; Settings → Social
→ Username). Note the DB `ALTER` as a manual prod step in the deploy notes.
