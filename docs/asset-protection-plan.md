# Asset protection plan

How habrp.com keeps its assets away from scrapers, what we expose today, and a
phased plan to close the gap. Observations are from 2026-10-15.

**Scope:** beta and prod, on Cloudflare's **Free** plan.

**Status:**
- **Phase 2, the asset pass:** built on `feat/asset-protection` (parent, cms,
  client). Each box's secret is made by its deploy workflow on first run.
- **Phase 0 logging:** built in, now per account instead of per IP.
- **Phase 1:** dashboard steps, below.
- **Phase 3:** waits on a week of Phase 0 data.

## TL;DR

- **habrp.com** puts its whole domain behind one Cloudflare challenge rule:
  every path, `robots.txt` included, answers a non-browser with
  `403 cf-mitigated: challenge`. That is the entire visible mechanism, an
  edge-only lock.
- **We currently lock nothing.** Every bundle and gamedata file downloads with a
  plain `curl`, and nginx sends `Access-Control-Allow-Origin: *` on all of
  them, so another hotel can even point its own client at our URLs.
  `FigureMap.json` and `FurnitureData.json` are a ready-made index for
  mirroring the whole tree in one script.
- **The plan copies habrp's edge challenge, then goes further.** It adds an
  origin-side **asset pass**: a signed cookie the CMS issues to logged-in
  players and nginx checks on every file. On top of that, a per-account rate
  limit and a nightly scrape detector.
- **The result:** anonymous bulk downloads and hotlinking become impossible. A
  scraper has to burn a real account, gets throttled, and gets flagged.
- **The limit:** nothing stops one logged-in player from saving what their own
  browser renders. This plan makes ripping slow, attributable and revocable,
  not impossible.

---

## 1. What habrp.com does

### Observed

| Check | Result |
|---|---|
| DNS | Apex `habrp.com` only, proxied by Cloudflare (`104.21.87.197`, `172.67.145.184`; NS `seamus`/`chin.ns.cloudflare.com`). None of `assets`, `cdn`, `images`, `swf`, `nitro`, `game`, `client`, `ws`, `api`, `static`, `gamedata`, `imager` and the rest resolve. |
| Certificate transparency (crt.sh) | Only `habrp.com` and `*.habrp.com`. A wildcard certificate, so subdomain names never appear in public logs. |
| `GET /` with a Chrome User-Agent | `403`, `cf-mitigated: challenge`, `server: cloudflare`. |
| `/robots.txt`, `/favicon.ico`, `/client`, `/nitro/`, `/gamedata/FigureMap.json`, `/bundled/figure/…`, `/renderer-config.json`, `/c_images/…`, `/api/` | All `403 cf-mitigated: challenge`. There is no exemption, not even for static files. |
| `/cdn-cgi/trace` | `200`. Cloudflare's own path, which is always exempt. |
| A real browser (in-app) | Cloudflare's "Performing security verification" interstitial with a Turnstile **"Verify you are human"** checkbox. |

### Inferred

- **The rule.** It is a catch-all WAF custom rule with a Managed Challenge
  action, or Under Attack mode. The two look identical from outside. Managed
  Challenge escalates to the checkbox when browser signals look automated, which
  fits what an embedded browser got.
- **What gets through.** After a visitor passes once, Cloudflare sets a
  `cf_clearance` cookie, and every same-origin request rides on it, asset
  fetches included. That is why one rule can cover `/bundled/…` too.
- **What it stops.** `curl`/`wget`, `habbo-downloader`-style scripts and
  cross-site hotlinking.
- **What it does not stop.** Anyone who passes the challenge in a real or
  headless browser. After that the assets are as open as ours. Their
  protection is therefore edge-only and depends on Challenge Passage.

### Not visible from outside

