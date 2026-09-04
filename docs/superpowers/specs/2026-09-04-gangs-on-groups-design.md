# Gangs on Groups — Design

**Date:** 2026-09-04 · **Scope:** client (this slice), emulator + renderer patch (next slices) · **Branch:** beta
**Status:** PROPOSED — slice 1 (create window UI) shipped; server slices need approval.

## Problem

The side drawer's Gangs button is a placeholder. Players who are not in a
gang (or don't own one) need a Create Gang flow: pick a name and two gang
colors, pay, done. Down the line gangs get turfs, and the group furniture
placed on a turf must render in the gang's colors.

## Core decision: a gang IS a Habbo group

Gangs repurpose the stock group system rather than growing a parallel one:

- **Colors → turf furni for free.** Group furniture already tints from the
  group's `colorA`/`colorB`. The two colors chosen at gang creation are
  exactly those columns, so turf furni inherits gang colors with zero new
  rendering work — client, emulator, and imager all already understand it.
- **Membership, badges, and rosters exist.** `group_memberships`,
  badge rendering, member lists, admin/ownership — all stock tables and
  packets. Gang features layer on top instead of re-implementing them.
- **One flag distinguishes them.** `groups ADD COLUMN is_gang tinyint(1)`
  (migration). Gangs are hidden from the normal Groups UI/catalog surface,
  and groups are hidden from gang surfaces, by filtering on the flag.

## Create flow (reference: the habrp.com Gang window)

One compact "Gang" NitroCard, not the 4-step group wizard:

1. Identity band across the top previewing the two selected colors.
2. Badge well + "Enter gang name..." input.
3. `EDITING: PRIMARY | SECONDARY` chip toggle; a swatch grid below edits
   whichever is active. The palettes are the stock `GroupBadgePartsEvent`
   `colorsA`/`colorsB` lists (ids, not hexes, are what the emulator stores).
4. `[cost] [Create Gang]` — one control: cost tab + green button.

### Differences from stock group purchase (server slice)

| stock groups | gangs |
|---|---|
| 10 credits | 500 RP cash (`server_settings` key `gang.cost`, default 500) |
| requires owning a room (homeroom) | no room required; homeroom nullable, later set to the turf HQ |
| buyable by anyone with HC | one gang per player (owner or member); rank/level gates TBD |
| badge from the 5-part editor | slice 1 sends a default badge (first base, first part color); a gang badge editor is a later slice |

## Packets (renderer patch + emulator, slice 2)

Following the corp pattern (`RpCorpsEvent` / `RpUserCorpEvent`):

- `RpGetUserGangComposer` → `RpUserGangEvent { gangId, name, colorA, colorB, badge, rank, isOwner }`
  (gangId 0 = not in a gang). Client gates the window: no gang → Create
  view (slice 1); in a gang → gang view (roster, leave, manage — slice 3).
- `RpBuyGangComposer { name, colorA, colorB }` → validates uniqueness of
  name, one-gang-per-player, charges RP cash, inserts the `is_gang` group,
  auto-joins the buyer as owner. Slice 1 temporarily sends the stock
  `GroupBuyComposer` (roomless, so a stock server refuses it harmlessly);
  swap the composer when this lands.

## Slices

1. **Create window (client)** — SHIPPED with this spec: `RpGangsView` on
   `rp-gangs/*` link events, drawer button wired, palettes + cost from the
   stock group packets, always shows Create (nobody has a gang yet).
2. **Server purchase + membership gate** — migration, the two packet pairs
   above, window gates on `RpUserGangEvent`, cost tab switches to RP cash.
3. **Gang view + management** — roster, disband/leave, badge editor.
4. **Turfs** — HQ room as group homeroom, group furni in gang colors, turf
   capture mechanics (own spec when we get there).

## Open questions (for slice 2 approval)

- Which currency is "RP cash" for the charge — `activity_points` type, or
  the corp-wage balance? (The reference art shows the green cash icon.)
- Can a player be in a gang AND a corporation simultaneously? (Assumed yes.)
- Gang name rules: profanity/wordfilter reuse from group names? Length cap
  29 matches groups for now.
