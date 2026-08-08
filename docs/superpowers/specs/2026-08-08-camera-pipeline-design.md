# Camera pipeline: capture → purchase → publish → CMS Photos

**Date:** 2026-08-08
**Status:** Approved (design); implementation pending
**Branch:** `feature/camera` (emulator submodule) + matching branch on the plus repo

## Goal

A fully functioning camera flow for PlusEMU + Atom CMS. Staff (the only users
with the camera button, per existing client gating) can capture a room photo,
preview it, purchase it (free), receive it as a placeable wall-photo inventory
item, publish it (free), and see it appear on the CMS Photos page for
everyone.

## Current state (verified)

- **Client (nitro-react)**: complete camera UI — capture, editor, checkout.
  Sends `RenderRoomThumbnailMessageComposer`, `RenderRoomMessageComposer`
  (PNG bytes in-packet), `PurchasePhotoMessageComposer`,
  `PublishPhotoMessageComposer`; waits on `InitCameraMessageEvent`,
  `CameraStorageUrlMessageEvent`, `CameraPurchaseOKMessageEvent`,
  `CameraPublishStatusMessageEvent`. The checkout dead-ends today because no
  reply ever arrives.
- **Emulator (PlusEMU fork)**: all six incoming camera handlers
  (`emulator/Communication/Packets/Incoming/Camera/*.cs`) are
  `NotImplementedException` stubs. No outgoing camera composers exist.
- **CMS (Atom)**: `PhotosController` + `CameraService` + `community.photos`
  view are complete; they render `camera_web` rows
  (`id, user_id, room_id, timestamp, url, visible`) where `visible = 1`,
  paginated. **No CMS changes needed.**
- **DB**: `camera_web` exists (empty). The `furniture` rows at sprite ids
  4536/4541 are mislabeled floor items from the original seed
  ("Valentines card"/"Habbo Selfie" pointing at unrelated classnames), while
  the client's FurnitureData correctly defines `external_image_wallitem`
  (4536) and `external_image_wallitem_photo` (4541) as wall items.

## Design

### Emulator: CameraPhotoManager + handlers + composers

New `CameraPhotoManager` (DI singleton) owning pending photos and disk/DB
writes. The thumbnail is held in memory per session; the full PNG is written
to disk at `RenderRoom` time (that's what makes the checkout preview URL
resolvable before purchase). Purchase marks the file permanent; a photo never
purchased leaves an orphan file that a boot-time sweep may clean (orphans are
harmless — nothing references them).

Handler behavior:

| Incoming | Behavior | Reply |
|---|---|---|
| `InitCameraEvent` | none | camera config with all prices **0** |
| `PhotoCompetitionEvent` | no-op (no competitions) | none |
| `RenderRoomThumbnailEvent` | stash thumbnail bytes for session | thumbnail-ok status |
| `RenderRoomEvent` | stash full PNG for session | `CameraStorageUrl` with preview URL |
| `PurchasePhotoEvent` | write `photo_<id>.png` (+ thumbnail) to disk; create inventory wall-photo item (base item = corrected 4541) with extradata carrying `{"w":"<url>", "n":..., "s":..., "u":..., "t":..., "m":...}` as the client photo renderer expects; zero cost | `CameraPurchaseOK` |
| `PublishPhotoEvent` | insert `camera_web` row (`user_id`, `room_id`, unix `timestamp`, `url`, `visible=1`); zero cost | `CameraPublishStatus` (ok, wait 0, url) |

The preview URL for `CameraStorageUrl` is served from the same photo id and
file the purchase step keeps — written once at `RenderRoom` time, so the
checkout preview and the purchased item reference the same URL.

Outgoing composers to create (+ `ServerPacketHeader` entries + revision
`1.6.6.json` mappings, mirroring the incoming ids already registered there):
`InitCameraMessageComposer`, `ThumbnailStatusMessageComposer`,
`CameraStorageUrlMessageComposer`, `CameraPurchaseOKMessageComposer`,
`CameraPublishStatusMessageComposer`.

### Storage & serving

- Directory: `nitro/assets/c_images/camera/` (git-ignored asset tree).
- Compose: bind-mount `./nitro/assets/c_images/camera` **read-write** into
  the emulator container (dev `compose.yaml` + prod `compose.prod.yaml`).
  nginx already serves the path at `/nitro-assets/assets/c_images/camera/…`
  with week-long cache headers — fine, since each photo file is unique.
- `camera_web.url` stores the absolute URL. Base URL comes from emulator
  config (`camera.url.base` or equivalent env-templated value in
  `docker/emulator/config.template.json`): `http://localhost:8080/...` dev,
  `https://pixelrp.co/...` prod. Fits `varchar(128)`.

### Furniture fix

Correct the `furniture` row for sprite id 4541 to:
`item_name = external_image_wallitem_photo`, wall item (`type = i`),
public name "Photo", interaction the emulator serializes with the item's
extradata (JSON string) so the client's photo furniture renderer displays
the image. If PlusEMU lacks a suitable interaction type, add a minimal
`Photo` interaction that just carries extradata through item serialization.
Applied as SQL to dev + prod (documented in the spec/plan; the repo does not
migrate the game DB).

### Client

No changes expected. The camera button is already staff-gated
(`isInRoom && isMod`). If checkout shows currency labels for 0-cost items,
that is acceptable for this iteration.

### Error handling

- Handler exceptions surface via the packet-exception logging added earlier
  (never silently swallowed).
- Disk/DB failures reply with the failing status variant of the relevant
  composer so the client UI unblocks; the pending photo stays in memory so
  the player can retry.
- Missing pending photo on purchase/publish (e.g. after reconnect) replies
  with the failure status; no crash.

### Testing

Local end-to-end as ClaudeTest (staff): capture → editor → Preview shows
checkout with 0 cost → purchase → PNG exists on disk, wall-photo item in
inventory (placeable, renders the image) → publish → `camera_web` row →
photo renders on the CMS Photos page. Then prod: emulator rebuild with the
compose volume addition; verify one staff photo end-to-end.

## Out of scope

- Photo competitions (`PhotoCompetitionEvent` stays a polite no-op).
- Purchase/publish pricing (all free; revisit if the camera opens to players).
- CMS moderation UI for hiding photos (the `visible` flag exists; hiding is
  a manual DB flip for now).
- Photo deletion/expiry.
