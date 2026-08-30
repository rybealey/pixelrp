# In-Game Discord Settings — Design

**Date:** 2026-08-29
**Status:** Approved, pending implementation plan
**Scope:** Settings → Social → Verification → Discord subpage; beta-first

## Problem

Two distinct issues with the Discord subpage in the in-game Settings window
(`client/src/components/rp-settings/RpSettingsView.tsx`).

### 1. The unlinked state flashes on every first open

`discordLinked` is initialised to `null` to mean "unknown / still loading", but
the render branches are:

```tsx
{ (discordLinked === true) && <>…connected…</> }
{ (discordLinked !== true) && <>…Connect Discord…</> }
```

`null !== true`, so the **unlinked** branch — the full "Link your Discord
account…" pitch with a Connect button — paints immediately, and is replaced only
once `RpDiscordStatusComposer` (3952) round-trips from the emulator. A player
with a connected account sees a request-to-verify screen flash every time they
open the page in a fresh session.

There is no loading state at all; the page has exactly two visual states for
three logical ones.

### 2. Connect and disconnect both leave the game

Today both actions `window.open()` a CMS page in a new tab:

- Connect → `/discord/connect`
- Manage / disconnect → `/discord` (status page with a `POST /discord/unlink` form)

The player lands on CMS chrome, acts there, comes back, and then has to click an
"I've connected - check again" link in the Settings panel to re-poll status,
because nothing pushes the change into the open client.

### 3. The subpage reuses the empty-state layout

The Discord card renders inside `rp-settings-placeholder` — the same centred
layout used by the literal "Nothing here yet." empty state — which is why a
shipped feature reads as unfinished.

## Constraint: what cannot move in-game

Discord's OAuth consent screen must render on `discord.com` in a real browser
context:

- Discord serves it with `X-Frame-Options`, so it cannot be embedded in an
  iframe inside the Nitro client.
- No bot token can grant `guilds.join` on a user's behalf; the user's own OAuth
  authorisation is required.

The only way to avoid a browser entirely is a bot DM code flow (client shows a
code, player DMs it to Trina), which requires an always-on Discord **gateway
daemon** — infrastructure the current architecture deliberately avoids
(CMS owns every Discord REST call; there is no gateway process).

**Therefore:** disconnect becomes fully in-game. Connect keeps exactly one
browser step — Discord's own consent screen — and sheds every piece of PixelRP
CMS chrome around it.

## Existing architecture (unchanged foundations)

- Emulator **never** calls the Discord API. It answers a status request and
  enqueues work into `discord_sync_queue`; the `cms-scheduler` service drains
  the queue (`discord:process`, every minute) and makes every Discord call.
- A live **RCON bridge** already exists in the other direction
  (`cms/app/Contracts/Rcon.php` → `RconService`, used by Filament today) for
  CMS → emulator pushes.
- The user's OAuth token is used once (identify + `guilds.join`) and never
  stored. `discord_id` is deliberately absent from `User::$fillable`.

Both properties are preserved by this design.

## Design

### Flows

**Status read** — unchanged. Client sends `RpGetDiscordStatusComposer` on page
open; emulator answers 3952 from `users.discord_id`.

**Connect**

1. Client opens a popup directly at `/discord/connect` (the CMS status page is
   no longer an intermediate stop) and enters its *pending* state.
2. CMS redirects to Discord; the player consents on `discord.com`.
3. `/discord/callback` links the account exactly as it does today (state check,
   uniqueness check, `joinGuild`, `syncUser`).
4. Callback then pushes over **RCON** to the emulator, which sends an unprompted
   3952 to that player's session if they are online.
5. The popup renders a bare result page that closes itself on success.

The player's experience: click Connect → Discord consent → popup vanishes → the
Settings panel is already updated. No "check again" link.

**Disconnect** — fully in-game, no browser:

1. Client sends `RpDiscordUnlinkEvent` (3956) after an inline confirm.
2. Emulator reads the current `discord_id`, clears `users.discord_id` and
   `users.discord_linked_at`, inserts a `discord_sync_queue` row with
   `reason = 'unlink'` **carrying that captured `discord_id`**, and immediately
   answers 3952 with `linked = false`.
3. The CMS scheduler strips the managed Discord roles on its next drain
   (≤ 60s). In-game status is authoritative and instant; the Discord-side role
   removal trails slightly, which the UI copy accounts for.

### Wire changes

| Id | Direction | Change |
|----|-----------|--------|
| 3952 `RpDiscordStatusComposer` | server → client | Gains a second int, `linkedAt` (0 when unlinked) |
| 3956 `RpDiscordUnlinkEvent` | client → server | **New** (internal `43956`) |

