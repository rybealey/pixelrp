# Changelog → Discord — Design

**Date:** 2026-08-29 · **Scope:** repo root (workflow + script) · **Branch:** beta

## Problem

CHANGELOG.md entries should reach Discord automatically: beta-branch
changes to #planned (features live on beta), main-branch changes to
#updates (patch notes for what shipped to the hotel).

## Design (approved)

**Trigger.** `.github/workflows/changelog-discord.yml` runs on push to
`beta` or `main` when `CHANGELOG.md` changed, plus `workflow_dispatch`
for manual test posts. Branch picks the destination secret:
`beta` → `DISCORD_WEBHOOK_PLANNED`, `main` → `DISCORD_WEBHOOK_UPDATES`.
Per-channel webhooks (least privilege); the user creates them in each
channel's Integrations settings and names them PixelRP. If the secret is
unset the run logs a notice and exits 0 (safe rollout).

**Extraction.** `scripts/changelog-to-discord.mjs` (Node 20, no deps)
diffs `CHANGELOG.md` between the push's before/after commits, maps added
line numbers onto the after-version of the file, groups file lines into
bullets (a `- ` line plus its indented continuations), and keeps bullets
with at least one added line — each attached to its `##` release title
and `###` section. Appending two bullets posts exactly those two; a
beta→main merge posts everything new since the last merge; edits repost
only the corrected bullet; deletions and bullet-free pushes post nothing.
`github.event.before` of all zeros falls back to `HEAD~1`.

**Formatting.** One Discord embed per release with new bullets, posted
oldest-first. Title = release name; color: brand orange (#updates) or
construction yellow (#planned); one field per section — ✨ Added /
🔁 Changed / 🛠️ Fixed / ⚠️ Known issues — bullets rendered as `•` lines
with bold leads preserved, wrapped lines joined. Footer: "Live on beta
now - <date>" (#planned) or "Now in the hotel - <date>" (#updates).
Limits handled: fields chunked at 1024 chars (continuation fields named
with a zero-width space), embeds split near 6000 chars / 25 fields, one
webhook POST per embed, single retry on HTTP 429.

**Testing.** `--dry-run` prints the payload instead of posting; verified
locally against real historical diffs from this repo before shipping.

## Files

- `.github/workflows/changelog-discord.yml`
- `scripts/changelog-to-discord.mjs`
- `CHANGELOG.md` (player-facing entry)

## Rollout

1. Ship to beta (workflow self-triggers, skips gracefully — no secrets).
2. User creates the two webhooks and adds both secrets.
3. Fire `workflow_dispatch` for a real test post into #planned.
