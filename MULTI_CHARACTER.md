# Multiple characters per account

One login, up to three player characters, created and switched from the phone's
Wallet app. Agreed shape and decisions, ahead of any code.

Status: **planned, nothing built**. Decisions below are settled unless marked
open.

---

## 1. Data model

Keep one `users` row per character. Two new columns, both on `users`:

| column | meaning |
| --- | --- |
| `parent_id` | NULL = this row is an account root. Otherwise the root it belongs to. |
| `active_character_id` | Root rows only: which character the next `/game` load enters as. |

Credentials (`password`, `mail`, 2FA, `referral_code`) stay meaningful only on
the root. Child characters are created with no mail and an unusable password
hash — there is no way to log in *as* a child directly, only to enter the hotel
as one.

Every existing row becomes its own root (`parent_id` NULL). No data moves, and
nothing in the hotel changes behaviour on the migration alone.

**Why not a separate `accounts` table holding the credentials.** Fortify,
Filament, housekeeping, the ban system, IP tracking and referrals all
authenticate `users` directly, and every roleplay table keys off `users.id` —
inventory, rooms, friends, groups, corp employment, gangs, RP stats, charges,
phone contents, `rp_user_privacy`. Moving credentials out is a multi-week
refactor of things that currently work and buys nothing `parent_id` does not.

Depth is exactly one: a child can never itself be a root, so there is no tree
to walk. Resolving an account is `parent_id ?? id`.

## 2. The ticket authority does not move

`NitroController` stays the only thing that issues an SSO ticket. It resolves
root → `active_character_id` → `ssoTicket()` on **that** row, and drops it into
the nitro iframe exactly as it does today.

The emulator never issues tickets. The client's bootstrap does not change at
all.

## 3. Switching is a reconnect

The emulator binds the Habbo at SSO and cannot rebind a live session, so a
switch is a reconnect:

1. Wallet → Switch → packet to the emulator.
2. Emulator checks the target shares this session's root, writes
   `active_character_id`, replies "go".
3. Client reloads the iframe; the CMS issues the newly-selected character's
   ticket.

About two seconds, and it reads as a client reload. It needs a confirm step —
you leave the room you are standing in.

**One character online at a time per account.** `GameClientManager` already
disconnects a duplicate login of the same user; the same path widens to the
sibling set.

## 4. What is shared and what is not

Per **character** — everything the hotel already keys to a user id:

look, motto, **credits, duckets, diamonds**, inventory, rooms, friends, groups,
corp employment, gang, RP stats, rap sheet, phone contents (notes, photos,
contacts), badges, achievements, birthday, region, profile privacy.

Per **account** (the root row): login, mail, 2FA, and **discipline**.

### Settled decisions

- **Credits: separate.** Farming three characters and pooling is a different
  economy.
- **Diamonds and VIP: separate.** Bought for the character, not the person.
- **Characters cannot be deleted.** A character carries a corp job, gang
  membership, room ownership and an open rap sheet; unwinding that safely is
  its own project. Three slots are permanent once used.
- **The selector is in-game only** for now. No character chooser on the
  website; `/game` enters whoever `active_character_id` names, which is
  whoever you last played.
- **Three, fixed.** No staff grant, no purchase, no exceptions.

### Consequence to handle: purchases attribute to the wrong row

`DiamondCheckoutController` writes `WebsiteDiamondOrder.user_id` from the
*authenticated* user — which after this change is the account **root**, not the
character being played. Fulfilment then looks the order up by
`stripe_session_id` and credits `User::find($order->user_id)`, so with diamonds
per character that silently credits the wrong one: buy while playing your
second character, the diamonds land on your first.

Every purchase path targets the **active character**, not the authenticated
row: the order row, the Stripe `metadata.user_id`, the crypto controller, and
the RCON passive grant that shields the player while the form is open. This is
not optional polish; it is a money bug the moment a second character exists.

Worth being clear about what fulfilment does NOT use: the email address. It is
prefilled on the Checkout form purely to spare the buyer a field. The order row
is the source of truth, and it is written server-side before Stripe is ever
called.

**The buyer should also be able to SEE which character they are paying for**,
because "I bought on the wrong character" is the mistake three slots invites.
Two display-only places, both server-set:

- the line item's `product_data.name` — `250 Diamonds — Marlowe` — which shows
  on the payment page and on the receipt;
- the page around the embedded Checkout, which is ours to write.

Not a Stripe **custom field**. Those are an input control the customer fills,
so a prefilled value is still editable at the payment screen — and anything
fulfilment trusts from it becomes a self-serve way to credit somebody else's
account, plus a support queue of typos. Confirmation, not identity.

## 5. Moderation

- **Bans are account-wide.** Anything else makes alts the ban-evasion
  mechanism rather than a feature. The SSO path checks the root's bans, so
  every character on a banned account is locked out.
- **Staff rank does not inherit.** A child character starts at rank 1
  regardless of what the root holds. Staff who want a civilian character get a
  civilian character.
