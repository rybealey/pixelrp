# "67" Chat Emote — Design

**Date:** 2026-08-31 · **Scope:** renderer patch (client repo) + emulator · **Branch:** beta

## Problem

Typing `67` in chat should make the avatar perform the 6-7 meme gesture,
as seen on WaveRP. The feature comes from two sources the user provided:
the WavePlus emulator (github.com/OliverRetro/WavePlus, `ChatEvent.cs`) and
WaveRP's nitro-renderer source drop (commit `d36683d8`), which contains the
client-side animation. The gesture is pure frame data - it re-choreographs
existing body-part frames - so no sprite assets are needed.

## Design (approved)

### Renderer (stacked yarn patch on `@nitrots/nitro-renderer` 1.6.6)

Six surgical changes, ported from WaveRP's renderer (theirs is 1.6.22; the
touched files are stable between versions):

1. New `src/nitro/avatar/data/DanceSixSevenAnimation.ts` - the 122-line
   animation data file, verbatim: 14 frames alternating `CarryItem` arm
   poses with 1px dx/dy offsets and `Talk`/`Default` head bobs, keyed
   `dance.sixseven`.
2. `AvatarRenderManager.ts` - import the file and
   `this._structure.registerAnimation(DanceSixSevenAnimation)` next to the
   existing dance registrations.
3. `api/nitro/avatar/enum/AvatarAction.ts` - add
   `public static EXPRESSION_67 = '67';`, early-return cases in
   `getExpressionId` (`'67'` → 67) and `getExpression` (67 → `'67'`), and
   `case 67: return 990;` in `getExpressionTimeout` (the gesture auto-stops
   client-side after ~1s).
4. `nitro/avatar/AvatarImage.ts` - add `case AvatarAction.EXPRESSION_67:`
   to the expression group of the `appendAction` switch.
5. `nitro/room/object/visualization/avatar/AvatarVisualization.ts` - in the
   expression switch, `case AvatarAction.EXPRESSION_67:` →
   `this._avatarImage.appendAction(AvatarAction.DANCE, 'sixseven');`.
6. `api/ui/widget/enums/AvatarExpressionEnum.ts` - add
   `EXPRESSION_67 = new AvatarExpressionEnum(67)`.

No new wire ids: the feature rides the stock Expression/Action packet the
renderer already parses. Patch applied via the established stacked-patch
workflow (`yarn patch -u` on the LAST patch descriptor; `yarn install`
before resealing; verify per-file patch content against the prior patch,
not just the file list).

### Emulator (Plus lineage, same file layout as WavePlus)

Ported near-verbatim from WavePlus:

- `HabboHotel/Rooms/RoomUser.cs` - new `public int EffectReapplyTimer;`
  field.
- `Communication/Packets/Incoming/Rooms/Chat/ChatEvent.cs` - after
  `user.OnChat(...)`: if `message.Trim() == "67"`, then (a) if
  `user.DanceId > 0` set it to 0, (b) if the habbo's current effect > 0,
  broadcast `AvatarEffectComposer(user.VirtualId, 0)` and set
  `user.EffectReapplyTimer = 2`, (c) broadcast
  `ActionComposer(user.VirtualId, 67)` to the room.
- `Communication/Packets/Incoming/Rooms/Chat/ShoutEvent.cs` - same trigger
  block (shouting `67` also fires the gesture). WhisperEvent is
  deliberately untouched.
- `HabboHotel/Rooms/RoomUserManager.cs` - in the user cycle: when
  `EffectReapplyTimer > 0`, decrement; when it reaches 0 and the user is
  not dancing, re-broadcast the habbo's current effect (mirroring
  WavePlus's reapply block) so the player's enable comes back ~2 ticks
  after the ~990ms client animation ends.

### Behavior

- Exact trimmed match `67` only, in talk and shout. The message still
  renders as a normal chat bubble; the gesture plays on top.
- Spam is bounded by the existing chat flood control; no extra cooldown.
- Works for every player (no rank gate) - it is a fun emote, not an RP
  mechanic.

## Out of scope

- No client (nitro-react) UI changes - there is no button; chat is the
  only trigger.
- No other WavePlus behaviors (their `ActionEvent`/`DanceEvent` timer
  interactions beyond what the reapply logic needs).
- No whisper trigger.

## Files

- `client/.yarn/patches/` + `client/package.json` (new stacked renderer
  patch descriptor)
- `emulator/Communication/Packets/Incoming/Rooms/Chat/ChatEvent.cs`
- `emulator/Communication/Packets/Incoming/Rooms/Chat/ShoutEvent.cs`
- `emulator/HabboHotel/Rooms/RoomUser.cs`
- `emulator/HabboHotel/Rooms/RoomUserManager.cs`
- `CHANGELOG.md`

## Verification

Client `yarn build` passes with the resealed patch; emulator `dotnet build`
passes; user tests in-game on beta (say `67`, shout `67`, confirm whisper
does nothing, confirm an active enable comes back afterwards). Deploy
commit tagged `(bump client + emulator)` per house convention.
