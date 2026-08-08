# Camera Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Staff capture room photos, preview, purchase (free) into inventory as wall-photo items, publish (free) to the CMS Photos page.

**Architecture:** All new logic in the PlusEMU emulator: a `CameraPhotoManager` singleton plus six incoming handlers and five outgoing composers. Photos are written to a bind-mounted directory inside the web-served asset tree; publish inserts a `camera_web` row the existing CMS Photos page already renders. Zero client or CMS code changes.

**Tech Stack:** C# (.NET 7, PlusEMU fork), Dapper, MySQL 8, docker compose, nginx static serving.

**Spec:** `docs/superpowers/specs/2026-08-08-camera-pipeline-design.md`

## Global Constraints

- All camera prices are **0** (free) — `InitCamera` reply writes `0, 0, 0`.
- Emulator work happens on branch `feature/camera` of the emulator submodule; plus-repo work (compose, docs, SQL notes) on branch `feature/camera` of the plus repo. Merge to `pixelrp` / `main` only after E2E verification.
- The emulator has no unit-test project; each task's test cycle is: `docker compose build emulator` compiles clean → runtime verification steps given in the task.
- Photo files: `nitro/assets/c_images/camera/photo_<photoId>.png` (and `thumb_<photoId>.png`), where `<photoId>` is a lowercase GUID (`Guid.NewGuid().ToString("N")`).
- Served URL shape: `<camera.url.base>/photo_<photoId>.png` where the `camera.url.base` server_settings row is `http://localhost:8080/nitro-assets/assets/c_images/camera` (dev) / `https://pixelrp.co/nitro-assets/assets/c_images/camera` (prod). NOTE: `SettingsManager` lowercases values — all our URL/path values are already lowercase, safe.
- Wire ids (verified against `@nitrots/nitro-renderer` 1.6.6):
  - incoming (client→server): `InitCameraEvent`=796, `PhotoCompetitionEvent`=3959, `PublishPhotoEvent`=2068, `PurchasePhotoEvent`=2408, `RenderRoomEvent`=3226, `RenderRoomThumbnailEvent`=1982
  - outgoing (server→client): `InitCameraMessageComposer`=3878, `ThumbnailStatusMessageComposer`=3595, `CameraStorageUrlMessageComposer`=3696, `CameraPurchaseOkComposer`=2783, `CameraPublishStatusMessageComposer`=2057
- Internal header const values must be UNIQUE within each header class and must NOT collide with existing ids (max existing: incoming 4000, outgoing 3968). Use **4101-4106** (incoming) and **4101-4105** (outgoing).
- Reply payload shapes (verified against nitro-renderer parsers):
  - InitCamera: `WriteInteger(0); WriteInteger(0); WriteInteger(0);` (credit, ducket, publish-ducket prices)
  - ThumbnailStatus: `WriteBoolean(ok); WriteBoolean(false);` (ok, renderLimitHit)
  - CameraStorageUrl: `WriteString(url);`
  - CameraPurchaseOk: **no payload**
  - CameraPublishStatus: `WriteBoolean(ok); WriteInteger(0); WriteString(url);` (ok, secondsToWait, extraDataId=url)
