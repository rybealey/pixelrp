# PixelRP Hotel — Design Spec

**Date:** 2026-08-06
**Status:** Approved by user

## Goal

Deploy a Habbo retro hotel: PlusEMU emulator (forked), Atom CMS adapted to PlusEMU, Nitro HTML5 client, all under Docker Compose. Local deployment first; the same stack ships later to a VPS running Docker. Standard hotel now; roleplay (RP) features come later as separate feature branches.

## Key decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| Emulator | Fork of [80O/PlusEMU](https://github.com/80O/PlusEMU) | User's choice; C# codebase suits future RP work. This fork natively speaks the Nitro WebSocket protocol (revision 1.6.6) — no proxy needed. Dormant upstream (Apr 2024, .NET 7), so we self-maintain. |
| Client | Nitro (HTML5/WebSocket), pinned to revision 1.6.6 | Browser-based; matches the emulator's supported revision. Flash is legacy. |
| CMS | [Atom CMS (ObjectRetros)](https://github.com/ObjectRetros/atomcms), adapted to PlusEMU | Only actively maintained modern CMS (Laravel 13, Filament housekeeping, themes, RCON). All maintained CMSes target Arcturus Morningstar's schema, so adaptation to PlusEMU is required regardless — Atom is the best base. Runner-up BrainCMS works with PlusEMU unmodified but is dead since 2020 and insecure. |
| Fork location | `rybealey/PlusEMU` (personal account) | Simplest; can transfer to an org later. |
| Local stack | Docker Compose from day one | Dev/prod parity with the future VPS. |

## Repository layout

- **`rybealey/PlusEMU`** — fork of 80O/PlusEMU. Changes (Dockerfile, config, future RP features) live on a `pixelrp` branch; `master` stays clean to track upstream.
- **`rybealey/pixelrp`** — main project repo (this repo). Contains:
  - Docker Compose stack
  - Adapted Atom CMS (forked/vendored from ObjectRetros/atomcms)
  - Nitro client config and converted assets
  - Database seed/migration scripts
  - Docs (including this spec)
  - Emulator fork included as a **git submodule**.

## Services (Docker Compose)

| Service | Image/build | Purpose |
| --- | --- | --- |
| `db` | MySQL 8 | Single database: PlusEMU schema plus Atom's own CMS tables alongside. |
| `emulator` | Custom Dockerfile (.NET 7 SDK build → runtime image) | Game server. Exposes Nitro WebSocket port; RCON port internal-only. |
| `cms` | PHP-FPM 8.x + Composer | Adapted Atom CMS (Laravel). |
| `web` | Nginx | Serves CMS, Nitro client bundle, and converted Habbo assets; reverse-proxies the WebSocket. |
| `assets` | Nitro converter tooling (build step, not a runtime service) | One-time conversion/download of furni, figure, and room assets for Nitro. |

Configuration is env-var driven — no hardcoded hosts — so the same Compose file deploys to the VPS with only a TLS reverse proxy (Caddy, or Nginx + certbot) added. Nitro requires `wss://` in production; TLS is a deploy-time concern the config accommodates now.

## Atom → PlusEMU adaptation (core engineering work)

Bounded to three areas:

1. **Database models** — repoint Atom's Eloquent models/queries (users, currencies, ranks/permissions, settings, SSO ticket column, news/articles) at PlusEMU's schema. Atom's own non-game tables (CMS content, themes) stay as its migrations create them, in the same database.
2. **Registration/login/SSO** — Atom creates users PlusEMU accepts and mints SSO tickets into the column PlusEMU reads when the Nitro client connects.
3. **RCON** — rewrite Atom's RCON client to speak PlusEMU's RCON protocol (CMS→emulator calls like refreshing credits or disconnecting a user). Commands with no PlusEMU equivalent degrade gracefully (DB write, takes effect on next relog).

## Nitro client pairing

Nitro client build pinned to the emulator's revision (1.6.6). The CMS hosts Nitro in its client page and passes the SSO ticket. Assets are converted once with the standard Nitro converter tooling and served statically by Nginx.

## Error handling & testing

- **End-to-end acceptance test:** `docker compose up` → register on CMS → click "enter hotel" → Nitro loads → land in a room.
- Logs surfaced via `docker compose logs`; healthchecks on `db` and `emulator` so the CMS fails loudly rather than mysteriously.
- Targeted tests on the adaptation seams: SSO ticket round-trip; registration writes a PlusEMU-valid user row.

## Out of scope (this phase)

- RP features (future feature branches on the emulator fork)
- Executing the VPS deployment (designed-for only)
- Custom theming beyond Atom defaults
- Email and payment integrations
