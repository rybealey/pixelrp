# Deploying to a VPS

Push to `main` → GitHub Actions syncs the code → the server rebuilds and
health-checks itself. Assets are sent separately with `make sync-assets`.

**A deploy is code-only.** `data/` (database, uploads, emulator config),
`.env`, and `artifacts/` on the server are never written or deleted by a
deploy, and a database dump is taken before every one.

Deploys queue rather than cancel each other: if you push twice in a row, the
second run waits for the first to finish instead of interrupting it. A deploy
that looks "stuck" in the Actions tab is not blocking you forever — it will
run, and yours will follow.

## The one rule that will save you an afternoon

**On the server, only `data/`, `.env`, `artifacts/`, and `cms/src/` are safe
to hand-edit.** Every other path is wiped and replaced on every deploy —
the sync step runs `rsync --delete`, so a file dropped anywhere else
(a stray script in the repo root, a manual tweak to `docker-compose.yml`,
a config file you meant to keep) is silently deleted the next time anyone
pushes to `main`. If you need to change something server-side permanently,
change it in the repo and let the deploy carry it — don't edit it in place.

## One-time server setup

1. **Provision.** 2 vCPU / 4 GB RAM / 80+ GB NVMe recommended. The RAM
   requirement is driven by Docker **builds**, not by player count — the
   Vite build inside `docker compose up -d --build` needs real headroom, and
   under-provisioning here causes deploys (not gameplay) to fail or OOM.
   Install Docker Engine + the compose plugin, `git`, `make`, `rsync`, `curl`.

2. **Create a deploy keypair** on your workstation (no passphrase — CI cannot
   type one):

       ssh-keygen -t ed25519 -f ~/.ssh/pixelrp_deploy -C "pixelrp deploy" -N ""
       ssh-copy-id -i ~/.ssh/pixelrp_deploy.pub USER@SERVER

3. **Add GitHub repo secrets** (Settings → Secrets and variables → Actions):

   | Secret | Value |
   |---|---|
   | `DEPLOY_HOST` | server hostname or IP |
   | `DEPLOY_USER` | ssh user |
   | `DEPLOY_SSH_KEY` | contents of `~/.ssh/pixelrp_deploy` (the PRIVATE key) |
   | `DEPLOY_HOST_KEY` | optional — pins the server's SSH host key (see below) |
   | `DEPLOY_PORT` | optional, defaults to 22 |
   | `DEPLOY_PATH` | optional, defaults to `/opt/pixelrp` |

   `DEPLOY_HOST_KEY` is optional but recommended for any server reachable on
   the public internet. If it is unset, the workflow falls back to
   trust-on-first-use: it accepts whatever host key the server presents on
   that run, which is not verified against previous runs and gives no
   protection against a man-in-the-middle on that connection. To pin it,
   fetch the key from your own trusted connection to the box and use its
   output as the secret's value:

       ssh-keyscan -H <host>

   Paste the full output of that command as the `DEPLOY_HOST_KEY` secret.

4. **Prepare the directory** on the server:

       sudo mkdir -p /opt/pixelrp && sudo chown "$USER" /opt/pixelrp

5. **Author the server `.env`.** It is never deployed — the server keeps its
   own. Copy `.env.example` there and set, at minimum:

       PUBLIC_HOST=your-domain.example     # NOT localhost
       PUBLIC_SCHEME=https                 # if you terminate TLS
       PUBLIC_WS_SCHEME=wss                # must match the page's scheme
       APP_DEBUG=false                     # true leaks stack traces publicly
       # fresh DB_ROOT_PASSWORD / DB_PASSWORD / APP_KEY — not your local ones

6. **Send the assets** from your workstation (set `DEPLOY_*` in your local
   `.env` first):

       make sync-assets

7. **First deploy:** push to `main`, or run the workflow by hand from the
   Actions tab (`workflow_dispatch`).

## Everyday use

| You want to | Do this |
|---|---|
| Ship code/config | push to `main` |
| Ship new game assets | `make sync-assets`, then restart nitro on the server |
| Redeploy without a code change | Actions tab → Deploy to VPS → Run workflow |
| Deploy by hand from the box | `cd /opt/pixelrp && bash scripts/deploy.sh` |

## Restoring a database backup

Every deploy leaves a dump in `data/backups/` (the newest `BACKUP_KEEP`,
default 10, are kept). Restore is manual on purpose — an automatic restore
over a live database is more dangerous than the failure it guards against.

```bash
cd /opt/pixelrp
set -a; . ./.env; set +a                  # load DB_ROOT_PASSWORD, DB_DATABASE
docker compose stop emulator cms          # stop writers; leave db running
gunzip -c data/backups/pixelrp-<STAMP>.sql.gz \
  | docker compose exec -T -e MYSQL_PWD="$DB_ROOT_PASSWORD" db mariadb -uroot \
      "${DB_DATABASE:-arcturus}"
docker compose start cms emulator
```

The password goes via `MYSQL_PWD` in the container's exec environment, not on
argv — the same reason `scripts/deploy.sh` does it that way for the backup:
an argv password is visible to any `ps`/`docker top` for the life of the
command.

This is a deploy-time safety net, **not a backup strategy**: it lives on the
same disk and only runs when you deploy. Schedule off-box backups separately.

## Before you let real players in

This repo was built for local development. The pipeline deploys it faithfully
— it does not harden it. These are yours to do, and a green deploy does not
imply any of them:

- [ ] **Ports are bound to `127.0.0.1`.** Nothing is publicly reachable until
      you front it with a reverse proxy. That is intentional — decide what to
      expose rather than exposing everything.
- [ ] **TLS.** If the site is `https://`, the websocket must be `wss://`, which
      means the proxy has to terminate TLS for the emulator port too. A plain
      `ws://` from an `https://` page is blocked by browsers.
- [ ] **Keep the database port off the public interface.**
- [ ] **`APP_DEBUG=false`** in the server `.env`.
- [ ] **Firewall** — allow only what the hotel needs.
- [ ] **Off-box backups** and monitoring.
- [ ] **Pin `DEPLOY_HOST_KEY`** so CI verifies the server's identity instead
      of trusting it on first use every run.
