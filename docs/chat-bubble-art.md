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
