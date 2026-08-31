# Corp Acronyms + Two-Line Working Motto — Design

**Date:** 2026-08-31 · **Scope:** emulator + client CSS · **Branch:** beta

## Problem

Every corporation should carry an acronym (SFPD for the San Francisco
Police Department), and the working motto should use it, formatted on two
lines: `[WORKING] SFPD` over `Officer II`.

## Design (approved)

### Emulator

- Migration `49_CorporationAcronyms.sql`:
  `ALTER TABLE rp_corporations ADD COLUMN acronym varchar(12) NOT NULL
  DEFAULT '' AFTER name;` then `UPDATE rp_corporations SET acronym = 'SFPD'
  WHERE id = 1;`
- `ShiftManager.StartShift`: the job query also selects `c.acronym`; the
  working motto becomes
  `$"[WORKING] {label}\n{rankName}{tierSuffix}"` where `label` is the
  acronym, falling back to the full corp name when the acronym is `''`
  (never a blank motto). The middot separator is dropped - the newline
  replaces it. The on-duty whisper keeps the FULL corp name.

### Client

`white-space: pre-line` on the motto elements so the newline renders:
- the infostand user motto (InfoStandWidgetUserView's motto element -
  locate its class/selector and add the rule in the widget's SCSS),
- the RP profile motto (`.rp-profile-motto`),
- the player HUD motto IF PlayerHudWidgetView renders motto text
  (verify; skip if it doesn't).
Minor surfaces (stock profile container, messenger caches) degrade to a
space-joined single line - acceptable.

## Out of scope

Showing acronyms anywhere else (corps window etc.); acronym management
commands (set via DB when creating a corp).

## Files

- `emulator/Resources/SQLs/Updates/49_CorporationAcronyms.sql`
- `emulator/HabboHotel/Corporations/ShiftManager.cs`
- Client: infostand widget SCSS, `rp-profile/RpProfileView.scss`
  (+ player HUD SCSS if applicable)
- `CHANGELOG.md`

## Verification

Emulator docker build 0 errors; client `yarn build` green; user tests
in-game: motto shows `[WORKING] SFPD` with the rank on its own line on the
infostand and profile. Deploy `(bump client + emulator)`.
