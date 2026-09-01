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

## 2026-08-31 — Headquarters, authorizations and emergencies

### Added

- **Rooms can be a corporation's headquarters.** In Room settings >
  Roleplay > Corporations, staff can point a room at a corporation. Once a
  corporation has a headquarters, its employees can only clock in where
  they're meant to work - at that headquarters, or anywhere an emergency
  service lets them in. Corporations with no headquarters keep working
  anywhere, as before.
- **Pick who works where.** Authorizations lists the corporation's ranks
  with a checkbox each - uncheck a rank and they can't clock in at that
  headquarters. Every rank starts allowed.
- **Emergency services.** Emergencies lets a room admit Medical, Police
  and Staff from outside - so hospital staff and officers can work a scene
  anywhere that allows them. All three are allowed by default; the room
  owner or staff can change them.
- **Leave your post, clock out.** If you walk away from where you're
  allowed to work - or your rank loses access mid-shift - you're clocked
  out on the spot.

## 2026-08-31 — Room settings, roleplay edition

### Changed

- **The Roleplay tab in Room settings got the Settings treatment.** Its
  options now sit in a sidebar on the left - Zoning holds the safe/unsafe
  zone picker - so new roleplay room options have an obvious home as they
  arrive.
- **A Corporations section is taking shape in the Roleplay tab.**
  Headquarters, Authorizations and Emergencies links now sit under it.

## 2026-08-31 — Clock in, get paid

### Added

- **Shifts are live.** If you have a job, type :startwork to clock in and
  :stopwork to clock out. Every 10 minutes on the clock pays your rank's
  wage straight into your coins, with a whisper each minute counting down
  to payday.
- **Your progress never resets.** Clock out (or log off) 3 minutes before
  payday and you'll be 3 minutes from payday when you clock back in. Going
  idle clocks you out automatically and banks your time.
- **Watch people work.** Employee cards in the Corporations window and the
  job card on profiles count full shifts worked - weekly and lifetime, one
  shift per 10 minutes on the clock - updating live while someone is on
  duty.
- **Bosses hire and fire.** Corporation leadership - the top two ranks,
  or Management at PixelRP Leadership - can :hire an unemployed player
  into the bottom rung and :fire anyone beneath them, but only while on
  duty. Firing works even when the target is offline, and so do the staff
  super-commands now.
- **You can walk out.** :quitjob resigns on the spot, with the room told
  in the blue shout. Fired or resigned, your shift record goes with you -
  a rehire starts from zero.
- **Wear your shift.** While you're on duty your motto shows it - your
  corporation's acronym with your rank on its own line, like "[WORKING]
  SFPD" over "Officer II" - and it flips back to normal the moment you
  clock out.
- **The city has leadership.** PixelRP Leadership (PRPL) runs the town -
  Design, Construction, Support and Management, no tiers, top wage across
  the board.
- **Every corporation has its own badge.** The SFPD's gold star, HMMC's
  stethoscope, The Muse's coffee cup and Elite Armory's crossed swords now
  mark the Corporations window, infostands and profiles.
- **The city has an armory.** Elite Armory (EA) is forging - Apprentice,
  Smith, Bladesmith and Weaponsmith at the tiered rungs, Forgemaster up
  through Master at Arms at the top. Blades and axes, never guns.
- **The city has a juice bar.** The Muse (MUSE) is hiring too - Busser,
  Juicer, Mixologist and DJ on the tiered rungs, Curator up through
  Creative Director at the top, same pay ladder as everyone else.
- **The city has a hospital.** The Harvey Milk Medical Center (HMMC) has
  opened its doors - Nurse through Chief of Medicine, on the same pay
  ladder as the SFPD. Find it in the Corporations window.
- **Everyone sees the paperwork.** Hires, fires and rank changes now update
  the Corporations window, profiles and infostands everywhere the moment
  they happen - even mid-shift, where your next paycheck follows your new
  rank. Clocking in and out is announced to the room.

## 2026-08-31 — Six seven

### Added

- **Say "67" out loud.** Typing or shouting 67 in a room makes your avatar
  throw the six-seven hands for a second - dance paused, enable briefly
  tucked away, then everything back to normal. Whispering it does nothing;
  some things have to be said out loud.

## 2026-08-30 — A sharper Corporations window

### Changed

- **Corporations got a proper front page.** Each corporation now opens with
  an identity header - its badge on a plate in your chosen UI colour, its
  description, and at-a-glance counts of employees, who's on duty right
  now, and stock. The window itself is roomier, so names stop getting cut
  off.
- **You can finally tell who's around.** A small legend explains the
  portrait colours (gray offline, green online, blue on duty), and every
  employee card carries a matching status dot.
- **Pay looks like pay.** Each rank's wage now sits in a little coin chip
  instead of plain text, and the top rank is marked so the ladder reads
  top-down at a glance.
- **The display-options drawer stopped shoving the roster around.** It now
  slides over the list instead of squeezing it into a single column.

## 2026-08-30 — Smoother movement

### Fixed

- **Walking no longer freezes and snaps.** Rooms were occasionally missing a
  beat entirely - avatars stood still for half a second and then jumped to
  where they should have been. The hotel was waiting on itself rather than
  actually being busy, so movement now keeps its rhythm.
- **Busy rooms stay as smooth as quiet ones.** The hotel was writing a
  diagnostic note for every step every avatar took, and that work grew faster
  than the crowd did. Those notes are off unless someone is debugging, so a
  packed room now feels like an empty one.

## 2026-08-30 — Your job on your profile

### Changed

- **Profiles show where you work.** The employment card on a player profile
  now names the corporation they actually work for, with their rank
  underneath - "Cadet II", or just the title for the top ranks that have no
  tiers. Profiles opened from the corporation directory show it too. Anyone
  without a job still reads as Unemployed. Shift counts and the duty label
  are still placeholders for now.

## 2026-08-30 — Discord, fully in-game

### Changed

- **Disconnect Discord without leaving the game.** Settings > Social >
  Discord now handles connecting and disconnecting from the same in-game
  panel - no more visiting the website to unlink.
- **The Discord panel catches up on its own.** Finish linking your account
  and Settings updates automatically, instead of sitting on "Waiting for
  Discord."

### Fixed

- **No more flash of "not connected" when opening Discord settings.** The
  panel no longer briefly shows the disconnected state before it catches up
  with your actual link status.

## 2026-08-29 — Get verified

### Added

