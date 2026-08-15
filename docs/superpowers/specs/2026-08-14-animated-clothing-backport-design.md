# Animated clothing — idle figure-part animation backport

**Date:** 2026-08-14
**Status:** Approved (design) — pending implementation plan
**Scope:** `client/` submodule (`nitro-react` @ `pixelrp`) — a `@nitrots/nitro-renderer@1.6.6` yarn patch. No emulator, asset, or figuredata changes.

## Problem

Many clothing items (animated hats, hair, head/face/waist accessories, some jackets)
are meant to loop through an animation while worn, but render as a single static
frame in-game. Reproduced in production on user **Peggy**'s animated head
accessory. We want animated clothing to play its loop while the avatar is idle
(standing), matching how a newer/forked renderer behaves.

## Findings (grounding)

### The artwork is already complete
Parsing the `.nitro` figure bundles directly (NitroBundle format: `>H` file
count, then per file `>H` name-len, name, `>i` data-len, zlib-deflated payload):

- **1,217 of ~2,958** figure bundles contain multi-frame sprite assets.
- The extra frames exist for the **idle `std` posture**, not only during actions.
  Examples: `acc_head_U_spider` and `acc_head_U_nftmoon` each encode **8 frames
  (0–7)** of `std` per direction; `jacket_U_animtest` (a built-in test asset)
  carries `std`, `sit`, `lay`, `wlk`, `wav`, `crr`, `drk` frame sets.
- Asset name grammar: `h_<action>_<parttype>_<id>_<direction>_<frame>`. A static
  item has frame `0` only; an animated one has `…_<dir>_0`, `_1`, … `_N`.
- **Zero** bundles use an `animations` manifest key — expected. Habbo avatar
  animation stores frames as discrete assets; the *sequence* is not per-bundle.

Conclusion: this is a **playback** problem, not an asset problem. No art needs
redrawing.

### Why 1.6.6 never plays them (root cause)
The renderer's frame machinery is entirely **action-gated**:

- `AvatarImage` has one global `_frameCounter`, advanced only by
  `updateAnimationByFrames(k)`. A new composite bitmap is produced only when its
  `_changes` flag is set; `getImage()` short-circuits to the cached image
  otherwise (`AvatarImage.ts` ~line 300).
- `AvatarImage.isAnimating()` is driven by animated **actions** (dance, effect,
  gesture, wave, walk). It is set inside the `definition.isAnimation` branch
  (`setActionsToParts`) and via `_animationFrameCount = maxFrames(sortedActions)`.
  A plain `std` avatar reports `isAnimating() === false`.
- `AvatarVisualization.update()` only advances the counter while
  `isAnimating()` (or a one-shot `_forcedAnimFrames`) is true. Idle avatar →
  counter frozen → one cached bitmap forever.
- Per-part multi-frame sequences are attached **only** by
  `AvatarStructure.getParts` via `AvatarAnimationData.getAction(activeAction.definition)`,
  keyed by the active action + setType. A clothing SET has no way to declare its
  own frames: `FigurePart`, `FigurePartSet`, `SetType`, and `IFigureDataPart`
  carry no animation field, and the figuredata parser would discard one.

So two capabilities are missing:
1. A way to mark a worn clothing part as animated and feed its frame sequence,
   independent of the active action.
2. An idle-time tick that keeps `isAnimating()` true so the composite
   re-renders each interval for anyone wearing an animated part.

The frame-**cycling** primitive already exists and is reusable:
`AvatarImagePartContainer.getFrameIndex(frameCount) = frameCount % frames.length`,
consumed in `AvatarImageCache.renderBodyPart`. Give a part an N-length `frames`
array and the counter advances → it cycles.

### Hard constraint — version handshake
The emulator only accepts a `ClientHelloEvent` string matching `NITRO-1-6-6`,
derived from the renderer's own `NitroVersion.RENDERER_VERSION` (`1.6.6`).
Swapping to a different renderer would require moving the emulator revision
handshake in lockstep. **The backport keeps 1.6.6**, so the handshake is
untouched — a key reason to patch rather than adopt a fork.

## Approach — backport (approved)

Two surgical additions to the renderer, delivered as an expanded yarn patch on
`@nitrots/nitro-renderer@1.6.6`, built with `docker/nitro/build-client.sh`.

### 1. Detect idle-animated parts from the assets
In `AvatarStructure.getParts`, for a worn clothing part whose active posture
supplies no action-driven animation, probe the loaded figure asset library for
how many frames the current-posture partition has (`…_<dir>_1` present? `_2`? …).
If the count is >1, assign the part a `frames = [0…N-1]` sequence so the existing
cycling primitive plays it. Frame count is derived from the art (the bundle is
already downloaded to render at all), so **no new gamedata file** is introduced.

### 2. Keep idle avatars ticking
Make `AvatarImage.isAnimating()` return true whenever a worn part is animated
(from #1). `AvatarVisualization` then keeps calling `updateAnimationByFrames(1)`
each interval and invalidating the composite cache, so frames advance while the
avatar stands.

### Decisions
- **Scope rule — auto-detect by frame count.** Any part whose current posture has
  >1 frame animates. Matches intent exactly (that is what the extra frames are
  for) and needs no per-item curation. Add an optional deny-list constant to
  force-disable a specific set if one ever misbehaves.
- **Speed — one tunable cadence constant**, starting near Habbo's default idle
  rate, adjustable after in-game review.
- **Performance — the watch item.** Animated wearers re-composite every ~2 ticks
  instead of caching one frame; a packed room with many animated wearers costs
  more GPU. Keep the existing 2-tick throttle; dial back if jank appears. Not a
  blocker.

### Explicitly out of scope
- No emulator / revision-handshake changes.
- No asset re-authoring or figuredata edits.
- No adoption of an external renderer fork.
- Action-driven animation (dance/effect/walk) already works; untouched.

## Implementation risk to resolve in the plan
The exact asset-library API for counting frames at `getParts` time. The data is
reachable there (the figure library is loaded); pinning the precise call — and
whether it is cheaper to count frames once at part-build time and cache the
length on the part container — is a plan-phase detail, not a design unknown.

## Verification
- Local-first, in-game (no browser screenshot automation): confirm idle looping
  on `jacket_U_animtest`, `acc_head_U_nftmoon`, `acc_head_U_spider`.
- Confirm static items (e.g. `acc_head_U_cyfins`) still render one frame and are
  untouched.
- Confirm action animations (dance/effect/walk) still behave.
- Hand off to the user to confirm on prod's actual Peggy item in-game.
- Watch a crowded room for compositing cost.

## Rollout
Client-only. Build with `build-client.sh --prod`, ship the built `nitro/client/`
to the VPS (gitignored client output — same non-git deploy path as other client
changes). Emulator untouched.
