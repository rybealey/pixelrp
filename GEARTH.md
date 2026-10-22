# Packet injection (G-Earth) — what we defend and what we should

Assessed 9 September 2026 against `beta`; updated 21 October 2026 for the
packet limits, the Builder rank and the handshake clean-up.

G-Earth is a man-in-the-middle proxy. It sees every packet the client sends and
can forge any packet a logged-in session is *allowed* to send. The one thing it
cannot do is authenticate as somebody else. So the rule this codebase already
encodes is:

> **Client-side hiding is presentation, never enforcement.**

A button the client does not draw is still a packet anyone can send.

## What exists today

Four layers, all in [`PacketManager`](emulator/Communication/Packets/PacketManager.cs).

**1. Packet limits.** Every packet comes out of a per-connection budget before
any handler runs, before log in too
([`PacketLimits`](emulator/Communication/Packets/PacketLimits.cs), applied by
`PacketBudget`): a token bucket per packet type and one for everything a
connection sends together, with tighter buckets on chat and commands, buying,
moving money and the catalog search. A packet over budget is dropped; a
connection that keeps going far over it is disconnected and written to
`rp_packet_flood_log`, which the housekeeping player page shows. What a click
on a player asks for (turning to look, badges, partner, gang, group, pet info,
the HUD target) keeps only its own bucket: it takes nothing from the total and
is never counted towards a flood. Walking is never limited - it belongs to the
movement system.

**2. Handshake gate.** Packets sent before authentication are dropped unless the
handler is marked `[NoAuthenticationRequired]` — 5 of them: client hello,
version check, SSO ticket, pong and unique id. (The Flash-era key exchange is
gone: Nitro never sent it.)

**3. `[StaffOnly]` / `[BuilderOnly]` / `[VipOnly]` attributes.** 10, 42 and 7
handlers respectively. Checked *before the handler runs*, and a rejection logs a
warning naming the user, id and rank. `[BuilderOnly]` opens from the Builder
rank up and covers the Furni Shop (`PurchaseFromCatalogEvent` among it), the
navigator and the Function tool; `[VipOnly]` covers the camera and photo
publishing.

**4. Handlers that refuse outright.** `ChangeMottoEvent` is a deliberate no-op:
the motto is RP-managed, the client no longer offers an editor, and an injected
packet rewrites nothing.

Alongside those, the pattern from the custom-chat-bubbles work: **validate the
value, never the client's claim about it.** An injected bubble style falls back
to 0 rather than being trusted.

## Current state — the packets added most recently

Every recent feature ships a new client-writable packet, so each was assessed
against the model above.

| Packet | Posture | Verdict |
| --- | --- | --- |
| `RpSetFurniAlphaEvent` | `room.CheckRights(session, true)`; value clamped 10–100 | Sound. The 10% floor is enforced server-side, so fully invisible furni cannot be forged. |
| `RpSetRegionEvent` | Whitelist of exactly `na` / `eu` / `oc` / `''`; writes the caller's own row only | Sound. |
| `RpSavePhoneStateEvent` | Size cap and JSON-kind check; writes the caller's own row only | Sound, and deliberately permissive — the document is the player's own to corrupt, and every field is re-validated on read. |
| `RpGetUserRegionEvent` | No gate; reads any user id | Acceptable — region is public by design, it is printed on profiles — but see enumeration below. |
| Catalog quantity | Server clamps 1–100 and re-derives the price; the client's number is never trusted for cost | Sound. |

One change materially reduced exposure rather than adding to it: **the catalog
is free hotel-wide** (`90_FreeCatalog`). Purchase-packet forgery has always been
the highest-value target here, and there is presently nothing to gain from it.

## Gaps worth closing

**1. Enumeration is slower, not closed.** The per-user lookups
(`RpGetUserRegionEvent`, `RpGetUserCorpEvent`, `RpGetUserGangEvent`,
`RpGetBirthdayEvent`) now come out of the default packet budget - 10 a second
per lookup - so the user table can still be walked, only slower. The data is
low-value (it is all shown on profiles); a tighter limit in `PacketLimits` is a
one-line change if that ever matters.

**2. The rank attributes are applied by hand.** 59 handlers carry one; nothing
fails if the next one does not. The attribute should go on at the same moment as the header
constant, and ideally the build should say so when it does not.

**3. Authorisation style is inconsistent.** Attributes, `room.CheckRights`,
`GangManager.GetActor(session, Perm…)`, and delegation to managers such as
`JukeboxStation.TrySkip` are all in use. Each is legitimate — `RpGangKickEvent`
is properly authorised despite carrying no attribute — but it means nobody can
answer "is this packet safe?" by looking in one place. A short map of handler
family to where its check lives would make review possible.

**4. Derive the actor from the session, never from the payload.** Every write
handler should read `session.GetHabbo()` and treat any user id in the packet as
a lookup key at most. The recent handlers all do; writing it down is what keeps
it true.

## Suggested next steps

- A CI check that fails the build when a handler in a staff-only namespace has
  no `[StaffOnly]` or `[BuilderOnly]`. It pairs naturally with a duplicate-packet-id check: both
  catch problems that compile cleanly and only surface at runtime, which is how
  two outages happened on 8 September.
- Keep the free catalog in mind when pricing returns. The day items cost
  something again, `PurchaseFromCatalogEvent` becomes the highest-value forgery
  target in the hotel, and its `[BuilderOnly]` gate is what currently stands in
  the way.
