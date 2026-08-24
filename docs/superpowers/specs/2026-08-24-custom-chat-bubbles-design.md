# Custom Chat Bubbles — Phase 1 (Testing) Design

**Date:** 2026-08-24
**Branch:** `chat-bubbles` (off `beta`)
**Status:** Approved

## Goal

Prove the custom chat-bubble art pipeline end-to-end: generate custom bubble art
with ChatGPT image generation, convert it to the 9-slice PNG format the Nitro
client consumes, render it in-game as a selectable staff-gated style, and
confirm the server enforces the gate.

This is the testing phase of a larger plan. The long-term direction (approved
as "approach A", deferred):

- Per-user ownership (`user_chat_styles` table), redeemable items that consume
  on use and permanently unlock a style (mirroring `UseSellableClothingEvent`),
  a custom composer pushing usable style ids to the client, and locking regular
  players to the default bubble (style 0) with stock styles repurposed for the
  RP system (server-forced via the existing `CustomBubbleId` path), unlockables,
  or staff.

None of that is built in this phase.

## Scope

**In scope:**

- One custom PixelRP bubble style, **id 40** (first custom style; also serves
  as the pipeline test).
- ChatGPT image-generation prompt spec for bubble art, including a first
  visual concept (PixelRP-themed, consistent with the chrome color system).
- Conversion script: oversized generated art → native-resolution 9-slice
  body PNG + pointer PNG + the `border-image-slice` numbers for the CSS.
- Client wiring: assets, SCSS block, `chat.styles` config entry (staff-gated).
- Server data: one `room_chat_styles` row with a staff `required_right`.

**Out of scope (phase A):** ownership table, redeemable items, custom packets,
player lockdown to bubble 0, revocation tooling.

## How the existing system works (verified)

- **Rendering:** bubbles are DOM/CSS. `ChatWidgetMessageView` renders
  `.chat-bubble.bubble-{styleId}`; each style is a block in
  `client/src/components/room/widgets/chat/ChatWidgetView.scss` using CSS
  `border-image` over a tiny PNG (~50×25) plus a separate pointer PNG (~9×6),
  from `client/src/assets/images/chat/chatbubbles/`. Stock ids run 0–38.
- **Selector:** `ChatInputView.tsx` builds the pickable list client-side from
  the `chat.styles` config array (`styleId`, `minRank`, `isSystemStyle`,
  `isHcOnly`, `isAmbassadorOnly`). `minRank` is checked via
  `GetSessionDataManager().hasSecurity(...)`. Config lives in the git-tracked
  `nitro/ui-config.json` / `ui-config.prod.json` (and the served copy under
  `nitro/client/`).
- **Server validation:** Plus emulator's `ChatEvent` (and shout/whisper
  equivalents) resolves the style id via `ChatStyleManager` against the
  `room_chat_styles` table (`id`, `name`, `required_right`); unknown ids or
  missing rights fall back to style 0. RP-forced bubbles already work via
  `Habbo.CustomBubbleId`.

## Design

### Style id allocation

Custom styles start at **40** (39 left as a buffer against upstream Nitro
additions). Ids are permanent and carry into phase A.

### Art pipeline

1. **Prompt spec (deliverable):** a ChatGPT prompt requesting oversized art
   (~16× native, e.g. ~800×400 for the body) on a transparent background,
   with explicit geometry constraints: uniform corner regions sized for
   9-slicing, a horizontally-tileable top/bottom edge, a vertically-tileable
   left/right edge, a flat interior fill region, and a separate pointer
   (tail) sprite. Includes one concrete first concept.
2. **User generates** the image(s) and drops them into the repo (location
   given in the plan).
3. **Conversion script (deliverable):** Python script in the client repo
   tooling that downscales to native resolution (nearest-neighbor — never
   resample pixel art smoothly), hardens semi-transparent alpha, crops and
   emits `bubble_40.png` + `bubble_40_pointer.png`, and prints the
   `border-image-slice` / `-width` / `-outset` values to paste into the SCSS.

### Client changes

- `client/src/assets/images/chat/chatbubbles/bubble_40.png` and
  `bubble_40_pointer.png`.
- `&.bubble-40 { ... }` block in `ChatWidgetView.scss`, mirroring the stock
  pattern (both the in-room bubble section and the selector-preview section —
  the file defines each style twice).
- `chat.styles` config entry `{ "styleId": 40, "minRank": 5,
  "isSystemStyle": false, "isHcOnly": false, "isAmbassadorOnly": false }` in
  every tracked ui-config copy that carries the array.
- Client rebuild via the standard `build-client.sh` flow.

### Server changes (data-only, no code)

- `INSERT INTO room_chat_styles (id, name, required_right) VALUES (40,
  'pixelrp_custom_1', 'mod_tool');` — `mod_tool` is the right the seed data
  already uses to gate staff stock styles (ids 1–2) and matches the staff
  checks in `ChatEvent`.
- Applied manually to local dev and beta DBs (and prod at release). Never
  ships via git → gets a `CHANGELOG.md` entry per repo discipline.

### Error handling / failure modes

- Non-staff user injecting style 40 (e.g. G-Earth): server falls back to
  style 0. Verified as part of testing.
- Style rendered but row missing server-side: everyone else sees style 0 —
  the DB insert is part of the definition of done, not an afterthought.
- Client without rebuilt CSS receiving style 40: no `bubble-40` class match;
  bubble renders with base styles only. Acceptable during beta testing
  (week-long browser asset cache noted for rollout timing).

### Testing

- Local: build client, sign in as `ClaudeTest` (staff), select style 40,
  confirm the bubble and selector preview render correctly; confirm a
  non-staff account cannot use it (server downgrades to 0).
- Hand off to Ry for manual in-game testing on beta — no screenshot-driving
  the Nitro client.

## Success criteria

1. Style 40 appears in the selector for staff only.
2. In-room bubble renders the custom art correctly at all message widths
   (1 word → full 100-char message) including the pointer.
3. Non-staff attempts to use style 40 are downgraded to 0 by the server.
4. The prompt spec + conversion script produce usable assets without manual
   pixel editing, so more styles can be added by repeating the loop.
