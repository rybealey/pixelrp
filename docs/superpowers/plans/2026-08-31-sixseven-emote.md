# "67" Chat Emote Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Typing or shouting `67` in a room plays the 6-7 meme gesture on the avatar, per `docs/superpowers/specs/2026-08-31-sixseven-emote-design.md`.

**Architecture:** Two coupled halves. Task 1 adds the client-side animation to `@nitrots/nitro-renderer` via a NEW stacked yarn patch in the client submodule (6 surgical file changes, no sprite assets, no new wire ids — rides the stock Expression packet). Task 2 ports the WavePlus server trigger into our emulator submodule (chat/shout hook + effect-reapply timer). Task 3 adds the changelog and bumps both submodule pointers in the root repo.

**Tech Stack:** TypeScript (nitro-renderer, patched via Yarn Berry `yarn patch`), C# (.NET Plus emulator), Vite.

## Global Constraints

- Branch: `beta` everywhere. Commit locally in each repo; do NOT push — the controller pushes after review.
- `client/` and `emulator/` are separate git repos (submodules of the root repo). Commit renderer-patch work in `client/`, emulator work in `emulator/`, changelog + pointer bumps in the root.
- Verification: `yarn build` from `client/` passes (Task 1); `dotnet build` from `emulator/` passes (Task 2). No test suites exist in either.
- Renderer patch discipline (established house workflow): run `yarn install` in `client/` BEFORE creating the patch; the patch must STACK on the existing 23-patch chain (the working copy you edit must already contain prior custom changes — verify before editing); after `yarn patch-commit`, verify the new patch file contains ONLY this feature's changes and that no prior patch file was modified.
- No em-dashes or middots in client-visible strings (none are added by this plan; the changelog heading may use an em-dash per existing entries).
- The trigger is exact trimmed `"67"` in talk (ChatEvent) and shout (ShoutEvent) only — WhisperEvent must NOT be touched.

---

### Task 1: Renderer stacked patch — the sixseven animation

**Files:**
- Modify (via yarn patch workflow, in `client/`): `.yarn/patches/` (one NEW patch file), `package.json` (resolution string), `yarn.lock`
- The patched package files (edited inside the `yarn patch` working directory, NOT in node_modules directly):
  - Create: `src/nitro/avatar/data/DanceSixSevenAnimation.ts`
  - Modify: `src/nitro/avatar/AvatarRenderManager.ts`
  - Modify: `src/api/nitro/avatar/enum/AvatarAction.ts`
  - Modify: `src/nitro/avatar/AvatarImage.ts`
  - Modify: `src/nitro/room/object/visualization/avatar/AvatarVisualization.ts`
  - Modify: `src/api/ui/widget/enums/AvatarExpressionEnum.ts`

**Interfaces:**
- Consumes: `AvatarStructure.registerAnimation(data)` (exists at `src/nitro/avatar/AvatarStructure.ts:131` in 1.6.6), `IAssetAnimation` from `../../../api`.
- Produces: expression id 67 handled end-to-end in the renderer — the server broadcasting the stock Expression/Action packet with id 67 (Task 2) makes the avatar play the `dance.sixseven` animation for ~990ms. No client (nitro-react) changes are needed.

- [ ] **Step 1: Open the patched package for stacking**

From `/Users/rybealey/Documents/Personal/pixelrp/plus/client`:

```bash
yarn install
yarn patch @nitrots/nitro-renderer
```

`yarn patch` prints a working directory path (call it `$WORKDIR`). **Verify the working copy is the PATCHED source, not pristine 1.6.6** — it must contain prior custom changes:

```bash
grep -c "RpRoomZoneSaveComposer" "$WORKDIR/src/nitro/communication/NitroMessages.ts"
```

Expected: 1 or more matches. If ZERO matches, the working copy is unpatched — STOP, do not edit it. Instead extract the full current resolution and re-run patch against it: `node -p "require('./package.json').resolutions['@nitrots/nitro-renderer']"` and `yarn patch "@nitrots/nitro-renderer@<that full patch:... string>"`, then re-verify.

- [ ] **Step 2: Create the animation data file**

Write `$WORKDIR/src/nitro/avatar/data/DanceSixSevenAnimation.ts` with exactly:

