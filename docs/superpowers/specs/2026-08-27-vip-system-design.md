# VIP System — Design

**Date:** 2026-08-27
**Branch:** `feat/vip`
**Status:** Approved pending final spec review

## Summary

A real, time-based VIP membership built on the emulator's existing (dormant) HC/club
plumbing. Single tier, timed and stackable. Players buy **VIP tokens** with diamonds
from the Diamonds Store's **Store** tab; tokens land in the RP Backpack and are
redeemed by clicking them, granting VIP for a fixed duration. VIP lights up the stock
Nitro HC surface (clothing, dances, bubbles, purse/HC Center) plus fork-specific perks
(camera, extra backpack slots, daily stipend, flair).

Two SKUs at launch:

| Token | Duration | Default price | Icon |
|---|---|---|---|
| `vip_token_31` | 31 days | 500 diamonds | gold VIP token |
| `vip_token_14` | 14 days | 250 diamonds | silver VIP token |

Daily stipend: **5 diamonds/day** while active, granted on first login each calendar day.

## Context (what exists today)

- PlusEMU has no time-based club. `users.rank_vip` is a static tier (defaults to 1),
  and a fully built but unused permission dimension exists:
  `subscriptions` + `permissions_subscriptions` (+ `permissions_commands.subscription_id`).
- "HC disabled" is actually five hardcodes: club level hardcoded to `2` for everyone
  (`UserRightsComposer.cs:19`), figure validation always passes `hasHabboClub: true`
  (4 call sites), `ScrSendUserInfoComposer` is a stub (0 days), the HC window handler
  is a no-op, and the HC purchase packets throw / are `[StaffOnly]`.
- The Nitro client's HC plumbing is stock and intact, keyed off the club level from
  `UserRightsComposer`. `hc.disabled` is `false` in `ui-config.json`.
- The RP Backpack already exists: `RpInventoryView` (client), `RpInventoryEvent` /
  `RpUseItemComposer` / `RpUseItemEvent` (live slot snapshots, click-to-consume,
  peek-before-consume discipline). 12 carry slots, last 2 locked.
- Diamonds are `users.vip_points`, sold for real money via the CMS Stripe store.
- Consequence of shipping: "free HC for everyone" ends. Non-VIPs keep their current
  outfit (soft lapse) but lose access to HC clothing/dances/bubbles until they buy VIP.

## Decisions

- **Acquisition:** diamonds only, via VIP tokens in the Diamonds Store's Store tab.
- **Tier:** single tier. Active VIP presents as club level 2 (VIP) to the client.
- **Duration:** timed, stackable — redeeming extends `max(now, current_expiry) + days`.
- **Expiry:** soft lapse. Keep what's equipped; block new use. No grace period.
- **Perks:** identity flair, exclusive clothing, camera, extra backpack slots,
  daily stipend.
- **Store pricing:** every listing has a default `price` and a nullable
  `special_price`; when set, `special_price` is the charged price and the client
  renders the default struck through with a sale tag.

## Data model (emulator DB, numbered migration in `Resources/SQLs/Updates/`)

New columns on `users`:

- `vip_expire` BIGINT NOT NULL DEFAULT 0 — unix timestamp; source of truth for VIP.
- `vip_last_stipend` DATE NULL — last calendar day the stipend was granted.

New table `diamonds_store_items`:

- `id`, `item_key` (unique, e.g. `vip_token_31`), `name`, `description`,
  `icon` (client icon class suffix), `price` INT, `special_price` INT NULL,
  `vip_days` INT NOT NULL DEFAULT 0 (0 = not a VIP token),
  `enabled` BOOLEAN DEFAULT TRUE, `sort_order` INT.
- Seeded with the two token rows above.

New table `diamonds_store_purchases` (audit trail):

- `id`, `user_id`, `item_key`, `diamonds_paid`, `created_at`.

`server_settings` row: `vip.stipend.daily` = `5`.

The static `users.rank_vip` column stops being read. `Habbo.VipRank` becomes derived:
`IsVip ? 1 : 0`, where `IsVip => vip_expire > UnixNow`. All existing `VipRank` gates
(catalog `min_vip`, respect allowance, `permissions_subscriptions` → `silver_vip`,
`permissions_commands.subscription_id`) inherit real semantics with no changes.

## Emulator

### Store packets (new, NOT `[StaffOnly]`)

- `GetDiamondsStoreEvent` → `DiamondsStoreComposer`: sent when the Store tab opens;
  lists enabled items with `item_key, name, description, icon, price, special_price`.
- `PurchaseDiamondsStoreItemEvent(item_key)`:
  1. Look up item; must exist and be enabled.
  2. Effective price = `special_price ?? price`; require `Diamonds >= effective`.
  3. Require a free unlocked backpack slot (respecting the VIP slot rule below).
  4. Deduct diamonds, persist, insert `diamonds_store_purchases` row.
  5. Add item to RP inventory; push updated purse credits composer and
     `RpInventoryComposer`.
  6. Respond with a result packet (ok / not-enough-diamonds / backpack-full) so the
     client can render inline feedback. Failures charge nothing.

### Redemption (`RpUseItemEvent`)

New cases `vip_token_31` / `vip_token_14` (days read from `diamonds_store_items`):

1. Consume the token (peek-before-consume as with `smoothie`).
2. `vip_expire = max(now, vip_expire) + days * 86400`; persist.
3. Grant the VIP badge (`subscriptions.badge_code` for subscription 1).
4. Rebuild the session's `PermissionComponent` (real re-init, not the no-op stub).
5. Resend `UserRightsComposer` (club level 2) and `ScrSendUserInfoComposer`.
6. Bubble shout announcing activation (plain hyphens only — no em-dashes in
   client-facing strings).

