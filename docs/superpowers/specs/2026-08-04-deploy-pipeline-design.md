# Deploy Pipeline: push to main → Vultr VPS — Design

**Date:** 2026-08-04
**Status:** Approved
**Scope:** Continuous deployment of the pixelrp stack to a single Vultr VPS on every push to `main`. Hardening of the public host (TLS, reverse proxy, firewall) is explicitly the operator's responsibility and is NOT built here — but the code changes required to make a public deployment *possible* are.

## Goal

A push to `main` updates the running stack on the VPS with no manual steps, and can never destroy the database. Assets are synced separately and deliberately.

## The constraint that shapes the design

Git carries **816 KB** of this project (32 files). The runtime additionally needs ~570 MB that is deliberately gitignored:

| Path | Size | Origin |
|---|---|---|
| `artifacts/nitro-assets` | 546 M | converted bundles, icons, gamedata |
| `artifacts/arcturus` | 20 M | emulator jar + websocket plugin |
| `artifacts/sql` | 2.4 M | base schema + migrations |
| `cms/src` | 131 M | cloned by `make up` on the server |
| `data/` | — | server-local state; must never be deployed |

Therefore: **push-to-main ships code and config only.** Assets travel over a separate, explicit channel (`make sync-assets`), because they change only when the operator re-converts.

## Blocking code change: client-facing URLs

`docker-compose.yml` currently hardcodes `localhost` into URLs that are handed to the **visitor's browser**:

```
NITRO_WS_URL: "ws://localhost:${WS_PORT}"
NITRO_ASSET_URL: "http://localhost:${NITRO_PORT}/game-assets"
NITRO_CMS_URL / APP_URL: "http://localhost:${CMS_PORT}"
```

Deployed unchanged, the pipeline would report success while every visitor's browser tried to reach its own machine. The stack would be silently, totally broken.

**Fix:** introduce `PUBLIC_SCHEME` (default `http`), `PUBLIC_HOST` (default `localhost`), and optional `PUBLIC_WS_URL` / `PUBLIC_CMS_URL` overrides for setups where TLS terminates at a proxy on standard ports. All client-facing URLs derive from these. Defaults preserve current local behaviour exactly.

## Architecture

```
push to main
   │
   ├─ GitHub Actions (ubuntu-latest)
   │    1. checkout
   │    2. rsync tracked files → DEPLOY_HOST:/opt/pixelrp
   │       (--delete scoped to code paths; never data/, .env, artifacts/)
   │    3. ssh → /opt/pixelrp/scripts/deploy.sh
   │
   └─ scripts/deploy.sh  (on the VPS; also runnable by hand)
        1. preflight: .env present? artifacts present? → else abort naming the fix
        2. docker compose up -d --build
        3. health gate: db healthy, cms 200, nitro 200, emulator "successfully loaded"
        4. non-zero exit on any failure, with the failing service's log tail
```

### Components

| File | Responsibility |
|---|---|
| `.github/workflows/deploy.yml` | trigger, secrets, rsync, invoke deploy script, surface failure |
| `scripts/deploy.sh` | server-side: preflight, compose up, health gate. Idempotent. |
| `scripts/sync-assets.sh` + `make sync-assets` | operator-initiated rsync of `artifacts/` |
| `docker-compose.yml` | consume `PUBLIC_*` for client-facing URLs |
| `.env.example` | document `PUBLIC_*` and deployment variables |
| `docs/DEPLOYMENT.md` | one-time server setup, secrets, rollback, public-hotel checklist |

## Data safety

Non-negotiable, mirroring the Phase 0 stance that only `make reset` destroys data:

- rsync **excludes** `data/`, `.env`, `artifacts/`, `cms/src`, `.git`
- `--delete` is scoped so it can never reach excluded paths
- the deploy script never runs `down -v`, never touches `data/`
- the database survives every deploy; a deploy is code-only

## Secrets

Operator-owned; never committed, never handled by tooling in this repo:

- GitHub repo secrets: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY` (private key of a deploy-only keypair), optional `DEPLOY_PORT`
- Server `.env`: authored once on the VPS. Distinct from local: real `PUBLIC_HOST`, `APP_DEBUG=false`, fresh DB passwords, fresh `APP_KEY`.

## Failure handling

| Situation | Behaviour |
|---|---|
| `.env` missing on server | abort before touching containers, print the exact remedy |
| `artifacts/` missing/empty | abort, point at `make sync-assets` |
| build fails | compose exits non-zero; workflow fails; previous containers keep running |
| health gate fails | workflow fails with the failing service's log tail |
| concurrent pushes | workflow concurrency group; newer run supersedes |

Rollback is `git revert` + push (the pipeline redeploys), or on the box: check out the previous SHA and re-run `deploy.sh`. Documented, not automated — with one server and a code-only deploy, an automated rollback path is more machinery than it earns.

## Out of scope (operator's responsibility, flagged in docs)

TLS/reverse proxy, firewall, `wss://` termination for port 2096, keeping the DB port off the public interface, backups, and monitoring. `docs/DEPLOYMENT.md` will carry a short checklist naming these so a green deploy is never mistaken for a hardened, publicly-working hotel.

## Acceptance criteria

1. A push to `main` updates the VPS with no manual step, and the workflow fails loudly if the stack does not come up healthy.
2. `PUBLIC_HOST`/`PUBLIC_SCHEME` unset locally reproduces today's behaviour byte-for-byte.
3. A deploy leaves `data/`, `.env`, and `artifacts/` untouched — verified by a registered account surviving a deploy.
4. `make sync-assets` transfers assets and is safe to re-run.
5. Missing `.env` or `artifacts/` aborts before any container action, naming the fix.