- **Connect your Discord.** Settings > Social > Discord now links your
  Discord account to PixelRP. Connecting joins you to the official server
  automatically, gives you the Verified role, and keeps your server nickname
  matched to your in-game name. Your Discord details are never shown
  in-game, and you can disconnect any time from Settings > Social > Discord.

### Fixed

- **No more freezing when crossing paths.** Walking past or through another
  player no longer briefly freezes either avatar in place or makes them jump
  to catch up afterward.
- **Sign-in errors for certain accounts are gone.** A permissions mix-up
  behind the scenes made the website show an error page to some players
  when they tried to log in - which accounts were affected was pure bad
  luck. Everyone can sign in normally again.
- **Avatars showing up without clothes across the site are fixed.** Online
  Friends, profiles, articles, and leaderboards now render avatars with our
  own imager, so custom clothing appears correctly.

### Changed

- **Walking together is finally in step.** Avatars walking side by side or in
  a line now move on one shared rhythm - a friend one tile behind stays
  exactly one tile behind, with no slow drifting, merging, or catching up.
  Groups of any size stay locked together, and laggy connections no longer
  make other players stutter or slide.
- **Patch notes post themselves to Discord.** New changelog entries now
  land in the official server automatically - #planned as they arrive on
  beta, #updates when they ship to the hotel.
- **Logging in lands on your profile page again.** Signing in on the
  website takes you to your profile dashboard as before, rather than
  jumping straight into the game.

### Changed

- **Employee cards in the Corporations directory.** The tiny name pills grew
  into proper cards: a full avatar portrait (tinted green when the player is
  online, blue while on duty), their tier within the rank, and a spot for
  weekly and total shifts worked - counting starts once paid shifts arrive.
  Click a card to open that player's profile.
- **Roleplay settings got section headers.** Macros and Messages now sit
  under a Functions group, with an Interactions group reserved below for
  what's coming.

### Fixed

- **Photos keep up with name changes.** The People groups in Photos >
  Collections now always show players under their current name - photos
  taken before someone changed their username no longer split off under
  the old one.

## 2026-08-28 — Straight into the city

### Added

- **Meet Trina.** A new bot is in the shop under Builders > Bots - she can
  talk, walk, dance and dress up like the other casual bots, and comes
  dressed in her own look.
- **Corporations are here.** The Corporations button in your side drawer now
  opens the city's business directory - starting with the San Francisco
  Police Department and its full rank ladder, from Cadet (15c per 10 minutes
  worked) up to Police Chief (27c). Every rank runs tiers I-V. Getting hired
  and paid shifts arrive next.
- **Employment shows everywhere.** Once you're hired, your employer's badge
  fills the reserved slot on your info panel and your profile gains a
  corporation line with your rank and tier - both update the moment you're
  hired. (Staff can hire with :superhire while proper hiring is built.)
- **The Mercury ATM has arrived.** A shiny new cash machine can now appear on
  street corners and building lobbies around the city - look for the glowing
  blue screen. (Builders will find it on the new Infrastructure page.)

### Changed

- **Staff are verified.** Hotel staff now show a blue verified badge next to
  their name when you click them.

- **The info panel glides in.** Clicking a player or furni now slides the info
  panel in from the right (and back out when you close it), and its badge
  area shows neat slot containers instead of floating badges.

- **Search your Photos.** The Photos app has a new Search tab (bottom right):
  find pictures by the room they were taken in, who was in frame, how they
  were captured, when - or type "shared" for photos on the city feed.

- **Rearranging phone apps works like a real phone.** Hold an app icon for a
  moment and the icons start jiggling - drag them anywhere on the home screen
  (icons can sit in any spot, gaps and all, just like iOS) or into the dock,
  then hit Done (top right) to finish. A quick tap just opens the app, no
  more accidental shuffling.

- **Username icons are back.** Pick an icon for your chat name again in
  Settings > Social > Personalization - now drawn from the hotel's own
  pixel-art icon set (bows, butterflies, the banana, the poop, and friends).

- **Logging in takes you to the game.** Signing in (or registering) on the
  website now drops you straight into the hotel instead of the website
  dashboard. Website pages are still there whenever you want them.
- **Walking together looks locked-in.** When two avatars walk the same path,
  the follower now moves in perfect step with the leader - exactly one tile
  behind, ahead, or side by side on the same stride - instead of slowly
  drifting into place or rubber-banding to catch up. If your paths split, both
  avatars simply carry on walking normally.
- **The Diamonds Store window fits its content.** It opens compact and only
  grows (with a smooth animation) when the card payment form needs the room.
- **Diamond top-ups start at 500.** The Buy Diamonds form now has a 500
  diamond ($5.00) minimum per purchase.
- **Safe while you pay.** Opening the card payment form in the Diamonds Store
  quietly gives you 5 minutes of passive status, so nobody can hit you while
  you're entering payment details.

### Fixed

- **Missing images filled in.** Thousands of previously missing hotel assets
  (badge artwork, group badge-editor parts, catalog icons, promo and article
  images, and the full sound machine sample library) are now in place, so
  images that used to render broken show correctly.
- **Broken chat commands work again.** :push, :pull, :spush and :kickpets
  failed silently every time (and :givebadge could too) - all repaired. The
  info panel's badge grid also lines up evenly now.
- **The VIP countdown in your wallet is now a neat square** instead of a tall
  sliver.
- **Backpack stacks cap at 10.** The same item now stacks up to 10 per slot,
  then starts a new stack - and the little count badge sits neatly inside the
  slot instead of poking out of it.
