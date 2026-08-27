# Jukebox YouTube Player Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the existing music-player UI shell so a room's Jukebox plays YouTube-sourced tracks, queued by players, synchronized for everyone in the room.

**Architecture:** The emulator owns everything (per-room queue, current track, timing, metadata via YouTube oEmbed) and broadcasts one state packet; clients are dumb renderers that seek an embedded YouTube IFrame player to the server's elapsed position. Five new custom packets ride the established `Rp*` pipeline (yarn-patched nitro-renderer classes + reflection-registered PlusEMU handlers). The player itself is a small always-visible dock (YouTube embed terms: no hidden audio-only playback), expandable to a larger view.

**Tech Stack:** PlusEMU (C# .NET 7, this repo's `emulator/` submodule), nitro-react + patched nitro-renderer 1.6.6 (`client/` submodule), YouTube IFrame Player API, YouTube oEmbed (server-side metadata).

## Global Constraints

- Custom header ids: **3917** (S→C state), **3918** (C→S add), **3919** (C→S remove), **3921** (C→S skip), **3922** (C→S report). Verified free in stock `IncomingHeader.ts`/`OutgoingHeader.ts`, the renderer patch, and both emulator header files. Task 1 re-verifies before use.
- No 64-bit ints on the wire (EvaWire int32/string/bool only) — timing travels as `elapsedSec: int`, never epoch millis.
- The YouTube player must be **visible whenever audio plays** — minimum 200×200px, never `display:none` while a track is active (YouTube embed terms).
- Jukebox base item: `furniture.item_name = 'jukebox*1'` (id 1008) emulator-side; room objects client-side carry the color-stripped type `'jukebox'`.
- All new dark UI surfaces paint from `--prp-chrome-*` vars (see `client/src/assets/styles/_chrome.scss`), never hardcoded dark rgba.
- Neither repo has a test framework: every task's verification is a compile/build gate (`docker run … dotnet build` for the emulator, `yarn build` for the client) plus scripted manual checks; final in-game verification is handed to Ry on beta (established preference).
- Queue rules: max 20 entries, 30s per-user add cooldown, unknown-duration fallback advance at 600s.
- Commits: emulator work on submodule branch `pixelrp` (PlusEMU), client work on submodule branch `pixelrp` (nitro-react), pointer bumps on superproject `beta`. Push only when Ry says push.

---

### Task 1: Emulator — headers, track model, RoomJukeboxManager

**Files:**
- Modify: `emulator/Communication/Packets/Incoming/ClientPacketHeader.cs` (append after `RpSaveScreenshotEvent = 3913;`)
- Modify: `emulator/Communication/Packets/Outgoing/ServerPacketHeader.cs` (append near other `Rp*` consts — grep `RpStats` for the block)
- Create: `emulator/HabboHotel/Rooms/Jukebox/JukeboxTrack.cs`
- Create: `emulator/HabboHotel/Rooms/Jukebox/RoomJukeboxManager.cs`

**Interfaces:**
- Consumes: `Plus.HabboHotel.Rooms.Room` (`GetRoomItemHandler().GetFloor`, `SendPacket`), `Plus.Communication.Packets.Outgoing.ServerPacket`, `Plus.HabboHotel.GameClients.GameClient`.
- Produces (used by Tasks 2–3):
  - `class JukeboxTrack { string VideoId; string Title; string Author; int DurationSec; string QueuedBy; int QueuedById; }`
  - `class RoomJukeboxManager` with: `bool HasJukebox()`, `ServerPacket BuildState()`, `void BroadcastState()`, `void SendState(GameClient session)`, `string TryAdd(GameClient session, string url)` (returns null on success, else a player-facing error string; **does not itself fetch metadata** — Task 3's handler resolves metadata and calls `Enqueue`), `void Enqueue(JukeboxTrack track)`, `bool TryRemove(GameClient session, int index)`, `bool TrySkip(GameClient session)`, `void Report(GameClient session, int durationSec, bool ended)`, `void Cycle()`, `void OnJukeboxPlaced()`, `void OnJukeboxRemoved()`, `static string ParseVideoId(string input)`.

- [ ] **Step 1: Re-verify the header ids are free**

Run (from repo root):
```bash
for id in 3917 3918 3919 3921 3922; do grep -rn "= $id;" client/node_modules/@nitrots/nitro-renderer/src/nitro/communication/messages/incoming/IncomingHeader.ts client/node_modules/@nitrots/nitro-renderer/src/nitro/communication/messages/outgoing/OutgoingHeader.ts client/.yarn/patches/@nitrots-nitro-renderer-npm-1.6.6-c15ae4be91.patch emulator/Communication/Packets/Incoming/ClientPacketHeader.cs emulator/Communication/Packets/Outgoing/ServerPacketHeader.cs; done
```
Expected: no output. If any id is taken, substitute from this verified-free pool and update every later task consistently: 3923, 3924, 3927, 3929, 3930.

- [ ] **Step 2: Add the emulator header consts**

`ClientPacketHeader.cs`, after the `RpSaveScreenshotEvent` line (names must equal the Task 3 class names — PacketManager maps by reflection on class name):
```csharp
public const uint RpJukeboxAddEvent = 3918;
public const uint RpJukeboxRemoveEvent = 3919;
public const uint RpJukeboxSkipEvent = 3921;
public const uint RpJukeboxReportEvent = 3922;
```
`ServerPacketHeader.cs`, next to the other `Rp*` consts:
```csharp
public const uint RpJukeboxStateComposer = 3917;
```

- [ ] **Step 3: Create JukeboxTrack.cs**

```csharp
namespace Plus.HabboHotel.Rooms.Jukebox;

public class JukeboxTrack
{
    public string VideoId { get; set; }
    public string Title { get; set; }
    public string Author { get; set; }
    public int DurationSec { get; set; } // 0 = unknown until a client reports it
    public string QueuedBy { get; set; }
    public int QueuedById { get; set; }
}
```

- [ ] **Step 4: Create RoomJukeboxManager.cs**

```csharp
using System.Text.RegularExpressions;
using Plus.Communication.Packets.Outgoing;
using Plus.HabboHotel.GameClients;

namespace Plus.HabboHotel.Rooms.Jukebox;

// PixelRP: per-room YouTube jukebox. The room owns the queue and the clock;
// clients only render. State is one broadcast packet (RpJukeboxStateComposer);
// timing travels as elapsed seconds so no client clock sync is needed.
public class RoomJukeboxManager
{
    private const string JukeboxItemName = "jukebox*1";
    private const int MaxQueue = 20;
    private const int AddCooldownSec = 30;
    private const int UnknownDurationCapSec = 600;

    private readonly Room _room;
    private readonly List<JukeboxTrack> _queue = new();
    private readonly Dictionary<int, DateTime> _lastAddByUser = new();
    private JukeboxTrack _current;
    private DateTime _currentStartedAt;

    public RoomJukeboxManager(Room room)
    {
        _room = room;
    }

    private int ElapsedSec => (_current == null) ? 0 : (int)(DateTime.UtcNow - _currentStartedAt).TotalSeconds;

    public bool HasJukebox() =>
        _room.GetRoomItemHandler().GetFloor.Any(item => item.GetBaseItem().ItemName == JukeboxItemName);

    // Accepts full watch URLs, youtu.be links, shorts links or a bare 11-char id.
    public static string ParseVideoId(string input)
    {
        if (string.IsNullOrWhiteSpace(input))
            return null;
        input = input.Trim();
        if (Regex.IsMatch(input, "^[A-Za-z0-9_-]{11}$"))
            return input;
        var match = Regex.Match(input, @"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})");
        return match.Success ? match.Groups[1].Value : null;
    }

    // Pre-flight checks only; the packet handler fetches metadata then calls Enqueue.
    public string TryAdd(GameClient session, string url)
    {
        if (!HasJukebox())
            return "There's no jukebox in this room.";
        if (_queue.Count >= MaxQueue)
            return "The queue is full.";
        if (ParseVideoId(url) == null)
            return "That doesn't look like a YouTube link.";
        if (_lastAddByUser.TryGetValue(session.GetHabbo().Id, out var last) &&
            (DateTime.UtcNow - last).TotalSeconds < AddCooldownSec)
            return "Hold on a moment before queueing another song.";
        _lastAddByUser[session.GetHabbo().Id] = DateTime.UtcNow;
        return null;
    }

    public void Enqueue(JukeboxTrack track)
    {
        _queue.Add(track);
        if (_current == null)
            StartNext();
        else
            BroadcastState();
    }

    private void StartNext()
    {
        if (_queue.Count == 0)
        {
            _current = null;
            BroadcastState();
            return;
        }
        _current = _queue[0];
        _queue.RemoveAt(0);
        _currentStartedAt = DateTime.UtcNow;
        BroadcastState();
    }

    public bool TryRemove(GameClient session, int index)
    {
        if (index < 0 || index >= _queue.Count)
            return false;
        var canManage = _room.CheckRights(session, true) || _room.CheckRights(session);
        if (!canManage && _queue[index].QueuedById != session.GetHabbo().Id)
            return false;
        _queue.RemoveAt(index);
        BroadcastState();
        return true;
    }

    public bool TrySkip(GameClient session)
    {
        if (_current == null || !(_room.CheckRights(session, true) || _room.CheckRights(session)))
            return false;
        StartNext();
        return true;
    }

    // Clients report the player's real duration once loaded, and the ended signal.
    public void Report(GameClient session, int durationSec, bool ended)
    {
        if (_current == null)
            return;
        if (!ended && _current.DurationSec == 0 && durationSec >= 10 && durationSec <= 7200)
        {
            _current.DurationSec = durationSec;
            BroadcastState();
            return;
        }
        if (ended)
        {
            var minElapsed = (_current.DurationSec > 0) ? (int)(_current.DurationSec * 0.8) : 30;
            if (ElapsedSec >= minElapsed)
                StartNext();
        }
    }

    // Called from the room cycle: server-side auto-advance safety net.
    public void Cycle()
    {
        if (_current == null)
            return;
        var cap = (_current.DurationSec > 0) ? (_current.DurationSec + 2) : UnknownDurationCapSec;
        if (ElapsedSec > cap)
            StartNext();
    }

    public void OnJukeboxPlaced() => BroadcastState();

    public void OnJukeboxRemoved()
    {
        if (HasJukebox())
            return;
        _current = null;
        _queue.Clear();
        BroadcastState();
    }

    public ServerPacket BuildState()
    {
        var packet = new ServerPacket(ServerPacketHeader.RpJukeboxStateComposer);
        packet.WriteBoolean(HasJukebox());
        packet.WriteBoolean(_current != null);
        if (_current != null)
        {
            packet.WriteString(_current.VideoId);
            packet.WriteString(_current.Title);
            packet.WriteString(_current.Author);
            packet.WriteInteger(_current.DurationSec);
            packet.WriteInteger(ElapsedSec);
            packet.WriteString(_current.QueuedBy);
        }
        packet.WriteInteger(_queue.Count);
        foreach (var track in _queue)
        {
            packet.WriteString(track.VideoId);
            packet.WriteString(track.Title);
            packet.WriteString(track.Author);
            packet.WriteString(track.QueuedBy);
        }
        return packet;
    }

    public void BroadcastState() => _room.SendPacket(BuildState());

    public void SendState(GameClient session) => session.SendPacket(BuildState());
}
```
Note for the implementer: `ServerPacket`'s constructor and `CheckRights` signatures vary between PlusEMU forks — before compiling, grep an existing composer (e.g. `grep -rn "class ServerPacket" emulator/Communication` and `grep -rn "CheckRights(" emulator/HabboHotel/Rooms/Room.cs | head -5`) and adjust the two call sites to match this repo exactly. If `ServerPacket` takes `uint`, the code above is already correct.

- [ ] **Step 5: Compile**

```bash
cd emulator && docker run --rm -v "$PWD":/src -w /src mcr.microsoft.com/dotnet/sdk:7.0 dotnet build "Plus Emulator.sln" -v q --nologo 2>&1 | tail -3
```
Expected: `0 Error(s)`.

- [ ] **Step 6: Commit (emulator repo)**

```bash
cd emulator && git add -A && git commit -m "feat: jukebox headers, track model and room manager"
```

---

### Task 2: Emulator — Room integration (cycle, item hooks, room entry)

**Files:**
- Modify: `emulator/HabboHotel/Rooms/Room.cs` (add manager field + accessor; hook the cycle)
- Modify: `emulator/HabboHotel/Rooms/RoomItemHandling.cs` (or wherever floor items are added/removed — grep `GetFloor` usages)
- Modify: the room-entry completion path (grep `EnterRoom`/`OnUserEnter` in `emulator/HabboHotel/Rooms/`)

**Interfaces:**
- Consumes: `RoomJukeboxManager` (Task 1): `Cycle()`, `OnJukeboxPlaced()`, `OnJukeboxRemoved()`, `SendState(GameClient)`.
- Produces: `Room.GetJukeboxManager()` returning the per-room instance (used by Task 3 handlers).

- [ ] **Step 1: Add the manager to Room**

In `Room.cs`, follow the existing per-room manager pattern (find how `GetRoomUserManager()` is declared and mirror it):
```csharp
private RoomJukeboxManager _jukeboxManager;
public RoomJukeboxManager GetJukeboxManager() => _jukeboxManager ??= new RoomJukeboxManager(this);
```

- [ ] **Step 2: Hook the room cycle**

Find the room's periodic tick (grep `ProcessRoom` or the method the wired/bot ticks run from in `Room.cs`) and add one line inside it:
```csharp
GetJukeboxManager().Cycle();
```
Wrap in try/catch matching how sibling ticks are guarded if the surrounding code does so.

- [ ] **Step 3: Hook item placement/removal**

In `RoomItemHandling.cs`, locate the methods that (a) finish placing a floor item and (b) finish removing one (grep `SetFloorItem` / `RemoveFurniture`). After each succeeds, add:
```csharp
if (item.GetBaseItem().ItemName == "jukebox*1")
    _room.GetJukeboxManager().OnJukeboxPlaced();   // placement path
```
```csharp
if (item.GetBaseItem().ItemName == "jukebox*1")
    _room.GetJukeboxManager().OnJukeboxRemoved();  // removal path
```
(Use whatever the file's reference to its room is — grep `_room` in that file.)

- [ ] **Step 4: Send state on room entry**

In the path that completes a user entering a room (where the room sends its initial object/user packets to the arriving session), add:
```csharp
room.GetJukeboxManager().SendState(session);
```
Only send when `HasJukebox()` is true OR unconditionally — send unconditionally; the packet is tiny and the client uses `present=false` to hide the panel.

- [ ] **Step 5: Compile (same command as Task 1 Step 5), expect 0 errors**

- [ ] **Step 6: Commit (emulator repo)**

```bash
git add -A && git commit -m "feat: wire jukebox manager into room lifecycle"
```

---

### Task 3: Emulator — packet handlers + oEmbed metadata

**Files:**
- Create: `emulator/Communication/Packets/Incoming/Rooms/Jukebox/RpJukeboxAddEvent.cs`
- Create: `emulator/Communication/Packets/Incoming/Rooms/Jukebox/RpJukeboxRemoveEvent.cs`
- Create: `emulator/Communication/Packets/Incoming/Rooms/Jukebox/RpJukeboxSkipEvent.cs`
- Create: `emulator/Communication/Packets/Incoming/Rooms/Jukebox/RpJukeboxReportEvent.cs`

**Interfaces:**
- Consumes: `Room.GetJukeboxManager()` (Task 2), `JukeboxTrack`/manager methods (Task 1), `IPacketEvent` (class name must equal its `ClientPacketHeader` const — reflection registration is automatic, no manual wiring).
- Produces: the complete C→S wire surface; wire formats must match Task 4's client composers exactly:
  - 3918 add: `string url`
  - 3919 remove: `int index`
  - 3921 skip: (no payload)
  - 3922 report: `int durationSec, bool ended`

- [ ] **Step 1: Write RpJukeboxAddEvent.cs**

Follow `emulator/Communication/Packets/Incoming/Users/RpUseItemEvent.cs` for the class shape/ctor/DI conventions of this repo, with this logic:
```csharp
using System.Text.Json;
using Plus.HabboHotel.GameClients;
using Plus.HabboHotel.Rooms.Jukebox;

namespace Plus.Communication.Packets.Incoming.Rooms.Jukebox;

internal class RpJukeboxAddEvent : IPacketEvent
{
    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(5) };

    public async Task Parse(GameClient session, IIncomingPacket packet)
    {
        var url = packet.ReadString();
        var room = session.GetHabbo()?.CurrentRoom;
        if (room == null)
            return;
        var manager = room.GetJukeboxManager();
        var error = manager.TryAdd(session, url);
        if (error != null)
        {
            session.SendNotification(error);
            return;
        }
        var videoId = RoomJukeboxManager.ParseVideoId(url);
        try
        {
            // oEmbed: no API key, returns title + channel. Server-side fetch
            // dodges CORS and keeps clients out of the metadata trust path.
            var json = await Http.GetStringAsync(
                $"https://www.youtube.com/oembed?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3D{videoId}&format=json");
            using var doc = JsonDocument.Parse(json);
            manager.Enqueue(new JukeboxTrack
            {
                VideoId = videoId,
                Title = doc.RootElement.GetProperty("title").GetString() ?? videoId,
                Author = doc.RootElement.TryGetProperty("author_name", out var author) ? (author.GetString() ?? "") : "",
                DurationSec = 0,
                QueuedBy = session.GetHabbo().Username,
                QueuedById = session.GetHabbo().Id
            });
        }
        catch
        {
            // 404/401 from oEmbed = video missing, private or embed-restricted.
            session.SendNotification("That video can't be played (missing, private, or embedding disabled).");
        }
    }
}
```
Check whether `IPacketEvent.Parse` in this repo returns `Task` (it does — see `SaveBotActionEvent`); `async Task` is therefore valid. Verify `session.SendNotification` exists (grep it — `SaveBotActionEvent`-adjacent handlers use it); if the repo variant is `SendNotifClick`/whisper, use what exists.

- [ ] **Step 2: Write the three small handlers**

`RpJukeboxRemoveEvent.cs`:
```csharp
using Plus.HabboHotel.GameClients;

namespace Plus.Communication.Packets.Incoming.Rooms.Jukebox;

internal class RpJukeboxRemoveEvent : IPacketEvent
{
    public Task Parse(GameClient session, IIncomingPacket packet)
    {
        var index = packet.ReadInt();
        session.GetHabbo()?.CurrentRoom?.GetJukeboxManager().TryRemove(session, index);
        return Task.CompletedTask;
    }
}
```
`RpJukeboxSkipEvent.cs` — identical shape, body:
```csharp
session.GetHabbo()?.CurrentRoom?.GetJukeboxManager().TrySkip(session);
```
`RpJukeboxReportEvent.cs` — identical shape, body:
```csharp
var durationSec = packet.ReadInt();
var ended = packet.ReadInt() == 1;
session.GetHabbo()?.CurrentRoom?.GetJukeboxManager().Report(session, durationSec, ended);
```
Note: read the boolean the way sibling handlers do — if the repo's `IIncomingPacket` has `ReadBoolean()`, use it and have the client composer write a boolean; keep the two sides matched (Task 4 note repeats this).

- [ ] **Step 3: Compile (Task 1 Step 5 command), expect 0 errors**

- [ ] **Step 4: Commit (emulator repo)**

```bash
git add -A && git commit -m "feat: jukebox packet handlers with oEmbed metadata"
```

---

### Task 4: Client — renderer patch packets

**Files (all inside `client/node_modules/@nitrots/nitro-renderer/src/`, then resealed into the yarn patch):**
- Modify: `nitro/communication/messages/incoming/IncomingHeader.ts` (add `RP_JUKEBOX_STATE = 3917;` beside the other `RP_*`)
- Modify: `nitro/communication/messages/outgoing/OutgoingHeader.ts` (add `RP_JUKEBOX_ADD = 3918; RP_JUKEBOX_REMOVE = 3919; RP_JUKEBOX_SKIP = 3921; RP_JUKEBOX_REPORT = 3922;`)
- Create: `nitro/communication/messages/parser/rp/RpJukeboxStateParser.ts` (put beside the existing `Rp*` parsers — find with `ls .../parser/rp/ 2>/dev/null || grep -rl "RpStatsParser" src`)
- Create: `nitro/communication/messages/incoming/rp/RpJukeboxStateEvent.ts` (beside `RpStatsEvent`)
- Create: `nitro/communication/messages/outgoing/rp/RpJukeboxComposers.ts` (beside the other `Rp*` composers)
- Modify: the `index.ts` barrels that export the sibling `Rp*` classes (grep `RpStatsEvent` to find each)
- Modify: `nitro/communication/NitroMessages.ts` (register beside the existing `RP_*` blocks)

**Interfaces:**
- Consumes: wire formats from Tasks 1/3 — parser reads exactly: `present:bool, hasCurrent:bool, [videoId:string, title:string, author:string, durationSec:int, elapsedSec:int, queuedBy:string], queueCount:int, N×[videoId, title, author, queuedBy:string]`.
- Produces (used by Tasks 5–7): `RpJukeboxStateEvent` (with `getParser(): RpJukeboxStateParser` exposing `present`, `current: { videoId, title, author, durationSec, elapsedSec, queuedBy } | null`, `queue: { videoId, title, author, queuedBy }[]`), `RpJukeboxAddComposer(url: string)`, `RpJukeboxRemoveComposer(index: number)`, `RpJukeboxSkipComposer()`, `RpJukeboxReportComposer(durationSec: number, ended: boolean)`.

- [ ] **Step 1: Write the parser + event**

`RpJukeboxStateParser.ts`:
```typescript
import { IMessageDataWrapper, IMessageParser } from '../../../../../api';

export interface RpJukeboxQueueEntry { videoId: string; title: string; author: string; queuedBy: string; }
export interface RpJukeboxCurrent extends RpJukeboxQueueEntry { durationSec: number; elapsedSec: number; }

export class RpJukeboxStateParser implements IMessageParser
{
    private _present: boolean;
    private _current: RpJukeboxCurrent;
    private _queue: RpJukeboxQueueEntry[];

    public flush(): boolean
    {
        this._present = false;
        this._current = null;
        this._queue = [];
        return true;
    }

    public parse(wrapper: IMessageDataWrapper): boolean
    {
        if(!wrapper) return false;
        this._present = wrapper.readBoolean();
        if(wrapper.readBoolean())
        {
            const videoId = wrapper.readString();
            const title = wrapper.readString();
            const author = wrapper.readString();
            const durationSec = wrapper.readInt();
            const elapsedSec = wrapper.readInt();
            const queuedBy = wrapper.readString();
            this._current = { videoId, title, author, durationSec, elapsedSec, queuedBy };
        }
        const count = wrapper.readInt();
        for(let i = 0; i < count; i++)
        {
            this._queue.push({ videoId: wrapper.readString(), title: wrapper.readString(), author: wrapper.readString(), queuedBy: wrapper.readString() });
        }
        return true;
    }

    public get present(): boolean { return this._present; }
    public get current(): RpJukeboxCurrent { return this._current; }
    public get queue(): RpJukeboxQueueEntry[] { return this._queue; }
}
```
(Adjust the relative import path for `IMessageDataWrapper`/`IMessageParser` to match a sibling `Rp*` parser file — copy its import line.)

`RpJukeboxStateEvent.ts` — copy a sibling `RpStatsEvent` verbatim, swapping the class and parser names.

- [ ] **Step 2: Write the composers**

`RpJukeboxComposers.ts` — follow the sibling `Rp*` composer file's shape (`IMessageComposer<ConstructorParameters<...>>` pattern; copy one and adapt):
```typescript
export class RpJukeboxAddComposer implements IMessageComposer<[ string ]>
{
    private _data: [ string ];
    constructor(url: string) { this._data = [ url ]; }
    public getMessageArray() { return this._data; }
    public dispose(): void { return; }
}
```
…and the same shape for `RpJukeboxRemoveComposer([ index ])`, `RpJukeboxSkipComposer([])`, `RpJukeboxReportComposer([ durationSec, ended ? 1 : 0 ])`. **Booleans:** the report composer sends the ended flag as int `0/1` and the emulator reads `ReadInt()` (Task 3) — if Task 3 used `ReadBoolean()` instead, pass the raw boolean here; the two sides must match.

- [ ] **Step 3: Register + export**

In `NitroMessages.ts` add, beside the existing `RP_*` registrations:
```typescript
this._events.set(IncomingHeader.RP_JUKEBOX_STATE, RpJukeboxStateEvent);
this._composers.set(OutgoingHeader.RP_JUKEBOX_ADD, RpJukeboxAddComposer);
this._composers.set(OutgoingHeader.RP_JUKEBOX_REMOVE, RpJukeboxRemoveComposer);
this._composers.set(OutgoingHeader.RP_JUKEBOX_SKIP, RpJukeboxSkipComposer);
this._composers.set(OutgoingHeader.RP_JUKEBOX_REPORT, RpJukeboxReportComposer);
```
Add exports to the same `index.ts` barrels that export the sibling `Rp*` classes (grep `RpStatsEvent` and `RpSaveUiSettingsComposer` to find every barrel touched).

- [ ] **Step 4: Build to verify the edited node_modules sources compile**

```bash
cd client && yarn build 2>&1 | tail -2
```
Expected: `✓ built`.

- [ ] **Step 5: Reseal the yarn patch**

Follow the documented reseal procedure (memory: client-renderer patch workflow — the patch is a list of files; reseal = regenerate with all previously-patched files PLUS the new/modified ones):
```bash
cd client && yarn patch @nitrots/nitro-renderer
# copy EVERY file the old patch touches plus the files from Steps 1-3
# from node_modules/@nitrots/nitro-renderer/ into the printed temp dir,
# preserving paths, then:
yarn patch-commit -s <printed-temp-dir>
yarn install && yarn build 2>&1 | tail -2
```
Verify: `grep -c RP_JUKEBOX .yarn/patches/@nitrots-nitro-renderer-npm-1.6.6-*.patch` ≥ 10, and the build still passes **after** `yarn install` (this proves the patch, not the loose node_modules edits, carries the changes).

- [ ] **Step 6: Commit (client repo)**

```bash
git add -A && git commit -m "feat: jukebox packet classes in renderer patch"
```

---

### Task 5: Client — jukebox state hook, panel shows real data

**Files:**
- Create: `client/src/components/music-player/useJukebox.ts`
- Modify: `client/src/components/music-player/MusicPlayerView.tsx`

**Interfaces:**
- Consumes: `RpJukeboxStateEvent` (Task 4), `useMessageEvent` + `useRoom` hooks.
- Produces (used by Tasks 6–7):
```typescript
interface JukeboxCurrent { videoId: string; title: string; author: string; durationSec: number; startedAtMs: number; queuedBy: string; }
interface JukeboxQueueEntry { videoId: string; title: string; author: string; queuedBy: string; }
const useJukebox: () => { present: boolean; current: JukeboxCurrent | null; queue: JukeboxQueueEntry[]; }
```

- [ ] **Step 1: Write useJukebox.ts**

```typescript
import { RpJukeboxStateEvent } from '@nitrots/nitro-renderer';
import { useEffect, useState } from 'react';
import { useMessageEvent, useRoom } from '../../hooks';

export interface JukeboxCurrent { videoId: string; title: string; author: string; durationSec: number; startedAtMs: number; queuedBy: string; }
export interface JukeboxQueueEntry { videoId: string; title: string; author: string; queuedBy: string; }

// Server-authoritative jukebox state. Timing arrives as elapsed seconds;
// we anchor it to the local clock on receipt so the player can seek.
export const useJukebox = () =>
{
    const [ present, setPresent ] = useState(false);
    const [ current, setCurrent ] = useState<JukeboxCurrent>(null);
    const [ queue, setQueue ] = useState<JukeboxQueueEntry[]>([]);
    const { roomSession = null } = useRoom();

    useMessageEvent<RpJukeboxStateEvent>(RpJukeboxStateEvent, event =>
    {
        const parser = event.getParser();

        setPresent(parser.present);
        setCurrent(parser.current ? {
            videoId: parser.current.videoId,
            title: parser.current.title,
            author: parser.current.author,
            durationSec: parser.current.durationSec,
            startedAtMs: (Date.now() - (parser.current.elapsedSec * 1000)),
            queuedBy: parser.current.queuedBy
        } : null);
        setQueue(parser.queue);
    });

    useEffect(() =>
    {
        // Leaving/changing rooms clears everything; the new room's entry
        // packet repopulates it.
        setPresent(false);
        setCurrent(null);
        setQueue([]);
    }, [ roomSession ]);

    return { present, current, queue };
}
```

- [ ] **Step 2: Rewire MusicPlayerView**

Replace the furni-scan (`updateJukeboxPresence`, `useFurniAddedEvent`/`useFurniRemovedEvent`, `GetRoomEngine` import, `JUKEBOX_CLASS_NAME`) with `useJukebox()`. Render:
- panel hidden unless `present`;
- the NOW PLAYING kicker becomes a header row with a **plus-large icon top-right** (the project's FontAwesome kit, same classes the username icons use — memory: `fa-pixel fa-regular fa-<name>`):
```tsx
<div className="music-player-header">
    <div className="music-player-kicker">NOW PLAYING</div>
    <i className="fa-pixel fa-regular fa-plus-large music-player-add" title="Add a song" onClick={ event => setIsQueueOpen(true) } />
</div>
```
with `const [ isQueueOpen, setIsQueueOpen ] = useState(false);` — Task 7's window mounts from this state;
- title: `current ? current.title : 'Nothing playing'`;
- meta line: artist span = `current?.author || 'Unknown artist'`; the album span becomes `current ? \`queued by ${ current.queuedBy }\` : 'Unknown album'` (class names unchanged);
- Up next: `queue[0] ? queue[0].title : 'Queue is empty'`.
Keep the volume slider exactly as-is (Task 6 drives the player from it).
SCSS additions inside `.nitro-music-player`:
```scss
.music-player-header {
    display: flex;
    align-items: center;
    justify-content: space-between;

    .music-player-add {
        cursor: pointer;
        color: rgba($light, 0.6);

        &:hover { color: $white; }
    }
}
```

- [ ] **Step 3: Build (`yarn build`), expect success; commit (client repo)**

```bash
git add -A && git commit -m "feat: music player renders server jukebox state"
```

---

### Task 6: Client — YouTube IFrame player (mini dock, sync, reports)

**Files:**
- Create: `client/src/components/music-player/JukeboxYoutubePlayer.tsx`
- Modify: `client/src/components/music-player/MusicPlayerView.tsx`
- Modify: `client/src/components/music-player/MusicPlayerView.scss`

**Interfaces:**
- Consumes: `JukeboxCurrent` (Task 5), `RpJukeboxReportComposer` (Task 4), `SendMessageComposer` from `client/src/api`.
- Produces: `<JukeboxYoutubePlayer current={ JukeboxCurrent } volume={ number } expanded={ boolean } />` — mounted by MusicPlayerView whenever `current` is non-null.

- [ ] **Step 1: Write the player component**

```typescript
import { FC, useEffect, useRef, useState } from 'react';
import { RpJukeboxReportComposer } from '@nitrots/nitro-renderer';
import { SendMessageComposer } from '../../api';
import { JukeboxCurrent } from './useJukebox';

// Compliance note: YouTube's embed terms forbid hidden/audio-only playback.
// This player is ALWAYS rendered (>= 200x200) while a track is active —
// "collapsed" means the mini dock, never display:none.
let apiPromise: Promise<void> = null;

const loadIframeApi = () =>
{
    if(apiPromise) return apiPromise;
    apiPromise = new Promise<void>(resolve =>
    {
        if((window as any).YT && (window as any).YT.Player) { resolve(); return; }
        (window as any).onYouTubeIframeAPIReady = () => resolve();
        const tag = document.createElement('script');
        tag.src = 'https://www.youtube.com/iframe_api';
        document.head.appendChild(tag);
    });
    return apiPromise;
}

interface JukeboxYoutubePlayerProps { current: JukeboxCurrent; volume: number; expanded: boolean; }

export const JukeboxYoutubePlayer: FC<JukeboxYoutubePlayerProps> = props =>
{
    const { current = null, volume = 50, expanded = false } = props;
    const containerRef = useRef<HTMLDivElement>(null);
    const playerRef = useRef<any>(null);
    const reportedDurationFor = useRef<string>(null);
    const [ needsUnmute, setNeedsUnmute ] = useState(true);

    // create the player once
    useEffect(() =>
    {
        let disposed = false;

        loadIframeApi().then(() =>
        {
            if(disposed || !containerRef.current) return;
            playerRef.current = new (window as any).YT.Player(containerRef.current, {
                width: '100%', height: '100%',
                playerVars: { autoplay: 1, controls: 0, disablekb: 1, rel: 0 },
                events: {
                    onReady: () =>
                    {
                        playerRef.current.mute();
                        syncToCurrent();
                    },
                    onStateChange: (event: any) =>
                    {
                        if(event.data === (window as any).YT.PlayerState.ENDED)
                            SendMessageComposer(new RpJukeboxReportComposer(0, true));
                        if(event.data === (window as any).YT.PlayerState.PLAYING)
                        {
                            const duration = Math.round(playerRef.current.getDuration());
                            if(duration > 0 && reportedDurationFor.current !== currentRef.current?.videoId)
                            {
                                reportedDurationFor.current = currentRef.current?.videoId;
                                SendMessageComposer(new RpJukeboxReportComposer(duration, false));
                            }
                        }
                    },
                    // embed-disabled / removed videos: advance the room queue
                    onError: () => SendMessageComposer(new RpJukeboxReportComposer(0, true))
                }
            });
        });

        return () => { disposed = true; playerRef.current?.destroy?.(); playerRef.current = null; }
    }, []);

    // track changes / seeks
    const currentRef = useRef<JukeboxCurrent>(null);
    const syncToCurrent = () =>
    {
        const track = currentRef.current;
        if(!playerRef.current?.loadVideoById || !track) return;
        const elapsed = Math.max(0, (Date.now() - track.startedAtMs) / 1000);
        playerRef.current.loadVideoById({ videoId: track.videoId, startSeconds: elapsed });
    }

    useEffect(() =>
    {
        currentRef.current = current;
        syncToCurrent();
    }, [ current?.videoId, current?.startedAtMs ]);

    useEffect(() => { playerRef.current?.setVolume?.(volume); }, [ volume ]);

    const unmute = () =>
    {
        playerRef.current?.unMute?.();
        playerRef.current?.setVolume?.(volume);
        setNeedsUnmute(false);
    }

    return (
        <div className={ `jukebox-player${ expanded ? ' is-expanded' : '' }` }>
            <div ref={ containerRef } className="jukebox-player-frame" />
            { needsUnmute &&
                <div className="jukebox-player-unmute phone-tap" onClick={ unmute }>Tap to unmute</div> }
        </div>
    );
}
```
Implementation notes: browsers block unmuted autoplay, hence the muted start + explicit unmute tap (a user gesture, which satisfies the autoplay policy). `loadVideoById` on the same video with a new `startSeconds` performs the seek on re-broadcasts (duration updates re-anchor `startedAtMs` server-side as elapsed, so guard: only re-sync when `videoId` changes OR local position drifts > 3s from `elapsed` — add that check inside `syncToCurrent` using `playerRef.current.getCurrentTime()`).

- [ ] **Step 2: Mount in MusicPlayerView + expand control**

In `MusicPlayerView.tsx`: `const [ expanded, setExpanded ] = useState(false);` — render below the volume row:
```tsx
{ current &&
    <JukeboxYoutubePlayer current={ current } volume={ volume } expanded={ expanded } /> }
{ current &&
    <div className="music-player-expand phone-tap" onClick={ event => setExpanded(value => !value) }>{ expanded ? 'Shrink video' : 'Expand video' }</div> }
```

- [ ] **Step 3: SCSS for the dock**

Append inside `.nitro-music-player`:
```scss
.jukebox-player {
    position: relative;
    margin-top: 6px;
    width: 200px;   // YouTube embed minimum — never smaller, never hidden
    height: 200px;
    align-self: center;

    &.is-expanded {
        width: 356px;
        height: 200px;
        align-self: flex-end; // grows leftward past the 200px column
    }

    .jukebox-player-frame,
    .jukebox-player-frame iframe {
        width: 100%;
        height: 100%;
        border: 0;
        border-radius: $border-radius;
    }

    .jukebox-player-unmute {
        position: absolute;
        left: 50%;
        bottom: 8px;
        transform: translateX(-50%);
        padding: 4px 10px;
        border-radius: $border-radius;
        background: var(--prp-chrome-95);
        color: $white;
        font-family: 'Ubuntu', sans-serif;
        font-size: 11px;
        font-weight: 700;
        cursor: pointer;
        white-space: nowrap;
    }
}

.music-player-expand {
    margin-top: 4px;
    text-align: center;
    font-size: 11px;
    color: rgba($light, 0.6);
    cursor: pointer;

    &:hover { color: $white; }
}
```
(`phone-tap` already exists globally for tap feedback; if it's phone-scoped, drop the class — verify with `grep -n "\.phone-tap" client/src/components/phone/PhoneView.scss` and use plain `cursor: pointer` styling if scoped.)

- [ ] **Step 4: Build (`yarn build`), commit (client repo)**

```bash
git add -A && git commit -m "feat: synced YouTube dock player for the jukebox"
```

---

### Task 7: Client — queue window (add / remove / skip), opened from the panel's plus icon

**Files:**
- Create: `client/src/components/music-player/JukeboxQueueView.tsx`
- Modify: `client/src/components/music-player/MusicPlayerView.tsx` (render the window when `isQueueOpen`)
- Modify: `client/src/components/music-player/MusicPlayerView.scss`

**Interfaces:**
- Consumes: `JukeboxCurrent`/`JukeboxQueueEntry` types (Task 5), `RpJukeboxAddComposer`/`RpJukeboxRemoveComposer`/`RpJukeboxSkipComposer` (Task 4), `NitroCardView`/`NitroCardHeaderView`/`NitroCardContentView`, `Button` from `client/src/common`.
- Produces: `<JukeboxQueueView current={ JukeboxCurrent | null } queue={ JukeboxQueueEntry[] } onClose={ () => void } />` — a nitro window mounted by MusicPlayerView when the panel's plus-large icon is clicked. State comes in as PROPS from the panel's single `useJukebox()` instance — do NOT call `useJukebox()` here (a second hook instance mounts empty and only fills on the next broadcast).

- [ ] **Step 1: Write JukeboxQueueView.tsx**

```tsx
import { RpJukeboxAddComposer, RpJukeboxRemoveComposer, RpJukeboxSkipComposer } from '@nitrots/nitro-renderer';
import { FC, useState } from 'react';
import { SendMessageComposer } from '../../api';
import { Button, NitroCardContentView, NitroCardHeaderView, NitroCardView } from '../../common';
import { JukeboxCurrent, JukeboxQueueEntry } from './useJukebox';

// Opened from the music player panel's plus-large icon: paste a YouTube
// link to queue it for the room; rights holders (and the person who queued
// a song) can remove; rights holders can skip. All enforcement is
// server-side — these controls just send the packets.
interface JukeboxQueueViewProps
{
    current: JukeboxCurrent;
    queue: JukeboxQueueEntry[];
    onClose: () => void;
}

export const JukeboxQueueView: FC<JukeboxQueueViewProps> = props =>
{
    const { current = null, queue = [], onClose = null } = props;
    const [ url, setUrl ] = useState('');

    const addUrl = () =>
    {
        if(!url.trim().length) return;
        SendMessageComposer(new RpJukeboxAddComposer(url.trim()));
        setUrl('');
    }

    return (
        <NitroCardView uniqueKey="jukebox-queue" className="nitro-jukebox-queue" theme="primary-slim">
            <NitroCardHeaderView headerText="Jukebox" onCloseClick={ event => (onClose && onClose()) } />
            <NitroCardContentView className="text-black">
                <div className="jukebox-queue-now">
                    <b>Now playing:</b> { current ? `${ current.title } — ${ current.author }` : 'Nothing' }
                    { current && <Button variant="secondary" onClick={ event => SendMessageComposer(new RpJukeboxSkipComposer()) }>Skip</Button> }
                </div>
                <div className="jukebox-queue-list">
                    { queue.map((entry, index) => (
                        <div key={ `${ entry.videoId }-${ index }` } className="jukebox-queue-row">
                            <span className="jukebox-queue-title">{ entry.title }</span>
                            <span className="jukebox-queue-by">{ entry.queuedBy }</span>
                            <Button variant="danger" onClick={ event => SendMessageComposer(new RpJukeboxRemoveComposer(index)) }>×</Button>
                        </div>
                    )) }
                    { !queue.length && <div className="jukebox-queue-empty">Queue is empty — add a song below.</div> }
                </div>
                <div className="jukebox-queue-add">
                    <input type="text" className="form-control form-control-sm" spellCheck={ false } placeholder="Paste a YouTube link" value={ url } onChange={ event => setUrl(event.target.value) } onKeyDown={ event => (event.key === 'Enter') && addUrl() } />
                    <Button onClick={ event => addUrl() }>Add</Button>
                </div>
            </NitroCardContentView>
        </NitroCardView>
    );
}
```
Mount inside `MusicPlayerView`'s render (the NitroCard portals itself into the draggable-windows layer, so nesting is fine):
```tsx
{ isQueueOpen &&
    <JukeboxQueueView current={ current } queue={ queue } onClose={ () => setIsQueueOpen(false) } /> }
```

- [ ] **Step 2: SCSS**

Append (top level, beside `.nitro-music-player`):
```scss
.nitro-jukebox-queue {
    width: 280px;

    .jukebox-queue-now { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
    .jukebox-queue-list { display: flex; flex-direction: column; gap: 3px; max-height: 200px; overflow-y: auto; margin-bottom: 8px; }
    .jukebox-queue-row { display: flex; align-items: center; gap: 6px; }
    .jukebox-queue-title { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .jukebox-queue-by { color: $muted; font-size: 11px; flex-shrink: 0; }
    .jukebox-queue-empty { color: $muted; }
    .jukebox-queue-add { display: flex; gap: 6px; }
}
```

- [ ] **Step 3: Build (`yarn build`), commit (client repo)**

```bash
git add -A && git commit -m "feat: jukebox queue widget - add, remove, skip"
```

---

### Task 8: Changelog, pointer bumps, deploy, in-game handoff

**Files:**
- Modify: `CHANGELOG.md` (superproject)
- Modify: submodule pointers `client`, `emulator` (superproject `beta`)

- [ ] **Step 1: Changelog entry**

Under the current date's `### Added` (create the dated section if a new day):
```markdown
- **The Jukebox actually plays music now.** When a room has a Jukebox, hit
  the + on the music player under your wallet and paste a YouTube link to
  queue a song for everyone in the room — the player shows what's on, who
  queued it, and what's next, with a small video dock you can expand to
  watch. Room owners can skip and prune the queue; the person who queued a
  song can pull their own. First time it plays you'll need to tap "unmute"
  — browsers insist.
```

- [ ] **Step 2: Commit both submodules' final state, bump pointers**

```bash
cd emulator && git log --oneline -3   # confirm the 3 emulator commits exist
cd ../client && git log --oneline -4  # confirm the 4 client commits exist
cd .. && git add client emulator CHANGELOG.md
git commit -m "feat: jukebox YouTube player wiring (bump client, emulator)"
```

- [ ] **Step 3: Push only with Ry's go-ahead** (push order: `emulator` → `client` → superproject `beta`; the beta push triggers the deploy workflow)

- [ ] **Step 4: Manual verification script (on beta, after deploy)**

Hand to Ry — the checklist:
1. Room with Jukebox placed → panel appears under purse with "Nothing playing".
2. Click the plus-large icon top-right of the Now Playing box → Jukebox window opens; paste a normal YouTube URL → track starts for you; title/artist/queued-by populate; unmute pill works; volume slider works.
3. Second client (ClaudeTest/other account or second browser) in the same room → hears/sees the same track at the same position (±2s).
4. Queue a second track → appears in Up Next; first track ending auto-advances everyone.
5. Skip works with rights; a non-rights account can't skip (nothing happens) but can remove its own queued entry.
6. Pick up the Jukebox mid-song → playback stops, panel disappears for everyone; re-place → panel returns empty.
7. Leave/re-enter the room mid-song → playback resumes at the correct position.
8. Paste an embed-disabled video → error notification on add, or (if it slips through oEmbed) the room auto-skips it.
