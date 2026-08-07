# PixelRP Retro Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A locally running Habbo retro: forked PlusEMU emulator + Atom CMS (its built-in `plus` driver completed) + Nitro client, all under one Docker Compose stack.

**Architecture:** One MySQL 8 database seeded with PlusEMU's schema, shared by the emulator (.NET 7, WebSocket port 2096 for Nitro, plaintext RCON on 30001) and Atom CMS (Laravel 13, `EMULATOR_DRIVER=plus`). Nginx fronts the CMS (php-fpm), serves the Nitro client bundle and assets statically, and proxies the WebSocket. The CMS-side work is completing Atom's existing Plus emulator driver: a PlusEMU RCON client, schema-compatibility migrations, and rank-table retargeting.

**Tech Stack:** Docker Compose, MySQL 8, .NET 7, PHP 8.5/Laravel 13/Filament 5, Nitro client (revision `NITRO-1-6-6`), Nginx.

## Global Constraints

- Emulator fork: `rybealey/PlusEMU` (from `80O/PlusEMU`), work branch `pixelrp`, submodule path `emulator/`
- CMS fork: `rybealey/atomcms` (from `ObjectRetros/atomcms`), work branch `pixelrp`, submodule path `cms/`
- Nitro revision the emulator accepts: `NITRO-1-6-6` (from `emulator/Resources/Revisions/1.6.6.json`); Flash fallback revision exists but Flash is out of scope
- All host/port/credential config via env vars (`.env` at repo root); no hardcoded hosts. PlusEMU's `config.json` does NOT read env vars — it is generated from a template by `envsubst` at container start
- Emulator container MUST run with `tty: true` and `stdin_open: true` (`Program.Main` loops on `Console.ReadKey`)
- PlusEMU RCON: `Rcon.Hostname` must be an IP literal (`0.0.0.0`); `AllowedAddresses` matches exact numeric IPs, so the CMS container gets a static IP (`172.28.0.20`) on the compose network (subnet `172.28.0.0/16`)
- The emulator never verifies `users.password` — auth is SSO-ticket-only; the CMS owns password hashing (Laravel bcrypt, already Atom's default)
- SSO tickets must be ≥ 15 chars (Atom's `{hotel_name}-{uuid}` format satisfies this)
- MySQL must run with `--sql-mode=NO_ENGINE_SUBSTITUTION` (PlusEMU's dump has zero-date defaults)
- CMS keeps it simple: `CACHE_STORE=file`, `SESSION_DRIVER=file`, `QUEUE_CONNECTION=sync` — no Redis service
- Commit after every task; emulator/cms submodule changes are committed on their `pixelrp` branches, then the submodule pointer is committed in the root repo

---

### Task 1: Fork repos, add submodules, create work branches

**Files:**
- Create: `.gitmodules`, `emulator/` (submodule), `cms/` (submodule), `.gitignore`

**Interfaces:**
- Produces: `emulator/` = rybealey/PlusEMU @ branch `pixelrp`; `cms/` = rybealey/atomcms @ branch `pixelrp`. All later tasks read/patch files under these paths.

- [ ] **Step 1: Fork both upstreams (no clone)**

```bash
gh repo fork 80O/PlusEMU --clone=false
gh repo fork ObjectRetros/atomcms --clone=false
```

Expected: both report "Created fork rybealey/…" (or "already exists").

- [ ] **Step 2: Add submodules**

Run from the repo root (`/Users/rybealey/Documents/Personal/pixelrp/plus`):

```bash
git submodule add https://github.com/rybealey/PlusEMU.git emulator
git submodule add https://github.com/rybealey/atomcms.git cms
```

- [ ] **Step 3: Create `pixelrp` branches in each submodule and push**

```bash
cd emulator && git checkout -b pixelrp && git push -u origin pixelrp && cd ..
cd cms && git checkout -b pixelrp && git push -u origin pixelrp && cd ..
```

- [ ] **Step 4: Root .gitignore**

Create `.gitignore`:

```gitignore
.env
nitro/assets/
```

- [ ] **Step 5: Verify submodule state**

Run: `git submodule status`
Expected: two lines, `emulator` and `cms`, each on branch heads matching their remotes.

- [ ] **Step 6: Commit**

```bash
git add .gitmodules emulator cms .gitignore
git commit -m "feat: add PlusEMU and atomcms forks as submodules"
```

---

### Task 2: Database service seeded with PlusEMU schema

**Files:**
- Create: `compose.yaml`, `.env.example`, `.env` (copy, git-ignored)

**Interfaces:**
- Produces: compose service `db` (MySQL 8, database `${DB_NAME}`, network `pixelrp` subnet `172.28.0.0/16`), seeded with `emulator/Resources/SQLs/Original Database.sql`. Later tasks add services to this same `compose.yaml`.

- [ ] **Step 1: Write `.env.example` and copy to `.env`**

```dotenv
# Database
DB_NAME=pixelrp
DB_USER=pixelrp
DB_PASSWORD=changeme-local
DB_ROOT_PASSWORD=changeme-root

# Emulator
NITRO_PORT=2096
RCON_PORT=30001
# Exact-IP allowlist entries for PlusEMU RCON (CMS static IP)
RCON_ALLOWED_IP=172.28.0.20

# Web
HTTP_PORT=8080
HOTEL_NAME=PixelRP
```

```bash
cp .env.example .env
```

- [ ] **Step 2: Write `compose.yaml` with the db service**

```yaml
name: pixelrp

networks:
  pixelrp:
    ipam:
      config:
        - subnet: 172.28.0.0/16

volumes:
  dbdata:

services:
  db:
    image: mysql:8.0
    command: --sql-mode=NO_ENGINE_SUBSTITUTION --character-set-server=utf8mb4
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_ROOT_PASSWORD}
      MYSQL_DATABASE: ${DB_NAME}
      MYSQL_USER: ${DB_USER}
      MYSQL_PASSWORD: ${DB_PASSWORD}
    volumes:
      - dbdata:/var/lib/mysql
      - ./emulator/Resources/SQLs/Original Database.sql:/docker-entrypoint-initdb.d/01-plusemu.sql:ro
    ports:
      - "127.0.0.1:3306:3306"
    networks:
      pixelrp:
        ipv4_address: 172.28.0.10
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "127.0.0.1", "-p${DB_ROOT_PASSWORD}"]
      interval: 5s
      timeout: 3s
      retries: 20
```

- [ ] **Step 3: Bring up and verify seed**

```bash
docker compose up -d db
sleep 45
docker compose exec db mysql -u"$(grep ^DB_USER .env | cut -d= -f2)" -p"$(grep ^DB_PASSWORD .env | cut -d= -f2)" "$(grep ^DB_NAME .env | cut -d= -f2)" -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE(); DESCRIBE users;" 
```

Expected: table count > 100; `users` shows `auth_ticket`, `credits`, `vip_points`, `activity_points` columns. If the init script fails, `docker compose logs db` shows the SQL error — fix means adjusting `command:` sql-mode flags, NOT editing the dump.

- [ ] **Step 4: Commit**

```bash
git add compose.yaml .env.example .gitignore
git commit -m "feat: MySQL service seeded with PlusEMU schema"
```

---

### Task 3: Emulator image and service

**Files:**
- Create: `docker/emulator/Dockerfile`, `docker/emulator/config.template.json`, `docker/emulator/entrypoint.sh`
- Modify: `compose.yaml` (add `emulator` service)

**Interfaces:**
- Consumes: `db` service from Task 2.
- Produces: service `emulator` at static IP `172.28.0.30`, Nitro WebSocket on `${NITRO_PORT}` (2096), RCON on `${RCON_PORT}` (30001) restricted to `${RCON_ALLOWED_IP}`. Later tasks (RCON client, nginx ws proxy) target `emulator:2096` / `emulator:30001`.

- [ ] **Step 1: Write the config template**

`docker/emulator/config.template.json` — key names must match `emulator/Config/config.json` exactly (sections `Database`, `Flash`, `Nitro`, `Rcon`). Start from the submodule's file and replace values:

```json
{
  "Database": {
    "Hostname": "${DB_HOST}",
    "Port": 3306,
    "Username": "${DB_USER}",
    "Password": "${DB_PASSWORD}",
    "Name": "${DB_NAME}",
    "MinimumPoolSize": 5,
    "MaximumPoolSize": 25
  },
  "Flash": { "Hostname": "0.0.0.0", "Port": 1232, "Name": "Flash" },
  "Nitro": { "Hostname": "0.0.0.0", "Port": ${NITRO_PORT}, "Name": "Nitro" },
  "Rcon": {
    "Hostname": "0.0.0.0",
    "Port": ${RCON_PORT},
    "AllowedAddresses": ["${RCON_ALLOWED_IP}", "127.0.0.1"]
  }
}
```

Before finalizing, diff against `emulator/Config/config.json` and carry over any additional keys it defines verbatim (defaults are fine); missing sections fall back to code defaults but keep the file complete.

- [ ] **Step 2: Write the entrypoint**

`docker/emulator/entrypoint.sh`:

```bash
#!/bin/sh
set -e
envsubst < /templates/config.template.json > /app/Config/config.json
exec dotnet "/app/Plus Emulator.dll"
```

- [ ] **Step 3: Write the Dockerfile**

`docker/emulator/Dockerfile` (build context = repo root):

```dockerfile
FROM mcr.microsoft.com/dotnet/sdk:7.0 AS build
WORKDIR /src
COPY emulator/ .
RUN dotnet publish "Plus Emulator.csproj" -c Release -o /app

FROM mcr.microsoft.com/dotnet/runtime:7.0
RUN apt-get update && apt-get install -y --no-install-recommends gettext-base && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /app .
COPY docker/emulator/config.template.json /templates/config.template.json
COPY docker/emulator/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
```

- [ ] **Step 4: Add the compose service**

Append to `compose.yaml` services:

```yaml
  emulator:
    build:
      context: .
      dockerfile: docker/emulator/Dockerfile
    tty: true
    stdin_open: true
    environment:
      DB_HOST: db
      DB_USER: ${DB_USER}
      DB_PASSWORD: ${DB_PASSWORD}
      DB_NAME: ${DB_NAME}
      NITRO_PORT: ${NITRO_PORT}
      RCON_PORT: ${RCON_PORT}
      RCON_ALLOWED_IP: ${RCON_ALLOWED_IP}
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "127.0.0.1:${NITRO_PORT}:${NITRO_PORT}"
    networks:
      pixelrp:
        ipv4_address: 172.28.0.30
```

- [ ] **Step 5: Build, run, verify**

```bash
docker compose up -d --build emulator
sleep 10
docker compose logs emulator | tail -30
docker compose exec emulator sh -c 'ls /app/revisions/'
```

Expected: logs show a successful boot (rooms/catalog/settings managers loading, no MySQL connection errors, no crash loop); `revisions/` contains `1.6.6.json`. If it exits immediately with a `Console.ReadKey` `InvalidOperationException`, confirm `tty: true` took effect (`docker compose config`).

- [ ] **Step 6: Verify the WebSocket listener**

```bash
curl -s -o /dev/null -w '%{http_code}\n' --max-time 3 "http://127.0.0.1:${NITRO_PORT:-2096}/" || true
```

Expected: any HTTP status or an empty-reply error is fine — what matters is NOT "connection refused" (listener is up).

- [ ] **Step 7: Commit**

```bash
git add docker/emulator compose.yaml
git commit -m "feat: containerized PlusEMU emulator service"
```

If any emulator source change was required to boot on Linux, commit it inside `emulator/` on `pixelrp`, push, then commit the submodule pointer at root.

---

### Task 4: CMS image (php-fpm) and Nginx web service

**Files:**
- Create: `docker/cms/Dockerfile`, `docker/cms/entrypoint.sh`, `docker/web/nginx.conf`
- Modify: `compose.yaml` (add `cms` and `web` services)

**Interfaces:**
- Consumes: `db` (Task 2), `emulator` (Task 3).
- Produces: `cms` = php-fpm at static IP `172.28.0.20` with the Atom code at `/var/www/html`; `web` = nginx on host port `${HTTP_PORT}` serving the CMS, plus `/nitro-assets/` static path and `/ws` WebSocket proxy used by Task 8.

- [ ] **Step 1: Write the CMS Dockerfile**

`docker/cms/Dockerfile` (context = repo root). Verify the exact PHP extension list against `cms/composer.json` `require` before building; this is the expected baseline:

```dockerfile
FROM node:22-alpine AS assets
WORKDIR /app
COPY cms/ .
RUN npm ci && npm run build:atom

FROM composer:2 AS vendor
WORKDIR /app
COPY cms/ .
RUN composer install --no-dev --no-interaction --ignore-platform-req=ext-* --optimize-autoloader

FROM php:8.5-fpm-alpine
RUN apk add --no-cache icu-dev libzip-dev libpng-dev libjpeg-turbo-dev freetype-dev oniguruma-dev \
 && docker-php-ext-configure gd --with-jpeg --with-freetype \
 && docker-php-ext-install pdo_mysql bcmath intl zip gd exif
WORKDIR /var/www/html
COPY --from=vendor /app .
COPY --from=assets /app/public/build ./public/build
COPY docker/cms/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown -R www-data:www-data storage bootstrap/cache
ENTRYPOINT ["/entrypoint.sh"]
CMD ["php-fpm"]
```

Note: `npm run build:atom` is Atom's documented theme build script (see `cms/package.json`). If it needs `vendor/` present (themer package), reorder: run the `vendor` stage first and `COPY --from=vendor /app/vendor ./vendor` into the assets stage.

- [ ] **Step 2: Write the CMS entrypoint**

`docker/cms/entrypoint.sh`:

```bash
#!/bin/sh
set -e
if [ ! -f /var/www/html/.env ]; then
  cp /var/www/html/.env.example /var/www/html/.env
fi
php artisan key:generate --force --no-interaction || true
exec "$@"
```

(Migrations and `atom:install` run manually in Task 5 — first boot is interactive by design.)

- [ ] **Step 3: Write nginx config**

`docker/web/nginx.conf`:

```nginx
worker_processes auto;
events { worker_connections 1024; }
http {
  include /etc/nginx/mime.types;
  sendfile on;
  map $http_upgrade $connection_upgrade { default upgrade; '' close; }

  server {
    listen 80;
    root /var/www/html/public;
    index index.php;
    client_max_body_size 25m;

    location /nitro-assets/ {
      alias /var/www/nitro-assets/;
      add_header Cache-Control "public, max-age=604800";
    }

    location /ws {
      proxy_pass http://emulator:2096;
      proxy_http_version 1.1;
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection $connection_upgrade;
      proxy_read_timeout 3600s;
    }

    location / { try_files $uri $uri/ /index.php?$query_string; }

    location ~ \.php$ {
      fastcgi_pass cms:9000;
      fastcgi_index index.php;
      include fastcgi_params;
      fastcgi_param SCRIPT_FILENAME $realpath_root$fastcgi_script_name;
    }
  }
}
```

- [ ] **Step 4: Add compose services**

Append to `compose.yaml` services:

```yaml
  cms:
    build:
      context: .
      dockerfile: docker/cms/Dockerfile
    env_file: .env
    environment:
      APP_ENV: local
      APP_DEBUG: "true"
      APP_URL: http://localhost:${HTTP_PORT}
      DB_CONNECTION: mysql
      DB_HOST: db
      DB_PORT: 3306
      DB_DATABASE: ${DB_NAME}
      DB_USERNAME: ${DB_USER}
      DB_PASSWORD: ${DB_PASSWORD}
      CACHE_STORE: file
      SESSION_DRIVER: file
      QUEUE_CONNECTION: sync
      EMULATOR_DRIVER: plus
      RCON_HOST: emulator
      RCON_PORT: ${RCON_PORT}
    volumes:
      - ./cms:/var/www/html
    depends_on:
      db:
        condition: service_healthy
    networks:
      pixelrp:
        ipv4_address: 172.28.0.20

  web:
    image: nginx:1.27-alpine
    volumes:
      - ./docker/web/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./cms:/var/www/html:ro
      - ./nitro:/var/www/nitro-assets:ro
    ports:
      - "127.0.0.1:${HTTP_PORT}:80"
    depends_on:
      - cms
      - emulator
    networks:
      pixelrp:
        ipv4_address: 172.28.0.40
```

Note the `./cms` bind mount: in local dev the image's baked-in copy is shadowed by the working tree, so composer/npm artifacts must exist in `cms/` too — run once on host: `cd cms && composer install && npm ci && npm run build:atom` (PHP 8.5 + Node LTS required on host; if unavailable, run these inside the container: `docker compose run --rm cms composer install` etc.).

- [ ] **Step 5: Build and boot check**

```bash
docker compose up -d --build cms web
sleep 5
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:${HTTP_PORT:-8080}/
```

Expected: an HTTP status from Laravel (200 or a 500 about missing app key/migrations is acceptable at this stage — fixed by Task 5). NOT expected: 502 (php-fpm unreachable).

- [ ] **Step 6: Commit**

```bash
git add docker/cms docker/web compose.yaml
git commit -m "feat: Atom CMS and nginx services"
```

---

### Task 5: Point Atom's Plus driver at the shared DB and reconcile schemas

All CMS source edits in this task happen inside `cms/` (the fork, branch `pixelrp`).

**Files:**
- Create: `cms/database/migrations/2026_08_06_000001_plus_users_compatibility_columns.php`
- Modify: `cms/database/migrations/2023_09_09_030403_add_item_id_index_to_items_table.php`, `cms/app/Models/Game/Permission.php`, the four permissions ALTER migrations (`2022_08_14_210623_add_hidden_rank_to_permissions_table.php`, `2022_09_17_225245_add_staff_color_and_description_to_permissions_table.php`, `2022_09_25_153707_add_staff_background_to_permissions_table.php`, `2023_04_07_231919_remove_can_apply_from_permissions_table.php`)

**Interfaces:**
- Consumes: seeded PlusEMU schema (Task 2); `cms` service (Task 4).
- Produces: `php artisan migrate` passes against the PlusEMU database with `EMULATOR_DRIVER=plus`; `Game\Permission` reads PlusEMU's `ranks` table. Registration (Task 7) depends on the compatibility columns.

Background (verified against both codebases):
- PlusEMU `users` lacks columns Atom's `User` model and Fortify flow write: `real_name`, `mail_verified`, `account_day_of_birth`, `last_login`, `ip_register`, `ip_current`, `extra_rank`. (PlusEMU has its own `ip_last`/`ip_reg`, which the emulator keeps using — the CMS columns are additive and harmless.)
- Atom's `add_item_id_index` migration indexes `items.item_id` — the column doesn't exist in PlusEMU's `items` (it uses `base_item`); unguarded, `migrate` dies.
- Atom's `Game\Permission` model (table `permissions`) is Arcturus's RANK table. PlusEMU's `permissions` table is an unrelated permission-string list; PlusEMU ranks live in `ranks` (`id`, `name`, `badgeid`, `title`, `tab_colour`). The model and the four ALTER-permissions migrations must target `ranks` when the driver is `plus`.

- [ ] **Step 1: Write the users compatibility migration**

`cms/database/migrations/2026_08_06_000001_plus_users_compatibility_columns.php`:

```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        if (config('emulator.driver') !== 'plus') {
            return;
        }

        Schema::table('users', function (Blueprint $table) {
            foreach ([
                'real_name' => fn () => $table->string('real_name')->nullable(),
                'mail_verified' => fn () => $table->boolean('mail_verified')->default(false),
                'account_day_of_birth' => fn () => $table->integer('account_day_of_birth')->default(0),
                'last_login' => fn () => $table->integer('last_login')->default(0),
                'ip_register' => fn () => $table->string('ip_register', 45)->default(''),
                'ip_current' => fn () => $table->string('ip_current', 45)->default(''),
                'extra_rank' => fn () => $table->unsignedInteger('extra_rank')->nullable(),
            ] as $column => $add) {
                if (! Schema::hasColumn('users', $column)) {
                    $add();
                }
            }
        });
    }

    public function down(): void
    {
    }
};
```

(Exact column list may grow: any later `migrate` failure of the form "Unknown column X in users" gets X appended here — same guard pattern.)

- [ ] **Step 2: Guard the item_id index migration**

In `2023_09_09_030403_add_item_id_index_to_items_table.php`, wrap both `up()` and `down()` bodies:

```php
public function up(): void
{
    if (! Schema::hasColumn('items', 'item_id')) {
        return;
    }

    Schema::table('items', function (Blueprint $table) {
        $table->index(['item_id'], 'items_item_id_index');
    });
}
```

(and the mirror-image guard in `down()`).

- [ ] **Step 3: Retarget ranks**

In `cms/app/Models/Game/Permission.php`, replace the hard-coded table:

```php
protected $table = 'permissions';
```

with a constructor-set table:

```php
public function __construct(array $attributes = [])
{
    parent::__construct($attributes);
    $this->setTable(config('emulator.driver') === 'plus' ? 'ranks' : 'permissions');
}
```

Add an accessor so themes that render a rank name keep working (Arcturus column is `rank_name`, PlusEMU's is `name`):

```php
public function getRankNameAttribute(): string
{
    return (string) ($this->attributes['rank_name'] ?? $this->attributes['name'] ?? '');
}
```

In each of the four permissions ALTER migrations, replace `Schema::table('permissions', ...)` with:

```php
$rankTable = config('emulator.driver') === 'plus' ? 'ranks' : 'permissions';
Schema::table($rankTable, function (Blueprint $table) { /* unchanged body */ });
```

and guard `remove_can_apply` with `Schema::hasColumn($rankTable, 'can_apply')` (PlusEMU's `ranks` never had it).

- [ ] **Step 4: Run the installer and migrations**

```bash
docker compose exec cms php artisan atom:install --skip-arcturus --skip-catalog
```

Answer the DB prompts with the compose values (host `db`, database/user/password from `.env`). If any migration fails on a missing emulator column/table, apply the fix per Step 1's pattern and re-run `docker compose exec cms php artisan migrate --force`.

- [ ] **Step 5: Verify**

```bash
docker compose exec cms php artisan migrate:status | tail -20
docker compose exec db mysql -u${DB_USER} -p${DB_PASSWORD} ${DB_NAME} -e "SHOW COLUMNS FROM users LIKE 'ip_current'; SELECT COUNT(*) FROM website_settings;"
```

Expected: all migrations "Ran"; `ip_current` exists; `website_settings` seeded (> 30 rows). Then set runtime settings the hotel page needs:

```bash
docker compose exec db mysql -u${DB_USER} -p${DB_PASSWORD} ${DB_NAME} \
  -e "UPDATE website_settings SET value='emulator' WHERE \`key\`='rcon_ip'; UPDATE website_settings SET value='${RCON_PORT}' WHERE \`key\`='rcon_port'; UPDATE website_settings SET value='PixelRP' WHERE \`key\`='hotel_name';"
docker compose exec cms php artisan cache:clear
```

- [ ] **Step 6: Homepage smoke test**

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:${HTTP_PORT:-8080}/
```

Expected: 200 (or a redirect to `/installation` — complete that wizard in a browser once; it is Atom's first-run page).

- [ ] **Step 7: Commit (submodule then root)**

```bash
cd cms && git add -A && git commit -m "feat: complete plus driver schema compatibility (users columns, ranks table, item_id guard)" && git push && cd ..
git add cms && git commit -m "chore: bump cms submodule (plus schema compatibility)"
```

---

### Task 6: PlusEMU RCON client for the CMS

All edits inside `cms/`.

**Files:**
- Create: `cms/app/Services/PlusRconService.php`, `cms/tests/Unit/PlusRconServiceTest.php`
- Modify: `cms/app/Providers/AppServiceProvider.php` (bind per driver, around the existing `Rcon` binding ~line 64)

**Interfaces:**
- Consumes: `App\Contracts\Rcon` (read it first — implement every method), `App\Data\RconResponse`, settings keys `rcon_ip`/`rcon_port`, `config('habbo.rcon.*')` timeouts.
- Produces: `PlusRconService` bound as `App\Contracts\Rcon` when `config('emulator.driver') === 'plus'`. All existing CMS call sites (shop fulfillment, housekeeping user edit, motto/badge/currency actions) work unchanged.

Protocol facts (from `emulator/Communication/RCON/`): raw TCP, one command per connection, wire format `command \x01 param1:param2:…`, no response bytes ever sent back, source IP must be in `AllowedAddresses`. Alert messages must not contain `:` (PlusEMU splits params on it) — strip/replace before sending.

Command mapping (Atom method → PlusEMU command; "DB+" = write the database first, then send a reload):

| Atom `Rcon` method | PlusEMU wire command | Notes |
|---|---|---|
| `giveCredits(user, amount)` | `give_user_currency\x01{id}:credits:{amount}` | only affects online users; callers already DB-fallback |
| `givePoints(user, amount, type)` | `give_user_currency\x01{id}:{name}:{amount}` | type map: 0→`duckets`, 5→`diamonds`, 101→`gotw` |
| `giveBadge(user, badge)` | `give_user_badge\x01{id}:{badge}` | |
| `setMotto(user, motto)` | DB+ `reload_user_motto\x01{id}` | update `users.motto` first |
| `setRank(user, rank)` | DB+ `reload_user_rank\x01{id}` | update `users.rank` first |
| `disconnect(user, username)` | `disconnect_user\x01{id}` | |
| `alertUser(user, message)` | `alert_user\x01{id}:{message}` | replace `:` in message with `;` |
| `updateWordFilter()` | `reload_filter\x01` | |
| `updateCatalog()` | `reload_catalog\x01` | |
| `sendGift(...)` | **unsupported** → return failure response | callers fall back to FurnitureRepository insert |
| `forwardUser(...)` | **unsupported** → return failure response | graceful degrade |
| `executeCommand(...)` | **unsupported** → return failure response | graceful degrade |

Because PlusEMU sends no reply, supported commands return a synthesized success `RconResponse` after a successful socket write; unsupported ones return a failure WITHOUT attempting a connection (so caller fallbacks fire).

- [ ] **Step 1: Write the failing test**

`cms/tests/Unit/PlusRconServiceTest.php` — spin up a local TCP server in the test, point the service at it, assert wire bytes:

```php
<?php

namespace Tests\Unit;

use App\Services\PlusRconService;
use PHPUnit\Framework\TestCase;

class PlusRconServiceTest extends TestCase
{
    private $server;
    private int $port;

    protected function setUp(): void
    {
        parent::setUp();
        $this->server = stream_socket_server('tcp://127.0.0.1:0', $errno, $errstr);
        $name = stream_socket_get_name($this->server, false);
        $this->port = (int) substr($name, strrpos($name, ':') + 1);
    }

    private function receiveOne(): string
    {
        $conn = stream_socket_accept($this->server, 2);
        $data = stream_get_contents($conn);
        fclose($conn);
        return $data;
    }

    public function test_give_credits_wire_format(): void
    {
        $rcon = new PlusRconService('127.0.0.1', $this->port);
        $response = $rcon->sendPlusCommand('give_user_currency', [42, 'credits', 100]);
        $this->assertSame("give_user_currency\x01" . '42:credits:100', $this->receiveOne());
        $this->assertTrue($response->successful());
    }

    public function test_unsupported_command_fails_without_connecting(): void
    {
        $rcon = new PlusRconService('127.0.0.1', 1); // nothing listens on port 1
        $response = $rcon->forwardUser(42, 7);
        $this->assertFalse($response->successful());
    }

    public function test_alert_strips_colons_from_message(): void
    {
        $rcon = new PlusRconService('127.0.0.1', $this->port);
        $rcon->alertUser(42, 'note: hello');
        $this->assertSame("alert_user\x01" . '42:note; hello', $this->receiveOne());
    }
}
```

Adjust assertions to `RconResponse`'s real success API after reading `cms/app/Data/RconResponse.php` (recon says it wraps `{status:int, message:string}`; construct success as the CMS does elsewhere).

- [ ] **Step 2: Run tests, verify they fail**

Run: `docker compose exec cms php artisan test --filter=PlusRconServiceTest`
Expected: FAIL — `PlusRconService` class not found.

- [ ] **Step 3: Implement `PlusRconService`**

`cms/app/Services/PlusRconService.php`:

```php
<?php

namespace App\Services;

use App\Contracts\Rcon;
use App\Data\RconResponse;
use App\Models\User;

class PlusRconService implements Rcon
{
    public function __construct(
        private ?string $host = null,
        private ?int $port = null,
    ) {
        $this->host ??= setting('rcon_ip');
        $this->port ??= (int) setting('rcon_port');
    }

    /** @param array<int, int|string> $params */
    public function sendPlusCommand(string $command, array $params = []): RconResponse
    {
        $payload = $command . "\x01" . implode(':', $params);

        $socket = @stream_socket_client(
            sprintf('tcp://%s:%d', $this->host, $this->port),
            $errno,
            $errstr,
            (float) config('habbo.rcon.connect_timeout', 2),
        );

        if ($socket === false) {
            return $this->failure("RCON connect failed: {$errstr}");
        }

        fwrite($socket, $payload);
        fclose($socket);

        return $this->success();
    }

    private function unsupported(string $method): RconResponse
    {
        logger()->info("PlusRconService: {$method} has no PlusEMU equivalent; degrading");

        return $this->failure("{$method} unsupported by PlusEMU");
    }

    private function sanitize(string $message): string
    {
        return str_replace(':', ';', $message);
    }

    public function giveCredits(User $user, int $credits): RconResponse
    {
        return $this->sendPlusCommand('give_user_currency', [$user->id, 'credits', $credits]);
    }

    public function givePoints(User $user, int $points, int $type): RconResponse
    {
        $currency = match ($type) {
            0 => 'duckets',
            5 => 'diamonds',
            101 => 'gotw',
            default => null,
        };

        if ($currency === null) {
            return $this->unsupported("givePoints(type={$type})");
        }

        return $this->sendPlusCommand('give_user_currency', [$user->id, $currency, $points]);
    }

    public function giveBadge(User $user, string $badge): RconResponse
    {
        return $this->sendPlusCommand('give_user_badge', [$user->id, $badge]);
    }

    public function setMotto(User $user, string $motto): RconResponse
    {
        $user->newQuery()->whereKey($user->id)->update(['motto' => $motto]);

        return $this->sendPlusCommand('reload_user_motto', [$user->id]);
    }

    public function setRank(User $user, int $rank): RconResponse
    {
        $user->newQuery()->whereKey($user->id)->update(['rank' => $rank]);

        return $this->sendPlusCommand('reload_user_rank', [$user->id]);
    }

    public function disconnectUser(User $user): RconResponse
    {
        return $this->sendPlusCommand('disconnect_user', [$user->id]);
    }

    public function alertUser(User $user, string $message): RconResponse
    {
        return $this->sendPlusCommand('alert_user', [$user->id, $this->sanitize($message)]);
    }

    public function updateWordFilter(): RconResponse
    {
        return $this->sendPlusCommand('reload_filter');
    }

    public function updateCatalog(): RconResponse
    {
        return $this->sendPlusCommand('reload_catalog');
    }

    public function sendGift(User $user, int $itemId, string $message): RconResponse
    {
        return $this->unsupported('sendGift');
    }

    public function forwardUser(User $user, int $roomId): RconResponse
    {
        return $this->unsupported('forwardUser');
    }

    public function executeCommand(User $user, string $command): RconResponse
    {
        return $this->unsupported('executeCommand');
    }

    private function success(): RconResponse
    {
        return new RconResponse(status: 1, message: 'ok');
    }

    private function failure(string $message): RconResponse
    {
        return new RconResponse(status: 0, message: $message);
    }
}
```

IMPORTANT: before finalizing, open `cms/app/Contracts/Rcon.php` and `cms/app/Services/RconService.php` and make every method name/signature/`RconResponse` construction match the real interface exactly (including any generic `sendCommand`/`isConnected` members — implement `sendCommand` by translating known Arcturus keys through the mapping table above, returning `unsupported()` for unknown keys). The mapping table is authoritative for semantics; the interface file is authoritative for signatures.

- [ ] **Step 4: Bind per driver**

In `cms/app/Providers/AppServiceProvider.php`, where `Rcon` is currently bound to `RconService` (wrapped by `AfterCommitRcon`), select by driver:

```php
$inner = config('emulator.driver') === 'plus'
    ? $app->make(\App\Services\PlusRconService::class)
    : $app->make(\App\Services\RconService::class);
```

keeping the existing `AfterCommitRcon`/`FakeRcon` wrapping structure unchanged.

- [ ] **Step 5: Run tests, verify they pass**

Run: `docker compose exec cms php artisan test --filter=PlusRconServiceTest`
Expected: PASS (3 tests).

- [ ] **Step 6: Live-fire against the emulator**

```bash
docker compose exec cms php artisan tinker --execute="dump(app(App\Contracts\Rcon::class)->updateCatalog());"
docker compose logs emulator | grep -i rcon | tail -5
```

Expected: emulator log shows the RCON connection/command from `172.28.0.20` (or, if it logs nothing on success, NO "not allowed"/rejection line). If rejected, the CMS container IP isn't matching `RCON_ALLOWED_IP` — check `docker inspect` for the actual IP.

- [ ] **Step 7: Commit (submodule then root)**

```bash
cd cms && git add -A && git commit -m "feat: PlusEMU rcon client with graceful degradation" && git push && cd ..
git add cms && git commit -m "chore: bump cms submodule (plus rcon client)"
```

---

### Task 7: Registration → SSO round-trip verification

**Files:**
- Create: `cms/tests/Feature/PlusRegistrationTest.php`
- Possibly modify: `cms/app/Actions/Fortify/CreateNewUser.php` (only if a written column is missing from PlusEMU — append to Task 5's compat migration instead where possible)

**Interfaces:**
- Consumes: compat columns (Task 5); Atom's `CreateNewUser`, `User::ssoTicket()`.
- Produces: a registered user row PlusEMU accepts, and an `auth_ticket` PlusEMU's `Authenticator` will validate (≥15 chars, stored in `users.auth_ticket`). Task 9's E2E depends on this.

PlusEMU acceptance facts: `SELECT id FROM users WHERE auth_ticket = @sso`, ticket consumed (set NULL) on login, no expiry/IP checks; `gender` must be enum `'M'`/`'F'`; `account_created` is `char(12)` (Atom writes `time()` — 10 digits, fits).

- [ ] **Step 1: Write the failing feature test**

`cms/tests/Feature/PlusRegistrationTest.php`:

```php
<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class PlusRegistrationTest extends TestCase
{
    use RefreshDatabase;

    public function test_registered_user_row_is_plusemu_valid(): void
    {
        $response = $this->post('/register', [
            'username' => 'testduck',
            'mail' => 'duck@example.com',
            'password' => 'secret-password-1',
            'password_confirmation' => 'secret-password-1',
        ]);

        $user = User::where('username', 'testduck')->firstOrFail();

        $this->assertContains($user->gender, ['M', 'F']);
        $this->assertLessThanOrEqual(12, strlen((string) $user->account_created));
        $this->assertNotNull($user->look);
        $this->assertSame('', (string) $user->auth_ticket);
    }

    public function test_sso_ticket_is_plusemu_acceptable(): void
    {
        $user = User::factory()->create();
        $ticket = $user->ssoTicket();

        $this->assertGreaterThanOrEqual(15, strlen($ticket));
        $this->assertDatabaseHas('users', ['id' => $user->id, 'auth_ticket' => $ticket]);
    }
}
```

Adapt the POST field names to Atom's real Fortify registration payload (read `CreateNewUser::create()` validation rules first; include Turnstile/captcha bypass config for testing if enforced — set the relevant config to disabled in the test's `setUp`). If `User::ssoTicket()` returns the model not the string, read the ticket from `$user->refresh()->auth_ticket`.

- [ ] **Step 2: Run tests, expect failure or errors revealing schema gaps**

Run: `docker compose exec cms php artisan test --filter=PlusRegistrationTest`
Expected first run: failures like unknown columns — each one gets appended to the Task 5 compat migration (same `hasColumn` guard), then `php artisan migrate:fresh` is NOT used (would wipe emulator seed data in the test DB — Atom's testing env imports its own schema; if the testing schema is Arcturus (`database/migrations/sqls/default.sql`), set the test suite's driver env to `arcturus` for unrelated suites and run these two tests against a MySQL test database seeded with the PlusEMU dump: create `pixelrp_test` DB, import `emulator/Resources/SQLs/Original Database.sql`, point `phpunit.xml`'s `DB_DATABASE` there with `EMULATOR_DRIVER=plus`).

- [ ] **Step 3: Fix gaps until green**

Run: `docker compose exec cms php artisan test --filter=PlusRegistrationTest`
Expected: PASS (2 tests).

- [ ] **Step 4: Manual browser check**

Register at `http://localhost:8080/register`, then:

```bash
docker compose exec db mysql -u${DB_USER} -p${DB_PASSWORD} ${DB_NAME} -e "SELECT id, username, gender, account_created, auth_ticket FROM users ORDER BY id DESC LIMIT 1;"
```

Expected: your new user with sane values.

- [ ] **Step 5: Commit (submodule then root)**

```bash
cd cms && git add -A && git commit -m "test: plus-driver registration and sso round-trip" && git push && cd ..
git add cms && git commit -m "chore: bump cms submodule (registration/sso tests)"
```

---

### Task 8: Nitro client build, assets, and hotel page wiring

**Files:**
- Create: `nitro/` (built client bundle + converted assets; git-ignored except config), `docker/nitro/README.md` (build recipe), `nitro/renderer-config.json` (committed)
- Modify: `docker/web/nginx.conf` (only if paths need adjusting), `website_settings.nitro_path` (DB)

**Interfaces:**
- Consumes: emulator WebSocket `ws://localhost:2096` (direct in local dev; `/ws` proxy exists for the VPS/wss case), Atom's client page (`resources/themes/*/views/client/nitro.blade.php` iframing `{setting('nitro_path')}/index.html?sso={ticket}`).
- Produces: browsable client at `http://localhost:8080/nitro-assets/client/index.html`, `nitro_path` setting pointing at it. Task 9 depends on this.

The emulator only accepts client build `NITRO-1-6-6`, so the client must be a Nitro build whose `client.version` handshake string matches. Community 1.6.x builds of `billsonnn/nitro-react` are the match. This task builds it once on the host (Node) and drops the bundle + assets under `nitro/`, which nginx already serves at `/nitro-assets/`.

- [ ] **Step 1: Clone and pin nitro-react**

```bash
git clone https://github.com/billsonnn/nitro-react.git /tmp/nitro-react
cd /tmp/nitro-react
git log --oneline -5   # identify the 1.6.x-era tag/commit; check tags with: git tag -l
```

Pin to the newest tag/commit in the 1.6 line (if tags are absent, use the commit contemporaneous with the emulator's `1.6.6.json`, dated ~early 2024). Record the exact commit hash in `docker/nitro/README.md`.

- [ ] **Step 2: Configure the renderer**

Copy the repo's config template (in `public/` — `renderer-config.json` and `ui-config.json`), set at minimum:

```json
{
  "socket.url": "ws://localhost:2096",
  "asset.url": "http://localhost:8080/nitro-assets/assets",
  "external.texts.url": "http://localhost:8080/nitro-assets/assets/gamedata/ExternalTexts.json",
  "furnidata.url": "http://localhost:8080/nitro-assets/assets/gamedata/FurnitureData.json",
  "figuredata.url": "http://localhost:8080/nitro-assets/assets/gamedata/FigureData.json",
  "productdata.url": "http://localhost:8080/nitro-assets/assets/gamedata/ProductData.json"
}
```

(Key names must be taken from the template file itself — set every URL key it defines to the `/nitro-assets/assets` tree; do not invent keys.) Save the final file as `nitro/renderer-config.json` (committed) and copy it into the build.

- [ ] **Step 3: Obtain converted assets**

Use the nitro-converter docker recipe from `https://github.com/Gurkengewuerz/nitro-docker` (its `assets`/converter service downloads official Habbo SWF gamedata and converts furni/figure/effects to `.nitro` bundles — emulator-agnostic, safe to use even though that repo targets Arcturus). Output goes to `nitro/assets/` (git-ignored; ~1-2 GB). Alternative accepted route: a prebuilt community default asset pack extracted to `nitro/assets/`. Record whichever route was used, with exact commands, in `docker/nitro/README.md`.

- [ ] **Step 4: Build and install the client**

```bash
cd /tmp/nitro-react && npm install && npm run build
mkdir -p /Users/rybealey/Documents/Personal/pixelrp/plus/nitro/client
cp -R dist/* /Users/rybealey/Documents/Personal/pixelrp/plus/nitro/client/
cp /Users/rybealey/Documents/Personal/pixelrp/plus/nitro/renderer-config.json /Users/rybealey/Documents/Personal/pixelrp/plus/nitro/client/
```

- [ ] **Step 5: Point the CMS at it**

```bash
docker compose exec db mysql -u${DB_USER} -p${DB_PASSWORD} ${DB_NAME} \
  -e "UPDATE website_settings SET value='/nitro-assets/client' WHERE \`key\`='nitro_path';"
docker compose exec cms php artisan cache:clear
```

- [ ] **Step 6: Verify client loads standalone**

Open `http://localhost:8080/nitro-assets/client/index.html` in a browser. Expected: Nitro loader appears and asset requests to `/nitro-assets/assets/...` return 200s (check the network tab; 404s mean Step 3 paths don't match the config URLs). It will stall at authentication without an SSO ticket — that's correct here.

- [ ] **Step 7: Commit**

```bash
git add nitro/renderer-config.json docker/nitro/README.md .gitignore
git commit -m "feat: nitro client build recipe and renderer config"
```

---

### Task 9: End-to-end acceptance and documentation

**Files:**
- Create: `README.md`
- Modify: anything the E2E run flushes out (each fix follows the owning task's pattern and is committed separately)

**Interfaces:**
- Consumes: everything above.
- Produces: the acceptance criterion from the spec: `docker compose up` → register → enter hotel → land in a room.

- [ ] **Step 1: Cold-start test**

```bash
docker compose down
docker compose up -d --build
sleep 30
docker compose ps
```

Expected: `db` healthy; `emulator`, `cms`, `web` running (no restart loops).

- [ ] **Step 2: The E2E walk**

In a browser: `http://localhost:8080` → register a fresh account → log in → click the hotel/client button. Expected: Nitro loads in the iframe with `?sso=...`, connects to `ws://localhost:2096`, hotel view appears, you land in a room (set `hotel_home_room`/default room in settings if landing fails with "no room").

Diagnostics if it fails at the handshake: `docker compose logs emulator | tail -50` — "unknown build" means the client bundle isn't 1.6.6-line (Task 8 Step 1); an SSO rejection means the ticket wasn't written (Task 7); silence means the WebSocket never reached the emulator (port/config).

- [ ] **Step 3: Housekeeping smoke test**

Log into Filament housekeeping (`/housekeeping`) with the account (raise its `rank` in DB to the min_housekeeping_rank first), open the Users resource, send yourself an alert while in-client. Expected: alert appears in the client (proves RCON path end-to-end). Arcturus-only resources are absent — correct behavior of the feature gates.

- [ ] **Step 4: Write README**

`README.md`: what this is, prerequisites (Docker, gh, Node for the one-time Nitro build), quickstart (`cp .env.example .env`, edit passwords, one-time Task 8 asset build, `docker compose up -d --build`, installer wizard, done), service map with ports, and a "VPS deployment" section stating the delta: put Caddy/nginx with TLS in front, point Nitro's `socket.url` at `wss://<domain>/ws` (the `/ws` proxy in `docker/web/nginx.conf` exists for exactly this), and change all `changeme` passwords.

- [ ] **Step 5: Final commit**

```bash
git add README.md
git commit -m "docs: quickstart and deployment notes"
```

---

## Self-review notes

- Spec coverage: repo layout (T1), compose stack db/emulator/cms/web (T2-T4), Atom→Plus adaptation trio — models/schema (T5), registration/SSO (T7), RCON (T6) — Nitro pairing + assets (T8), acceptance test + healthchecks + docs (T9). VPS TLS designed-for via `/ws` proxy + env config (T4, T9). RP features, theming, payments: out of scope, untouched.
- Known soft spots called out inline rather than hidden: exact `Rcon` interface signatures (T6 Step 3 note), Atom registration payload field names (T7 Step 1), nitro-react tag selection and renderer config key names (T8 Steps 1-2). Each names the authoritative file to read before coding.