- **Organize your backpack.** Drag an item onto another slot to move it there
  (or swap with what's already in it). A quick click still uses the item.

## 2026-08-28 — A shop you can actually browse

### Changed

- **The Furni tab got a real structure.** Instead of one enormous "Themed
  Lines" list, furniture is now organized into Lines (the classic ranges like
  Area, Iced, Lodge and Mode), Themes (Pirates, Cyberpunk, Jungle and friends),
  and Seasonal - which now opens into holidays (Christmas, Halloween, Easter,
  Valentine's, New Year and more), each with its years underneath.
- **Game furni have their own shelves.** Battle Banzai, Freeze, Football, Ice
  Hockey, Ice Tag, Snow Storm and Lost Monkey each get their own page under
  Games, with score boards and extras alongside.
- **Every category has a proper name and its own icon.** No more "Xmas2023" or
  "Habboween" - and the little coin purse next to every single category has
  been replaced with an icon that matches what's inside.

## 2026-08-28 — Wardrobe freedom

### Added

- **Every Habbo effect, in sync.** The full official effects catalog now
  renders in the hotel, including the newest additions (like the Enchanted
  Broomstick, enable 247).

### Changed

- **HC clothing and colors are free again.** Choose Your Looks no longer locks
  any clothing item or color behind VIP - the diamond badges are gone and
  everything selectable can be worn and saved by everyone. (VIP still covers
  dances, chat bubbles, camera access and the rest of its perks.)
- **Clothing left the shop.** Clothing items are no longer sold in the catalog
  in any category - outfits come from Choose Your Looks.

## 2026-08-28 — Photos gets Collections

### Added

- **A Collections tab in Photos.** Next to your Library there's now a
  Collections view: create your own albums, and delete them when you're done -
  the photos always stay in your library.
- **Shared albums.** Start a shared album and invite friends into it - everyone
  in the album can see it and add their own photos. The owner can invite or
  remove people at any time (removing someone also removes the photos they
  added).
- **People.** Players who were in frame when a photo was taken are grouped
  automatically - open a person to see every photo you have together, just
  like on a real phone.
- **Places.** Photos are also grouped by the room they were taken in.
- **A built-in Screenshots album.** Screenshots you take with the side button,
  and photos you save from chats, collect in a default Screenshots album that
  can't be deleted.

### Fixed

- **Your profile shows your real motto.** Opening your own profile now
  displays your actual motto instead of a placeholder.

## 2026-08-28 — Photo libraries reset

### Changed

- **Everyone's Photos app started fresh.** All previously saved photos were
  cleared from every player's photo library (and the city photo feed) as part
  of upgrading how photos are stored. New shots save as usual.

## 2026-08-27 — Friend requests move to your phone

### Changed

- **Friend requests no longer pop up in the room.** The old in-room prompt is
  gone. When someone asks to add you, it now waits quietly on your phone: the
  phone button lights up with an alert count, and the Contacts app shows the
  same count on its icon.
- **Contacts has Friends and Requests tabs.** The Contacts app is now split
  into a Friends tab (your online and offline contacts, plus search to add
  more) and a Requests tab that collects incoming friend requests. A request
  stays in the Requests tab until you Accept or Decline it, and the tab shows
  how many are waiting.

## 2026-08-27 — Phone refresh

### Added

- **Swipe with a trackpad in Messages.** You can now swipe a conversation
  sideways with a trackpad, not just a click-and-drag, to reveal its Pin,
  Mute and Delete actions.
- **A proper Settings app.** Settings now opens a full list with your own
  avatar and name at the top, and a dedicated Appearance page for switching
  the phone between Light, Dark and Automatic.
- **Choose where your phone opens.** Appearance has a new Left / Center / Right
  option that sets where the phone pops up on screen when you open it, and it
  remembers your choice. New phones open on the right by default.
- **See when a friend is typing.** In a conversation, a little animated bubble
  now appears while the other person is typing a reply, and disappears when
  they send it or stop.
- **Airplane Mode.** Flip Airplane Mode on in the phone's Settings and you go
  quiet: incoming friend requests are hidden, and any DM someone sends you
  won't arrive - they just see a red "Not Delivered" where the receipt would
  be. Turn it off to come back. Your choice is saved.

### Changed

- **Phone photos skip your backpack.** Shots taken with the phone's Camera now
  go straight into the Photos app only - they no longer drop a photo furni
  into your inventory.
- **The phone got a fresh coat of paint.** The status bar, dock, search box,
  chat headers and pop-up menus are now frosted glass, pinned chats sit in
  neat framed tiles, and every icon across the phone shares one clean,
  two-tone icon set.
- **A full home screen of apps.** The phone's home screen now has the complete
  app lineup - Phone, Messages, Camera, App Store, Contacts, Photos, Stocks,
  Music, Wallet, Calendar, Tasks, Notes, Weather, News, Translate and Settings -
  each with its own icon in familiar, phone-style colours.

### Removed

- **Username chat icons.** The little icon before your name in chat, and its
  picker in Settings, have been removed. Your username colour is unchanged.

### Fixed

- **Windows remember their spot again.** Draggable windows now reopen where you
  last left them, and the phone's Left / Center / Right open-position setting
  now actually moves the phone.

## 2026-08-27 — A much bigger shop

### Added

- **Thousands more furni in the catalog.** The shop is now stocked with the
  full furniture library, sorted into themed lines (Seasonal, Themed Lines,
  Classics, Functional and more) so there is far more to browse and buy.

### Changed

- **Prices are all in coins now.** Duckets have been retired as a shop
  currency, and everything in the catalog is priced in coins.
- **The shop was reorganized.** The Furni and Staff tabs were rebuilt for a
  cleaner, easier to browse layout. The old Club and Exchange sections were
  removed; the furni recycler and room promotion tools are still here.

## 2026-08-27 — VIP login fix

### Fixed

- **VIP members could get locked out.** After collecting a daily VIP
  diamond bonus, your next login following a hotel restart could fail
  silently and leave you stuck at the loading screen. Logins for VIP
  members work reliably again.

## 2026-08-27 — Walking in step

### Fixed

- **Falling into line behind someone works again after turning around.**
  When two people walking in single file turned around mid-walk, the one
  now behind could shuffle along awkwardly overlapping their partner for
  several seconds instead of settling neatly one tile back. Turning
  around now re-forms the line right away, and a pair that had already
  drifted into place locks in cleanly instead of never quite snapping.

## 2026-08-27 — VIP membership arrives

### Added

- **VIP membership.** The Diamonds Store's Store tab now sells two VIP
  tokens - 14 days for 250 diamonds and 31 days for 500 diamonds. Redeem
  a token from your Backpack to activate (or extend) your membership;
  redeeming again while already VIP just stacks more days on top.
- **What VIP gets you.** HC clothing, dances (`:dance` 1-4), and chat
  bubbles unlock in the avatar editor, plus camera access, two extra
  Backpack slots (11-12), a VIP badge, and a daily stipend of 5 diamonds
  for logging in. Your purse shows a chip with your remaining VIP days -
  click it to open the HC Center, whose button jumps straight to the
  Diamonds Store.

### Changed

- **HC-style perks now require VIP.** Clothing, dances, and chat bubbles
  that used to be free for everyone are now part of VIP membership.
  Outfits you're already wearing aren't touched, but once VIP lapses you
  won't be able to put HC pieces back on, dance, or use HC bubbles until
  you buy VIP again.

## 2026-08-27 — A handier phone

### Added

- **The Diamonds Store opens its doors.** The diamonds button next to the
  phone now opens the new store window. The shelves are still being
  stocked, but the Buy Diamonds tab already works: pick an amount (100
  diamonds per dollar) and pay by card right inside the window.
- **Smoothies are a safe-zone luxury.** Passive Smoothies can now only be
  drunk inside a safe zone, and only at full health - the smoothie stays
  in your backpack if the moment isn't right.
- **Calm down on your own terms.** Hover the PASSIVE tag on your HUD and
  an x slides out - click it to end your passive status early. Doing so
  announces your newfound anger to the room.
- **Staff can march you around.** A new staff command makes a player walk
  back and forth across the room, horizontally or vertically, without
  stopping at the walls. Walking anywhere yourself breaks the spell.
- **Safe zones.** Room settings has a new Roleplay tab where owners set the
  room's Zone Type — Safe or Unsafe. In a safe zone, your passive status
  stops counting down entirely; the timer only ticks while you're in
  unsafe rooms.
- **The Jukebox actually plays music now.** Double-click a Jukebox and
  paste a YouTube link to queue a song for everyone in the room. While
  music plays, the jukebox itself lights up and a player slides in under
  your wallet showing what's on and what's next, with a volume slider that
  remembers your setting and a speaker button to mute on the spot. Room owners can skip and prune the
  queue; the person who queued a song can pull their own. Sound plays right
  away — a "tap to unmute" pill only appears if your browser blocks it.
- **Bots can walk a beat.** The menu on a bot you own now has working
  "Walk Horizontally" and "Walk Vertically" options — the bot paces back
  and forth along that line, turning around when it reaches furni, a wall,
  or another person. "Walk freely" puts it back to wandering wherever it
  likes. The choice sticks, even after the room reloads.

### Fixed

- **Profiles stop pretending everyone's here.** The badge on a player's
  profile now actually shows Offline when they're offline, instead of
  always claiming Online.

### Changed

- **Room settings slimmed down.** The ModTool tab (room mute/kick/ban rules
  and the ban list) is gone from Room settings — city moderation runs
  through the staff tools instead.
- **Your motto is in the city's hands now.** The little text under your
  badges (like "Citizen") is managed by the roleplay systems, so the
  pencil-edit box in the click card is gone and motto changes are no longer
  accepted — for anyone, by any means.
- **A tidier click card.** Clicking a player shows their sprite from the
  classic angle, and the profile now opens from their name (it underlines
  when you hover) instead of a separate icon button.
- **Window tabs match your colors too.** Every tabbed window — Shop,
  Navigator, Inventory, Change Your Looks, Room settings, Camera editor,
  Group manager, the dimmer and the staff ticket tool — now uses the same
  dark tab strip as the Settings window, tinted to your UI color scheme,
  instead of the fixed blue bar.
- **Click menus match your colors.** The menu that pops up when you click a
  player (or furni) now follows the UI color scheme you picked in Settings >
  Interface — including your transparency choice — instead of always being
  blue. The two-tone button styling stays.
- **Contacts shows who's around.** The Contacts app now lists your online
  friends in their own section at the top, with offline friends below —
  both sorted alphabetically — so you can see at a glance who's in the city
  right now.
- **The phone is smaller.** It's been scaled down about 20% so it covers less
  of the room while you're chatting.
- **A tidier Messages screen.** The big PixelRP "P" badge no longer sits above
  "No messages yet" when your inbox is empty.
- **The phone moves freely.** You can now drag it anywhere on screen — even
  mostly off the edge to tuck it away — instead of it snapping back whenever
  it touched the bottom of the window. A corner always stays on screen so you
  can grab it back.

## 2026-08-25 — Smoother walking

### Fixed

- **Walk lag and rubber-banding.** Your connection to the hotel now takes a
  direct route instead of going through a middleman that bunched up movement
  updates — avatars had been freezing mid-walk and then teleporting to catch
  up, no matter how few people were online. Refresh the hotel once to get on
  the new connection.

## 2026-08-25 — Your phone is here

### Added

- **A bow for your name.** There's a new two-tone pixel bow in
  Settings > Social > Username > Icon. Pick it and it sits in front of your
  username in chat, tinted to match your icon colour.
- **Everyone gets a phone.** Tap the phone button on the toolbar and it opens
  right on screen — wallpaper, app grid and all. Click and hold the dynamic
  island (the black pill up top) to drag it around; the side button or the
  home bar puts it away.
- **Messages.** Your DMs now live in a proper messaging app: chat bubbles,
  a New Message composer, and a conversation list you can search. Drag a
  conversation left to pin, mute or delete it — pinned friends sit in their
  own grid up top, and muted chats stay quiet. Pins and mutes are remembered
  between visits.
- **Contacts.** Your friends list moved into the phone too: friend requests
  wait at the top, friends are listed A–Z with online dots, and each row has
  message / call / remove buttons (remove asks for a second tap, so no
  accidental break-ups). Search for players at the bottom to send new friend
  requests.
- **Calls.** You can ring a friend on PixelRP Audio. Nobody will pick up —
  voice hasn't been invented in the city yet — but it felt rude not to let
  you try.
- **Unread badges that make sense.** The Messages app badge (and the toolbar
  phone badge) only counts unread messages from your friends — muted
  conversations and group chats don't nag you.
- **Delivered and read receipts.** Under your latest message you'll see
  Sent, then Delivered the moment it reaches your friend (including when
  your messages catch up to them at login), then "Read at 14:53" once they
  open the conversation. Receipts are live — they show while you're both
  around, not dug up from the archives.
- **The Camera works — and your phone screen is the viewfinder.** Open the
  Camera app in a room and the screen turns see-through: whatever's behind
  the phone is your shot. Drag the phone around to frame it, hit the
  shutter, then Retake or Use Photo. Saved photos also land in your
  inventory as printable wall photos.
- **Gallery is now Photos, and it's real.** Every photo you save shows up
  in an iOS-style grid with a full-screen viewer. Shots you publish to the
  website's photo feed get a little "shared" mark.
- **The photo viewer grew up.** Photos now fill the whole screen edge to
  edge — tap the photo to hide the controls and just look. The overlay
  shows when it was taken, which shot you're on, and whether it's shared,
  with arrows to flick through. You can delete a photo (with an
  are-you-sure sheet — prints you own stay safe), or hit crop to zoom,
  drag to reframe, and save the edit back to your library.

- **Settings is open — starting with Appearance.** The Settings app now
  works: pick Light or Dark from the two mini previews, or flip on
  Automatic to follow your device's appearance (it switches live when
  your system does). Dark mode re-skins every phone app — Messages,
  Contacts, Photos, the lot — in a deep plum-black. Your choice sticks
  between visits, and it only changes the phone; the rest of the hotel
  stays exactly as it is.
