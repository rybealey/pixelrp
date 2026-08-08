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

## 2026-08-08 — You're a Pixel now

### Changed

- **The hotel speaks PixelRP.** Every mention of "Habbo" in the game's text
  now says PixelRP, and players are called Pixels — from the room-chat notice
  to quest stories and catalogue blurbs. Historical event names (Habboween,
  HabboQuests and friends) keep their original titles, and the hotel rules
  still name the other hotel where they genuinely mean it.

## 2026-08-08 — Emoji come to chat

### Added

- **Send emoji in chat.** A little emoji sits at the right end of the chat
  bar — hover it and it shuffles with a pop. Click it to open a drawer of
  every emoji there is, sorted by category, and tap any to drop it into your
  message.
- **Type shortcodes, get emoji.** Finish typing a code like `:sob:` or
  `:fire:` in the chat bar and it instantly becomes 😭 or 🔥. Nearly two
  thousand codes work — hover an emoji in the drawer to learn its code.

### Changed

- **The chat bar is wider**, so longer messages stay readable while you type.
- Chat history timestamps now include seconds (HH:MM:SS).

## 2026-08-08 — A tidier corner and toolbar

### Added

- **The room you're in is always visible.** A slim card next to your wallet
  shows the current room's name (staff also see the room's number).
- **See how many Pixels are online.** A small counter sits beside the room
  name card and keeps itself up to date.

### Changed

- **The toolbar is now just the P.** Your avatar portrait and the old row of
  icons are gone; staff tools (navigator, shop, inventory, camera, mod tools)
  slide out of the PixelRP emblem when staff click it, and tuck back in when
  they're done.
- The wallet now matches the width of the notices beneath it, and pop-up
  notices got roomier padding with text that uses the full card.
- The big room-name banner that slid in every time you entered a room is
  gone — the corner card replaced it.
- The "Join" club box in the wallet is gone — there's no club membership
  here.

## 2026-08-08 — A fresh coat of paint

### Changed

- **New loading screen.** Loading the hotel now shows PixelRP artwork instead
  of the old duck animation, with the same progress bar.
- **New look for the website.** The PixelRP wordmark replaces the old logo,
  and the banner behind the login area shows the city bar scene.

## 2026-08-08 — Missing pictures, found

### Fixed

- **Every furniture icon now shows.** Coloured furniture — most visibly the
  entire Builders Club range — had blank squares in the catalogue and
  inventory; all of them now have their proper coloured icons.
- **A few catalogue categories had broken icons** (Alphabet among them);
  they're fixed.
- **One hairstyle was invisible** in Change Your Looks — both in the picker
  and on your avatar. It's back.

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
