# PixelRP

A Habbo retro hotel: [PlusEMU](https://github.com/rybealey/PlusEMU) (C#/.NET 7
emulator, Nitro-native fork) + [Atom CMS](https://github.com/rybealey/atomcms)
(Laravel 13, adapted to PlusEMU via its `plus` emulator driver) + the Nitro
HTML5 client, all under Docker Compose. Standard hotel today; roleplay features
come later as feature branches on the emulator fork.

## Architecture

| Service | Image | Purpose | Address |
| --- | --- | --- | --- |
| `db` | mysql:8.0 | Shared DB: PlusEMU schema + CMS tables | 172.28.0.10 (dev host port 3306) |
| `emulator` | .NET 7 (built from `emulator/`) | Game server; Nitro WebSocket :2096, RCON :30001 (internal, IP-allowlisted) | 172.28.0.30 |
| `cms` | php:8.5-fpm-alpine (built from `cms/`) | Atom CMS, `EMULATOR_DRIVER=plus` | 172.28.0.20 |
| `web` | nginx:1.27-alpine | CMS vhost, Nitro client + assets at `/nitro-assets/`, `/ws` WebSocket proxy | 172.28.0.40, dev http://localhost:8080 |

`emulator/` and `cms/` are git submodules (branch `pixelrp` on each fork).

## Prerequisites

- Docker (Compose v2)
- `gh` CLI authenticated (for submodule clones over HTTPS)
- Node 22 + Python 3 (one-time Nitro client build; see `docker/nitro/README.md`)

## Quickstart (local)

```bash
git clone --recurse-submodules https://github.com/rybealey/pixelrp.git
cd pixelrp
cp .env.example .env          # then edit the changeme passwords
docker compose up -d db       # first boot imports the PlusEMU schema (~1 min)
docker compose up -d --build
docker compose exec cms php artisan migrate --force
docker compose exec cms php artisan db:seed --force
```

Build the Nitro client and assets once (full recipe, pitfalls, and repair
scripts: [docker/nitro/README.md](docker/nitro/README.md)), then set runtime
settings:

```bash
docker compose exec db mysql -u$DB_USER -p$DB_PASSWORD $DB_NAME -e \
  "UPDATE website_settings SET value='emulator' WHERE \`key\`='rcon_ip'; \
   UPDATE website_settings SET value='30001' WHERE \`key\`='rcon_port'; \
   UPDATE website_settings SET value='/nitro-assets/client' WHERE \`key\`='nitro_path'; \
   UPDATE website_settings SET value='0' WHERE \`key\` IN ('cloudflare_turnstile_enabled','google_recaptcha_enabled');"
docker compose exec cms php artisan cache:clear
```

Open http://localhost:8080 — complete the installation wizard, register, and
click into the hotel.

### Tests

```bash
# Plus-driver tests (isolated pixelrp_test DB; see cms/phpunit.plus.xml):
docker compose exec cms php artisan test -c phpunit.plus.xml
# NEVER run the stock feature suite against the shared dev DB — RefreshDatabase
# drops every table, including the emulator's. The stock suite uses its own
# `testing` database via cms/phpunit.xml.
```

## Production (pixelrp.co)

Production = the same stack plus [compose.prod.yaml](compose.prod.yaml). The
VPS's host nginx terminates TLS with the Cloudflare origin certs
(`/etc/ssl/pixelrp/`) and proxies `https://pixelrp.co` → `127.0.0.1:8080`
(our `web`) and `wss://pixelrp.co:2096` → `127.0.0.1:2096` (our `emulator`).
All container ports stay loopback-bound. The Nitro client uses
`nitro/renderer-config.prod.json` (socket.url `wss://pixelrp.co:2096`).

In prod there is **no `./cms` bind mount** — the image's `composer install
--no-dev` output and built theme assets are what run, with only `.env` and
`storage/` mounted through. Never `composer install` on the VPS.

```bash
# 1. Code
git clone --recurse-submodules https://github.com/rybealey/pixelrp.git /opt/pixelrp
cd /opt/pixelrp
cp .env.example .env        # then set real DB_PASSWORD / DB_ROOT_PASSWORD
cp cms/.env.example cms/.env

# 2. Assets — RSYNC the built tree from the build machine; do NOT regenerate
#    here. It carries three hand-applied repairs (FigureMap null-parts, bundle
#    compression, dangling sprite aliases) documented in docker/nitro/README.md.
#    rsync -az nitro/ root@<vps>:/opt/pixelrp/nitro/
cp nitro/renderer-config.prod.json nitro/client/renderer-config.json   # wss endpoint
cp nitro/ui-config.json nitro/client/ui-config.json                    # blanked promo widgets

# 3. Host nginx (TLS edge)
cp docker/host/pixelrp.nginx.conf /etc/nginx/sites-enabled/pixelrp
nginx -t && systemctl reload nginx

# 4. Stack
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
docker compose exec cms php artisan migrate --force
docker compose exec cms php artisan db:seed --force
# apply the website_settings block from Quickstart

# 5. Complete the /installation wizard in a browser BEFORE announcing the site
#    — every request redirects there until it's done.
```

Pre-cutover checks: a spoofed `X-Forwarded-For` must **not** change the
`X-RateLimit-*` bucket; housekeeping → "reload catalog" must reach the emulator
(RCON's allowlist is exact-IP, and it fails silently if the subnet shifts).


## Known limitations

- Catalog icons / badge images are not populated (`image.library.url` /
  `hof.furni.url` asset trees) — cosmetic; room, avatar, and furniture
  rendering are unaffected.
- The emulator upstream is dormant (last upstream commit Apr 2024) and builds
  on EOL .NET 7 images — self-maintained from here.
- `sendGift`/`forwardUser`-style RCON calls that PlusEMU cannot express
  degrade gracefully (DB write or logged no-op); see
  `cms/app/Services/PlusRconService.php`.
