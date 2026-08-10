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

## 2026-08-10 — New staff badge

### Changed

- **The badge floating above staff members' heads is new.** The old gold
  "Habbo Staff" diamond is gone — staff now glow with PixelRP's own pink
  medallion.

## 2026-08-10 — Staff dress free

### Added

- **Staff (rank 4+) can now use all sellable clothing in the Choose Your Look
  window without purchasing it.** Access is removed automatically if demoted
  below rank 4 — unpurchased items vanish from the panel and from the worn
  look at next login. Clothing they actually purchased is unaffected.

## 2026-08-10 — Changing booths are now how you change your look

### Changed

- **Changing booths (Builders > Corporations > Clothing) now open the Change
  Your Looks window automatically while you stand in them**, and close it when
  you step out. The "My clothes" context-menu item and the toolbar clothing
  button are removed — booths are now the only way to change your look.

## 2026-08-10 — Fresh staff toolbar icons

### Changed

- **The staff toolbar got new icons.** The menu that unfolds from the "P"
  button now shows a redrawn compass, shop bag, inventory box, camera and
  mod-tools badge — drawn at their real size, so they're crisp instead of
  stretched.

## 2026-08-10 — Jeen and Azul join the staff team

### Changed

- **Jeen and Azul are now hotel staff.** Say hi — they can now help out
  with staff tools around the hotel.
- **The old "Admin" account has been retired.** It's gone from the hotel;
  its news posts now live under Ry.

## 2026-08-10 — Shop rules up front

### Added

- **The Builders and Staff shop tabs now open with the ground rules.** An
  Information page sits at the top of each section explaining that its tools
  and furniture are for builders/staff only, for use in roleplay settings —
  and not to be freely handed out without approved justification.

### Changed

- **The Builders shop tab got a reorganization.** "Builders Club" is now
  called "Blocks" (which is what it actually holds), Navigation moved up
  above it, and there's a new Corporations category below with sections for
  each workplace: Armory, Cafe, Casino, Clothing, Hospital, Police and
  Staff. Police opens with a curated set of security furniture exclusive to
  the San Francisco Police Department, Clothing carries the boutique
  fittings (changing booths, mannequin, shoe racks and shelves), the
  Corporations page itself holds the shared business pieces — cash register
  and notice board — and the Navigation section now explains its role in
  getting between rooms.

### Fixed

- **Two Boutique furni finally show their shop icons.** The sofa and the
  cash register appeared as blank squares in the shop grid — both now have
  proper icons.

## 2026-08-10 — The chrome chain comes in colors

### Changed

- **The chrome chain is now colorable.** Pick it in the avatar editor and
  you'll get two color choices: one for the chain itself and one for the
  pendant. Mix and match to fit your look — already-saved chains keep
  working and simply use your first color for the chain.

## 2026-08-10 — Signs are now staff-only

### Changed

- **The Signs menu is now reserved for staff.** Clicking your avatar no longer
  shows the Signs option unless you're on the hotel team — regular players
  keep My clothes, Dance and Actions as before.

## 2026-08-10 — New wardrobe item: chrome chain

### Added

- **A chrome chain accessory is in the wardrobe.** Open the avatar editor's
  chest-accessory tab and you'll find a shiny new chrome chain. It's free and
  available to everyone, no membership or purchase needed.

## 2026-08-10 — Walls stay hidden, and they're gone by default

### Changed

- **Rooms now start with their walls hidden.** Every room — new and existing —
  has invisible walls out of the box, so backgrounds and open layouts are the
  norm. Prefer the classic boxed-in look? Untick "Hide walls" in your room's
  settings to bring them back.
- **The hotel view drape got a PixelRP makeover.** The old Habbo banner that
  hung over the hotel view has been replaced with proper PixelRP artwork.

### Fixed

- **"Hide walls" finally sticks.** Ticking it in room settings used to hide
  the walls only until the room reloaded — the saved choice was misread on
  load, and even when it wasn't, the client never got the memo. Both ends are
  fixed: the setting survives restarts and reloads, and wall thickness and
  floor thickness settings now reach the room view too (they were silently
  ignored before).

## 2026-08-10 — Room backgrounds actually show up

### Fixed

- **The background image you set now really appears in the room.** The earlier
  fix let staff open the Room Background editor and save an image link, but
  the picture itself stubbornly refused to draw — the saved settings reached
  everyone's screens in a shape the game didn't recognise. Saved backgrounds
  now display for everyone in the room, survive restarts, and previously
  saved ones start working on their own.

## 2026-08-10 — Room backgrounds actually work

### Fixed

- **The Room Background furni from the staff shop does something now.** Any
  staff member could buy it, place it… and then stare at it, because clicking
  it offered nothing to configure and no image ever appeared. Staff who own a
  room can now click the placed furni, paste an image link, nudge it into
  place with the offset fields, and the picture shows up behind the room for
  everyone who visits.

## 2026-08-10 — Wired furniture can't lock you out anymore

### Fixed

