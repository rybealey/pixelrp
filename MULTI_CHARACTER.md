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

`DiamondCheckoutController` and the crypto/Stripe webhooks stamp `user_id` from
the *authenticated* user — which after this change is the account **root**, not
the character being played. With diamonds per character that silently credits
the wrong one: buy while playing your second character, the diamonds land on
your first.

Every purchase path must target the **active character**, not the
authenticated row. Same for subscriptions if VIP is ever sold on the site.
This is not optional polish; it is a money bug the moment a second character
exists.

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

1. `parent_id` + `active_character_id`, migration, every row self-parented.
   No behaviour change.
2. CMS ticket resolution, account-wide bans, purchase attribution fix,
   housekeeping Characters panel.
3. Roster packet + Wallet cards, read-only. No create, no switch.
4. Switching.
5. Creation.
6. Anti-abuse pass — before creation is reachable on beta.

## 9. Still open

- Does an abandoned character keep its corporation job and gang seat
  indefinitely? Nothing reclaims a seat today, and three characters each make
  that three times more likely to matter.