```typescript
import { IAssetAnimation } from '../../../api';

export const DanceSixSevenAnimation: { [index: string]: IAssetAnimation } = {
    'dance.sixseven': {
        'name': 'dance.sixseven',
        'desc': '67 meme gesture',
        'frames': [
            {
                'bodyparts': [
                    { 'id': 'leftarm', 'action': 'Default', 'frame': 0, 'dx': -1, 'dy': 1, 'dd': 0 },
                    { 'id': 'torso', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 0, 'dd': 0 },
                    { 'id': 'head', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 1, 'dd': 0 },
                    { 'id': 'rightarm', 'action': 'Default', 'frame': 0, 'dx': 1, 'dy': 1, 'dd': 0 }
                ]
            },
            {
                'bodyparts': [
                    { 'id': 'leftarm', 'action': 'CarryItem', 'frame': 0, 'dx': -1, 'dy': 0, 'dd': 0 },
                    { 'id': 'torso', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 0, 'dd': 0 },
                    { 'id': 'head', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 0, 'dd': 0 },
                    { 'id': 'rightarm', 'action': 'CarryItem', 'frame': 0, 'dx': 1, 'dy': 1, 'dd': 0 }
                ]
            },
            {
                'bodyparts': [
                    { 'id': 'leftarm', 'action': 'CarryItem', 'frame': 0, 'dx': -1, 'dy': 1, 'dd': 0 },
                    { 'id': 'torso', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 0, 'dd': 0 },
                    { 'id': 'head', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 1, 'dd': 0 },
                    { 'id': 'rightarm', 'action': 'CarryItem', 'frame': 0, 'dx': 1, 'dy': 0, 'dd': 0 }
                ]
            },
            {
                'bodyparts': [
                    { 'id': 'leftarm', 'action': 'CarryItem', 'frame': 0, 'dx': -1, 'dy': 0, 'dd': 0 },
                    { 'id': 'torso', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 0, 'dd': 0 },
                    { 'id': 'head', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 0, 'dd': 0 },
                    { 'id': 'rightarm', 'action': 'CarryItem', 'frame': 0, 'dx': 1, 'dy': -1, 'dd': 0 }
                ]
            },
            {
                'bodyparts': [
                    { 'id': 'leftarm', 'action': 'CarryItem', 'frame': 0, 'dx': -1, 'dy': -1, 'dd': 0 },
                    { 'id': 'torso', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 0, 'dd': 0 },
                    { 'id': 'head', 'action': 'Talk', 'frame': 0, 'dx': 0, 'dy': 1, 'dd': 0 },
                    { 'id': 'rightarm', 'action': 'CarryItem', 'frame': 0, 'dx': 1, 'dy': 0, 'dd': 0 }
                ]
            },
            {
                'bodyparts': [
                    { 'id': 'leftarm', 'action': 'CarryItem', 'frame': 0, 'dx': -1, 'dy': 0, 'dd': 0 },
                    { 'id': 'torso', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 0, 'dd': 0 },
                    { 'id': 'head', 'action': 'Talk', 'frame': 1, 'dx': 0, 'dy': 0, 'dd': 1 },
                    { 'id': 'rightarm', 'action': 'CarryItem', 'frame': 0, 'dx': 1, 'dy': 1, 'dd': 0 }
                ]
            },
            {
                'bodyparts': [
                    { 'id': 'leftarm', 'action': 'CarryItem', 'frame': 0, 'dx': -1, 'dy': 1, 'dd': 0 },
                    { 'id': 'torso', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 0, 'dd': 0 },
                    { 'id': 'head', 'action': 'Talk', 'frame': 0, 'dx': 0, 'dy': 0, 'dd': 1 },
                    { 'id': 'rightarm', 'action': 'CarryItem', 'frame': 0, 'dx': 1, 'dy': 0, 'dd': 0 }
                ]
            },
            {
                'bodyparts': [
                    { 'id': 'leftarm', 'action': 'CarryItem', 'frame': 0, 'dx': -1, 'dy': 0, 'dd': 0 },
                    { 'id': 'torso', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 0, 'dd': 0 },
                    { 'id': 'head', 'action': 'Talk', 'frame': 1, 'dx': 0, 'dy': 0, 'dd': 0 },
                    { 'id': 'rightarm', 'action': 'CarryItem', 'frame': 0, 'dx': 1, 'dy': -1, 'dd': 0 }
                ]
            },
            {
                'bodyparts': [
                    { 'id': 'leftarm', 'action': 'CarryItem', 'frame': 0, 'dx': -1, 'dy': -1, 'dd': 0 },
                    { 'id': 'torso', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 0, 'dd': 0 },
                    { 'id': 'head', 'action': 'Talk', 'frame': 0, 'dx': 0, 'dy': 1, 'dd': 0 },
                    { 'id': 'rightarm', 'action': 'CarryItem', 'frame': 0, 'dx': 1, 'dy': 0, 'dd': 0 }
                ]
            },
            {
                'bodyparts': [
                    { 'id': 'leftarm', 'action': 'CarryItem', 'frame': 0, 'dx': -1, 'dy': 0, 'dd': 0 },
                    { 'id': 'torso', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 0, 'dd': 0 },
                    { 'id': 'head', 'action': 'Talk', 'frame': 1, 'dx': 0, 'dy': 0, 'dd': 0 },
                    { 'id': 'rightarm', 'action': 'CarryItem', 'frame': 0, 'dx': 1, 'dy': 1, 'dd': 0 }
                ]
            },
            {
                'bodyparts': [
                    { 'id': 'leftarm', 'action': 'CarryItem', 'frame': 0, 'dx': -1, 'dy': 1, 'dd': 0 },
                    { 'id': 'torso', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 0, 'dd': 0 },
                    { 'id': 'head', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 1, 'dd': 0 },
                    { 'id': 'rightarm', 'action': 'CarryItem', 'frame': 0, 'dx': 1, 'dy': 0, 'dd': 0 }
                ]
            },
            {
                'bodyparts': [
                    { 'id': 'leftarm', 'action': 'CarryItem', 'frame': 0, 'dx': -1, 'dy': 0, 'dd': 0 },
                    { 'id': 'torso', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 0, 'dd': 0 },
                    { 'id': 'head', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 0, 'dd': 0 },
                    { 'id': 'rightarm', 'action': 'CarryItem', 'frame': 0, 'dx': 1, 'dy': -1, 'dd': 0 }
                ]
            },
            {
                'bodyparts': [
                    { 'id': 'leftarm', 'action': 'Default', 'frame': 0, 'dx': -1, 'dy': 1, 'dd': 0 },
                    { 'id': 'torso', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 0, 'dd': 0 },
                    { 'id': 'head', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 1, 'dd': 0 },
                    { 'id': 'rightarm', 'action': 'Default', 'frame': 1, 'dx': 1, 'dy': 1, 'dd': 0 }
                ]
            },
            {
                'bodyparts': [
                    { 'id': 'leftarm', 'action': 'Default', 'frame': 0, 'dx': -1, 'dy': 0, 'dd': 0 },
                    { 'id': 'torso', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 0, 'dd': 0 },
                    { 'id': 'head', 'action': 'Default', 'frame': 0, 'dx': 0, 'dy': 0, 'dd': 0 },
                    { 'id': 'rightarm', 'action': 'Default', 'frame': 0, 'dx': 1, 'dy': 0, 'dd': 0 }
                ]
            }
        ]
    }
};
```

