# Corporations Employee Cards — Design

**Date:** 2026-08-29 · **Scope:** client only (`rp-corporations`) · **Branch:** beta

## Problem

The employee pills in the Corporations window are too small for what they
show: a blurry 24px head crop, name, tier numeral, and an 8px presence dot.
They should carry the player render properly and make room for upcoming
shift stats.

## Design (approved)

**Layout.** Employees render as mini HUD-style plates, two per row, inside
each rank section. The window grows from 460x400 to 520x440 so two ~200px
cards sit beside the badge rail.

**Card anatomy.**
- Left: 44px circular masked portrait using the Player HUD's crisp
  native-size crop (`background-size: auto`, `image-rendering: pixelated`,
  head + shoulders framing of the 90x130 sprite). Full figure render, not
  `headOnly`.
- Portrait background tint replaces the presence dot: muted gray offline,
  green online, blue on-duty.
- Right: bold name (ellipsis truncation), with a small tier chip ("II")
  beside it when `rank.tiers > 0`.
- Below the name: muted placeholder stat line `Wk 0 / Total 0` — hardcoded
  zeros until the server sends shift data (plain slash; no em-dashes or
  middots, Habbo font constraint).
- Clicking a card sets `RpProfileState` (name, figure, motto '', online)
  and fires `CreateLinkEvent('rp-profile/show')`, same as HUD portraits.

**Unchanged.** Badge rail, rank ladder ordering, pay chips, packets. No
emulator changes.

## Files

- `client/src/components/rp-corporations/RpCorporationsView.tsx`
- `client/src/components/rp-corporations/RpCorporationsView.scss`
- `CHANGELOG.md`

## Verification

Client build passes; user tests in-game on beta (per manual-testing
preference).