`3956` verified free on the incoming side: `3954` is burned (stock collision),
`3955` is stock `ModerationTradeLockEvent`, `3960` is `RefreshCampaignEvent`.

Both `emulator/Resources/Revisions/1.6.6.json` and the renderer patch parser
must change together — the revisions map is the real header authority, not the
header constants.

A new renderer patch delta stacks on top of `081847e595`, adding the unlink
composer and the widened status parser.

### Client UI

Replace the `rp-settings-placeholder` reuse with a purpose-built card that has
**three real states plus a transient one**:

- **Loading** (`discordLinked === null`) — skeleton shimmer in the shape of the
  final card. The unlinked branch condition changes from `!== true` to
  `=== false`, so `null` can never render the connect pitch. This is the fix for
  the flash.
- **Unlinked** (`=== false`) — `fa-brands fa-discord` brand mark (kit
  `c305b2c178`, already loaded globally in `client/index.html` and already used
  by `RoomQuickToolsView`), the pitch copy, one **Connect Discord** button.
  The "I've connected - check again" link is deleted.
- **Linked** (`=== true`) — brand mark, connected state, "Connected since
  \<date\>" derived from `linkedAt`, and a **Disconnect** button with an inline
  confirm step.
- **Pending** — shown while a connect popup is open or an unlink is in flight,
  so the panel never looks inert. It is cleared by the arriving 3952 (the
  success path), and otherwise by a bounded timeout that falls back to the
  last known state — a player who cancels at Discord's consent screen, or
  closes the popup, must never leave the panel stuck in pending. Leaving and
  re-entering the page also resets it, since page open re-requests status.

Styling follows the existing `rp-settings-*` patterns in
`RpSettingsView.scss`. All player-facing copy uses plain hyphens, never
em-dashes (Habbo fonts render `—` as a music note).

### Server and CMS changes

- **Migration `46_DiscordUnlinkQueue.sql`** — nullable `discord_id varchar(32)`
  column on `discord_sync_queue`, so an unlink row still knows which Discord
  account to strip after the user row has been cleared. Schema migrations in
  `emulator/Resources/SQLs/Updates/` auto-apply on deploy.
- **`DiscordSyncUtility`** — new `EnqueueUnlink(userId, discordId)` alongside
  the existing `Enqueue`; the existing insert filters on
  `discord_id IS NOT NULL`, which an unlink row must bypass.
- **`DiscordProcessQueue`** — learns `reason = 'unlink'`: those rows resolve
  through a new `unlinkById(string $discordId)` on `DiscordSyncService`,
  alongside the existing `unlinkUser(User $user)`. Sync rows keep their current
  distinct-user behaviour.
- **RCON** — new `ReloadUserDiscordCommand` on the emulator (pushes 3952 to the
  user's session if online), plus a `syncDiscordStatus(User $user)` method on
  the `Rcon` contract, implemented in `RconService` and stubbed in `FakeRcon`.
- **Routes** — `/discord` (status page) and `POST /discord/unlink` are removed,
  along with `DiscordController::show()` and `::unlink()`. `/discord/connect`
  and `/discord/callback` remain.

### Error handling

- **Callback failures** — expired/invalid state, cancelled consent, Discord
  account already bound to another PixelRP account, and "not configured" all
  render inline on the callback result page with a "close this window and try
  again in-game" line. With `/discord` retired there is no redirect target, so
  the callback page absorbs the job the flash-message redirects did before.
- **RCON unavailable or player offline** — the link still succeeds; the push is
  best-effort. The existing refresh-on-page-open catches the change next time
  the player views the page.
- **Unlink idempotency** — clearing an already-clear `discord_id` is a no-op and
  enqueues nothing.
- **Discord not configured** (blank env) — unchanged "not available" state.

## Non-goals

- Bot DM code flow / gateway daemon.
- Showing the linked Discord username or avatar in-game. The wire stays a
  boolean plus a timestamp; Discord identity details are still never sent to the
  client.
- Any redesign outside the Discord subpage.
- Prod rollout (needs prod env vars and a prod redirect URI); beta first.

## Verification

- Client: `tsc`, vite build, immutable install.
- Renderer patch: reseal per the known trap — `yarn install` **before**
  resealing, and diff patch *content* against the prior layer, not just the file
  list.
- Emulator: build.
- CMS: existing test suite with `FakeRcon`.
- Then hand off for a manual in-game test on beta (connect, disconnect,
  reconnect, first-open-with-linked-account to confirm the flash is gone).

## Changelog

Player-facing, so `CHANGELOG.md` gets an entry.