- **Placing a wired gadget no longer breaks the room for everyone.** A wired
  item placed in a room could leave that room refusing to let anyone in —
  you'd walk through a teleporter or click a room and just never arrive.
  This briefly hit the main spawn room, which locked most of the city out;
  rooms now load normally even with wired gadgets in them. (Wired gadgets
  themselves still don't do anything — that's a project for another day.)

## 2026-08-09 — No more free coins for standing around

### Changed

- **Coins no longer trickle in while you're online.** Until now the hotel
  quietly handed out coins and pixels every 15 minutes just for being logged
  in. That tap is now off — your balance only changes when you actually earn
  or spend something.

## 2026-08-09 — Floor plan saves no longer strand you

### Fixed

- **Saving a floor plan now puts everyone back in the room.** Saving used to
  leave you (and anyone else standing in the room) staring at a black screen,
  unable to enter any room at all until you logged out and back in. Now the
  room reloads with its new layout and everyone walks right back in.

## 2026-08-09 — A tidier wallet

### Changed

- **Duckets are gone.** The purple ducket counter no longer appears in the
  wallet — PixelRP runs on credits and diamonds.

## 2026-08-09 — PixelRP gets its own tab icon

### Changed

- **A pixel-art "P" now marks every PixelRP tab.** The website, the hotel
  client, and housekeeping all show the same pink pixel "P" in your browser
  tab — no more mismatched or missing icons. It's also the icon you'll see
  if you pin PixelRP to your phone's home screen.

## 2026-08-09 — Restarts count themselves down

### Changed

- **Update restarts now warn you with a countdown.** Instead of the old
  pop-up box, a "Platform" toast appears in the corner: "A software update
  has been pushed. PixelRP is restarting in… 15 seconds." — and the number
  actually ticks down, second by second, before the hotel restarts and the
  update screen takes over.

## 2026-08-09 — Reconnect actually reconnects

### Fixed

- **The ▶ Reconnect button works now.** After an update finished, clicking
  Reconnect just showed you the update screen all over again. It now
  properly reloads the client with a fresh login, dropping you straight
  back into the city.

## 2026-08-09 — Idle players nap in place

### Changed

- **Going AFK no longer yanks you out of the room.** Stepping away used to
  eventually dump you back to the hotel view, stranding you mid-scene. Now
  your avatar just falls asleep where it stands, and if you haven't typed
  or moved for a full hour, you're simply logged out — reconnect and you'll
  land right back in the room.

## 2026-08-09 — Updates got a proper waiting room

### Added

- **A real "update in progress" screen.** When the team ships a hotel
  update, you're no longer dumped on the plain "you have been disconnected"
  box. Instead: the city terrace at sunset, the animated logo, a pixel
  progress bar following the update step by step with a time estimate, and
  the patch notes for what's landing — straight from this page. The moment
  every district is back online, a ▶ Reconnect button drops you right back
  in where you left off.

### Changed

- **The hotel says goodbye properly.** Restarts for updates now finish
  saving everyone's inventory and close every connection cleanly instead
  of cutting to black mid-step.

## 2026-08-09 — The hotel found its tannoy

### Added

- **Hotel-wide announcements.** Staff can now broadcast a message to everyone
  online. It arrives as the small dark notification bubble in the corner —
  the same style as the moderation notice — instead of a pop-up box.
- **Announcements got a proper look.** Hotel-wide messages now arrive as a
  tidy "Platform" toast — labeled so you know it's official, sized to fit
  the message, sticking around for 45 seconds, and dismissible with a small
  × in the corner. (An earlier version showed a broken picture and squashed
  the text sideways.)
- **Personal alerts from the team.** Staff can now send a notice to a single
  player. It shows up as the same corner toast as hotel announcements, but
  tinted red with a "Moderation" label so you know it's meant just for you.
  Staff can also send one to themselves to preview how it looks — the
  command no longer talks back when you try.
- **Moderation caught up with the new toasts.** Messages, cautions, mute and
  trade-ban notices from the moderation team — and the reason when you're
  kicked from a room — now arrive as the red "Moderation" toast, which stays
  on screen until you close it. Room-wide notices appear as a blue
  "Information" toast for everyone in the room.

### Fixed

- **Muting from the moderation panel works now.** Muting a player through
  the mod tools used to fail silently; it now mutes for the full hour and
  tells the player why.
- **The online counter isn't stuck at zero anymore.** The hotel always
  reported nobody online, no matter how many people were in. The count shown
  by `:info` and used by wired message boxes (`%USERSONLINE%`) is now real.
- **More staff tools reach people again.** Staff alerts, advertising
  reports to moderators, hotel-wide badge handouts, and live rank reloads
  were all quietly reaching no one — same void as the broadcast fix below.
  They now reach everyone online, and everyone's inventory is properly
  saved when the hotel shuts down.
- **Hotel-wide messages actually arrive now.** The under-the-hood channel
  for messaging everyone at once had been broadcasting into the void; any
  future hotel-wide announcements, staff alerts, and similar messages now
  reach every online player.

