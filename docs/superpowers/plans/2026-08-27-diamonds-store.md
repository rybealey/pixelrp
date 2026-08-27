# Diamonds Store Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An in-game Diamonds Store window (opened from the toolbar diamonds button) with a Store tab (unpopulated for now) and a Buy Diamonds tab that sells diamonds for real money at 100 diamonds = $1 USD through Stripe's embedded Checkout, crediting online players live.

**Architecture:** The nitro client window mirrors the provided competitor layout. Checkout is Stripe embedded (`ui_mode: 'embedded'`), backed by two standalone Laravel routes in the CMS (session-create + webhook) that deliberately do NOT touch the existing CMS shop system (packages/vouchers/website_balance stay untouched). Crediting is RCON-first (live, in-memory + DB via the emulator's existing `give_user_currency` command) with a direct-DB fallback for offline players — enabled by a new JSON dialect + response ack in the emulator's RCON listener, which the CMS's existing Arcturus-style RCON client already speaks.

**Tech Stack:** nitro-react + patched renderer (client submodule), Laravel/atomcms (cms submodule), PlusEMU (emulator submodule), stripe/stripe-php, Stripe.js embedded Checkout (test-mode keys first).

## Global Constraints

- Pricing: **1 diamond = 1 US cent** (100 diamonds = $1.00). Currency USD everywhere.
- Diamonds live in `users.vip_points` AND in-memory (`Habbo.Diamonds`) for online players, which is written back on logout — **crediting an online player via SQL alone is a lost write**. Online credits MUST go through emulator RCON (`give_user_currency` updates memory + DB + sends the purse composer); offline credits go direct to DB. The RCON ack (Task 1) is what makes "online path succeeded" knowable.
- The existing CMS shop (PayPal, packages, `website_balance`, `PurchaseShopPackage`, force-disconnect crediting) is OFF LIMITS — no reuse, no modification.
- No em/en-dashes in any in-game string (Habbo fonts render them as a music note) — plain hyphens.
- New dark chrome surfaces paint from `--prp-chrome-*` vars; the window tab strip uses the shared `prp-chrome-tab-strip` mixin like every other tabbed window.
- Stripe secrets are VPS-only `.env` values (never committed): `STRIPE_KEY` (publishable), `STRIPE_SECRET`, `STRIPE_WEBHOOK_SECRET`. The publishable key reaches the client in the checkout-session response — never bake it into the bundle.
- Webhook crediting must be idempotent (an order row transitions `pending → paid` exactly once; Stripe retries must not double-credit).
- Verification gates: emulator = docker dotnet build 0 errors; client = `yarn build` + `npx tsc --noEmit` (only the two pre-existing `motto` errors allowed); CMS = `php -l` on each changed file (no local composer runtime assumed) plus careful reading — flag in the handoff that the CMS deploy runs composer install/migrations.
- Commits per submodule branch `pixelrp` (client, emulator), `master`-equivalent branch for cms (check `git -C cms branch --show-current` — commit on the branch the submodule tracks), pointer bumps on superproject `beta`. Push only when Ry says push.
- The client window fetches the CMS over the SAME origin (beta.pixelrp.co) with `credentials: 'include'`; POSTs carry the `X-XSRF-TOKEN` header read from Laravel's `XSRF-TOKEN` cookie. The webhook route is excluded from CSRF.

---

### Task 1: Emulator — RCON JSON dialect + response ack

**Files:**
- Modify: `emulator/Communication/RCON/Commands/CommandManager.cs`
- Modify: `emulator/Communication/RCON/RCONConnection.cs`
- Read first (context): `cms/app/Services/RconService.php` (`sendCommand`, `parseResponse`) — the dialect being matched.

**Interfaces:**
- Consumes: existing `IRconCommand` registry (keys like `give_user_currency`, `alert_user`... — enumerate with `grep -rn "public string Key" emulator/Communication/RCON/Commands/`).
- Produces: the RCON socket accepts BOTH dialects: (a) legacy `command\x01p1:p2` (unchanged, no response), and (b) JSON `{"key": "<name>", "data": {...}}` — mapped to a registered command, executed, and answered with a single JSON line the CMS's `parseResponse` accepts, then the connection closes. CMS command names map to PlusEMU keys at minimum: `givepoints` → `give_user_currency` (data: user_id, points, type → params [user_id, currency-name, points]; type 5 or "diamonds" → "diamonds", 0/"duckets" → "duckets", -1/"credits" → "credits"), `givecredits` → `give_user_currency` credits, `alertuser` → whatever key `AlertUserCommand` declares, `disconnect` → `DisconnectUserCommand`'s key.

- [ ] **Step 1: Read the CMS response contract**

Read `cms/app/Services/RconService.php:124-160` (`parseResponse`) fully and note exactly which JSON shape counts as success (it decodes the response, then inspects fields — mirror whatever it accepts; if it accepts any decodable JSON with a status-ish field, respond `{"status":"success"}` / `{"status":"error","message":"..."}`; match what the code actually checks, not this plan's guess).

- [ ] **Step 2: JSON branch in CommandManager.Parse**

In `CommandManager.cs`, add a public method `ParseJson(string payload, out string response)` (keep `Parse` untouched for the legacy path): `System.Text.Json`-parse `{key, data}`; translate CMS names → PlusEMU command keys + positional parameter arrays per the mapping above; unknown key → error response. Execute via the existing `_commands` dictionary. Return true/false with the response JSON in the out param.

- [ ] **Step 3: Respond from RCONConnection**

In `RCONConnection.cs`, where the buffer is decoded: if the trimmed payload starts with `{`, route to `ParseJson` and `Send`/write the response bytes back on the socket before closing (the CMS reads until the emulator shuts the connection — mirror how the socket currently closes and make sure the response is flushed first). Legacy payloads keep the exact current behavior.

- [ ] **Step 4: Compile (docker dotnet build, 0 errors); commit** `feat: RCON speaks the CMS JSON dialect with a response ack`

---

### Task 2: CMS — Stripe checkout session + webhook + crediting (standalone)

**Files:**
- Modify: `cms/composer.json` (+ run `composer require stripe/stripe-php` if a local composer exists; otherwise add the requirement line + note that the deploy's composer install resolves it — check how the cms Docker image installs deps: `grep -rn composer docker/cms/Dockerfile ../docker/cms/Dockerfile 2>/dev/null` from cms/)
- Modify: `cms/config/services.php` (stripe block: `key`, `secret`, `webhook_secret` from env)
- Create: `cms/database/migrations/2026_08_27_000000_create_website_diamond_orders_table.php`
- Create: `cms/app/Http/Controllers/Diamonds/DiamondCheckoutController.php`
- Create: `cms/app/Http/Controllers/Diamonds/DiamondStripeWebhookController.php`
- Create: `cms/app/Services/DiamondCreditService.php`
- Modify: `cms/routes/web.php` (auth'd session-create route), `cms/routes/api.php` or web.php (webhook route), CSRF exclusion for the webhook (find the middleware: `grep -rn "except" cms/app/Http/Middleware/VerifyCsrfToken.php` or the Laravel 11-style `bootstrap/app.php` `validateCsrfTokens(except:)`)

**Interfaces:**
- Consumes: `App\Contracts\Rcon` (now functional against the emulator after Task 1), `App\Models\User`, `stripe/stripe-php`.
- Produces (consumed by Task 4's client):
  - `POST /diamonds/checkout-session` (auth + throttle:10,1) body `{ diamonds: int }` → `200 { clientSecret, publishableKey }` or `422 { message }`.
  - `POST /webhooks/diamonds-stripe` → Stripe webhook (signature-verified), idempotent crediting.
  - Table `website_diamond_orders`: id, user_id (indexed), diamonds int, amount_cents int, currency char(3) default 'usd', stripe_session_id (unique), status enum/string ('pending','paid','failed') default 'pending', paid_at nullable timestamp, timestamps.

- [ ] **Step 1: Migration + config + composer requirement** (shapes above; follow neighboring migrations' style)

- [ ] **Step 2: DiamondCheckoutController**

Validation: `diamonds` required integer, min 100, max 100000, multiple of 100 (`'integer','min:100','max:100000',` + closure or `multiple_of:100`). Create the Stripe session:
```php
\Stripe\Stripe::setApiKey(config('services.stripe.secret'));
$session = \Stripe\Checkout\Session::create([
    'ui_mode' => 'embedded',
    'mode' => 'payment',
    'redirect_on_completion' => 'never',
    'line_items' => [[
        'quantity' => 1,
        'price_data' => [
            'currency' => 'usd',
            'unit_amount' => $diamonds, // 1 diamond = 1 cent
            'product_data' => ['name' => $diamonds . ' Diamonds'],
        ],
    ]],
    'metadata' => ['user_id' => $user->id, 'diamonds' => $diamonds],
]);
```
Insert the pending `website_diamond_orders` row (session id, user, diamonds, amount), return `['clientSecret' => $session->client_secret, 'publishableKey' => config('services.stripe.key')]`.

- [ ] **Step 3: Webhook controller**

Verify with `\Stripe\Webhook::constructEvent($request->getContent(), $request->header('Stripe-Signature'), config('services.stripe.webhook_secret'))` (400 on failure). On `checkout.session.completed` with `payment_status === 'paid'`: inside a DB transaction, load the order by `stripe_session_id` with `lockForUpdate()`; if missing or status !== 'pending', return 200 (idempotent no-op); mark `paid` + `paid_at`, then call `DiamondCreditService::credit($order)`. Always 200 on handled events.

- [ ] **Step 4: DiamondCreditService**

```php
public function credit(WebsiteDiamondOrder $order): void
{
    $user = User::find($order->user_id);
    if (! $user) return; // orphan order: log it
    if ($user->online) {
        try {
            $this->rcon->sendCommand('givepoints', [
                'user_id' => $user->id,
                'points' => $order->diamonds,
                'type' => 5, // diamonds (CurrencyTypes::Diamonds)
            ]);
            return; // ack received: emulator updated memory + DB + purse
        } catch (RconConnectionException) {
            // fall through to DB fallback below
        }
    }
    DB::table('users')->where('id', $user->id)->increment('vip_points', $order->diamonds);
}
```
Caveat to encode in a comment: if the RCON path fails for an ONLINE user, the DB fallback can still be overwritten by that user's logout write-back — log a warning naming the order id in that branch so a support script can reconcile. (Do not force-disconnect; that is the CMS shop's approach and it is off limits.)

- [ ] **Step 5: Routes** — session-create inside the authenticated web group (find the group wrapping existing authenticated shop-ish routes and place a standalone `diamonds` prefix OUTSIDE the shop groups); webhook route public + CSRF-excluded + `->withoutMiddleware(...)` as the codebase style dictates (mirror how the PayPal webhook route is registered: `grep -n paypal cms/routes/web.php`).

- [ ] **Step 6: `php -l` every changed file; commit** `feat: standalone Stripe diamonds purchase flow`

---

### Task 3: Client — Diamonds Store window (layout only)

**Files:**
- Create: `client/src/components/diamonds-store/DiamondsStoreView.tsx`
- Create: `client/src/components/diamonds-store/DiamondsStoreView.scss`
- Modify: `client/src/components/index.scss` (import), `client/src/components/main/MainView.tsx` or wherever sibling top-level views mount (find where `<MusicPlayerView />`'s ancestors mount top-level windows: `grep -rn "PhoneView" client/src/components/main/MainView.tsx` — mount beside `<PhoneView />`)
- Modify: `client/src/components/toolbar/ToolbarView.tsx` (wire the diamonds button)

**Interfaces:**
- Consumes: `NitroCardView`/`NitroCardHeaderView`/`NitroCardTabsView`/`NitroCardTabsItemView`/`NitroCardContentView`, `Button`, `LocalizeText` not needed (plain labels), link-event pattern (`AddEventLinkTracker`).
- Produces: window opens/closes via `CreateLinkEvent('diamonds-store/toggle')`; internal state `currentTab: 'store' | 'buy'`; the Buy tab exposes `diamonds` (number input, default 300), computed `totalCents = diamonds` and `$ total = (diamonds / 100).toFixed(2)`, an accept toggle, and a `Purchase $X.XX` button disabled until the toggle is on — Task 4 wires the button.

- [ ] **Step 1: Window component** — `NitroCardView uniqueKey="diamonds-store" className="nitro-diamonds-store" theme="primary-slim"`, header "Diamonds Store", tabs Store / Buy Diamonds (chrome tab strip via the shared mixin in the SCSS). Store tab content: a quiet empty state (`Nothing here yet - diamond items are coming soon.`). Buy tab, mirroring the screenshot top-to-bottom: "BUY DIAMONDS" section header; label DIAMONDS + `<input type="number" step={100} min={100} max={100000}>`; summary rows (`Diamonds` → count, `Total` → `$X.XX`); the acceptance row `I accept that all purchases are final, and are non-refundable.` with a toggle (styled checkbox/switch); full-width `Purchase $X.XX` button (disabled until accepted; no-op this task). Link tracker for `diamonds-store/show|hide|toggle` following PhoneView's tracker pattern.
- [ ] **Step 2: Toolbar wiring** — `onClick={ event => CreateLinkEvent('diamonds-store/toggle') }` on the existing `icon-diamonds` Base (ToolbarView.tsx:95).
- [ ] **Step 3: SCSS** — window ~420px wide; tab strip via `@include prp-chrome-tab-strip` under `&.theme-primary-slim .nitro-card-tabs, .nitro-card-tabs`; content is a standard light nitro card (match the screenshot's plain form look); summary rows as label/value flex rows; toggle styled as a small switch.
- [ ] **Step 4: Build + tsc; commit** `feat: Diamonds Store window - layout, tabs, buy form`

---

### Task 4: Client — Stripe embedded checkout wiring

**Files:**
- Create: `client/src/components/diamonds-store/useStripeCheckout.ts`
- Modify: `client/src/components/diamonds-store/DiamondsStoreView.tsx` + `.scss`

**Interfaces:**
- Consumes: Task 2's `POST /diamonds/checkout-session` contract; `https://js.stripe.com/v3` (singleton script loader, same pattern as the jukebox's IFrame API loader).
- Produces: clicking Purchase swaps the Buy tab's form for a mounted Stripe embedded Checkout; `onComplete` → success state ("Diamonds delivered - enjoy!") with a Done button returning to the form; errors surface inline (session-create failure, Stripe load failure).

- [ ] **Step 1: useStripeCheckout** — `loadStripeJs()` singleton promise (script tag, resolves on load); `createSession(diamonds)`:
```ts
const xsrf = decodeURIComponent((document.cookie.match(/XSRF-TOKEN=([^;]+)/) || [])[1] ?? '');
const response = await fetch('/diamonds/checkout-session', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-XSRF-TOKEN': xsrf },
    body: JSON.stringify({ diamonds })
});
```
non-OK → throw with the JSON message. Then `const stripe = window.Stripe(publishableKey); const checkout = await stripe.initEmbeddedCheckout({ clientSecret, onComplete }); checkout.mount(container);` — return a handle whose `destroy()` unmounts (embedded checkout instances have `destroy()`; call it on window close/tab switch, and never mount two at once).
- [ ] **Step 2: View states** — `'form' | 'checkout' | 'complete' | 'error'`; the checkout state renders a container div (min-height ~460px; the window grows for it) and mounts on entry, destroys on exit/unmount. Keep the accept toggle requirement before entering checkout.
- [ ] **Step 3: Build + tsc; commit** `feat: Stripe embedded checkout in the Diamonds Store`

---

### Task 5: Changelog, pointer bumps, handoff notes

- [ ] **Step 1: CHANGELOG** (superproject, current dated section, Added):
```markdown
- **The Diamonds Store opens its doors.** The diamonds button next to the
  phone now opens the new store window. The shelves are still being
  stocked, but the Buy Diamonds tab already works: pick an amount (100
  diamonds per dollar) and pay by card right inside the window.
```
- [ ] **Step 2: Commit submodules, bump pointers on beta** (message `feat: Diamonds Store with Stripe checkout (bump client, cms, emulator)`). Do NOT push without Ry's go-ahead.
- [ ] **Step 3: Handoff checklist for Ry** (include in the final report):
  1. VPS `.env` for the cms container needs `STRIPE_KEY=pk_test_...`, `STRIPE_SECRET=sk_test_...`, `STRIPE_WEBHOOK_SECRET=whsec_...` (non-git deploy item), then restart cms.
  2. Stripe dashboard (test mode): add webhook endpoint `https://beta.pixelrp.co/webhooks/diamonds-stripe` for event `checkout.session.completed`; copy the signing secret into the env.
  3. Deploy runs the cms migration + composer install — verify `website_diamond_orders` exists after deploy.
  4. Test with card `4242 4242 4242 4242`, any future date/CVC: buy 300 diamonds ($3.00), confirm the purse updates live in-game without relog, `website_diamond_orders` row flips to `paid`, and a Stripe webhook redelivery does NOT double-credit.
