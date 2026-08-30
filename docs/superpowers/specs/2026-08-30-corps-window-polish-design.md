# Corporations Window Polish — Design

**Date:** 2026-08-30 · **Scope:** client only (`rp-corporations`) · **Branch:** beta

## Problem

The Corporations window works but reads as an unstyled wireframe: a plain
14px title, gray-on-gray rank bars that look like disabled buttons, a
hardcoded mustard pay color, color-only presence signaling with no legend,
a slide-out panel that collapses the roster from three columns to one, and
no motion beyond a 0.1s border transition. The corp's badge — its identity —
never appears larger than 40px in the rail.

## Design (approved)

No packet or emulator changes. All work lands in
`RpCorporationsView.tsx` / `RpCorporationsView.scss`.

### Frame

- Window grows from 520x440 to 640x480. Same `primary-slim` NitroCard,
  light surface.
- Roster stays three cards per row; the extra width brings each card to
  ~175px so names stop truncating.

### Identity header (signature element)

Replaces the plain title row at the top of the content area:

- **Left:** corp badge at native 40px (never scaled) on a soft plate tinted
  with the player's chrome color —
  `color-mix(in srgb, var(--prp-chrome-solid) 12%, transparent)` fill,
  hairline chrome-mixed border, 6px radius.
- **Middle:** corp name at 16px weight 700; description beneath at muted
  11px, clamped to 2 lines with ellipsis.
- **Right:** stat chips — `Employees n`, `On duty n`, `Stock n`. White
  chips, hairline border, bold value. On-duty count is computed client-side
  by summing `employee.onDuty` across ranks (no new server data).
- Switching corps fades the header + roster content in over ~120ms.

### Rank ladder

- Rank headers stop being filled bars: transparent background, 10px
  uppercase letter-spaced rank name (same microcopy style as the existing
  panel titles), thin hairline rule.
- Pay becomes a coin chip: small pill, coin-gold text on a warm faint
  fill, muted `/ 10 min` suffix. Replaces the bare `#8a6d1d` text.
- The highest rank's header carries a subtle chrome-tinted accent (a short
  3px left border on the rank name) so seniority reads at a glance.
- Ranks with zero employees render a single muted "No employees" line
  instead of a bare header-only bar.

### Employee cards

- Three per row, ~175px each. Portrait crop/tint mechanics unchanged
  (native-size sprite, pixelated, circular mask; gray offline / green
  online / blue on-duty).
- Hover: `translateY(-1px)`, soft shadow, border darken, 0.12s ease.
  Active press state.
- A 7px status dot pinned to the card's top-right corner matches the
  portrait tint (colorblind-safe second signal).
- Card `title` gains the status word (e.g. "Rank II - On duty"). Plain
  hyphen only — no em-dashes in client strings (Habbo font renders them as
  a music note).
- The `Wk 0 / Total 0` stat line stays, still governed by the panel
  toggles, until the server sends real shift stats.

### Presence legend

- One compact right-aligned line between header and ladder: three
  dot+label pairs (Offline / Online / On duty) at 9px muted.
- Presence colors promoted to shared SCSS variables used by the portrait
  tints, the status dots, and the legend, so they cannot drift.

### Details panel → overlay settings drawer

- The rail's slider button remains the toggle.
- The panel becomes an overlay: absolutely positioned over the roster's
  left edge (below the header, beside the rail), white surface, hairline
  border, soft shadow, 0.16s slide+fade. The three-column roster never
  reflows.
- Contents: only the "Show on cards" toggles (checkboxes restyled to
  match the window), leaving room for future corp settings. The
  Employees/Stock figures move to the header chips.
- Dismissed by re-clicking the tool button or clicking the roster.

### States

- Loading: lightweight skeleton — one rank bar ghost with three shimmering
  card ghosts — instead of the bare "Loading..." string.
- No corporations: centered empty state with the default NPH17 badge and
  one line of copy.

## Out of scope

- New server data (shift stats, rank management, corp actions).
- Dark mode (the window family is light-surface).
- Rail interaction model and the profile click-through (unchanged).

## Files

- `client/src/components/rp-corporations/RpCorporationsView.tsx`
- `client/src/components/rp-corporations/RpCorporationsView.scss`
- `CHANGELOG.md`

## Verification

Client build passes; user tests in-game on beta (per manual-testing
preference).
