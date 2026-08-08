# PixelRP — Hotel Updates

What's changed in the hotel, written for players. Newest first.

<!--
For maintainers: this file is player-facing. Describe what someone *sees or
does* in the hotel, not how it was built — "avatars stood around with their
mouths open" rather than "sprite alias resolution". No file paths, commit
hashes, container names, or version numbers of internal components. If a
change has no effect a player could notice, it doesn't belong here; put it in
the commit message instead.

Group each dated release under Added / Changed / Fixed / Known issues (drop
any heading with nothing under it).
-->

## 2026-08-08 — Check your ping

### Added

- **Type `:ping` to see your connection speed.** A quick whisper pops up over
  your avatar showing your current ping in milliseconds — only you can see it,
  and it doesn't get sent to the room.

## 2026-08-08 — Easier-to-read text

### Changed

- **The in-game text uses a cleaner font.** We swapped the narrow "condensed"
  lettering across the interface for the standard, slightly wider Ubuntu font,
  so menus, chat, and labels are a touch easier to read.

## 2026-08-08 — Pick up where you left off

### Added

- **You now log back in right where you were.** Closing the game — or losing
  connection — no longer sends you back to the hotel screen. On your next
  login you'll be standing in the same room, on the same tile, facing the
  same way as when you left. If that room has since been locked or removed,
  you'll land on the hotel screen like before.

## 2026-08-08 — Tidier toolbar

### Changed

- Removed the "Find new friends" bar from the bottom toolbar.

## 2026-08-08 — Shop banners are back

### Fixed

- **Catalogue category pictures now show.** The banner image to the right of
  the furniture list (and the front-page promos) were blank on most pages;
  they now load. A handful of very old or one-off pages still have no banner
  because the original artwork is no longer available anywhere.

## 2026-08-08 — Your look updates instantly

### Fixed

- **Changing your look updates everywhere right away.** Your avatar in the
  bottom-left menu button and on the hotel landing screen now refresh the
  moment you save a new look — no page reload needed.

## 2026-08-08 — Clothes you pick are the clothes you get

### Fixed

- **Wearables now save correctly.** Picking many newer clothing items — modern
  shorts, jeans, and lots of other pieces — used to silently swap to a default
  garment when you saved (famously: choose denim shorts, end up in a skirt).
  Every item the wardrobe offers is now recognised when you save, so your
  avatar wears exactly what you chose, across every clothing category.

## 2026-08-08 — Snappier walking

### Changed

- **Walking starts the instant you click.** There used to be a brief, uneven
  hesitation before your avatar set off — up to half a second depending on
  timing. Your first step now goes out immediately. Walking speed itself is
  exactly the same; only the delay before that first step is gone.

## 2026-08-08 — Shop, badges & catalogue art

### Added

- **The shop looks like a shop again.** Furniture, the exchange, and the pet
  shop now show item pictures instead of blank boxes, so you can actually see
  what you're browsing.
- **Badges have their pictures back** across profiles, the badge inventory, and
  room displays.

### Known issues

- A small number of custom badges and catalogue icons still show blank — those
  particular images don't exist in the standard art set and need to be added by
  hand.

## 2026-08-07 — Hotel launch 🎉

The hotel is open! PixelRP now runs on a brand-new server and a modern
browser-based client — no downloads, no plugins, just open the site and click
into the hotel.

### Added

- **The hotel is live at [pixelrp.co](https://pixelrp.co).** Create an account,
  design your avatar, and step in.
- **Play straight from your browser.** The client runs in any modern browser on
  a secure connection.
- **Make your own rooms.** Build, decorate, and invite people in.
- **Chat, walk, and hang out** — the classic hotel experience.

### Fixed

- Avatars no longer stand around with their mouths hanging open — your mouth
  now moves only when you're actually talking.
- Faces render properly. Noses and mouths were invisible on idle avatars.
- The hotel view is clean: the placeholder promo panels that used to cover the
  scene with leftover demo text are gone.

### Known issues

- **IP bans don't stick.** Staff: banning by IP currently has no effect — use
  account bans until this is sorted.