Everything past the challenge stays unseen. We could not check whether their
asset requests also need a login, how they name files, their Challenge Passage
length, their Cloudflare plan, or their origin firewall. (Passing the challenge
isn't something we do.)

---

## 2. Where we are

| Fact | Where |
|---|---|
| `pixelrp.co` and `beta.pixelrp.co` are Cloudflare-proxied (NS `uriah`/`mallory`). There is no challenge: `curl` gets `200` for the site, `FigureMap.json` and `hh_human_body.nitro`. | measured |
| Every `/nitro-assets/` location and `/gamedata/` and `/imaging/` send `Access-Control-Allow-Origin *`, which was added for the Vite dev client. | `docker/web/nginx.conf:29-89` |
| Bundles are `Cache-Control: public, max-age=604800`; gamedata and config are `no-store`. | same |
| `cf-cache-status: DYNAMIC` on `.nitro` and `.json`: Cloudflare caches neither (neither extension is in its default cache list). **Every asset request therefore reaches our nginx**, and that is what makes an origin gate effective. | measured |
| `renderer-config.json` is public and lists every asset URL template. `FigureMap.json` and `FurnitureData.json` name every library. | `/nitro-assets/client/renderer-config.json` |
| **Origin firewall:** `67.219.109.182:443` refuses connections that don't come through Cloudflare. That IP is public through `play.pixelrp.co`, a grey-cloud record, so this firewall is the only thing stopping a Cloudflare bypass. Port 80 is open but only redirects. | measured, `docker/host/pixelrp.nginx.conf` |
| The game: `/game` (`NitroController`, logged in) renders a **same-origin iframe** at `setting('nitro_path')/index.html?sso=…`, so every asset request carries the player's cookies. | `cms/resources/themes/pixelrp/views/client/nitro.blade.php:25` |
| The game socket goes to `wss://play.pixelrp.co:2097` (beta), which is direct and outside Cloudflare. Nothing here touches it. | renderer-config |
| The imager pulls gamedata from `http://web/nitro-assets/…` over the Docker network. | `compose.yaml:159-161` |
| Public CMS pages show badges and furni icons from the asset tree (`badges_path`, `furniture_icons_path`). | `WebsiteSettingsSeeder.php`, `FurniIconService.php` |
| Cookies are encrypted by Laravel unless listed in `EncryptCookies::$except`. | `cms/app/Http/Middleware/EncryptCookies.php` |

---

## 3. The plan

Two kinds of files, two treatments:

- **Protected** (the value): `bundled/**` (figure, furniture, effect, pet,
  generic), `gamedata/*.json`, `sounds/`, `client/**` (the built client and its
  configs).
- **Public images**: `c_images/**` (badges) and `dcr/hof_furni/icons/**`. The
  website shows these to logged-out visitors. They stay public, protected only
  against hotlinking.

### Phase 0: measure (built in, 1 week)

The rate limits in Phase 3 must not hit real players, so first measure what a
real session looks like.

1. **Logging (built in).** Every gated request logs one `ASSET` line to the web
   container's stdout: `ASSET <client ip> <user id> [time] <status> <bytes>
   "<uri>"`, read with `docker logs`. The client IP is the host proxy's
   `X-Real-IP`, which it recovers from Cloudflare. Denied requests log with
   user `-`.
2. After a week, compute per account:
   - requests per 10 s (p99 and max);
   - distinct `bundled/furniture/*` per day;
   - distinct `bundled/figure/*` per day.

   These set the thresholds below. The expected shape: a busy-room entry bursts
   to a few hundred requests in seconds, and a heavy catalog browser reaches a
   few hundred distinct furni a day. A mirror needs about 18k furni.

### Phase 1: Cloudflare edge (dashboard only, the habrp equivalent)

**1a. Security Settings.**

- **Challenge Passage:** raise it from the default **30 min** to the longest
  dropdown value of at least **24 h**. Players then aren't re-challenged
  mid-session.
- **Hotlink Protection:** turn it **on**. It covers GIF, ICO, JPG/JPEG and PNG
  and blocks a non-blank Referer that isn't ours, which protects badges and
  icons.
- **Bot Fight Mode:** **leave it off.** It can't be skipped by any rule, it
  challenges API and non-browser traffic, and it would break the Stripe webhook.

**1b. WAF custom rule "Challenge the hotel", action Managed Challenge.**
Create it under Security, then WAF, then Custom rules, using "Edit expression".
This uses 1 of the Free plan's 5 custom rules; plain operators only, since
regex needs Business. Start with only `"beta.pixelrp.co"` in the host set, and
add `"pixelrp.co" "www.pixelrp.co"` once beta has been checked.

```
(http.host in {"pixelrp.co" "www.pixelrp.co" "beta.pixelrp.co"})
and cf.edge.server_port in {80 443}
and not starts_with(http.request.uri.path, "/nitro-assets/")
and not starts_with(http.request.uri.path, "/webhooks/")
and not starts_with(http.request.uri.path, "/api/")
and not starts_with(http.request.uri.path, "/imaging/")
and not cf.client.bot
```

Why each exclusion matters:

- **`server_port`:** keeps the proxied `:2096` sockets out. A WebSocket upgrade
  cannot solve a challenge.
- **`/nitro-assets/`:** Cloudflare documents that a challenge **fails for
  fetch/XHR requests that expect non-HTML**, and every asset is one. A player
  whose clearance lapsed would see the client die at the next lazy-loaded
  bundle. Assets are locked at the origin instead (Phase 2), where the lifetime
  is ours.
- **`/webhooks/`:** the Stripe server-to-server webhook
  (`/webhooks/diamonds-stripe`).
- **`/api/`:** public JSON (online count and friends) that other sites may poll.
  It already has Laravel throttles.
- **`/imaging/`:** avatar images that Discord and other sites embed.
- **`cf.client.bot`:** verified search and preview crawlers (Google, Discord's
  link unfurler).

**1c. Rate limiting rule.** The Free plan allows 1 rule, counted by IP, with a
10 s period and a 10 s timeout.

- **Match:** `starts_with(http.request.uri.path, "/nitro-assets/")`.
- **Threshold:** a request count above the Phase 0 p99 × 3 per 10 s. Expect
  around 300.
- **Action:** Block.

This only blunts a fast, single-IP scraper. The real limit is per account, in
Phase 3.

### Phase 2: origin gate, the asset pass

A signed cookie trio, checked by nginx's `secure_link` module. There is no PHP
on the hot path: nginx checks an MD5 HMAC, so the CMS is never called per
asset.

**CMS** (`cms/`):

1. **`App\Support\AssetPass::issue(User $user): array`.** Returns three cookies.
   - Values:
     - `prp_ap_u` = user id;
     - `prp_ap_e` = expiry, unix time, now + 24 h;
     - `prp_ap_s` = signature:

       ```php
       rtrim(strtr(base64_encode(md5("{$exp}{$uid} {$secret}", true)), '+/', '-_'), '=')
       ```
   - Attributes: `Path=/nitro-assets/` (so the CMS never receives them),
     `Secure`, `HttpOnly`, `SameSite=Lax`, host-only.
   - The secret is `ASSET_PASS_SECRET`, with a different value on beta and prod.
2. **`EncryptCookies::$except`:** add the three names. Without this, Laravel
   encrypts the values and nginx sees ciphertext, so every file returns 403.
3. **`NitroController`:** attach `AssetPass::issue()` to the `/game` response.
   The cookies land before the iframe asks for `index.html`.
4. **`GET /game/asset-pass`:** behind `auth`, `throttle:30,1`. Returns `204`
   with fresh cookies. It refuses a banned user, which is how a pass gets
   revoked.
5. **Housekeeping:** if the React panel loads anything under `/nitro-assets/`
   beyond icons and badges, issue the pass in its shell too. Check this during
   implementation; `MeController` currently passes only `badges_path`.

**Client** (`client/`): a refresher hook, mounted once in `App`:

```ts
fetch('/game/asset-pass', { credentials: 'same-origin' })
```

It lives in `src/api/assets/AssetPassRefresh.ts` and runs every **30 min**. The pass outlives any session shorter than 24 h
without it, and the refresher covers longer ones. There is no packet and no
emulator change.

**nginx** (`docker/web/`):

1. **The secret, without committing it.**
   - Mount `./docker/web/templates:/etc/nginx/templates:ro` and pass
     `ASSET_PASS_SECRET` to `web` and `cms`. The official `nginx:1.27-alpine`
     entrypoint runs `envsubst` over `templates/*.template` into `conf.d/`.
   - Where it comes from:
     - Locally, compose defaults it to `local-dev-asset-pass`.
     - `compose.prod.yaml` (prod and beta) uses
       `${ASSET_PASS_SECRET:?}`, so a box without it refuses to start rather
       than serving a broken game.
     - Both deploy workflows append a fresh
       `ASSET_PASS_SECRET=$(openssl rand -hex 32)` to the box's root `.env`
       if it is missing. Each box gets its own secret, and it never leaves
       the box.
   - `templates/asset-pass.conf.template`:

     ```nginx
     map "" $asset_pass_secret { default "${ASSET_PASS_SECRET}"; }
     ```
   - Then add `include /etc/nginx/conf.d/asset-pass.conf;` inside `http {}`.
     Include it by name, not `conf.d/*.conf`, which would also pull in the
     image's own `default.conf` server.
2. **`asset-gate.conf`**, included in every protected location:

   ```nginx
   secure_link     $cookie_prp_ap_s,$cookie_prp_ap_e;
   secure_link_md5 "$secure_link_expires$cookie_prp_ap_u $asset_pass_secret";
   if ($secure_link = "")  { return 403; }   # missing or forged
   if ($secure_link = "0") { return 403; }   # expired
   ```
3. **Protected locations:**
   - `gamedata/`;
   - the two configs;
   - `client/index.html`;
   - the general `/nitro-assets/`.

   In each one:
   - include the gate;
   - **delete `Access-Control-Allow-Origin *`**, which kills cross-site use of
     our bundles outright;
   - change `public` to **`private`** in `Cache-Control`, so no shared cache
     (Cloudflare included) ever stores a gated file.

   Add two **ungated** locations ahead of them: `/nitro-assets/assets/c_images/`
   and `/nitro-assets/assets/dcr/hof_furni/icons/`. Hotlink Protection covers
   these.
4. **An internal server for the imager.** Add `server { listen 8088; … }`,
   serving `/nitro-assets/` ungated. It is not published in `ports:`, so it is
   reachable only on the compose network. Point the imager's `AVATAR_*_URL` at
   `http://web:8088/…`. There is no IP allowlist to maintain.
5. **Never add a Cloudflare Cache Rule for `/nitro-assets/` while the gate is
   on.** A cached object is served from the edge without ever reaching the
   check.

**Local development:**

- Vite already proxies `/nitro-assets` to the local web container
  (`localhost:8080`) and uses relative URLs, so it was never using the CORS
  wildcard.
- The gate is on locally too, with the default secret. Open
  `localhost:8080/game` once to get a pass. Cookies ignore the port, so
  `:5173`'s proxied requests carry it.

### Phase 3: per-account limit and detection

1. **Rate limit, nginx.** Key the limit on the verified user id:
   `limit_req_zone $cookie_prp_ap_u zone=assets_user:10m rate=<p99>r/s;`, then
   `limit_req zone=assets_user burst=<Phase 0 max burst> nodelay;` in the
   protected locations.
   - The rewrite-phase `if` (the gate) runs **before** `limit_req`, so only a
     verified id is ever a key.
   - Return `429`.
2. **Logging.** Add `$cookie_prp_ap_u` to `assets.log`, so every file is now
   attributed to an account.
3. **Nightly detector.** A script (cron on the box, or `docker/nitro/`)
   counts distinct `bundled/furniture/*` and `bundled/figure/*` per user per
   day. Above the threshold (Phase 0 max × 5, expected around 2,000 furni), it
   posts to the staff Discord webhook with the user, counts and IPs.
4. **Revocation without a deploy.**
   - Add `map $cookie_prp_ap_u $asset_denied { include /etc/nginx/asset-deny.map; default 0; }`
     and `if ($asset_denied) { return 403; }` in the gate.
   - Adding a line and reloading nginx cuts an account off instantly.
   - Banning them in the CMS stops new passes.

### Phase 4: optional, later

- **Turnstile on registration.** `config/turnstile.php` is already wired. It
  makes the burner accounts that Phase 3 forces scrapers to use expensive.
- **Provenance markers in our own custom bundles** (Kasja, Zara, designer
  furni): an inert asset or metadata key unique to us, which proves a leaked
  pack came from here.
- **Not recommended.**
  - **Encrypting `.nitro` bundles.** It means patching the renderer's loader,
    and the key ships in the JS anyway.
  - **Opaque library names.** Scrapers read our own `FigureMap`, so renaming
    adds churn for no protection.

---

## 4. Rollout and verification (beta first)

1. **Phase 0** logging: deploy and wait a week.
2. **Phase 1** on Cloudflare, scoped to `beta.pixelrp.co` first (the host
   condition).
   - `curl https://beta.pixelrp.co/` → `403 cf-mitigated: challenge`.
   - `curl -X POST …/webhooks/diamonds-stripe` → the app's own signature error,
     not a challenge. Send a Stripe test event too.
   - The game socket still connects. Discord unfurls a profile link with its
     avatar.
3. **Phase 2** on beta.
   - `curl` `FigureMap.json`:
     - without cookies → `403`;
     - with the three `prp_ap_*` cookies copied from a logged-in browser →
       `200`;
     - with a forged `prp_ap_s` or an edited `prp_ap_u` → `403`;
     - with a copied pass the next day → `403` (expired).
   - In the game's DevTools, `fetch('/game/asset-pass')` → `204` with three
     fresh `Set-Cookie`s. The client makes the same call by itself every
     30 min.
   - Log in and play: a busy room, the catalog, the avatar editor, a pet, an
     effect. Look for missing sprites and 403s in the network tab.
   - The imager still renders (`/imaging/?figure=…`).
   - Logged out: the Rare Values icons and profile badges still show.
   - From another origin: `fetch()` of a `.nitro` is blocked by CORS.
4. **Phase 3** with thresholds from Phase 0.
   - Run a scripted pull of 3,000 furni with a copied pass → `429`s, then the
     detector flags it the next night.
   - A deny-map entry → instant `403`.
5. **Prod** arrives with the next `main` promotion.
   - Its deploy creates prod's own secret.
   - Its asset tree is maintained apart from the overrides rsync; the gate
     covers whatever is there.
   - The Cloudflare rule's host set gains `pixelrp.co` and `www.pixelrp.co`.
   - Players already in the game when it deploys keep running until their next
     lazy load, then need one reload of `/game` to pick up a pass. Prod's
     deploy disconnects everyone anyway.

## 5. Things that break if done naively

- **Challenging `/nitro-assets/` at the edge**, as habrp does. The client dies
  whenever `cf_clearance` lapses, because fetches can't solve a challenge.
  Lock assets at the origin.
- **Leaving out `EncryptCookies::$except`.** Every file returns 403 for
  everyone.
- **Bot Fight Mode.** It can't be exempted and challenges the Stripe webhook.
- **A Cloudflare Cache Rule on assets.** Cached files skip the gate.
- **Gating `c_images` / `hof_furni/icons`.** Public website images break for
  logged-out visitors.
- **Gating the imager's internal fetches.** Every avatar image breaks. Use the
  `:8088` internal server.
- **Opening `:443` to the world.** `play.pixelrp.co` publishes the origin IP,
  so the Cloudflare-only firewall on 443 is part of this design. Keep it.
