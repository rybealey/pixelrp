# Room Background offset scrubbers — design

## Goal

Let staff position a Room Background (`ads_background`) image without
guesswork: the infostand's offsetX/offsetY/offsetZ rows gain interactive
controls that move the image on screen in realtime, while the text inputs
remain for precise values.

## Decisions (agreed with Ry, 2026-08-10)

- **Local preview + explicit Save.** Adjustments update only the editing
  client's view, by writing `FURNITURE_BRANDING_OFFSET_X/Y/Z` into the room
  object's model. Nothing is sent to the server until Save (existing
  `SetObjectDataMessageComposer` path, unchanged). Closing the infostand
  without saving restores the model values captured when editing began.
- **Steppers + drag-to-scrub.** Each offset row is: axis label (drag target)
  · `−` · text input · `+`.
  - Click `−`/`+` = ±1; Shift-click = ±10; holding repeats (~120 ms,
    accelerating to ±10 steps after ~1 s).
  - Dragging horizontally on the label scrubs the value (1 px = 1 unit,
    Shift = 10×); cursor shows `ew-resize`.
  - Typed input previews too; non-numeric (e.g. legacy `NaN`) is treated
    as 0 for preview but the field keeps what was typed until blurred.

## Scope

Client only (`client/` nitro-react). No emulator, protocol, or permission
changes. The controls appear only in the god-mode branding editor
(`RoomWidgetEnumItemExtradataParameter.BRANDING_OPTIONS`), which requires
controller level 5 — staff holding `room_item_save_branding_items`.

## Components

- `FurniSettingScrubberInput.tsx` (new, colocated with
  `InfoStandWidgetFurniView`): presentational control owning stepper/scrub
  /hold-repeat interaction. Props: `label`, `value: string`,
  `onChange(value: string)`. Emits string values; no room-engine knowledge.
- `InfoStandWidgetFurniView.tsx`: renders the new control for keys
  `offsetX|offsetY|offsetZ` (other keys keep the plain input); on any offset
  change also writes the parsed number into the room object model via
  `GetRoomEngine().getRoomObject(...)`; snapshots the three model values when
  the branding editor opens and restores them on close/unmount unless Save
  was pressed.

## Why the preview works with no renderer changes

`FurnitureBrandedImageVisualization.updateModel` re-reads
`FURNITURE_BRANDING_OFFSET_X/Y/Z` whenever the model version changes, and
`FurnitureRoomBackgroundVisualization.getLayer(X|Y|Z)Offset` applies them
each render pass. `model.setValue` bumps the version, so the sprite moves on
the next frame. Z is applied negated by the renderer; the controls pass the
raw number through, identical to today's save semantics.

## Error handling

- Missing room object (e.g. item removed mid-edit): preview writes are
  skipped silently; Save already no-ops server-side.
- Restore-on-close only runs if the editor was opened on a branding item and
  Save wasn't pressed.

## Testing

Manual, on the local stack as ClaudeTest (rank 7), Vite dev client:
scrub X/Y and watch the image track in realtime; hold a stepper; type an
exact value; Save → reload room → values persist (DB `extra_data` map);
close without saving → image snaps back to saved position.
