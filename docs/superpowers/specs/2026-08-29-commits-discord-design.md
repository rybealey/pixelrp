# Commits → Discord — Design

**Date:** 2026-08-29 · **Scope:** repo root (workflow + script) · **Branch:** beta

## Problem

Every commit pushed to `beta` should land in the staff-only #commits
channel (id 1543234642537222345) with its full message, so staff can
follow development without watching GitHub.

## Design (approved)

**Trigger.** `.github/workflows/commits-discord.yml` runs on every push
to `beta` (no path filter), plus `workflow_dispatch` with before/after
overrides for manual test posts. Posts via a per-channel webhook in
`DISCORD_WEBHOOK_COMMITS` (created in #commits by the Trina bot's token;
least privilege, same pattern as the changelog webhooks). If the secret
is unset the run logs a notice and exits 0.

**Extraction.** `scripts/commits-to-discord.mjs` (Node 20, no deps)
lists `before..after` oldest-first with `git rev-list --reverse` and
reads each commit's author, date, and full message. A zero/unknown
`before` (first push, force push) falls back to just the head commit.

**Formatting.** One embed per commit: title = subject line, linked to
the commit on GitHub; description = full body; author = commit author;
footer = `beta · <short sha>`; timestamp = author date; color blurple.
Limits handled: title 256 / description 4000 with `…` truncation, at
most 25 commits per push (a final embed links the GitHub compare view
with the leftover count), webhook POSTs chunked at 10 embeds, single
retry on HTTP 429.

**Not in scope.** `main` pushes post nothing (a beta→main merge would
only re-post commits staff already saw). CHANGELOG.md untouched — a
staff-only feed has no player-noticeable effect.

**Testing.** `--dry-run` prints the payload instead of posting;
verified locally against real ranges from this repo before shipping.

## Files

- `.github/workflows/commits-discord.yml`
- `scripts/commits-to-discord.mjs`

## Rollout

1. Create the #commits webhook with the bot token (VPS cms/.env) and
   store it as repo secret `DISCORD_WEBHOOK_COMMITS`.
2. Ship to beta — the shipping push itself is the live test post.
