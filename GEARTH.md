# Packet injection (G-Earth) — what we defend and what we should

Assessed 9 September 2026 against `beta`.

G-Earth is a man-in-the-middle proxy. It sees every packet the client sends and
can forge any packet a logged-in session is *allowed* to send. The one thing it
cannot do is authenticate as somebody else. So the rule this codebase already
encodes is:

> **Client-side hiding is presentation, never enforcement.**

A button the client does not draw is still a packet anyone can send.

## What exists today

Three layers, all in [`PacketManager`](emulator/Communication/Packets/PacketManager.cs).

**1. Handshake gate.** Packets sent before authentication are dropped unless the
handler is marked `[NoAuthenticationRequired]` — 7 of them: client hello,
version check, SSO ticket, pong, unique id, and the two key-exchange packets.

**2. `[StaffOnly]` / `[VipOnly]` attributes.** 56 and 7 handlers respectively.
Checked *before the handler runs*, and a rejection logs a warning naming the
user, id and rank. Current coverage includes the whole catalog
(`PurchaseFromCatalogEvent` among them), builders-club placement, the camera and
photo publishing.

**3. Handlers that refuse outright.** `ChangeMottoEvent` is a deliberate no-op:
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

**1. There is no packet-level rate limiting.** Flood control exists for chat
only. Every other handler runs as fast as a session can send. Two consequences:

- *Enumeration.* The per-user lookups (`RpGetUserRegionEvent`,
  `RpGetUserCorpEvent`, `RpGetUserGangEvent`, `RpGetBirthdayEvent`) are one
  indexed query each with no ceiling, so the whole user table can be walked.
  The data is low-value — it is all shown on profiles — but the walk is free.
- *Self-inflicted load.* Any write handler is a database DoS vector from a
  single authenticated session.

This is the largest structural gap and it lives in one file.

**2. `[StaffOnly]` is applied by hand.** 56 handlers carry it; nothing fails if
the 57th does not. The attribute should go on at the same moment as the header
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

- Add a per-session rate limiter to `PacketManager` — a token bucket keyed on
  handler type, generous by default and tight on the lookup packets.
- A CI check that fails the build when a handler in a staff-only namespace has
  no `[StaffOnly]`. It pairs naturally with a duplicate-packet-id check: both
  catch problems that compile cleanly and only surface at runtime, which is how
  two outages happened on 8 September.
- Keep the free catalog in mind when pricing returns. The day items cost
  something again, `PurchaseFromCatalogEvent` becomes the highest-value forgery
  target in the hotel, and its `[StaffOnly]` gate is what currently stands in
  the way.
