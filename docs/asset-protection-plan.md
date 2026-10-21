# Asset protection plan

How habrp.com keeps its assets away from scrapers, what we expose today, and a
phased plan to close the gap. Observations are from 2026-10-15.

**Scope:** beta and prod, on Cloudflare's **Free** plan.

**Status:**
- **Phase 2, the asset pass:** built on `feat/asset-protection` (parent, cms,
  client). Each box's secret is made by its deploy workflow on first run.
- **Phase 0 logging:** built in, now per account instead of per IP.
- **Phase 1:** dashboard steps, below.
- **Phase 3:** the daily furni allowance (item 1) is built, sized from two
  weeks of the host proxy's logs (2026-10-06 to 10-20). So is the browser
  guard pause (item 5). The nightly detector and the deny map are not built
  yet.

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
and http.request.method in {"GET" "HEAD"}
and not starts_with(http.request.uri.path, "/nitro-assets/")
and not starts_with(http.request.uri.path, "/gamedata/")
and not starts_with(http.request.uri.path, "/assets/")
and not starts_with(http.request.uri.path, "/build-housekeeping/")
and not starts_with(http.request.uri.path, "/api/")
and not starts_with(http.request.uri.path, "/imaging/")
and not starts_with(http.request.uri.path, "/housekeeping/api/")
and not starts_with(http.request.uri.path, "/game/asset-pass")
and not starts_with(http.request.uri.path, "/home/")
and not cf.client.bot
```

The rule's principle is **challenge page loads, never what a loaded page
fetches.** A challenge can only be solved by a page the browser navigates to.
Cloudflare documents that it fails for any request expecting something other
than HTML, so a fetch, an image or a script answered with a challenge is
simply a `403`. Normally a page's subresources ride on the `cf_clearance` the
page just earned. But a tab opened before the rule existed, or a game client
left open past Challenge Passage, has no valid clearance, and every such
request breaks. The first version of this rule broke the client's asset pass
renewal exactly that way (`403` on `/game/asset-pass` in the console).

Why each condition matters:

- **`server_port`:** keeps the proxied `:2096` sockets out. A WebSocket upgrade
  cannot solve a challenge.
- **`GET`/`HEAD` only:** every POST is either a form or a fetch from a page
  that was itself challenged, and Laravel's CSRF token can only be had from
  such a page. So a bot still cannot post a login, a purchase or a message
  without first passing a challenge. This covers the Diamonds checkout, badge
  purchase, the logo generator, the home editor's saves and the Stripe webhook.
  The webhook is a server-to-server POST, excluded from CSRF and verified by
  its Stripe signature.
- **`/nitro-assets/`:** game files, locked at the origin instead (Phase 2),
  where the lifetime is ours.
- **`/gamedata/`, `/assets/`, `/build-housekeeping/`:** static files: uploaded
  images, camera photos, badges, the CMS theme and the housekeeping build.
  Nothing a scraper wants, and all of it loaded by pages rather than visited.
- **`/api/`:** public JSON (online count and news images) that the client and
  other sites fetch. It already has Laravel throttles.
- **`/imaging/`:** avatar images that Discord and other sites embed.
- **`/housekeeping/api/`, `/game/asset-pass`, `/home/`:** session-authenticated
  GET fetches from the housekeeping panel, the game client and the home
  editor. `/home/` also covers the public home pages, which is harmless.
- **`cf.client.bot`:** verified search and preview crawlers (Google, Discord's
  link unfurler).

**Adding a GET endpoint the page fetches** (rather than navigates to) means
adding its prefix here, or it fails for anyone without clearance.

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

1. **`App\Support\AssetPass::issue(User $user): array`.** Returns four cookies.
   - Values:
     - `prp_ap_u` = user id;
     - `prp_ap_e` = expiry, unix time, now + 1 h (`ASSET_PASS_TTL`; it was
       24 h until October 2026);
     - `prp_ap_t` = tier: `staff` for Developers only
       (`AssetPass::UNLIMITED_RANK`), otherwise `player` (Phase 3's furni
       allowance);
     - `prp_ap_s` = signature over the other three, space-separated:

       ```php
       rtrim(strtr(base64_encode(md5("{$exp} {$uid} {$tier} {$secret}", true)), '+/', '-_'), '=')
       ```
   - Attributes: `Path=/nitro-assets/` (so the CMS never receives them),
     `Secure`, `HttpOnly`, `SameSite=Lax`, host-only.
   - The secret is `ASSET_PASS_SECRET`, with a different value on beta and prod.
2. **`EncryptCookies::$except`:** add the four names. Without this, Laravel
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

It lives in `src/api/assets/AssetPassRefresh.ts` and runs every **30 min**,
half the pass's 1 h lifetime, retrying every 5 min if a renewal fails and at
once when the tab comes back. There is no packet and no emulator change.

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
   secure_link_md5 "$secure_link_expires $cookie_prp_ap_u $cookie_prp_ap_t $asset_pass_secret";
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

1. **Daily furni allowance, nginx + njs (built).** Each non-staff account may
   fetch **2,000 different furni files a day** (UTC). After that, new furni
   files answer `429` until midnight.
   - **What the logs showed.** Two weeks of the host proxy's access log
     (2026-10-06 to 10-20), with IPv6 grouped by /64:
     - The heaviest real day was about **300 different furni files**, staff
       included.
     - Clothing was **2,000 to 4,800 a day**, most of the ~3,800 libraries,
       because the wardrobe loads them as it scrolls.
     - Entering a busy room fired up to **1,100 requests in 10 s**.
   - **Why it counts furni only.** A request-rate limit (`limit_req`) can't
     tell those room-entry bursts from a scraper. A clothing count would catch
     ordinary wardrobe use. Furni (~22,900 files) is where a copy stands out:
     2,000 is about 7× the heaviest real day, and a full copy takes one account
     more than a week.
   - **What counts.** Only *different* files count. A file the account already
     fetched today is free, so reloads, cleared caches and a second tab cost
     nothing. Files already fetched keep loading after the allowance runs out,
     and clothing is never limited.
   - **Staff.** Developers (`AssetPass::UNLIMITED_RANK`) carry
     `prp_ap_t=staff` and have no allowance, so import work is never cut off;
     every other rank, staff included, gets the allowance. The tier is
     signed, so a player can't set it.
   - **How it works.** `docker/web/njs/asset-limit.js`, run through
     `js_set $asset_furni_over` in its own `bundled/furniture/` location,
     right after the gate's `if`s. Only a verified pass is ever counted.
   - **Where the counts live.** Two `js_shared_dict_zone`s: one entry per
     account per file per day, and one count per account per day. They are in
     memory, so they start over whenever the web container is recreated (every
     beta deploy).
2. **Logging (built).** `assets.log` carries `$cookie_prp_ap_u` and
   `$cookie_prp_ap_t`, so every file is attributed to an account and its tier,
   and a refused furni file logs as `429`.
3. **Nightly detector.** A script (cron on the box, or `docker/nitro/`)
   counts distinct `bundled/furniture/*` and `bundled/figure/*` per user per
   day. Above the threshold (Phase 0 max × 5, expected around 2,000 furni), it
   posts to the staff Discord webhook with the user, counts and IPs.
4. **Revocation without a deploy.**
   - Add `map $cookie_prp_ap_u $asset_denied { include /etc/nginx/asset-deny.map; default 0; }`
     and `if ($asset_denied) { return 403; }` in the gate.
   - Adding a line and reloading nginx cuts an account off instantly.
   - Banning them in the CMS stops new passes.
5. **Browser guard pause (built).** The client's browser guard (DevTools
   opened, or an automated browser) already sends the player back to the
   website, and the emulator writes it in `rp_browser_guard_log`. For
   **30 minutes** after the latest catch (`ASSET_GUARD_PAUSE_MINUTES`), the
   whole account gets no game file at all.
   - **Why.** The guard only watches the game page. The pass cookies are sent
     by any page on the site, so without this a script pasted into DevTools on
     the website could carry on downloading where the game left off.
   - **CMS.** `App\Support\AssetPause` reads the log. A guard row is per
     character; the pause is per account (`COALESCE(parent_id, id)`, as the
     pass is). Staff are never paused.
     - `/game` shows the ordinary "Connection lost" screen and issues no
       ticket or pass. It never says why, so a player isn't told what was
       caught.
     - `/game/asset-pass` answers `403` with no cookies.
     - `GET /api/internal/asset-pauses` lists `<account> <unix end>` per
       line. It needs the asset pass secret in `X-Asset-Pass-Secret`.
   - **nginx.**
     - `js_periodic` asks that route every 10 s, from inside the container,
       and keeps the list in the `asset_paused` dict.
     - The gate answers `403` to a paused account, whatever page asks.
     - An answer that doesn't come leaves the last list standing.
     - `location ~ /api/internal/` lets only `127.0.0.1` through, so the
       public never reaches the route.
   - **The limit.** The report comes from the client, so a player who blocks
     it is never paused. It can only ever pause the reporting account itself.

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
     - with the four `prp_ap_*` cookies copied from a logged-in browser →
       `200`;
     - with a forged `prp_ap_s` or an edited `prp_ap_u` → `403`;
     - with a copied pass an hour later → `403` (expired).
   - In the game's DevTools, `fetch('/game/asset-pass')` → `204` with four
     fresh `Set-Cookie`s. The client makes the same call by itself every
     30 min.
   - Log in and play: a busy room, the catalog, the avatar editor, a pet, an
     effect. Look for missing sprites and 403s in the network tab.
   - The imager still renders (`/imaging/?figure=…`).
   - Logged out: the Rare Values icons and profile badges still show.
   - From another origin: `fetch()` of a `.nitro` is blocked by CORS.
4. **Phase 3** on beta.
   - Run a scripted pull of 3,000 furni with a copied player pass → `200` for
     the first 2,000 different files, then `429`. Re-fetching one of the first
     2,000 is still `200`, and so is a figure bundle.
   - The same pull with a staff pass → all `200`.
   - A player pass with `prp_ap_t` edited to `staff` → `403`.
   - The detector flags the pull the next night (once it is built).
   - Press F12 in the game as a player. The guard sends you to the website,
     and `/game` then shows "Connection lost". A copied pass gets `403` on
     every file within 10 s. After 30 minutes it all loads again. A staff
     account is never paused.
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