- **Photos in chat are first-class.** Tap a photo in a conversation to view
  it full screen; received photos have a little save button beside them
  (and a Save to Photos button in the viewer) that files a copy into your
  own library.
- **Grab the phone by its edge.** The orange border now drags the phone
  around, just like the dynamic island.
- **Share photos in Messages.** The + button next to the message box opens
  the attach menu — pick Share Photo, tap up to six shots from your
  library (numbered in the order you pick them), and they land in the
  conversation as photo bubbles for both of you. Conversation previews
  say "Shared a photo" instead of showing gibberish.
- **Hold the side button for a screenshot.** A quick press still puts the
  phone away, but holding it flashes the screen and snaps whatever your
  phone is showing — straight into your Photos library, ready to view,
  edit or share. Works anywhere, no room needed.
- **Arrange your home screen.** Click-hold an app icon and drag it where
  you want it — swap grid spots, pull apps into the dock (it holds four)
  or back out. Your layout sticks between visits. The pinned grid in
  Messages works the same way: drag your pinned friends into whatever
  order you like, and it stays put.

### Changed

- **The classic friends list is retired.** The old friends window and
  messenger popup are gone; everything they did now happens on the phone.
- **Pinned friends are just their head now.** In Messages, the coloured
  square behind each pinned friend is gone — it's the avatar's head on its
  own, full and uncropped, tall hair and all.