## 2026-08-09 — The emoji face calmed down

### Fixed

- **The chat bar's emoji face no longer strobes in Safari.** Hovering the
  emoji button is supposed to show one new random face with a little pop;
  in Safari it flickered through faces endlessly until you moved the mouse
  away. It now behaves the same in every browser.

## 2026-08-08 — Doorways stopped swallowing people

### Changed

- **Room doorways no longer dump you out of the room.** The tile you arrive
  on when entering a room used to double as an exit — one wrong step and you
  were staring at the hotel view. It's now a normal tile you can walk on and
  stand on. Move between rooms using the teleport arrows.

## 2026-08-08 — Claude has an off switch

### Added

- **Staff can now send Claude home for the night.** Typing `:bot off` in any
  room disconnects the Claude bot within a few seconds; `:bot on` brings it
  back, and `:bot` alone whispers whether it's currently on or off. The
  setting sticks — Claude stays off through restarts until someone turns it
  back on.

## 2026-08-08 — Rooms unfroze, furni found their owners

### Fixed

- **Stepping onto furniture no longer freezes the room.** Walking onto any
  item placed since the room was loaded — a teleport arrow, a chair, anything
  — left every avatar in the room marching in place forever: nobody could
  walk, sit, or teleport until the hotel was restarted. Freshly placed
  furniture now behaves exactly like furniture that was already there.
- **Furniture knows who owns it.** Clicking an item used to show a blank
  Owner line unless the stars aligned. The info panel now names the owner for
  every floor and wall item — including ones just placed, and ones owned by
  someone other than the room's owner.

## 2026-08-08 — The create-room button answers back

### Fixed

- **Creating a room no longer fails silently.** If something goes wrong —
  the name is too short or too long, or the chosen layout isn't available —
  the hotel now shows a message saying so instead of doing nothing. A rare
  case where picking an unrecognized category could make the request vanish
  entirely now files the room under "All Other Rooms" instead.

## 2026-08-08 — Ways to get around

### Added

- **New navigation furni for builders.** The staff shop's Builders section
  has a new Navigation page with directional arrows, an animated action
  point, and a taxi sign. The arrows come in linked pairs — step on one and
  you're whisked to its twin, even if it's in a different room. They're the
  new backbone for walking between connected areas of the hotel.

## 2026-08-08 — Claude moved in

### Added

- **Claude now lives in the hotel.** Say "claude" in any room it's in (it
  hangs out in Moody's Pointe) and it'll chat back — or whisper it for a
  private word. It remembers things you tell it, walks around, and follows
  the hotel gossip. Be nice to it; it fixed your rooms.

## 2026-08-08 — The Create button really creates now

### Fixed

- **For some players, creating a room did nothing at all.** If one of your
  existing rooms dated back far enough, the Create room button silently
  failed no matter what name you typed, and the My World tab could load
  empty. Those older rooms no longer break anything — creating rooms and
  browsing My World work for everyone again.

## 2026-08-08 — Photos on the wall, for real this time

### Fixed

- **Wall photos showed up as a black square once a room reloaded.** A photo
  you hung looked fine right after placing it, but the next time the room
  loaded it turned into a plain black rectangle. Wall photos now keep their
  picture across reloads, and opening one still shows the full shot.
- **Furniture that remembers a setting kept its memory across reloads.** The
  same underlying issue could wipe saved details on other items when a room
  reloaded; those now stick too.

## 2026-08-08 — Room for a longer name

### Fixed

- **The Create room button looked broken for longer room names.** Giving a
  new room a name longer than 25 characters made the green Create button do
  nothing at all — no room, no error. Names up to 60 characters now work,
  matching what renaming a room already allowed.

## 2026-08-08 — Say cheese 📸

### Added

- **The camera works end to end.** Staff can take photos of rooms, keep them
  as placeable wall photos, and publish them — published photos appear on the
  website's Photos page for everyone to browse.

## 2026-08-08 — A new face in the mirror

### Added

- **The sunburnt faces are now available to everyone** — both the male and
  female versions. Open Change Your Looks → Face & Body and they're in the
  selector — no purchase needed.

## 2026-08-08 — The online counter counts

### Fixed

- **The online counter was stuck at 0.** The hotel never recorded anyone as
  online, so the counter (and anything else showing who's online) always read
  zero. It now tracks real connections and refreshes every few seconds.

## 2026-08-08 — Fresh toolbar icons

### Changed

- **New icons for the toolbar.** The navigator is now a compass, the shop a
  paper bag, your inventory a crate, the camera a polaroid, and the friends list a
  phone — all sized
  to a matching height so the row sits evenly.

## 2026-08-08 — Navigator un-stuck

### Fixed

- **The navigator's My World tab could gray out and never load** for staff,
  most likely when a friend was logging in or out at the same moment. The
  hotel also now records these failures properly so anything similar shows
  up immediately instead of failing silently.

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