- [ ] **Step 3: Register the animation in AvatarRenderManager**

In `$WORKDIR/src/nitro/avatar/AvatarRenderManager.ts`:

Add to the import block (after the existing `import { AvatarStructure } from './AvatarStructure';` line):

```typescript
import { DanceSixSevenAnimation } from './data/DanceSixSevenAnimation';
```

In `private loadAnimations()`, add the register call directly after `this._structure.initAnimation(HabboAvatarAnimations.animations);`:

```typescript
        this._structure.registerAnimation(DanceSixSevenAnimation);
```

(The method currently reads: `if(!this._structure) return;` → `initAnimation(...)` → `this._animationsReady = true;` → `this.checkReady();`.)

- [ ] **Step 4: Teach AvatarAction about expression 67**

In `$WORKDIR/src/api/nitro/avatar/enum/AvatarAction.ts`:

(a) Next to the other `EXPRESSION_*` constants, add:

```typescript
    public static EXPRESSION_67 = '67';
```

(b) In `getExpressionTimeout(expressionId)` (line ~54), add a case to the switch:

```typescript
            case 67:
                return 990;
```

(c) In `getExpressionId(expression)` (the function returning `EXPRESSION_MAP.indexOf(expression)`, line ~87), add as its first line:

```typescript
        if(expression === AvatarAction.EXPRESSION_67) return 67;
```

(d) In `getExpression(expressionId)` (line ~90, which starts with `if(expressionId > AvatarAction.EXPRESSION_MAP.length) return null;`), add as its first line:

```typescript
        if(expressionId === 67) return AvatarAction.EXPRESSION_67;
```

- [ ] **Step 5: AvatarImage appendAction case**

In `$WORKDIR/src/nitro/avatar/AvatarImage.ts`, find the `switch` group that contains `case AvatarAction.EXPRESSION_BLOW_A_KISS:` (line ~767) and add alongside it:

```typescript
            case AvatarAction.EXPRESSION_67:
```

(It joins the fall-through group with EFFECT/DANCE/TALK/EXPRESSION_WAVE/... that ends in `this.addActionData(k, _local_3);`.)

- [ ] **Step 6: AvatarVisualization expression mapping**

In `$WORKDIR/src/nitro/room/object/visualization/avatar/AvatarVisualization.ts`, find the expression switch containing `case AvatarAction.DANCE:` → `this._avatarImage.appendAction(AvatarAction.DANCE, 2);` (line ~942) and add a sibling case:

```typescript
                    case AvatarAction.EXPRESSION_67:
                        this._avatarImage.appendAction(AvatarAction.DANCE, 'sixseven');
                        break;
```

- [ ] **Step 7: AvatarExpressionEnum entry**

In `$WORKDIR/src/api/ui/widget/enums/AvatarExpressionEnum.ts`, after the `RESPECT` entry add:

```typescript
    public static EXPRESSION_67: AvatarExpressionEnum = new AvatarExpressionEnum(67);
```

- [ ] **Step 8: Seal the patch and verify the stack**

```bash
yarn patch-commit -s "$WORKDIR"
yarn install
```

Verify, from `client/`:
1. `grep -c "dance.sixseven" node_modules/@nitrots/nitro-renderer/src/nitro/avatar/data/DanceSixSevenAnimation.ts` → non-zero (patch applied).
2. `grep -c "RpRoomZoneSaveComposer" node_modules/@nitrots/nitro-renderer/src/nitro/communication/NitroMessages.ts` → non-zero (prior patches intact).
3. `git status --short` shows a NEW `.yarn/patches/@nitrots-nitro-renderer-patch-*.patch` file plus modified `package.json`/`yarn.lock`, and NO modifications to pre-existing patch files.
4. The new patch file's diff touches ONLY the six files from Steps 2-7.

- [ ] **Step 9: Build**

Run from `client/`: `yarn build`
Expected: completes with no TypeScript or Vite errors.

- [ ] **Step 10: Commit (client repo)**

```bash
git add .yarn/patches package.json yarn.lock
git commit -m "feat(renderer): sixseven dance animation for expression 67

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Emulator trigger — say or shout 67

**Files:**
- Modify: `emulator/HabboHotel/Rooms/RoomUser.cs` (~line 28)
- Modify: `emulator/Communication/Packets/Incoming/Rooms/Chat/ChatEvent.cs` (~line 110)
- Modify: `emulator/Communication/Packets/Incoming/Rooms/Chat/ShoutEvent.cs` (~line 108)
- Modify: `emulator/HabboHotel/Rooms/RoomUserManager.cs` (~line 1289)

**Interfaces:**
- Consumes: `ActionComposer(int virtualId, int action)` and `AvatarEffectComposer(int playerId, int effectId)` (both exist in `Communication/Packets/Outgoing/Rooms/Avatar/`, namespace `Plus.Communication.Packets.Outgoing.Rooms.Avatar`); `session.GetHabbo().Effects.CurrentEffect` (property, NOT a method); `user.IsDancing`, `user.DanceId`, `user.GetClient()`.
- Produces: broadcasting Expression id 67, which Task 1's renderer maps to the sixseven dance. `RoomUser.EffectReapplyTimer` consumed only by RoomUserManager's cycle.

- [ ] **Step 1: Add the RoomUser field**

In `emulator/HabboHotel/Rooms/RoomUser.cs`, directly under `public int CarryTimer; //byte` (line ~28), add:

```csharp
    // pixelrp: >0 while an enable is paused for the "67" gesture; the room
    // cycle counts it down and reapplies the effect at zero.
    public int EffectReapplyTimer;
```

- [ ] **Step 2: Add the trigger to ChatEvent**

In `emulator/Communication/Packets/Incoming/Rooms/Chat/ChatEvent.cs`, add to the using block at the top:

```csharp
using Plus.Communication.Packets.Outgoing.Rooms.Avatar;
```

Then find the end of `Parse` (currently `user.OnChat(user.LastBubble, message, false);` followed by `return;`) and insert BETWEEN those two lines:

```csharp
        // pixelrp: saying "67" plays the six-seven gesture (the client maps
        // expression 67 to a built-in dance). Any enable is paused so the
        // gesture is visible; the room cycle reapplies it two ticks later.
        if (message.Trim() == "67")
        {
            if (user.DanceId > 0)
                user.DanceId = 0;
            if (session.GetHabbo().Effects.CurrentEffect > 0)
            {
                room.SendPacket(new AvatarEffectComposer(user.VirtualId, 0));
                user.EffectReapplyTimer = 2;
            }
            room.SendPacket(new ActionComposer(user.VirtualId, 67));
        }
```

(`room` and `user` are existing locals in `Parse`; verify the names on sight before inserting.)

- [ ] **Step 3: Add the trigger to ShoutEvent**

In `emulator/Communication/Packets/Incoming/Rooms/Chat/ShoutEvent.cs`, add the same `using Plus.Communication.Packets.Outgoing.Rooms.Avatar;` to the using block, then insert the IDENTICAL code block from Step 2 between `user.OnChat(user.LastBubble, message, true);` and the final `return;`. Adjust the comment's first word to "shouting". Do NOT touch WhisperEvent.cs.

- [ ] **Step 4: Add the reapply countdown to the room cycle**

In `emulator/HabboHotel/Rooms/RoomUserManager.cs` (which already has `using Plus.Communication.Packets.Outgoing.Rooms.Avatar;`), find the carry-timer block in the user cycle (~line 1284):

```csharp
                    if (user.CarryItemId > 0)
                    {
                        user.CarryTimer--;
                        if (user.CarryTimer <= 0)
                            user.CarryItem(0);
                    }
```

Insert directly AFTER that block:

```csharp
                    // pixelrp: restore an enable paused by the "67" gesture once
                    // the ~1s client animation has finished.
                    if (user.EffectReapplyTimer > 0)
                    {
                        user.EffectReapplyTimer--;
                        if (user.EffectReapplyTimer <= 0 && !user.IsDancing)
                        {
                            var effect = user.GetClient()?.GetHabbo()?.Effects?.CurrentEffect ?? 0;
                            if (effect > 0)
                                _room.SendPacket(new AvatarEffectComposer(user.VirtualId, effect));
                        }
                    }
```

- [ ] **Step 5: Build**

Run from `emulator/`: `dotnet build 2>&1 | tail -5`
Expected: `Build succeeded` (warnings acceptable if pre-existing; zero errors).

- [ ] **Step 6: Commit (emulator repo)**

```bash
git add HabboHotel/Rooms/RoomUser.cs HabboHotel/Rooms/RoomUserManager.cs Communication/Packets/Incoming/Rooms/Chat/ChatEvent.cs Communication/Packets/Incoming/Rooms/Chat/ShoutEvent.cs
git commit -m "feat(chat): 67 plays the six-seven gesture (say + shout)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Changelog + root submodule bumps

**Files:**
- Modify: `CHANGELOG.md` (root repo; new dated section at the top, directly below the maintainer comment block, above any existing top entry)
- Modify: root repo `client` and `emulator` submodule pointers

**Interfaces:**
- Consumes: the committed client and emulator HEADs from Tasks 1 and 2.
- Produces: nothing.

- [ ] **Step 1: Add the changelog entry**

Insert into `CHANGELOG.md` immediately after the maintainer comment block's closing `-->`, above the current top entry:

```markdown
## 2026-08-31 — Six seven

### Added

- **Say "67" out loud.** Typing or shouting 67 in a room makes your avatar
  throw the six-seven hands for a second - dance paused, enable briefly
  tucked away, then everything back to normal. Whispering it does nothing;
  some things have to be said out loud.
```

- [ ] **Step 2: Commit (root repo, deploy-tagged)**

From the root repo:

```bash
git add CHANGELOG.md client emulator
git commit -m "feat(chat): 67 six-seven gesture (bump client + emulator)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

Do NOT push. The controller pushes all three repos (client and emulator before root) after review; pushing `beta` auto-deploys beta.pixelrp.co, and the user then tests in-game: say `67`, shout `67`, confirm whisper does nothing, and confirm an active enable returns ~1s after the gesture.