### Fixed

- **Shouted hearts are hearts again.** The special chat symbols (like `|`
  turning into a heart) only worked when you talked — shouting showed the
  raw characters instead. Symbols now convert no matter how loud you are.

## 2026-08-24 — A badge for your name

### Added

- **Put an icon before your name in chat.** Settings → Social → Username now
  has an Icon picker (and an Icon Color to match). Pick one and it shows as
  `[ icon ]` in front of your name in chat bubbles and history for everyone in
  the room; pick the X to remove it. Your choice sticks between visits.

## 2026-08-24 — Color your name

### Added

- **Pick a color for your username.** Head to Settings → Social → Username →
  Color and choose from 20 shades. Your name shows up in that color inside
  your chat bubbles — everyone in the room sees it — and it sticks between
  visits. Black is the default; pick it again any time to go back to normal.

## 2026-08-24 — A new bubble for staff

### Added

- **A brand-new chat bubble style is being tested.** Staff members will spot
  an extra bubble design at the end of the chat style picker — a dark
  "Pixel City Neon" look. It's staff-only while we test; if all goes well,
  more custom bubbles (and ways for everyone to unlock them) come later.
- **A second test bubble joins the picker.** A soft cream-and-pink pixel
  frame, also staff-only for now.

### Changed

- **The test bubbles now show your face.** Both custom bubbles display your
  avatar's head next to your name, just like the classic bubbles do.

## 2026-08-23 — The backpack comes alive

### Fixed

- **The shop search actually finds things now.** Searching the furni shop
  used to come back empty no matter what you typed. Type a name — even a
  multi-word one like "gray sofa" — and matching items appear with working
  previews, prices and Buy buttons.

### Changed

- **The Diamonds button moved into the toolbar.** It now lives at the
  bottom right, just left of the friends list, instead of up in the purse.
- **The loading screen joined the city.** Loading into the hotel now shows
  the same pixel-city skyline as the landing view, with the animated
  PixelRP logo front and center instead of the old panel artwork.
- **The infostand dresses to match.** When you select a player, the panel
  behind their sprite and their bio line now carry a subtle transparency
  and take on your chosen UI Color instead of flat gray.
- **The PASSIVE badge means it now.** The HUD chip next to your name only
  appears while you actually hold passive status (from a Passive Smoothie),
  showing up the moment you drink one and vanishing when the hour runs out.
  AGGRESSIVE still takes over whenever your aggression is up.

### Added

- **Consumable items are here — starting with the Passive Smoothie.** Items
  now appear in your Backpack with their own icons, stack together with a
  count badge, and can be used with a single click. Drinking a Passive
  Smoothie announces it to the room and grants passive status for one hour
  of online play — with a whisper each minute counting down how long you
  have left.
- **Staff can hand out items.** A new `:spawn` command places an item
  directly into a player's backpack.

## 2026-08-22 — Profiles take shape

### Added

- **Click a HUD portrait to open a profile.** Your own portrait opens your
  profile; your target's portrait opens theirs. The new profile window
  shows identity, combat and farming levels, employment, gang and an RP
  stat sheet — all placeholder numbers until those systems go live.
- **The old profile window is retired.** Every way of opening a profile —
  avatar menus, the infostand, friends and messenger, group members —
  now opens the new RP profile instead.

## 2026-08-22 — The website wears the brand

### Changed

- **Website colors are PixelRP colors now.** The gold accents became brand
  magenta, action buttons went sunset orange, dark mode is a warm
  plum-black instead of slate gray, and light mode surfaces carry a soft
  cream cast — matching the hotel's pixel-art identity in both modes.

## 2026-08-22 — Fresh drops for staff

### Added

- **Two new hats: Puffle Hat (dyeable, two color channels) and Chiikawa
  Hat — plus the dyeable Ribbon Shnibbony head accessory.** Staff-only in
  the wardrobe for now.
- **The Chrome chest accessory is now staff-only** ahead of the clothing
  economy — it was briefly wearable by everyone.

## 2026-08-22 — Duckets fully retired

### Fixed

- **Duckets no longer appear on the website.** They were already disabled
  in-game; the site's header counter, the Top Duckets leaderboard and the
  profile currency list have now caught up.

## 2026-08-22 — A new view from the hill

### Changed

- **The landing view got a skyline.** Leaving a room now overlooks a
  pixel-art PixelRP city at sunset — bay, bridge and all — replacing the
  old hotel curtains.

## 2026-08-22 — Falling into step

### Changed

- **Joining someone's walk now reads as falling into step.** Instead of
  being pulled sideways onto the other player's position, the joining
  avatar stays on its own path and its stride timing catches up over about
  one step — the brief offset melts away like two people syncing their
  pace. Whoever was already walking is never touched.