### Making club state real

- `UserRightsComposer`: club level = `IsVip ? 2 : 0` (replaces hardcoded 2).
- `ScrSendUserInfoComposer`: real implementation — days to period end from
  `vip_expire`, proper response state; drives the purse chip and HC Center.
- The four `ProcessFigure(..., hasHabboClub: true)` call sites
  (`SSOTicketEvent`, `UpdateFigureDataEvent`, `SaveWardrobeOutfitEvent`,
  `FacelessCommand`) pass `habbo.IsVip`. Validation only runs on outfit save,
  which is exactly the soft-lapse behavior.
- `GetHabboClubWindowEvent` stays a no-op; HC purchase packets stay disabled
  (purchases go through the token flow only).

### Expiry runtime

- All server-side checks read the live computed `IsVip` — perks stop at the exact
  second without any scheduler.
- `ProcessComponent`'s periodic cycle detects the active→expired crossing for online
  users: resend club level 0 + subscription info, remove the VIP badge, rebuild
  permissions, whisper "Your VIP has expired - visit the Diamonds Store to renew."
- Offline expiry needs nothing: next login computes fresh state.

### Stipend

On login (`SSOTicketEvent` region where login rewards run): if `IsVip` and
`vip_last_stipend` is not today, grant `vip.stipend.daily` diamonds, update the
column, notify with the standard currency update.

### Perk gates

- **Camera:** camera packet family allowed for `IsStaff || IsVip` (today it is
  effectively staff-only via the client toolbar; server packets get an explicit gate).
- **Backpack slots 11-12:** unlocked while `IsVip`. Purchase/pickup into 11-12
  requires active VIP; on lapse, items already there remain usable and removable
  (soft lapse) but the slots accept nothing new. Server enforces; client renders
  the slots unlocked/locked from a flag on `RpInventoryComposer` (or from club level).
- **Chat bubbles:** VIP-only styles enforced server-side in the chat style
  validation path; client already respects `isHcOnly`.
- **Username icons:** a reserved VIP set in `IconChoices.ts`; server validates the
  chosen icon against `IsVip`.
- **Effects/dances:** dances are client-gated by club level (now real). The existing
  `EnableCommand` effect gate keys on `gold_vip`/`events_staff`; VIP effects for this
  system key on `silver_vip` (granted via `permissions_subscriptions` while active).

## Client (nitro-react fork)

### Diamonds Store — Store tab (`components/diamonds-store/`)

- On tab open, send `GetDiamondsStoreEvent`; render the listings grid: icon, name,
  description, diamond price. With `special_price`: show it as the price, default
  struck through, small "SALE" tag.
- Purchase: confirm step → composer → result: success ("Check your backpack!") or
  inline error (not enough diamonds / backpack full).
- New packets follow the existing custom-packet pattern (renderer yarn-patch, custom
  header IDs — same pattern as RpInventory; do not touch the retail header map).

### Backpack (`components/rp-inventory/RpInventoryView.tsx`)

- Add `vip_token_31` / `vip_token_14` to the `ITEMS` map (gold / silver icon classes).
- Token PNGs land in `assets/images/rp-items/` (supplied by Ry — the two attached
  icons; gold = 31d, silver = 14d).
- Locked slots 11-12 render unlocked while the server says so.

### Small touches

- HC Center extend/buy button retargets to `diamonds-store/show` (catalog is
  unreachable for players). Purse HC chip works unchanged once days are real.
- Toolbar camera button: `isMod || HasHabboVip()`.
- `hc.disabled` stays `false`.

## CMS

No v1 changes — diamonds already flow via Stripe checkout → webhook → RCON.
Fast-follow (not in this branch): Filament resource for `diamonds_store_items`
(edit prices, toggle sales, enable/disable).

## Error handling

- Purchase failures never charge: validation happens before deduction, deduction and
  inventory insert happen in one transaction with the purchase log row.
- Redemption failure paths never burn the token (peek-before-consume).
- Unknown `item_key` / disabled item / tampered packets: silently refuse (consistent
  with the fork's packet-injection posture).

## Testing / rollout

- Manual in-game testing by Ry (ClaudeTest on local dev): buy both tokens, redeem,
  verify clothing/dance/bubble gates, purse days, stipend on next-day login, expiry
  demotion (short-duration test token via DB), soft-lapse behavior, camera, slots.
- Migration auto-applies on deploy; no manual prod SQL beyond the seeded rows the
  migration itself inserts.
- CHANGELOG.md entry (player-facing). Consider an in-game announcement that HC
  perks are now VIP-gated.
- Branch flow: `feat/vip` → merge to `beta` (auto-deploys beta.pixelrp.co) when Ry
  says; `main` only on Ry's go.

## Out of scope (v1)

- Multiple tiers, gifts/kickbacks in HC Center, VIP-only catalog page, recurring
  Stripe subscriptions, staff grant commands, Filament store admin, token trading.

## Open items

- Ry to supply the two token PNGs as files (gold 31d, silver 14d) for
  `assets/images/rp-items/`.
- Exact VIP badge code (use `subscriptions.badge_code` for row 1, currently `SVIP`;
  swap art/code if a dedicated VIP badge is wanted).
- Which specific clothing sets / bubbles / username icons are VIP-flagged at launch
  (content decision, not architecture).