- **Housekeeping gains a Characters panel** on the player page: the three rows,
  who is currently active, and a link between them. Staff cannot see the link
  today and alt visibility is a real moderation need.
- Mutes stay per character. A mute is about what that person did in that room
  as that character; a ban is about the human.

## 6. Anti-abuse

The plumbing above is straightforward. This part is the actual design work, and
it lands **before** creation goes live on beta — so the first three-character
account cannot do anything that has to be unwound afterwards.

Same-account characters must not be able to:

- trade, gift, or hand items to each other
- add each other as friends
- hold jobs in the same corporation, or belong to the same gang
- use police powers on one another: `:stun`, `:cuff`, `:escort`, `:charge`,
  `:pardon`, and the Wanted list's per-charge ×

The one that matters most: **a police character and a criminal character on one
account** — an officer who clears their own alt's rap sheet or lets it walk.
`:pardon` already refuses a self-pardon; that check widens from "same user" to
"same account", and the same test is added to the rest of the chain.

Implementation note: every one of these is the same question — `AccountOf(a) ==
AccountOf(b)` — so it wants one helper, not seven copies.

## 7. Wallet

- Cards stack: the character you are playing first and marked as current,
  siblings below, each with a Switch action.
- **+** top-right, disabled at three.
- A roster packet (ids, names, looks, mottos, jobs, gangs) pushed at login and
  after a create — sent **only** to a session whose Habbo belongs to that
  account. It is your own data, so no privacy gate applies, but the ownership
  check is not optional.
- Creating asks for a name and nothing else: the same rules registration uses
  (the `username_regex` setting, the wordfilter, uniqueness), then starting
  look, motto and credits from settings. Offer to switch to it once made.

## 8. Build order

1. ~~`parent_id` + `active_character_id`, migration, every row self-parented.~~
   **Done** — `101_MultiCharacter.sql`.
2. CMS ticket resolution **done** (`activeCharacter()`, the client entry, the
   diamond controllers). Account-wide bans **done** (`AccountBanCheckTask`).
   **Housekeeping Characters panel still to do.**
3. ~~Roster packet + Wallet cards.~~ **Done** — stacked, expanding.
4. ~~Switching.~~ **Done** — sets the column, reloads the parent page.
5. ~~Creation.~~ **Done** — name and starting look, rules read from the
   website's own settings and wordfilter.
6. Anti-abuse **done for**: bans, one-online-at-a-time, trade, friend
   requests, and every police power (`:charge`, `:pardon`, `:stun`, `:cuff`,
   `:escort`, the Wanted list's x). **Still to do: same corporation, same
   gang.** Both are joins rather than commands, so neither is a one-line
   guard the way the police chain was.

### What is NOT done

- **Same-corporation and same-gang membership.** Two of your characters can
  still be hired into one corporation or join one gang. This is the remaining
  hole in section 6 and it wants doing before the limit means anything.
- **The housekeeping Characters panel.** Staff cannot see that two accounts
  are one person, which is exactly the visibility the shared-IP noise makes
  necessary.
- **The website identity audit** (section 10): only the ticket path and the
  purchase paths resolve the active character. Every other CMS page and blade
  still renders the account root, so the site shows the root's avatar, motto
  and credits while you play somebody else.

## 9. Two things checked since

**Creating a character needs no call to the CMS.** The rules registration uses
are database-backed, not code: `username_regex` and
`website_wordfilter_enabled` are `settings` rows and the word list is the
`website_wordfilter` table. The emulator reads the same rows and applies the
same rules, so there is one word list rather than two that drift, and no HTTP
hop between the phone and the website.

**Alt detection gets noisier for staff.** Legitimate characters on one account
now share an IP and machine id, which is exactly the signal staff use to spot
ban evasion. The housekeeping Characters panel is what separates the two: a
shared IP with a shared `parent_id` is a feature, a shared IP without one is
still worth a look.

## 10. Two identities on the website

**The site follows the active character** — which at login is simply the last
one played, since `active_character_id` persists. No chooser for now; one
arrives with the frontend overhaul.

That means the CMS has two identities where it used to have one, and every
call site has to say which it means:

| | which row | examples |
| --- | --- | --- |
| **Account** | the root | password, email, 2FA, sessions, referrals, tickets, staff applications, Filament and housekeeping |
| **Character** | `active_character_id` | avatar, motto, **credits and diamonds**, badges, the public profile, purchases, the RCON grants that reach into the hotel |

`AuthenticatedUser::from()` keeps returning the **account**, and call sites opt
in to the character through a new accessor. Deliberately that way round rather
than flipping the default: a call site missed in the audit then renders the
root — today's behaviour, wrong but harmless — instead of pointing a password
change or a 2FA reset at a child row.

The audit is not enormous but it is not one line either: 29 `AuthenticatedUser`
calls across 25 files, plus about 20 `auth()->user()` reads in the pixelrp
theme's blades. It belongs in step 2, before anything else reads the column.

## 11. Still open

- Does an abandoned character keep its corporation job and gang seat
  indefinitely? Nothing reclaims a seat today, and three characters each make
  that three times more likely to matter.