## 2026-08-22 — The Backpack

### Added

- **The drawer's Inventory button opens your Backpack.** Weapon and armor
  slots up top, ten carry slots below — the RP item system that fills them
  is on its way.

## 2026-08-22 — Merging mid-stride

### Fixed

- **Joining someone's walk looks like one continuous motion.** Whoever was
  already walking keeps moving untouched; the player who joins the path
  bends onto their track mid-stride — no snap, no pause, no speed dip —
  and peels off just as smoothly when your paths split.

## 2026-08-22 — Headers in brand colors

### Changed

- **Window title bars wear PixelRP colors now.** All windows default to the
  brand's two-tone orange, and Settings → Interface lets you pick pink or
  purple instead — same classic split-tone style, your choice saves to
  your account.

## 2026-08-22 — Frosted glass

### Changed

- **The interface got a subtle frosted-glass look.** The customizable dark
  panels — HUDs, drawer, purse, toolbars and friends — now softly blur the
  room behind them. Pairs especially well with a lower UI opacity.

## 2026-08-22 — Walking together, smoothly

### Fixed

- **Walking stacked with another player aligns cleanly.** When you and
  another player travel the same path on the same tile, their avatar now
  eases onto your track over a quarter second and then matches your
  position exactly — no snap when it engages, no snap when either of you
  breaks off. Your own avatar's movement is never touched.

## 2026-08-22 — See-through settings

### Added

- **Interface opacity is yours to set.** Next to the UI color picker,
  a new slider with five stops controls how solid the dark interface
  surfaces are — slide down to see more of the room through your HUDs,
  drawer and toolbars. Saves to your account like the color scheme.

## 2026-08-22 — Targets stick around

### Changed

- **Your target stays targeted.** Clicking the floor or furniture no longer
  clears your HUD target — it now persists until you pick a new target,
  close it with the ✕ on the target HUD, or the player leaves the room.

## 2026-08-22 — Targeting works with click-through

### Fixed

- **Click-through no longer blocks targeting.** With click-through enabled,
  clicking another player now sets them as your HUD target while still
  walking you to the exact tile you clicked — and still without opening
  their menu or showing their name tag.

## 2026-08-22 — Snappier starts near walkers

### Changed

- **Clicking to walk next to a moving player responds instantly again.**
  A brief hold that synced you with nearby walkers before your first step
  is gone — the newer avatar-alignment smoothing made it unnecessary.

## 2026-08-22 — Make it yours

### Added

- **A real Settings window.** The gear in the side drawer now opens a
  multi-tab settings window — General, Social, Roleplay, Interface and
  System. Most tabs are still being furnished; more settings land soon.
- **Pick your interface color.** Under Interface you'll find eight color
  schemes — Charcoal, Midnight, Ocean, Forest, Plum, Wine, Ember and
  Slate — that recolor the dark interface everywhere: HUDs, side drawer
  (icons included), purse, room tools, chat bar, name tags and more. Your
  choice saves to your account and follows you between sessions and
  devices.

## 2026-08-22 — Lightning strikes

### Added

- **Staff can knock a player out on the spot.** A bolt of lightning drops
  the target to zero health instantly — they collapse where they stand,
  announced to the room with an emote shout.

## 2026-08-22 — A prettier goodbye

### Changed

- **The disconnect screen matches the hotel now.** Getting disconnected
  shows the PixelRP pixel-art card — logo, proper buttons and all — instead
  of the old plain text over a dimmed room.

## 2026-08-22 — Knocked out at zero health

### Added

- **Hitting 0 health knocks you out.** Your avatar drops to the floor and
  lies there frozen — no walking, no getting up — until someone brings your
  health back above zero. Being knocked out survives relogging, so there's
  no escaping it by signing out.

## 2026-08-22 — Target shorthand in commands

### Added

- **"x" now works in commands.** With a target selected in your HUD, typing
  `x` as a command argument stands in for their name — `:restore x` instead
  of typing the full username. Works for everyone, in any command, alongside
  the existing `@x` mention shorthand.

## 2026-08-22 — Restore command

### Added

- **Staff can fully heal a player.** A new command instantly refills a
  player's health and energy, announced in the room with an emote shout.

## 2026-08-22 — Cleaner name tags

### Changed

- **Hover name tags got smaller and quieter.** The big bordered box that
  appeared over players, bots and pets is now a compact dark chip matching
  the rest of the interface. Friends stand out with a green chip and white
  name.

## 2026-08-22 — Two new hairstyles

### Added

- **Two new hairs: Cookie Dana and Brit Pigtails.** Both fully dyeable with
  two color channels (main hair + accent). Staff-only in the wardrobe for
  now — they'll reach everyone once clothing can be bought.

## 2026-08-21 — Crossing paths looks right

### Fixed

- **Walking through another walking player no longer looks offset.** When
  your avatar and another moving avatar cross the same tile, their feet now
  line up instead of one floating slightly beside the other. The pull is
  gradual — no snapping or teleporting — and everyone walks normally the
  rest of the time.

## 2026-08-21 — Aggression is real

### Added

- **The aggression meter is live.** Staff can raise a player's aggression,
  the strip slides out under their energy bar for everyone to see, and it
  drains back down on its own over 45 seconds. Groundwork for combat and
  wanted systems to come.

## 2026-08-21 — Health and energy are real

### Added

- **Your health and energy bars are live.** The HUD now shows your actual
  stats — everyone starts at 100/100, values persist between sessions, and
  changes appear instantly for everyone in the room, including on the target
  panel when you select someone. Staff can adjust a player's stats, announced
  in the room as they do.

### Changed

- **The HUD bars are taller with clearer numbers**, the aggression strip no
  longer shifts the bars when it appears, and the wanted stars sit straight.

## 2026-08-19 — Walkers fall into step

### Fixed

- **Players walking together now line up on whole tiles.** Following someone
  no longer leaves you floating half a tile behind them — after a few steps,
  everyone walking falls into the same rhythm, so you're either on their tile
  or cleanly one behind.
- **Joining someone mid-walk locks in step immediately.** Starting a walk
  right next to a player who's already walking now waits a beat to match
  their rhythm, so you fall in perfectly from your very first step instead
  of trailing at a half-tile offset.

## 2026-08-19 — Target mentions

### Added

