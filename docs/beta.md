# Beta hotel — beta.pixelrp.co

A full second hotel on the same VPS: its own checkout (`/opt/pixelrp-beta`,
branch `beta`), its own compose project (`-p pixelrp-beta`), its own database
and volumes. Staff-only (rank ≥ 5, enforced at SSO login via
`STAFF_ONLY_LOGIN=1`). The live hotel is never touched.

| | prod | beta |
|---|---|---|
| checkout | `/opt/pixelrp` (main) | `/opt/pixelrp-beta` (beta) |
| compose | `-f compose.yaml -f compose.prod.yaml` | same + `-f compose.beta.yaml`, `-p pixelrp-beta` |
| site | pixelrp.co → 127.0.0.1:8080 | beta.pixelrp.co → 127.0.0.1:8081 |
| game socket | :2096 → 127.0.0.1:12096 | :2096 (SNI) → 127.0.0.1:12097 |
| network | 172.28.0.0/16 | 172.29.0.0/16 |
| deploys | `gh workflow run deploy.yml` (manual) | push to `beta` branch (automatic) |

## Workflow

1. Branch work off `main` (parent repo) / `pixelrp` (submodules) as usual.
2. Point the parent `beta` branch at the submodule commits to test, push —
   `deploy-beta.yml` builds and deploys automatically.
3. Test at beta.pixelrp.co with a staff account.
4. Merge to `main` / fast-forward submodule branches, run the normal prod
   deploy.

To refresh beta's data from prod (accounts, rooms, catalog — run on the VPS):

    bash /opt/pixelrp-beta/docker/beta/refresh-from-prod.sh          # DB only
    bash /opt/pixelrp-beta/docker/beta/refresh-from-prod.sh --assets # DB + game assets

## One-time VPS setup

DNS first: add an A record `beta` → the VPS IP in Cloudflare (proxied, like
the apex). The origin cert already covers `*.pixelrp.co`.

```bash
# 1. Checkout on the beta branch (deploy key already trusts the repo)
git clone git@github.com:rybealey/pixelrp.git /opt/pixelrp-beta
cd /opt/pixelrp-beta
git checkout beta
git submodule update --init emulator cms

# 2. Environment files (same secrets as prod; compose overlay changes the rest)
cp /opt/pixelrp/.env /opt/pixelrp-beta/.env
cp /opt/pixelrp/cms/.env /opt/pixelrp-beta/cms/.env
# php-fpm runs as www-data - a root-umask 600 copy reads as "no .env" to
# Laravel (MissingAppKeyException on every page).
chmod 644 /opt/pixelrp-beta/cms/.env

# 3. Game assets + client configs from prod
rsync -a /opt/pixelrp/nitro/ /opt/pixelrp-beta/nitro/
# Point the VPS-only client configs at the beta hostname:
sed -i 's#//pixelrp\.co#//beta.pixelrp.co#g; s#//ws\.pixelrp\.co#//beta.pixelrp.co#g; s#//www\.pixelrp\.co#//beta.pixelrp.co#g' \
  /opt/pixelrp-beta/nitro/client/ui-config.json /opt/pixelrp-beta/nitro/client/renderer-config.json
grep -o 'wss://[^"]*' /opt/pixelrp-beta/nitro/client/ui-config.json   # sanity: should say beta.pixelrp.co:2096

# 4. Host nginx vhost
cp /opt/pixelrp-beta/docker/host/pixelrp-beta.nginx.conf /etc/nginx/sites-enabled/pixelrp-beta
nginx -t && systemctl reload nginx

# 5. First start + clone prod's data into it
cd /opt/pixelrp-beta
docker compose -p pixelrp-beta -f compose.yaml -f compose.prod.yaml -f compose.beta.yaml up -d db
sleep 20   # let MySQL initialise
bash docker/beta/refresh-from-prod.sh
```

Then push anything to the `beta` branch (or run the "Deploy Beta" workflow
manually) to build and start the full stack.

## Gotchas

- **Always `-p pixelrp-beta`.** Without the project flag, compose commands run
  from `/opt/pixelrp-beta` would attach to the prod project's volumes.
- Beta's `nitro/client/ui-config.json` / `renderer-config.json` are VPS-only,
  exactly like prod's — the deploy rsync excludes them.
- The Claude bot is disabled in beta (`profiles: ["disabled"]`).
- `STAFF_ONLY_LOGIN` rejects rank < 5 at SSO — non-staff see the standard
  "Handshake Failed".
- The refresh script wipes beta's database. Anything created only in beta is
  lost on refresh — that is the point.
- A fresh beta db container spends minutes seeding before MySQL listens on
  TCP; the refresh script waits for the container healthcheck before touching
  the schema (dropping mid-init corrupts the data dictionary, MySQL 3681).
