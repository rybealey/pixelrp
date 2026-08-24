# Custom Chat Bubbles — Phase 1 (Testing) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship one staff-gated custom chat bubble style (id 40) end-to-end — AI-generated art → conversion script → client CSS/config → server gate — proving the pipeline for future custom styles.

**Architecture:** No emulator code changes. The client renders bubbles from CSS `border-image` 9-slice PNGs and builds the selector from the `chat.styles` ui-config array (`minRank: 5` hides it from non-staff). The Plus emulator already validates style ids against the `room_chat_styles` table and downgrades to style 0 when `required_right` (`mod_tool`) is missing. New pieces: an art prompt spec, a Python conversion script, one SCSS block, two config entries, one DB row.

**Tech Stack:** nitro-react client (SCSS/React, built via `docker/nitro/build-client.sh`), Python 3 + Pillow (conversion tool), MySQL 8 in docker compose (service `db`, database `pixelrp`), Plus emulator (C#, untouched).

**Spec:** `docs/superpowers/specs/2026-08-24-custom-chat-bubbles-design.md`

## Global Constraints

- Branch: `chat-bubbles` in the plus repo (off `beta`). Client submodule work happens on a new `chat-bubbles` branch in `client/` (off its `pixelrp` branch). Do NOT push to `beta` or client `pixelrp` — the user decides merges/pushes (beta auto-deploys).
- Custom style id is **40**. Id 39 stays reserved/unused.
- Pixel art is never smoothly resampled — nearest-neighbor only, and rendered 1:1 (`image-rendering: pixelated` is already applied by the widget's parent styles; do not add scaling).
- The DB insert never ships via git → it gets a `CHANGELOG.md` entry (repo discipline), and must be applied manually to each environment (local now; beta/prod at rollout).
- The client submodule currently sits 1 commit behind `origin/pixelrp` with local commits recorded past the plus repo's pointer — run `git pull --ff-only origin pixelrp` in `client/` before branching, and treat submodule state changes in the plus repo as expected.
- Do not screenshot-drive the Nitro client for final verification — static/build checks only, then hand off to the user for in-game testing (their stated preference).

## File map

| File | Action | Responsibility |
| --- | --- | --- |
| `docs/chat-bubble-art.md` | Create (plus repo) | Asset spec + ChatGPT generation prompt + iteration guide |
| `docker/nitro/make-chat-bubble.py` | Create (plus repo) | Oversized art → native 9-slice PNGs + printed SCSS |
| `client/src/assets/images/chat/chatbubbles/bubble_40.png`, `bubble_40_pointer.png` | Create (client submodule) | Bubble body + pointer art |
| `client/src/components/room/widgets/chat/ChatWidgetView.scss` | Modify (client submodule) | `&.bubble-40` render block |
| `nitro/ui-config.json`, `nitro/ui-config.prod.json` | Modify (plus repo) | `chat.styles` entry, staff-gated |
| `CHANGELOG.md` | Modify (plus repo) | Player-facing change + manual DB step |
| local `pixelrp` DB | Data | `room_chat_styles` row 40 |

---

### Task 1: Art prompt spec (`docs/chat-bubble-art.md`)

**Files:**
- Create: `docs/chat-bubble-art.md`

**Interfaces:**
- Consumes: nothing.
- Produces: the generation contract Task 2's script assumes — single PNG, transparent background, bubble body above a fully-transparent gap row, pointer below; decoration confined to edges; interior flat.

- [ ] **Step 1: Write the doc**

Create `docs/chat-bubble-art.md` with exactly this content (the prompt block is the deliverable the user pastes into ChatGPT):

````markdown
# Custom Chat Bubble Art — Generation Guide

Custom bubble styles are 9-slice CSS `border-image` assets. Native size is
tiny (body ~64×32 px, pointer ~11×7 px), so art is generated oversized and
converted down with `docker/nitro/make-chat-bubble.py`.

## Asset contract (what the converter expects)

One PNG, fully transparent background, containing **two shapes separated by
at least one fully-transparent horizontal band**:

1. **Top — bubble body.** A rounded-rectangle speech bubble, roughly 2:1
   width:height. All decoration (border, corner accents) must stay within
   the outer ~15% of the shape; the interior must be one flat, uniform
   fill — the middle gets stretched to any message length, so any texture
   or gradient there will smear.
2. **Bottom — pointer (tail).** A small downward-pointing triangle in the
   same style, drawn separately below the gap.

Hard-edged pixel art only. No anti-aliasing, no drop shadows, no outer
glow, no text, no background.

## ChatGPT prompt (paste as-is, then iterate)

> Create a single pixel-art image on a fully transparent background
> (PNG with alpha). The image contains exactly two separate shapes with a
> clear transparent gap between them, and nothing else.
>
> Shape 1 (top, large): a rounded-rectangle speech bubble body, about
> 900×420 pixels. Flat dark slate-blue fill (#2A2E3A). Crisp chunky
> pixel border (about 40 px thick) in neon cyan (#3EE6FF), with small
> square notch accents at the four corners in amber (#FFC94A). The
> interior must be completely flat and uniform — no gradients, no
> texture, no highlights — because it will be stretched. Keep all
> decoration within 120 pixels of the shape's edges.
>
> Shape 2 (bottom, small): a downward-pointing triangular speech-bubble
> tail, about 260×170 pixels, same fill and same neon cyan border style.
>
> Style rules: hard-edged pixels only, no anti-aliasing, no shadows, no
> glow, no outline bleed, no text, no watermark, transparent background.

This first concept is "Pixel City Neon" (dark surface + neon accents,
matching the PixelRP chrome look). For other concepts, keep the geometry
paragraphs and swap the colors/decoration description.

## After generating

Save the PNG (e.g. `~/Downloads/bubble40.png`) and run:

```bash
python3 docker/nitro/make-chat-bubble.py ~/Downloads/bubble40.png --id 40
```

The script writes the two assets into
`client/src/assets/images/chat/chatbubbles/` and prints the SCSS block
values. Rebuild the client (`docker/nitro/build-client.sh`) to see it.

Dark-fill concepts need white text overrides in the style's SCSS block
(see `&.bubble-40` in `ChatWidgetView.scss`); light-fill concepts don't.
````

- [ ] **Step 2: Commit (plus repo)**

```bash
git add docs/chat-bubble-art.md
git commit -m "docs: chat bubble art generation guide + ChatGPT prompt"
```

- [ ] **Step 3: Tell the user** the prompt is ready at `docs/chat-bubble-art.md` so they can start generating while the rest is built.

---

### Task 2: Conversion script (`docker/nitro/make-chat-bubble.py`)

**Files:**
- Create: `docker/nitro/make-chat-bubble.py`
- Test: throwaway self-test in the session scratchpad (synthetic input) — not committed.

**Interfaces:**
- Consumes: a PNG per Task 1's asset contract.
- Produces: `client/src/assets/images/chat/chatbubbles/bubble_<id>.png` (body, height 32 px) and `bubble_<id>_pointer.png` (pointer, height 7 px); prints an SCSS block using `--border` (default 12) as the slice value. CLI: `make-chat-bubble.py <input.png> --id <n> [--height 32] [--pointer-height 7] [--border 12] [--out <dir>]`.

- [ ] **Step 1: Write the failing test (synthetic input + expectations)**

Write `<scratchpad>/test_make_bubble.py`:

```python
import subprocess, sys, pathlib
from PIL import Image, ImageDraw

scratch = pathlib.Path(__file__).parent
out = scratch / "chatbubbles"
out.mkdir(exist_ok=True)

# Synthetic input honoring the asset contract: body on top, gap, pointer below.
img = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([60, 60, 960, 480], radius=60, fill=(42, 46, 58, 255), outline=(62, 230, 255, 255), width=40)
d.polygon([(400, 600), (660, 600), (530, 770)], fill=(42, 46, 58, 255))
src = scratch / "synthetic_bubble.png"
img.save(src)

REPO = "/Users/rybealey/Documents/Personal/pixelrp/plus"
r = subprocess.run([sys.executable, "docker/nitro/make-chat-bubble.py", str(src), "--id", "40", "--out", str(out)],
                   capture_output=True, text=True, cwd=REPO)
print(r.stdout, r.stderr)
assert r.returncode == 0

body = Image.open(out / "bubble_40.png")
pointer = Image.open(out / "bubble_40_pointer.png")
assert body.height == 32, body.size
assert body.width >= 28, body.size            # >= 2*border + 4
assert pointer.height == 7, pointer.size
# alpha is hardened: only 0 or 255
alphas = set(body.getchannel("A").getdata()) | set(pointer.getchannel("A").getdata())
assert alphas <= {0, 255}, sorted(alphas)[:5]
assert "border-image-slice: 12 12 12 12 fill" in r.stdout
print("OK")
```

(Fix `cwd=` to the actual plus repo root path when writing the file — the
executor knows it; do not commit this test.)

- [ ] **Step 2: Run it to make sure it fails**

Run: `python3 <scratchpad>/test_make_bubble.py`
Expected: FAIL — `make-chat-bubble.py` does not exist yet. If Pillow is missing, `pip3 install --user pillow` first (the other `docker/nitro/*.py` tools already use it).

- [ ] **Step 3: Write the script**

Create `docker/nitro/make-chat-bubble.py`:

```python
#!/usr/bin/env python3
"""make-chat-bubble.py - convert oversized AI-generated chat bubble art into
native-resolution 9-slice assets for the Nitro client.

Input: one PNG on a transparent background containing the bubble BODY on top
and the POINTER (tail) below it, separated by at least one fully transparent
row (see docs/chat-bubble-art.md).

Output: bubble_<id>.png + bubble_<id>_pointer.png in the client's chatbubbles
asset dir (or --out), downscaled with nearest-neighbor and alpha-hardened,
plus a ready-to-paste SCSS block on stdout.

Usage:
  python3 docker/nitro/make-chat-bubble.py input.png --id 40
"""
import argparse
import pathlib
import sys

from PIL import Image

DEFAULT_OUT = pathlib.Path(__file__).resolve().parents[2] / "client/src/assets/images/chat/chatbubbles"
ALPHA_THRESHOLD = 64


def opaque_rows(img):
    alpha = img.getchannel("A")
    w, h = img.size
    data = alpha.getdata()
    return [any(data[y * w + x] >= ALPHA_THRESHOLD for x in range(w)) for y in range(h)]


def split_regions(img):
    """Split into (body, pointer) at the widest fully-transparent row band."""
    rows = opaque_rows(img)
    bands = []  # (start, length) of transparent bands strictly between opaque content
    y = 0
    while y < len(rows):
        if not rows[y]:
            start = y
            while y < len(rows) and not rows[y]:
                y += 1
            if start > 0 and y < len(rows):  # interior band only
                bands.append((start, y - start))
        else:
            y += 1
    if not bands:
        sys.exit("error: no transparent band between body and pointer - input must contain two shapes (see docs/chat-bubble-art.md)")
    split_at = max(bands, key=lambda b: b[1])[0]
    return img.crop((0, 0, img.width, split_at)), img.crop((0, split_at, img.width, img.height))


def crop_to_alpha(img):
    bbox = img.getchannel("A").point(lambda a: 255 if a >= ALPHA_THRESHOLD else 0).getbbox()
    if bbox is None:
        sys.exit("error: region is fully transparent")
    return img.crop(bbox)


def harden_alpha(img):
    r, g, b, a = img.split()
    return Image.merge("RGBA", (r, g, b, a.point(lambda v: 255 if v >= 128 else 0)))


def downscale(img, target_height):
    scale = target_height / img.height
    width = max(1, round(img.width * scale))
    return img.resize((width, target_height), Image.NEAREST)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=pathlib.Path)
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--height", type=int, default=32, help="native body height (px)")
    p.add_argument("--pointer-height", type=int, default=7, help="native pointer height (px)")
    p.add_argument("--border", type=int, default=12, help="9-slice border (px) for the SCSS block")
    p.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = p.parse_args()

    img = Image.open(args.input).convert("RGBA")
    body_raw, pointer_raw = split_regions(img)
    body = harden_alpha(downscale(crop_to_alpha(body_raw), args.height))
    pointer = harden_alpha(downscale(crop_to_alpha(pointer_raw), args.pointer_height))

    if body.width < 2 * args.border + 4:
        sys.exit(f"error: body too narrow ({body.width}px) for a {args.border}px 9-slice border")

    args.out.mkdir(parents=True, exist_ok=True)
    body_path = args.out / f"bubble_{args.id}.png"
    pointer_path = args.out / f"bubble_{args.id}_pointer.png"
    body.save(body_path)
    pointer.save(pointer_path)

    b = args.border
    print(f"wrote {body_path} ({body.width}x{body.height})")
    print(f"wrote {pointer_path} ({pointer.width}x{pointer.height})")
    print(f"""
SCSS block for ChatWidgetView.scss (inside `.bubble-container .chat-bubble`,
after the last stock `&.bubble-38` block):

        &.bubble-{args.id} {{
            border-image-source: url('@/assets/images/chat/chatbubbles/bubble_{args.id}.png');

            border-image-slice: {b} {b} {b} {b} fill;
            border-image-width: {b}px {b}px {b}px {b}px;
            border-image-outset: 0px 0px 0px 0px;

            .chat-content {{
                margin-left: 20px;
            }}

            .pointer {{
                background: url('@/assets/images/chat/chatbubbles/bubble_{args.id}_pointer.png');
                width: {pointer.width}px;
                height: {pointer.height}px;
                bottom: -{pointer.height - 1}px;
            }}
        }}
""")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 <scratchpad>/test_make_bubble.py`
Expected: `OK`, and the two PNGs exist under the scratchpad `chatbubbles/` dir.

- [ ] **Step 5: Commit (plus repo)**

```bash
git add docker/nitro/make-chat-bubble.py
git commit -m "feat: chat bubble art conversion tool (9-slice from AI art)"
```

---

### Task 3: Client wiring — placeholder assets + SCSS (client submodule)

**Files:**
- Create: `client/src/assets/images/chat/chatbubbles/bubble_40.png`, `bubble_40_pointer.png` (placeholder, from Task 2's synthetic art)
- Modify: `client/src/components/room/widgets/chat/ChatWidgetView.scss` (after the `&.bubble-38` block, which ends near line 723)

**Interfaces:**
- Consumes: Task 2's script and its synthetic test input.
- Produces: `bubble-40` CSS class the running client resolves; assets committed on client branch `chat-bubbles`.

- [ ] **Step 1: Branch the client submodule**

```bash
cd client
git pull --ff-only origin pixelrp
git checkout -b chat-bubbles
```

Expected: clean fast-forward, new branch. (The plus repo will show a changed submodule pointer later — expected.)

- [ ] **Step 2: Generate placeholder assets into the real asset dir**

From the plus repo root, rerun the converter on the synthetic image Task 2 created, without `--out` so it writes into the client tree:

```bash
python3 docker/nitro/make-chat-bubble.py <scratchpad>/synthetic_bubble.png --id 40
```

Expected: `bubble_40.png` (~64×32 or narrower) and `bubble_40_pointer.png` (~×7) appear in `client/src/assets/images/chat/chatbubbles/`, and the SCSS block prints.

- [ ] **Step 3: Add the SCSS block**

In `client/src/components/room/widgets/chat/ChatWidgetView.scss`, immediately after the closing brace of the `&.bubble-38 { ... }` block (still inside `.bubble-container .chat-bubble`), paste the block the script printed, then add the dark-fill text overrides so the block reads:

```scss
        &.bubble-40 {
            border-image-source: url('@/assets/images/chat/chatbubbles/bubble_40.png');

            border-image-slice: 12 12 12 12 fill;
            border-image-width: 12px 12px 12px 12px;
            border-image-outset: 0px 0px 0px 0px;

            .chat-content {
                margin-left: 20px;
            }

            .username {
                color: rgba($white, 1);
            }

            .message {
                color: rgba($white, 1) !important;
            }

            .pointer {
                background: url('@/assets/images/chat/chatbubbles/bubble_40_pointer.png');
                width: 11px;
                height: 7px;
                bottom: -6px;
            }
        }
```

(Use the actual pointer width/height/bottom values the script printed if they differ. The `.username`/`.message` white overrides follow the `&.bubble-2` pattern in the same file and exist because the concept has a dark fill. Do NOT add anything to the dead `.chat-bubble-icon` section at the bottom of the file — it has no consumer.)

- [ ] **Step 4: Verify the build compiles the CSS**

From the plus repo root:

```bash
docker/nitro/build-client.sh
grep -c "bubble-40" nitro/client/src/assets/*.css
```

Expected: build succeeds; grep finds at least 1 match.

- [ ] **Step 5: Commit (client submodule)**

```bash
cd client
git add src/assets/images/chat/chatbubbles/bubble_40.png src/assets/images/chat/chatbubbles/bubble_40_pointer.png src/components/room/widgets/chat/ChatWidgetView.scss
git commit -m "feat: custom chat bubble style 40 (placeholder art)"
```

Do not push.

---

### Task 4: Config entries + DB row + reload

**Files:**
- Modify: `nitro/ui-config.json`, `nitro/ui-config.prod.json` (the `chat.styles` array, currently ending at styleId 38)
- Modify: `CHANGELOG.md`
- Data: local `pixelrp` DB, `room_chat_styles`

**Interfaces:**
- Consumes: `bubble-40` CSS from Task 3.
- Produces: style 40 selectable by rank ≥ 5 accounts, server-enforced.

- [ ] **Step 1: Add the config entry to both files**

In each of `nitro/ui-config.json` and `nitro/ui-config.prod.json`, append to the `"chat.styles"` array after the styleId 38 entry:

```json
{ "styleId": 40, "minRank": 5, "isSystemStyle": false, "isHcOnly": false, "isAmbassadorOnly": false }
```

Verify both parse and carry the entry:

```bash
python3 - <<'EOF'
import json
for f in ("nitro/ui-config.json", "nitro/ui-config.prod.json"):
    styles = json.load(open(f))["chat.styles"]
    e = [s for s in styles if s["styleId"] == 40]
    assert e == [{"styleId": 40, "minRank": 5, "isSystemStyle": False, "isHcOnly": False, "isAmbassadorOnly": False}], (f, e)
    assert 40 not in json.load(open(f))["chat.styles.disabled"], f
print("OK")
EOF
```

Expected: `OK`.

- [ ] **Step 2: Reinstall the served config**

`build-client.sh` already copies `nitro/ui-config.json` → `nitro/client/ui-config.json`; rerun the copy (no rebuild needed):

```bash
cp nitro/ui-config.json nitro/client/ui-config.json
python3 -c "import json; assert any(s['styleId'] == 40 for s in json.load(open('nitro/client/ui-config.json'))['chat.styles']); print('OK')"
```

Expected: `OK`.

- [ ] **Step 3: Insert the DB row (local) and hot-reload**

```bash
docker compose up -d db
docker compose exec db sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" pixelrp -e "INSERT INTO room_chat_styles (id, name, required_right) VALUES (40, \"pixelrp_custom_1\", \"mod_tool\");"'
docker compose exec db sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" pixelrp -e "SELECT * FROM room_chat_styles WHERE id = 40;"'
```

Expected: the SELECT prints `40  pixelrp_custom_1  mod_tool`.

If the emulator is running, hot-reload styles from any staff account in-game with `:update chat_styles` (permission `command_update_chat_styles`); otherwise the row loads at next emulator boot — note which applies in the handoff message.

- [ ] **Step 4: CHANGELOG entry**

Add under today's date in `CHANGELOG.md`, matching the file's existing entry style:

```markdown
- Added custom chat bubble style 40 ("Pixel City Neon", staff-only for testing). Requires manual DB step per environment: `INSERT INTO room_chat_styles (id, name, required_right) VALUES (40, 'pixelrp_custom_1', 'mod_tool');` then `:update chat_styles` in-game.
```

- [ ] **Step 5: Commit (plus repo, including the submodule pointer)**

```bash
git add nitro/ui-config.json nitro/ui-config.prod.json CHANGELOG.md client
git commit -m "feat: custom chat bubble style 40 - staff-gated config + changelog"
```

---

### Task 5: Verification + handoff

**Files:** none (checks only).

**Interfaces:**
- Consumes: everything above.
- Produces: a handoff message; the user tests in-game.

- [ ] **Step 1: Static end-to-end checks**

```bash
# CSS shipped in the built bundle
grep -c "bubble-40" nitro/client/src/assets/*.css
# assets shipped
ls nitro/client/src/assets | grep -i "bubble_40" || grep -rl "bubble_40" nitro/client/src/assets | head -2
# served config has the entry
python3 -c "import json; print([s for s in json.load(open('nitro/client/ui-config.json'))['chat.styles'] if s['styleId'] == 40])"
# DB row present
docker compose exec db sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" pixelrp -e "SELECT id, required_right FROM room_chat_styles WHERE id = 40;"'
```

Expected: every check non-empty. (Vite content-hashes/inlines small assets — if the `ls` finds nothing, the `grep -rl` for an inlined data URI or hashed name must hit.)

- [ ] **Step 2: Hand off to the user**

Report, in the final message: what to test in-game locally (staff account → selector shows the new style at the end → send chat/shout/whisper, bubble renders with placeholder art at short and 100-char message lengths; non-staff account → style absent from selector), that the art is a synthetic placeholder until they run the ChatGPT prompt from `docs/chat-bubble-art.md`, and the exact command to swap in real art (Task 6). Note that nothing has been pushed anywhere.

---

### Task 6: Real art swap-in (BLOCKED until the user delivers generated art)

**Files:**
- Modify: `client/src/assets/images/chat/chatbubbles/bubble_40.png`, `bubble_40_pointer.png` (overwrite)
- Possibly modify: the `&.bubble-40` block (pointer dimensions, text color if the final concept is light-filled)

**Interfaces:**
- Consumes: the user's generated PNG (per `docs/chat-bubble-art.md`) at a path they provide.
- Produces: final assets committed on the client `chat-bubbles` branch.

- [ ] **Step 1: Convert**

```bash
python3 docker/nitro/make-chat-bubble.py <user-provided-path>.png --id 40
```

Expected: overwrites both PNGs; printed pointer dimensions noted.

- [ ] **Step 2: Reconcile the SCSS block**

Update `.pointer` `width`/`height`/`bottom` in the `&.bubble-40` block to the printed values if they changed. If the final art has a light fill, delete the `.username`/`.message` white overrides.

- [ ] **Step 3: Rebuild and re-verify**

```bash
docker/nitro/build-client.sh
grep -c "bubble-40" nitro/client/src/assets/*.css
```

Expected: build succeeds, grep ≥ 1.

- [ ] **Step 4: Commit (client submodule + plus pointer)**

```bash
cd client && git add src/assets/images/chat/chatbubbles src/components/room/widgets/chat/ChatWidgetView.scss && git commit -m "feat: chat bubble 40 final art"
cd .. && git add client && git commit -m "chore: bump client - chat bubble 40 final art"
```

- [ ] **Step 5: Hand off for in-game testing again** (same checklist as Task 5 Step 2). Merging to `beta`/`pixelrp` and the beta DB insert happen only when the user says so.