- Client purchase/publish packets carry **no photo id** (`PurchasePhoto('')`, `PublishPhoto()`): the server must track the session's pending photo itself.
- Photo item extradata JSON (client `IPhotoData`, read by `useFurnitureExternalImageWidget` via `JSON.parse` of the item's data string): `{"t": <unix-millis>, "u": "<photoId>", "n": "<creator username>", "s": <creator user id>, "w": "<url>"}`.

---

### Task 0: Branches

**Files:** none (git only)

- [ ] **Step 1: Create the emulator feature branch**

```bash
cd emulator && git checkout -b feature/camera pixelrp && git push -u origin feature/camera
```

- [ ] **Step 2: Create the plus-repo feature branch**

```bash
cd .. && git checkout -b feature/camera main && git push -u origin feature/camera
```

### Task 1: Packet wire-up (headers, revision, composers)

**Files:**
- Modify: `emulator/Communication/Packets/Incoming/ClientPacketHeader.cs` (the commented `//Camera` block, ~line 320)
- Modify: `emulator/Communication/Packets/Outgoing/ServerPacketHeader.cs` (append before closing brace)
- Modify: `emulator/Resources/Revisions/1.6.6.json` (`IncomingHeaders` + `OutgoingHeaders` objects)
- Create: `emulator/Communication/Packets/Outgoing/Camera/InitCameraMessageComposer.cs`
- Create: `emulator/Communication/Packets/Outgoing/Camera/ThumbnailStatusMessageComposer.cs`
- Create: `emulator/Communication/Packets/Outgoing/Camera/CameraStorageUrlMessageComposer.cs`
- Create: `emulator/Communication/Packets/Outgoing/Camera/CameraPurchaseOkComposer.cs`
- Create: `emulator/Communication/Packets/Outgoing/Camera/CameraPublishStatusMessageComposer.cs`

**Interfaces:**
- Consumes: `IServerPacket`/`IOutgoingPacket` (existing), `ServerPacketHeader` consts (added here).
- Produces: the five composer classes exactly as named above; later tasks construct them with these signatures: `new InitCameraMessageComposer()`, `new ThumbnailStatusMessageComposer(bool ok)`, `new CameraStorageUrlMessageComposer(string url)`, `new CameraPurchaseOkComposer()`, `new CameraPublishStatusMessageComposer(bool ok, string url)`.

- [ ] **Step 1: Replace the commented camera block in ClientPacketHeader.cs**

```csharp
    //Camera
    public const uint InitCameraEvent = 4101;
    public const uint PhotoCompetitionEvent = 4102;
    public const uint PublishPhotoEvent = 4103;
    public const uint PurchasePhotoEvent = 4104;
    public const uint RenderRoomEvent = 4105;
    public const uint RenderRoomThumbnailEvent = 4106;
```

(Const names MUST equal the handler class names — `PacketManager` binds by reflection on the name.)

- [ ] **Step 2: Append camera consts to ServerPacketHeader.cs** (before the closing brace)

```csharp
    //Camera
    public const uint InitCameraMessageComposer = 4101;
    public const uint ThumbnailStatusMessageComposer = 4102;
    public const uint CameraStorageUrlMessageComposer = 4103;
    public const uint CameraPurchaseOkComposer = 4104;
    public const uint CameraPublishStatusMessageComposer = 4105;
```

- [ ] **Step 3: Add revision mappings to `emulator/Resources/Revisions/1.6.6.json`**

Inside `"IncomingHeaders": { ... }` add (json keys = handler class names, values = nitro wire ids):

```json
    "InitCameraEvent": 796,
    "PhotoCompetitionEvent": 3959,
    "PublishPhotoEvent": 2068,
    "PurchasePhotoEvent": 2408,
    "RenderRoomEvent": 3226,
    "RenderRoomThumbnailEvent": 1982,
```

Inside `"OutgoingHeaders": { ... }` add:

```json
    "InitCameraMessageComposer": 3878,
    "ThumbnailStatusMessageComposer": 3595,
    "CameraStorageUrlMessageComposer": 3696,
    "CameraPurchaseOkComposer": 2783,
    "CameraPublishStatusMessageComposer": 2057,
```

- [ ] **Step 4: Create the five composers.** Model on `emulator/Communication/Packets/Outgoing/Handshake/AuthenticationOKComposer.cs` for style. Full contents:

`InitCameraMessageComposer.cs`:
```csharp
namespace Plus.Communication.Packets.Outgoing.Camera;

public class InitCameraMessageComposer : IServerPacket
{
    public uint MessageId => ServerPacketHeader.InitCameraMessageComposer;

    public void Compose(IOutgoingPacket packet)
    {
        packet.WriteInteger(0); // credit price
        packet.WriteInteger(0); // ducket price
        packet.WriteInteger(0); // publish ducket price
    }
}
```

`ThumbnailStatusMessageComposer.cs`:
```csharp
namespace Plus.Communication.Packets.Outgoing.Camera;

public class ThumbnailStatusMessageComposer : IServerPacket
{
    private readonly bool _ok;
    public uint MessageId => ServerPacketHeader.ThumbnailStatusMessageComposer;

    public ThumbnailStatusMessageComposer(bool ok)
    {
        _ok = ok;
    }

    public void Compose(IOutgoingPacket packet)
    {
        packet.WriteBoolean(_ok);
        packet.WriteBoolean(false); // render limit hit
    }
}
```

`CameraStorageUrlMessageComposer.cs`:
```csharp
namespace Plus.Communication.Packets.Outgoing.Camera;

public class CameraStorageUrlMessageComposer : IServerPacket
{
    private readonly string _url;
    public uint MessageId => ServerPacketHeader.CameraStorageUrlMessageComposer;

    public CameraStorageUrlMessageComposer(string url)
    {
        _url = url;
    }

    public void Compose(IOutgoingPacket packet) => packet.WriteString(_url);
}
```

`CameraPurchaseOkComposer.cs`:
```csharp
namespace Plus.Communication.Packets.Outgoing.Camera;

public class CameraPurchaseOkComposer : IServerPacket
{
    public uint MessageId => ServerPacketHeader.CameraPurchaseOkComposer;

    public void Compose(IOutgoingPacket packet)
    {
        // no payload
    }
}
```

`CameraPublishStatusMessageComposer.cs`:
```csharp
namespace Plus.Communication.Packets.Outgoing.Camera;

public class CameraPublishStatusMessageComposer : IServerPacket
{
    private readonly bool _ok;
    private readonly string _url;
    public uint MessageId => ServerPacketHeader.CameraPublishStatusMessageComposer;

    public CameraPublishStatusMessageComposer(bool ok, string url)
    {
        _ok = ok;
        _url = url;
    }

    public void Compose(IOutgoingPacket packet)
    {
        packet.WriteBoolean(_ok);
        packet.WriteInteger(0); // seconds to wait
        packet.WriteString(_url);
    }
}
```

If the compiler complains that `IServerPacket`/`IOutgoingPacket` need imports, copy the `using` lines from `AuthenticationOKComposer.cs` verbatim.

- [ ] **Step 5: Build**

Run: `docker compose --project-directory . build emulator` (from the plus repo root)
Expected: `Image pixelrp-emulator Built`, no `error CS`.

- [ ] **Step 6: Boot check — no duplicate-header warnings**

Run: `docker compose up -d emulator && sleep 6 && docker compose logs emulator --tail 40 | grep -iE "warn|error" | head`
Expected: no new warnings about camera headers (the pre-existing "No incoming header defined" warnings for camera classes are GONE).

- [ ] **Step 7: Commit (emulator repo)**

```bash
cd emulator && git add Communication Resources && git commit -m "feat(camera): wire packet headers, revision ids, and reply composers" && cd ..
```

### Task 2: CameraPhotoManager

**Files:**
- Create: `emulator/HabboHotel/Camera/ICameraPhotoManager.cs`
- Create: `emulator/HabboHotel/Camera/CameraPhotoManager.cs`
- Create: `emulator/HabboHotel/Camera/PendingPhoto.cs`

**Interfaces:**
- Consumes: `ISettingsManager` (`emulator/Core/Settings`, method `TryGetValue(string key)` returning lowercased string), `[Singleton]` attribute (find it with `grep -rn "class SingletonAttribute" emulator --include="*.cs"` and copy the attribute usage pattern from `ISettingsManager`).
- Produces (used by Task 3 handlers):
  - `void StoreThumbnail(int userId, byte[] bytes)`
  - `string StorePhoto(int userId, uint roomId, byte[] bytes)` — writes `photo_<id>.png` (+ `thumb_<id>.png` if a thumbnail is stashed), records the pending photo, returns the photo **URL**
  - `bool TryGetPending(int userId, out PendingPhoto pending)`
  - `PendingPhoto` properties: `string PhotoId`, `uint RoomId`, `string Url`, `long TakenUnixMs`

- [ ] **Step 1: Write `PendingPhoto.cs`**

```csharp
namespace Plus.HabboHotel.Camera;

public record PendingPhoto(string PhotoId, uint RoomId, string Url, long TakenUnixMs);
```

- [ ] **Step 2: Write `ICameraPhotoManager.cs`** (copy the `[Singleton]`-attributed interface style from `ISettingsManager`)

```csharp
namespace Plus.HabboHotel.Camera;

[Singleton]
public interface ICameraPhotoManager
{
    void StoreThumbnail(int userId, byte[] bytes);
    string StorePhoto(int userId, uint roomId, byte[] bytes);
    bool TryGetPending(int userId, out PendingPhoto pending);
}
```

(Adjust the attribute's namespace import to match how `ISettingsManager` declares it.)

- [ ] **Step 3: Write `CameraPhotoManager.cs`**

```csharp
using System.Collections.Concurrent;
using Plus.Core.Settings;

namespace Plus.HabboHotel.Camera;

public class CameraPhotoManager : ICameraPhotoManager
{
    private const string DefaultStoragePath = "/camera-storage";
    private readonly ISettingsManager _settingsManager;
    private readonly ConcurrentDictionary<int, byte[]> _pendingThumbnails = new();
    private readonly ConcurrentDictionary<int, PendingPhoto> _pendingPhotos = new();

    public CameraPhotoManager(ISettingsManager settingsManager)
    {
        _settingsManager = settingsManager;
    }

    private string StoragePath
    {
        get
        {
            var path = _settingsManager.TryGetValue("camera.storage.path");
            return string.IsNullOrEmpty(path) ? DefaultStoragePath : path;
        }
    }

    private string UrlBase => _settingsManager.TryGetValue("camera.url.base") ?? "";

    public void StoreThumbnail(int userId, byte[] bytes) => _pendingThumbnails[userId] = bytes;

    public string StorePhoto(int userId, uint roomId, byte[] bytes)
    {
        Directory.CreateDirectory(StoragePath);
        var photoId = Guid.NewGuid().ToString("N");
        File.WriteAllBytes(Path.Combine(StoragePath, $"photo_{photoId}.png"), bytes);
        if (_pendingThumbnails.TryRemove(userId, out var thumb))
            File.WriteAllBytes(Path.Combine(StoragePath, $"thumb_{photoId}.png"), thumb);
        var url = $"{UrlBase}/photo_{photoId}.png";
        var pending = new PendingPhoto(photoId, roomId, url, DateTimeOffset.UtcNow.ToUnixTimeMilliseconds());
        _pendingPhotos[userId] = pending;
        return url;
    }

    public bool TryGetPending(int userId, out PendingPhoto pending) => _pendingPhotos.TryGetValue(userId, out pending);
}
```

If `ISettingsManager.TryGetValue` has a different signature (check `emulator/Core/Settings/SettingsManager.cs`), adapt the two call sites to it exactly.

- [ ] **Step 4: Build** — `docker compose --project-directory . build emulator`, expect clean.

- [ ] **Step 5: Commit**

```bash
cd emulator && git add HabboHotel/Camera && git commit -m "feat(camera): CameraPhotoManager (pending photos, disk writes, urls)" && cd ..
```

### Task 3: The six incoming handlers

**Files:**
- Modify: all six files in `emulator/Communication/Packets/Incoming/Camera/`

**Interfaces:**
- Consumes: `ICameraPhotoManager` (Task 2), the five composers (Task 1), `ItemFactory` (`emulator/HabboHotel/Items/ItemFactory.cs`, static `Instance`, method `CreateSingleItemNullable(ItemDefinition definition, Habbo habbo, string extraData, string displayFlags, int groupId = 0, ...)`), Dapper over `IDatabase` (constructor-inject like `Authenticator` does: `_database.Connection()` + `ExecuteAsync`).
- Produces: working camera round trip.

- [ ] **Step 1: `InitCameraEvent.cs`**

```csharp
using Plus.Communication.Packets.Outgoing.Camera;
using Plus.HabboHotel.GameClients;

namespace Plus.Communication.Packets.Incoming.Camera;

internal class InitCameraEvent : IPacketEvent
{
    public Task Parse(GameClient session, IIncomingPacket packet)
    {
        session.Send(new InitCameraMessageComposer());
        return Task.CompletedTask;
    }
}
```

- [ ] **Step 2: `PhotoCompetitionEvent.cs`** — polite no-op:

```csharp
using Plus.HabboHotel.GameClients;

namespace Plus.Communication.Packets.Incoming.Camera;

internal class PhotoCompetitionEvent : IPacketEvent
{
    public Task Parse(GameClient session, IIncomingPacket packet) => Task.CompletedTask;
}
```

- [ ] **Step 3: `RenderRoomThumbnailEvent.cs`**

```csharp
using Plus.Communication.Packets.Outgoing.Camera;
using Plus.HabboHotel.Camera;
using Plus.HabboHotel.GameClients;

namespace Plus.Communication.Packets.Incoming.Camera;

internal class RenderRoomThumbnailEvent : IPacketEvent
{
    private readonly ICameraPhotoManager _cameraPhotoManager;

    public RenderRoomThumbnailEvent(ICameraPhotoManager cameraPhotoManager)
    {
        _cameraPhotoManager = cameraPhotoManager;
    }

    public Task Parse(GameClient session, IIncomingPacket packet)
    {
        var length = packet.ReadInt();
        var bytes = packet.ReadBytes(length);
        _cameraPhotoManager.StoreThumbnail(session.GetHabbo().Id, bytes);
        session.Send(new ThumbnailStatusMessageComposer(true));
        return Task.CompletedTask;
    }
}
```

If `IIncomingPacket` has no `ReadBytes(int)`, check its interface (`grep -n "ReadBytes\|ReadInt\|Read" emulator/Communication/Packets/Incoming/IIncomingPacket.cs` or the class implementing it) and use the byte-reading method it does expose; add a `ReadBytes(int count)` to the packet implementation if genuinely absent, mirroring how `ReadString` consumes from the underlying buffer.

- [ ] **Step 4: `RenderRoomEvent.cs`**

```csharp
using Plus.Communication.Packets.Outgoing.Camera;
using Plus.HabboHotel.Camera;
using Plus.HabboHotel.GameClients;

namespace Plus.Communication.Packets.Incoming.Camera;

internal class RenderRoomEvent : IPacketEvent
{
    private readonly ICameraPhotoManager _cameraPhotoManager;

    public RenderRoomEvent(ICameraPhotoManager cameraPhotoManager)
    {
        _cameraPhotoManager = cameraPhotoManager;
    }

    public Task Parse(GameClient session, IIncomingPacket packet)
    {
        var length = packet.ReadInt();
        var bytes = packet.ReadBytes(length);
        var roomId = session.GetHabbo().CurrentRoomId;
        var url = _cameraPhotoManager.StorePhoto(session.GetHabbo().Id, (uint)roomId, bytes);
        session.Send(new CameraStorageUrlMessageComposer(url));
        return Task.CompletedTask;
    }
}
```

(`CurrentRoomId` — verify the property name on `Habbo` with `grep -n "CurrentRoomId\|CurrentRoom" emulator/HabboHotel/Users/Habbo.cs | head -5` and use what exists.)

- [ ] **Step 5: `PurchasePhotoEvent.cs`**

```csharp
using System.Text.Json;
using Plus.Communication.Packets.Outgoing.Camera;
using Plus.HabboHotel.Camera;
using Plus.HabboHotel.GameClients;
using Plus.HabboHotel.Items;

namespace Plus.Communication.Packets.Incoming.Camera;

internal class PurchasePhotoEvent : IPacketEvent
{
    private readonly ICameraPhotoManager _cameraPhotoManager;
    private readonly IItemDataManager _itemDataManager;

    public PurchasePhotoEvent(ICameraPhotoManager cameraPhotoManager, IItemDataManager itemDataManager)
    {
        _cameraPhotoManager = cameraPhotoManager;
        _itemDataManager = itemDataManager;
    }

    public Task Parse(GameClient session, IIncomingPacket packet)
    {
        // Protocol note: CameraPurchaseOK has no failure variant, so a missing
        // pending photo cannot send a "failed" reply — silent return + the
        // packet-exception logging is the agreed behavior (spec deviation, ok'd).
        if (!_cameraPhotoManager.TryGetPending(session.GetHabbo().Id, out var pending))
            return Task.CompletedTask;

        if (!_itemDataManager.GetItem(CameraPhotoItem.BaseItemId, out var definition))
            return Task.CompletedTask;

        var extradata = JsonSerializer.Serialize(new
        {
            t = pending.TakenUnixMs,
            u = pending.PhotoId,
            n = session.GetHabbo().Username,
            s = session.GetHabbo().Id,
            w = pending.Url,
        });

        var item = ItemFactory.Instance.CreateSingleItemNullable(definition, session.GetHabbo(), extradata, "");
        if (item != null)
        {
            session.GetHabbo().Inventory.Items.AddItem(item);
            session.Send(new CameraPurchaseOkComposer());
        }
        return Task.CompletedTask;
    }
}
```

Notes for the implementer, all verifiable in-repo:
- `CameraPhotoItem.BaseItemId`: add a one-line static class in `emulator/HabboHotel/Camera/CameraPhotoItem.cs`: `public static class CameraPhotoItem { public const uint BaseItemId = 4541; }` (the furniture row Task 5 fixes).
- `IItemDataManager.GetItem`: verify exact lookup signature with `grep -n "GetItem" emulator/HabboHotel/Items/ItemDataManager.cs | head -5` and adapt (it may be `TryGetItem(uint id, out ItemDefinition)` or index by id) — the requirement is: resolve base item definition id 4541.
- Inventory delivery: mirror EXACTLY how `sendGift`'s emulator-side equivalent or the catalog purchase delivers an item to a session — find it with `grep -rn "CreateSingleItemNullable" emulator --include="*.cs" | grep -v ItemFactory` and copy the add-to-inventory + refresh-composer lines from the closest existing usage (including any `UnseenItemsComposer`/`FurniListUpdateComposer` sends). Replace the `Inventory.Items.AddItem` line above with that exact pattern.

- [ ] **Step 6: `PublishPhotoEvent.cs`**

```csharp
using Dapper;
using Plus.Communication.Packets.Outgoing.Camera;
using Plus.Database;
using Plus.HabboHotel.Camera;
using Plus.HabboHotel.GameClients;

namespace Plus.Communication.Packets.Incoming.Camera;

internal class PublishPhotoEvent : IPacketEvent
{
    private readonly ICameraPhotoManager _cameraPhotoManager;
    private readonly IDatabase _database;

    public PublishPhotoEvent(ICameraPhotoManager cameraPhotoManager, IDatabase database)
    {
        _cameraPhotoManager = cameraPhotoManager;
        _database = database;
    }

    public async Task Parse(GameClient session, IIncomingPacket packet)
    {
        if (!_cameraPhotoManager.TryGetPending(session.GetHabbo().Id, out var pending))
        {
            session.Send(new CameraPublishStatusMessageComposer(false, ""));
            return;
        }

        using var connection = _database.Connection();
        await connection.ExecuteAsync(
            "INSERT INTO `camera_web` (`user_id`, `room_id`, `timestamp`, `url`, `visible`) VALUES (@userId, @roomId, @timestamp, @url, 1)",
            new { userId = session.GetHabbo().Id, roomId = pending.RoomId, timestamp = pending.TakenUnixMs / 1000, url = pending.Url });

        session.Send(new CameraPublishStatusMessageComposer(true, pending.Url));
    }
}
```

(`IDatabase`/`Connection()` usage: copy the exact namespace + pattern from `emulator/HabboHotel/Users/Authentication/Authenticator.cs`.)

- [ ] **Step 7: Build + boot + commit**

```bash
docker compose --project-directory . build emulator && docker compose up -d emulator
cd emulator && git add Communication HabboHotel/Camera && git commit -m "feat(camera): implement all six camera handlers" && cd ..
```

Boot log must show no camera-related warnings/errors.

### Task 4: server_settings rows + compose bind mounts

**Files:**
- Modify: `compose.yaml` (emulator service `volumes:`)
- Modify: `compose.prod.yaml` (emulator service — add `volumes:` list preserving the existing `!override` port entry semantics; volumes here are additive, ports stay as-is)

**Interfaces:** Produces the runtime environment Tasks 2-3 assume: `/camera-storage` inside the container ↔ `./nitro/assets/c_images/camera` on the host; `camera.*` settings rows.

- [ ] **Step 1: Create the host directory** (git-ignored tree)

```bash
mkdir -p nitro/assets/c_images/camera
```

- [ ] **Step 2: Add the bind mount to the emulator service in `compose.yaml`**

The emulator service currently has no `volumes:` key (verify with `grep -n "emulator:" -A 12 compose.yaml`). Add:

```yaml
    volumes:
      - ./nitro/assets/c_images/camera:/camera-storage
```

- [ ] **Step 3: Add the same to `compose.prod.yaml` under the emulator service**

```yaml
    volumes:
      - ./nitro/assets/c_images/camera:/camera-storage
```

- [ ] **Step 4: Insert dev settings rows**

```bash
echo 'INSERT INTO server_settings (`key`, `value`) VALUES ("camera.storage.path", "/camera-storage"), ("camera.url.base", "http://localhost:8080/nitro-assets/assets/c_images/camera") ON DUPLICATE KEY UPDATE value = VALUES(value);' | docker compose exec -T db sh -c 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"'
```

(If `server_settings` has no unique key on `key`, replace with a plain INSERT after a `SELECT` check — verify with `SHOW INDEX FROM server_settings`.)

Prod equivalent (run at deploy time, Task 7): same statement with `https://pixelrp.co/nitro-assets/assets/c_images/camera`.

- [ ] **Step 5: Recreate the emulator and verify the mount + settings**

```bash
docker compose up -d emulator
docker compose exec emulator sh -c 'touch /camera-storage/.rw-test && rm /camera-storage/.rw-test && echo MOUNT-OK'
docker compose logs emulator --tail 5 | grep -i "server settings"
```

Expected: `MOUNT-OK`; settings count in the boot log increased by 2 (17 vs the previous 15).

- [ ] **Step 6: Commit (plus repo, feature/camera branch)**

```bash
git add compose.yaml compose.prod.yaml && git commit -m "feat(camera): emulator photo storage bind mount"
```

### Task 5: Furniture row fix (photo wall item)

**Files:** none (SQL, documented in the commit + README task)

- [ ] **Step 1: Inspect the current row**

```bash
echo 'SELECT id, item_name, public_name, type, sprite_id, interaction_type, width, length FROM furniture WHERE id = 4541 OR sprite_id = 4541;' | docker compose exec -T db sh -c 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"'
```

- [ ] **Step 2: Correct it** (wall item, right classname, default interaction — wall items serialize their extradata string straight through, which is exactly what the JSON needs)

```bash
echo 'UPDATE furniture SET item_name = "external_image_wallitem_photo", public_name = "Photo", type = "i", interaction_type = "default", width = 1, length = 1, allow_trade = "0", allow_marketplace_sell = "0" WHERE id = 4541;' | docker compose exec -T db sh -c 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"'
```

- [ ] **Step 3: Restart the emulator** (item definitions are cached at boot) and verify it loads:

```bash
docker compose restart emulator && sleep 6 && docker compose logs emulator --tail 10 | grep -i "item manager"
```

Expected: `Item Manager -> LOADED` with no errors.

### Task 6: Local end-to-end verification

**Files:** none

- [ ] **Step 1: Ask the user to mint a ClaudeTest SSO ticket** (the assistant cannot mint; the user runs the usual tinker one-liner). Log into the local client with it.

- [ ] **Step 2: In the client:** expand the toolbar menu → camera → take a photo → editor → Preview.
Expected: checkout screen appears showing 0-cost purchase/publish options (previously: dead end). The preview image loads from `http://localhost:8080/nitro-assets/assets/c_images/camera/photo_<id>.png`.

- [ ] **Step 3: Purchase.** Expected: success UI; verify server side:

```bash
ls -t nitro/assets/c_images/camera/ | head -3
echo 'SELECT id, base_item, user_id, extra_data FROM items WHERE base_item = 4541 ORDER BY id DESC LIMIT 1;' | docker compose exec -T db sh -c 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"'
```

Expected: fresh `photo_*.png`; an `items` row whose `extra_data` is the IPhotoData JSON. (If the items table columns differ — check with `DESCRIBE items` — adjust the SELECT; the requirement is: a new inventory item exists for user 5 with the JSON extradata.)

- [ ] **Step 4: Publish.** Expected: success UI; verify:

```bash
echo 'SELECT * FROM camera_web ORDER BY id DESC LIMIT 1;' | docker compose exec -T db sh -c 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"'
curl -s http://localhost:8080/photos | grep -o "c_images/camera/photo_[a-f0-9]*\.png" | head -2
```

Expected: a `camera_web` row with the URL; the CMS Photos page HTML references the photo. (CMS route: verify the exact path with `grep -n "photos" cms/routes/web.php` — use whatever route is registered.)

- [ ] **Step 5: Place the photo item in the room** from inventory; click it. Expected: it renders the image on the wall and opens the photo viewer on click.

- [ ] **Step 6: Fix-forward loop.** Any failure: read `docker compose logs emulator --since 5m` (packet exceptions now log), fix, rebuild, re-test from the failing step. Commit fixes to the emulator `feature/camera` branch as they land.

### Task 7: Merge + prod deploy + docs

**Files:**
- Modify: `CHANGELOG.md` (new dated section)
- Modify: `docker/nitro/README.md` (camera storage note)

- [ ] **Step 1: Merge emulator branch**

```bash
cd emulator && git checkout pixelrp && git merge --no-ff feature/camera -m "merge: camera pipeline (feature/camera)" && git push origin pixelrp && cd ..
```

- [ ] **Step 2: Changelog + README.** CHANGELOG (player-facing, new top section):

```markdown
## 2026-08-08 — Say cheese 📸

### Added

- **The camera works end to end.** Staff can take photos of rooms, keep them
  as placeable wall photos, and publish them — published photos appear on the
  website's Photos page for everyone to browse.
```

README (`docker/nitro/README.md`, near the storage/serving notes): document that `nitro/assets/c_images/camera/` is written by the emulator (bind mount `/camera-storage`) and served like any other asset; `camera.*` keys live in `server_settings`.

- [ ] **Step 3: Merge plus branch**

```bash
git checkout main && git merge --no-ff feature/camera -m "merge: camera pipeline (feature/camera)" && git add CHANGELOG.md docker/nitro/README.md && git commit --amend --no-edit && git push origin main
```

(Or commit docs on the feature branch before merging — either way docs land with the merge.)

- [ ] **Step 4: Prod deploy** (user runs; emulator rebuild disconnects online players — coordinate timing):

```bash
ssh root@67.219.109.182 'cd /opt/pixelrp/emulator && git fetch origin && git checkout -f origin/pixelrp && cd /opt/pixelrp && git fetch origin && git checkout -f origin/main -- compose.yaml compose.prod.yaml && mkdir -p nitro/assets/c_images/camera && docker compose -f compose.yaml -f compose.prod.yaml up -d --build emulator'
```

Then the prod settings rows:

```bash
echo 'INSERT INTO server_settings (`key`, `value`) VALUES ("camera.storage.path", "/camera-storage"), ("camera.url.base", "https://pixelrp.co/nitro-assets/assets/c_images/camera") ON DUPLICATE KEY UPDATE value = VALUES(value);' | ssh root@67.219.109.182 'cd /opt/pixelrp && docker compose -f compose.yaml -f compose.prod.yaml exec -T db sh -c "mysql -u\"\$MYSQL_USER\" -p\"\$MYSQL_PASSWORD\" \"\$MYSQL_DATABASE\""'
```

And the prod furniture fix (same UPDATE as Task 5 via the ssh mysql pipe), then `docker compose -f compose.yaml -f compose.prod.yaml restart emulator`.

- [ ] **Step 5: Prod E2E** — one staff photo captured, purchased, published; confirm on https://pixelrp.co/photos (or the registered route) and `camera_web`.
