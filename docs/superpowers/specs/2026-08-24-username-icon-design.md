# Username Icon — Design

Date: 2026-08-24
Status: Approved design, pending spec review

## Summary

Add, directly below **Settings → Social → Username → Color**, two more
pickers on the same Username page:

1. **Icon** — a grid of selectable icons. When a player picks one, it renders
   as `[ <icon> ]` immediately **before** their username in their chat bubble
   (and in the chat-history panel), visible to everyone in the room.
2. **Icon Color** — the same 20-color palette as username color; recolors the
   selected icon.

Icons come from the project's **FontAwesome kit** (`19221c1121`), which holds
custom icons. The kit loader is embedded once in the client so `<i class="…">`
markup is swapped to SVG at runtime.

## Scope decisions (confirmed)

- **Default = the target-HUD X, which means "no icon."** The first/default
  swatch is the same X used to clear a target in the target HUD
  (`<FaTimes/>`). Selecting it renders **nothing** before the username — it is
  the "none / clear" choice. Only a non-X (custom) icon renders `[ <icon> ]`.
- **Icon color:** reuses `USERNAME_COLORS` (20 swatches, black default).
- **Where it applies:** live chat bubbles **and** the chat-history panel
  (matching username color).
- **Icon list:** discovered live from the kit (see Discovery) — the feature is
  data-driven, so populating the list is a content step, not an architecture
  change.

## Non-goals

- No per-icon unlock/gating, no staff-only restriction — every player may pick.
- The X swatch is never itself rendered in a bubble; it only represents the
  "no icon" state in the picker (shown as the familiar clear-X glyph).
- No change to the target HUD itself.

## Rendering

The bubble/username prefix, left to right:

```
[   <icon>   ]   <username>:   <message>
^black ^iconColor ^black ^usernameColor ^black(colon)
```

- The brackets `[` `]` and the surrounding spaces are **black** (no color
  treatment).
- Only the **icon** takes `iconColor`.
- The username keeps its own `usernameColor`; the colon stays black (as shipped).
- When the icon is the X / empty, the **entire prefix is omitted** — the bubble
  looks exactly as it does today.

Two icon render paths, unified by `currentColor` (so one `color` style covers
both):

- **Default X (empty value):** not rendered at all (no prefix).
- **Custom icon:** `<i className={iconClass} />`, which the embedded kit script
  replaces with an SVG. Colored by wrapping in a `<span style={{ color }}>`.

The picker's X swatch renders `<FaTimes/>` (react-icons — the exact target-HUD
component) so "none" reads as the familiar clear-X. Custom-icon swatches render
`<i className={iconClass} />`.

## Architecture

Identical two-path shape to [[username color]] (see
`2026-08-24-username-color-design.md`):