- **Call out anyone with `@`.** Mention `@TheirName` (capitals don't matter)
  in any message and, if they're in the room, they — and only they — see it in
  a special alert bubble and hear a mention sound, every time. With a target
  selected in your HUD, `@x` is a shortcut that swaps in your target's name
  and sends the message as a shout.

## 2026-08-19 — Stacked players render as one solid layer

### Fixed

- **Players sharing a tile no longer cut through each other.** When avatars
  stack, each one now renders as a single solid layer — a neighbour's effect
  glow or typing bubble can't slice through your avatar anymore, and your own
  avatar always stays fully on top in your view.
- **Walking onto or through another player no longer flickers.** The layering
  now holds steady the whole way through an overlap — including mid-step —
  instead of momentarily swapping who's in front.

## 2026-08-18 — Layering flicker fixed

### Fixed

- **The layering flicker when walking near other players is gone.** Who
  appears in front no longer swaps back and forth while players walk
  diagonally behind or beside each other — stacking stays put, and your own
  avatar still always wins the front spot in your own view. (The temporary
  diagnostics from earlier today have been removed.)

## 2026-08-18 — Stable stacking on shared tiles

### Fixed

- **Players standing or walking on the same tile no longer flicker** over who
  appears in front — the layering stays put.

## 2026-08-18 — Deploy screen polish

### Changed

- **The update screen's progress bar turns green** the moment the deployment
  hits 100%.

## 2026-08-18 — Snappier, smoother walking

### Changed

- **Walking responds faster and glides more smoothly.** Your avatar sets off
  the moment you click, steps flow evenly instead of hitching at each tile,
  and changing direction mid-walk takes effect right at the tile boundary —
  even during rapid clicking.

## 2026-08-17 — Animated clothing in the looks editor

### Changed

- **Animated clothing now plays its animation in the "Change Your Looks" preview**,
  matching how it already looks in the room.

## 2026-08-17 — Side drawer open by default

### Changed

- **The left-edge drawer now starts expanded**, and remembers whether you leave
  it open or collapsed between sessions.

## 2026-08-17 — Click-through polish

### Fixed

- **Click-through (`:ct`) now walks you to the exact tile you click**, even when
  your click lands on another player's avatar, instead of snapping to the tile
  they're standing on.
- **With click-through on, hovering another player no longer flips your cursor**
  to the hand pointer — it stays the normal cursor to match the walk behaviour.
- **With click-through on, hovering another player no longer pops their name tag**
  above them.

## 2026-08-17 — Player HUD

### Added

- **A new heads-up display** in the top-left corner showing your avatar. Click
  another player and their panel slides in next to yours, with lock and close
  buttons to hold or clear your target.

### Changed

- **The HUD now uses a cleaner, more readable font throughout** and shows names
  as typed rather than in all caps. HUD avatars now render crisp and sharp — the
  same way they look in the room — instead of appearing blurry on lower-resolution
  screens.

### Fixed

- **Your currency counter now widens to fit** larger balances instead of
  cutting them off.

## 2026-08-15 — Respect system removed

### Removed

- **The respect system is gone** — no more "Give respect" on the avatar menu.
- **The achievement score** no longer shows on the profile popup.

## 2026-08-15 — Emoji picker opens first try

### Fixed

- **The chat emoji picker now opens on the first click**, instead of needing a
  few tries.

## 2026-08-15 — Staff effect off by default

### Changed

- **Staff no longer get a glowing effect slapped on automatically** when they
  enter a room.

## 2026-08-15 — Readable command list

### Changed

- **The `:commands` list is now a proper table** — grouped by permission
  tier, with a filter box to find what you need, instead of one long wall of
  text.

## 2026-08-14 — Wardrobe button fix

### Fixed

- **The Wardrobe's "Wear" button reads properly again** — it was briefly
  showing a snippet of raw code instead of the word "Wear".

## 2026-08-14 — Animated clothing comes to life

### Fixed

- **Animated clothing actually animates now.** Hats, hair, and accessories
  that were built to move — the spinning, glowing, sparkling, and flapping
  ones — now play their animation while you're just standing around, not only
  mid-dance.

## 2026-08-14 — Bots feel alive again

### Fixed

- **Bots wander again.** Bots with automatic chat switched off had stopped
  walking entirely; they now free-roam around the room as they should.
- **"Copy my looks" works right away.** Telling a bot to copy your look used to
  do nothing until a reload — it now applies instantly.

### Changed

- **Bots are easy to spot.** Every bot now wears an identifier effect, so you
  can tell a bot from a real player at a glance.
- **The bot's walk toggle says what it'll do** — it reads "Relax" while the bot
  is wandering, and "Walk around" while it's standing still.

## 2026-08-14 — Room thumbnails you can actually set

### Fixed

- **Setting a room's thumbnail with the in-room camera now works.** Clicking
  Save used to do nothing; your captured shot now saves as the room's thumbnail
  and shows up in the room info and navigator.

## 2026-08-14 — Room ratings retired

### Changed

- **Rooms no longer have likes or ratings.** The like button is gone and the
  room info panel no longer shows a rating — the feature is switched off
  hotel-wide.

## 2026-08-14 — Achievements have left the hotel

### Changed

- **The achievement system is gone.** Achievements no longer track, unlock or
  pay out — no more achievement badges, pixels or points — and the
  achievements panel and its button in the "Me" menu have been removed. Any
  achievement badges and points accounts had earned have been cleared.

## 2026-08-14 — Bots you buy are actually bots now

### Fixed

- **Buying a bot from the catalog gave you a broken wall item instead of a
  bot.** The bot showed up fine in the catalog, but the moment you bought it,
  it landed in your inventory as an unnamed wall item that would not place or
  render. Bots now arrive as proper bots — in your bots inventory, ready to
  drop into a room, walk, talk and dress up. (Effects, badges and pets bought
  from the catalog were mis-delivered the same way and now arrive correctly
  too.)

## 2026-08-14 — A new front door

### Changed

- **The website's front page is now the login screen.** Arriving at pixelrp.co
  while logged out drops you straight onto a pixel-art terrace at sunset, with
  the animated PixelRP sign overhead and a single card asking for your username
  and password. No hunting for a login box in the menu bar. A ticker along the
  bottom shows how many players are in the hotel right now.
- **Signing up is a boarding pass.** The create-account page hands you a ticket
  out of the old world and into the city — a departure board that flips through
  cities as you fill in your details, then flies you to PXL on flight PXL-26.
  It asks for the same things it always did.
- **Forgotten passwords, password resets and the two-step security check wear
  the same look**, so the whole way in matches from the first screen to the
  last.

### Fixed

- **"Your password has been successfully reset!" never actually appeared.**
  After choosing a new password you were sent back to the front page with
  nothing to confirm it had worked. The confirmation now shows up where you
  land.

## 2026-08-14 — Room categories that fit the city

### Changed

- **The room categories are now Corporations, Residential, Commercial,
  Industrial, Farm and Staff.** They replace the old Habbo-style list (Chat &
  Chill, Trading & Casinos, Parties & Clubs and the rest), and they are what
  you pick from in Room Settings and what the navigator's All Rooms tab groups
  rooms under. Staff is reserved for staff to assign.
- **Every room in the hotel has been parked under Staff for now**, so staff can
  work through them and file each one under the category it really belongs to.
  Your room's own settings — name, description, rights, everything else — are
  untouched.

### Fixed

- **Staff could not change the category of a room they did not own.** Picking a
  category in someone else's Room Settings looked like it saved, but the room
  quietly stayed where it was.

## 2026-08-14 — Reloading the moderation settings stopped kicking staff

### Fixed

- **`:update moderation` threw whoever ran it out of the hotel.** The first use
  after a restart worked, but every one after that disconnected the staff
  member on the spot — so re-editing call topics or preset warnings mid-session
  meant waiting for the next restart before they took effect. The command now
  works as often as you like and confirms with the usual whisper.
- **Reloaded moderation presets piled up on top of the old ones.** The room
  warning presets and the preset action messages were added to the existing
  list instead of replacing it, so a reload could leave staff picking from
  duplicated entries.

## 2026-08-14 — Reports wait for staff through a restart

### Fixed

- **Reports no longer vanish when the hotel restarts.** Anything staff hadn't
  picked up or closed yet was thrown away every time the hotel went down for
  an update, so a report sent just before one simply never got looked at. Open
  reports — and ones a staff member has already picked up — now wait through a
  restart, still showing who reported whom, what they said, and the chat lines
  the reporter picked out.

### Known issues

- Closing a report with the mod tool's default-action button does nothing; use
  the ordinary close options instead.
- When one staff member picks up a report, it can briefly show in other staff
  members' own picked list until they reload.

## 2026-08-14 — Reporting someone actually reaches staff now

### Fixed

- **Reports sent from the Help window never reached staff.** Picking "Someone
  is misbehaving", choosing the player, the chat lines and a topic, then
  sending, looked like it worked — but the report was thrown away on arrival
  and never appeared in the staff ticket list, so nobody could act on it.
  Reports sent the other way, from the Report option on a player, were
  arriving fine. Both paths now work.
- **Sending a second report while your first one is still open** did nothing
  at all. You now get told that your existing call is still waiting for staff.

## 2026-08-14 — The Duck Afro

### Added

- **A new hairstyle, the Duck Afro, is now in Change Your Looks.** A big
  round curly afro with a duck tucked into it, and two colours to pick — one
  for the hair, one for the duck. It's stocked for staff for now, so it can
  be handed out in character at the boutique rather than sitting on a shelf.

## 2026-08-13 — You come back exactly where you left

### Fixed

- **You now return to the exact spot you left from, every time.** Sometimes
  you'd log back in somewhere you'd been earlier rather than where you
  actually were — an older room, or an older tile. Your spot was only being
  written down when you cleanly left a room, so if the hotel went down or
  your connection dropped where you stood, the last thing it remembered was
  wherever you'd been before that. It now keeps track as you move, so the
  room, the tile and the direction you're facing survive a dropped
  connection or a restart.

## 2026-08-13 — Staff-only tools locked down for real

### Changed

- **The catalogue, marketplace, and room navigator are now staff-only from
  the inside out.** These tools were already hidden for regular players, but
  the hotel now also refuses to *act* on any catalogue, marketplace, or
  navigator request from a non-staff account — so poking at them with an
  outside tool does nothing instead of sneaking a purchase or a search
  through.
- **You can only land in rooms the hotel sends you to.** Regular players
  move between rooms the normal way — teleports, doors, and the room you log
  back into. Trying to jump straight to a room by ID from an outside tool is
  now turned away.

### Fixed

- **The hotel no longer goes down when it's sent nonsense.** A garbled
  message from a badly-behaved or hostile connection could take the whole
  hotel offline for everyone. Those connections are now dropped on their own
  and everyone else keeps playing.
- **Only a room's owner can change that room's settings.** It was possible to
  rename a room, change its door lock, or change who may kick and ban in it
  without owning it. Now the hotel checks.
- **Group badges you haven't earned stay off your avatar.** You can only wear
  the badge of a group you're actually a member of.
- **Pet gear can't be taken or duplicated any more.** Saddles and dyes lying
  in a room can only be used by the player who owns them, taking a saddle off
  a horse gives back exactly the one that was on it, and only a pet's owner
  decides who may ride it.
- **Finished quests no longer pay out twice.** Re-starting a quest you had
  already completed could hand you its reward again.

## 2026-08-10 — Staff rights are back

### Changed

- **Staff have their room rights again, everywhere.** The experiment where
  staff walked around without rights until switching them on per room is
  over — the rights badge and build tools are back for staff in every room,
  and the `:rights` command is gone.
- **Clicking furniture shows the info panel for everyone again.** The
  rights-only infostand from earlier today has been rolled back along with
  the rest of the staff-rights changes.

## 2026-08-10 — Staff rights, tightened

### Fixed

- **Staff tools now switch off however you leave a room.** A few unusual
  exits — like being in a room while its floor plan was saved and rebuilt —
  could leave a staff member's tools silently switched on in the next room
  they visited. Tools now stay on only when returning straight to the room
  they were enabled in.
- **Giving rights to a staff member no longer shows them a badge that doesn't
  work.** A staff member with their tools off who was granted room rights saw
  the rights badge and furni info panels while every action was refused. What
  they see now matches what they can actually do.

## 2026-08-10 — Staff blend in

### Changed

- **Staff no longer have automatic rights in every room.** The rights badge is
  gone from staff by default — they walk, sit, and chat like any other player,
  even in rooms they own. Staff can switch their tools on in a specific room
  when they need to build, and it switches off again the moment they leave.
- **Clicking furniture only shows the info panel if you have rights in that
  room.** No rights, no infostand — the room's builds keep their secrets.

## 2026-08-10 — Kat joins the staff team

### Changed

- **Kat is now hotel staff.** Say hi — they can now help out with staff tools
  around the hotel.

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