1. **Persistence / ownership (self only).** The player's icon + icon color are
   stored in `user_ui_settings` and pushed to the owner at login (for the
   picker's selected state), via the existing UI-settings packets.
2. **Display (all users).** The sender's icon + icon color ride the **chat
   packet** so every recipient renders the prefix. Empty icon = no prefix.

```
Picker (Social▸Username: Icon + Icon Color)
  │ select
  ▼
RpSaveUiSettingsComposer(chrome…, usernameColor, icon, iconColor)  ── client → server
  ▼
RpSaveUiSettingsEvent → Habbo.RpUiUsernameIcon / RpUiUsernameIconColor
  ▼
user_ui_settings.username_icon / username_icon_color (DB)

login: user_ui_settings → RpUiSettingsComposer(… , icon, iconColor) ── server → owner → picker

any user speaks:
Habbo → ChatComposer/ShoutComposer/WhisperComposer(… , icon, iconColor)
  ▼ (server → every client in room)
RoomUnitChatParser.icon / .iconColor → RoomSessionChatEvent
  ▼
useChatWidget → ChatBubbleMessage / IChatEntry
  ▼
ChatWidgetMessageView + ChatHistoryView → render [ <icon> ] prefix
```

`''` icon = none. Icon color `''`/`#000000` = default (black), same convention
as username color.

## Components & changes

### A. Client — nitro-react (`client/`)

1. **`index.html`** — embed the kit loader in `<head>`:
   `<script src="https://kit.fontawesome.com/19221c1121.js" crossorigin="anonymous"></script>`.
   (No CSP anywhere in the nginx configs, so it loads.)

2. **`src/components/rp-settings/IconChoices.ts`** (new). Mirrors
   `UsernameColors.ts`'s data half:
   - `interface IconChoice { key: string; name: string; iconClass: string | null; }`
   - `USERNAME_ICONS: IconChoice[]` — first entry is the "none" X
     (`{ key: 'none', name: 'None', iconClass: null }`), then the custom kit
     icons (populated from Discovery).
   - `DEFAULT_USERNAME_ICON = ''` (the none/X state; stored value for "none").
   - `IsValidUsernameIcon(value: string)` — `''` OR a member `iconClass`.
   Icon **color** reuses `USERNAME_COLORS` / `DEFAULT_USERNAME_COLOR` /
   `IsValidUsernameColor` from `UsernameColors.ts` — no new palette.

3. **`src/components/rp-settings/UsernameIconGlyph.tsx`** (new, small). A shared
   renderer so the picker and both bubble/history views draw an icon
   identically:
   ```tsx
   export const UsernameIconGlyph: FC<{ iconClass: string | null; color?: string }> = ({ iconClass, color }) =>
       iconClass
           ? <i className={ iconClass } style={ color ? { color } : undefined } />
           : <FaTimes style={ color ? { color } : undefined } />;
   ```
   Bubbles never call it with the null/X case (they omit the prefix); the
   picker uses it for every swatch including the X.

4. **`src/api/room/widgets/ChatBubbleMessage.ts`** — append two ctor fields:
   `public usernameIcon: string = null, public usernameIconColor: string = null`.

5. **`src/api/chat-history/IChatEntry.ts`** — add
   `usernameIcon?: string; usernameIconColor?: string;`.

6. **`src/hooks/rooms/widgets/useChatWidget.ts`** — read `event.usernameIcon` /
   `event.usernameIconColor`; normalize icon color default the same way as
   username color (`'#000000'`/`''` → `null`); icon `''` → `null`. Pass both to
   `new ChatBubbleMessage(...)` and into the `addChatEntry({...})` object.

7. **Bubble prefix render** — in
   `src/components/room/widgets/chat/ChatWidgetMessageView.tsx` and
   `src/components/chat-history/ChatHistoryView.tsx`, before the username `<b>`,
   add (only when an icon is set):
   ```tsx
   { chat.usernameIcon &&
       <b className="username-icon mr-1">{ '[ ' }<span style={ chat.usernameIconColor ? { color: chat.usernameIconColor } : undefined }><i className={ chat.usernameIcon } /></span>{ ' ]' }</b> }
   ```
   (History uses `row.usernameIcon` / `row.usernameIconColor`.) Brackets sit in
   the black `<b>`; the icon span carries the color. Reuse the `.username`
   weight/spacing; add minimal `.username-icon` SCSS only if needed.

8. **`src/components/rp-settings/RpSettingsView.tsx`** — on the Username page,
   below the existing Color section, add an **Icon** section and an **Icon
   Color** section:
   - State: `usernameIcon`, `usernameIconColor`.
   - Apply from `RpUiSettingsEvent` (validate; fall back to defaults).
   - Icon grid: `USERNAME_ICONS.map` → swatch showing `<UsernameIconGlyph
     iconClass={entry.iconClass} />`, `is-selected` when
     `usernameIcon === (entry.iconClass ?? '')`, `onClick` →
     `selectUsernameIcon(entry.iconClass ?? '')`.
   - Icon Color grid: `USERNAME_COLORS.map` (same as the Color grid),
     `selectUsernameIconColor`.
   - Extend the unified `saveSettings(...)` to carry all six values (chrome
     color, opacity, header, username color, icon, icon color); every
     `select*` passes the current values. Black/none → send `''`.

### B. Renderer — nitro-react yarn patch

Append at the **end** of each packet, both sides (the wire-order rule):

1. **`RoomUnitChatParser`** — after `usernameColor`, read
   `this._icon = wrapper.readString();` and
   `this._iconColor = wrapper.readString();` (+ fields, flush `''`, getters).
2. **`RoomSessionChatEvent`** — add `icon`/`iconColor` ctor params (default
   `''`, appended last) + getters.
3. **`RoomChatHandler.onRoomUnitChatEvent`** — pass `parser.icon`,
   `parser.iconColor` into `new RoomSessionChatEvent(...)`.
4. **`RpUiSettingsParser`** — after `usernameColor`, read `icon` then
   `iconColor` (+ fields, flush, getters).
5. **`RpSaveUiSettingsComposer`** — ctor takes `icon`, `iconColor` as the 5th/6th
   args, stored last in `_data`.

### C. Emulator — PlusEMU (`emulator/`)

1. **`HabboHotel/Users/Habbo.cs`** — add `RpUiUsernameIcon` (string) and
   `RpUiUsernameIconColor` (string); load both in `EnsureRpUiSettingsLoaded`
   (extend the SELECT) and save in `SaveRpUiSettings` (extend the REPLACE).
2. **`RpSaveUiSettingsEvent`** — read `icon` + `iconColor`; validate:
   `iconColor` against the existing hex regex (allow `''`); `icon` against a
   strict allowlist regex `^$|^[a-z0-9][a-z0-9 -]{0,39}$` (empty, or fa-style
   classes only — blocks injection). Assign both before `SaveRpUiSettings()`.
3. **`RpUiSettingsComposer`** — 5th/6th ctor args `icon`, `iconColor`, written
   last; update the login send site in `SSOTicketEvent.cs`.
4. **Chat composers** (`ChatComposer`, `ShoutComposer`, `WhisperComposer`) —
   add trailing `string icon = ""`, `string iconColor = ""` params, written
   after the existing `_usernameColor`. Defaults keep all non-user call sites
   (pets/bots/wired) compiling and emitting empties.
5. **`RoomUser.OnChat`** — capture `icon`/`iconColor` from
   `GetClient().GetHabbo()` alongside `usernameColor`; pass to the four
   speaker-side composers.
6. **`WhisperEvent.Parse`** — capture the whisperer's `icon`/`iconColor`; pass
   to the four `WhisperComposer` calls.

### D. Data / deploy

New tracked migration (auto-applied by the deploy — see
[[pixelrp-nongit-deploy-items]]):
`emulator/Resources/SQLs/Updates/25_AddUsernameIcon.sql`:

```sql
ALTER TABLE `user_ui_settings`
  ADD COLUMN `username_icon` VARCHAR(64) NOT NULL DEFAULT '' AFTER `username_color`,
  ADD COLUMN `username_icon_color` VARCHAR(7) NOT NULL DEFAULT '' AFTER `username_icon`;
```

On beta the column was NOT applied out-of-band this time, so no manual
`_applied_sql_updates` insert is needed — the deploy applies `25_…` normally.

## Discovery (icon list)

The kit is domain-locked to the hotel, so enumerate on beta (or local dev if
the kit permits localhost):

1. Ship the `index.html` kit embed to beta.
2. Load the client, and in the console query the loaded custom icons — e.g.
   `Object.keys(window.FontAwesome?.library?.definitions ?? {})` and the
   kit's custom-icon families (`fa-kit`), plus DOM-probe a known class.
3. Populate `USERNAME_ICONS` with the discovered classes (each typically
   `fa-kit fa-kit-<name>` or `fa-kit-<name>`).

If the FA API won't cleanly enumerate the custom set, fall back to the
class names from the kit dashboard (ask the user to paste). Architecture is
unaffected either way.

## Wire-format safety

- Chat packet: `icon`, `iconColor` appended after `usernameColor`, read in the
  same order in `RoomUnitChatParser`; server always writes defined strings
  (default `""`).
- UI-settings packets: `icon`, `iconColor` appended last in
  `RpUiSettingsComposer` / `RpSaveUiSettingsComposer` and read last in
  `RpUiSettingsParser`.
- No `*PacketHeader` changes — field additions only.
- **Deploy coupling:** client and emulator ship together on beta; a stale
  cached client against the new emulator would misread the extra chat fields
  (same inherent risk as the username-color rollout). Beta is staff-only/low
  traffic.

## FontAwesome-in-React watch-out

The kit swaps `<i>`→SVG via a MutationObserver. Chat bubbles mount/unmount
constantly. Verify freshly-spawned bubbles get their icon swapped (they should:
the observer catches added nodes). If a bubble ever shows a bare `<i>` box,
the fallback is FA's explicit API (`window.FontAwesome.dom.i2svg({ node })`)
called in a bubble `useEffect`. Prefer the automatic path; only add the manual
nudge if verification shows a gap.

## Testing / verification

Manual in-game (no screenshot-driving the client):

1. Build renderer patch → client → emulator; deploy to beta (migration
   auto-applies).
2. Settings → Social → Username shows Color, **Icon**, **Icon Color**; Icon
   defaults to the X (none), Icon Color to black.
3. Pick a custom icon → own bubble shows `[ <icon> ] Name:`; a second account
   sees the same; it shows in chat history; relog persists it.
4. Pick a color for the icon → only the icon recolors; brackets stay black.
5. Select the X → the prefix disappears everywhere.
6. Bot/pet chat is unaffected (no prefix).

## CHANGELOG

Player-facing entry: choose an icon (and its color) to appear before your name
in chat, under Settings → Social → Username.
