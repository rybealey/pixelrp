# VIP System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A real, time-based single-tier VIP membership: players buy VIP tokens with diamonds in the Diamonds Store's Store tab, redeem them from the RP Backpack, and get the full HC surface (clothing, dances, bubbles, purse/HC Center) plus camera, extra backpack slots, and a daily diamond stipend.

**Architecture:** `users.vip_expire` (unix seconds) is the single source of truth. `Habbo.IsVip` is computed live; `Habbo.VipRank` becomes a derived `IsVip ? 1 : 0`, which makes the emulator's dormant subscription-permission dimension (`permissions_subscriptions` → `silver_vip`) and every existing `VipRank` gate real. The five HC hardcodes are replaced with live values; the stock Nitro client's HC plumbing then just works. Store listings live in a new `diamonds_store_items` table with `price` + nullable `special_price` (sale).

**Tech Stack:** PlusEMU fork (C#/.NET, Dapper, MySQL 8), nitro-react fork (React/TS, Vite, yarn Berry `patch:` on @nitrots/nitro-renderer), no CMS changes.

**Spec:** `docs/superpowers/specs/2026-08-27-vip-system-design.md`

## Global Constraints

- **No em-dashes in any client-facing string** — Habbo fonts render `—` as a music note. Plain hyphens only.
- Custom emulator code comments start `// pixelrp:`; SQL migration header comments start `-- PixelRP`.
- Incoming packet **class name must exactly match its `ClientPacketHeader` const name** (PacketManager binds by reflection on the class name). Wire ids must also be added to `emulator/Resources/Revisions/1.6.6.json` (keys are the C# class names) and must match the C# consts.
- New wire ids for this feature: `DiamondsStoreComposer = 3925`, `DiamondsStorePurchaseResultComposer = 3926` (server→client); `GetDiamondsStoreEvent = 3929`, `PurchaseDiamondsStoreItemEvent = 3930` (client→server). Before using them, verify none appear in `emulator/Resources/Revisions/1.6.6.json`.
- **Never let a composer `_data` element be `undefined`/`null`** (client side): EvaWire writes a bare 2-byte short and silently desyncs every later field. Write `-1` sentinels for "no value" ints.
- MySQL 8: **no `ADD COLUMN IF NOT EXISTS`**. Migrations run once, tracked by filename in `_applied_sql_updates`.
- `server_settings` values are lowercased at load; missing keys return the string `"0"`.
- Pixel-art icons render 1:1 native size — `background-size: auto; image-rendering: pixelated;` — never scale them.
- No automated test infra exists in the emulator (empty `Tests/`) or client (no jest/vitest). Per-task verification is `dotnet build` (emulator) / `yarn eslint` + `yarn build` (client); final verification is the manual in-game checklist in Task 14 (Ry tests in-game).
- Emulator tasks commit in the `emulator/` submodule; client tasks in the `client/` submodule; superproject files (`nitro/ui-config*.json`, `CHANGELOG.md`, submodule bumps) commit on `feat/vip` in the superproject. Commit messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- All emulator paths below are relative to `emulator/`, client paths to `client/`, unless prefixed otherwise.

---

### Task 1: Migration 29 — VIP schema and seeds

**Files:**
- Create: `emulator/Resources/SQLs/Updates/29_AddVipSystem.sql`

**Interfaces:**
- Consumes: nothing.
- Produces: `users.vip_expire` (BIGINT, 0 default), `users.vip_last_stipend` (DATE NULL), tables `diamonds_store_items` / `diamonds_store_purchases`, seed rows `vip_token_31` (500 diamonds, 31 days, icon `vip-token-gold`) and `vip_token_14` (250 diamonds, 14 days, icon `vip-token-silver`), `server_settings` key `vip.stipend.daily = 5`, `badge_definitions` row `SVIP`.

- [ ] **Step 1: Confirm 29 is the next migration number and `SVIP` is the subscription-1 badge**

Run: `ls emulator/Resources/SQLs/Updates/ | sort -V | tail -3` — expect `28_AddWalkCommandPermission.sql` as highest.
Run: `grep -n "INSERT INTO \`subscriptions\`" -A 3 "emulator/Resources/SQLs/Original Database.sql"` — confirm subscription id 1 (`Silver VIP`) has `badge_code` `SVIP`. If the badge code differs, use that value below instead of `SVIP`.

- [ ] **Step 2: Write the migration**

```sql
-- PixelRP VIP system: time-based single-tier membership bought with diamonds
-- via Store-tab tokens redeemed from the RP backpack. users.vip_expire (unix
-- seconds, 0 = never VIP) is the single source of truth; rank_vip is no
-- longer read. vip_last_stipend gates the daily diamond stipend to one grant
-- per calendar day. diamonds_store_items powers the in-game Store tab:
-- special_price, when non-NULL, overrides price and renders as a sale.
ALTER TABLE `users`
    ADD COLUMN `vip_expire` BIGINT NOT NULL DEFAULT 0 AFTER `rank_vip`,
    ADD COLUMN `vip_last_stipend` DATE NULL DEFAULT NULL AFTER `vip_expire`;

CREATE TABLE `diamonds_store_items` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `item_key` VARCHAR(64) NOT NULL,
    `name` VARCHAR(128) NOT NULL,
    `description` VARCHAR(512) NOT NULL DEFAULT '',
    `icon` VARCHAR(64) NOT NULL,
    `price` INT NOT NULL,
    `special_price` INT NULL DEFAULT NULL,
    `vip_days` INT NOT NULL DEFAULT 0,
    `enabled` TINYINT(1) NOT NULL DEFAULT 1,
    `sort_order` INT NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    UNIQUE KEY `item_key` (`item_key`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

CREATE TABLE `diamonds_store_purchases` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `user_id` INT NOT NULL,
    `item_key` VARCHAR(64) NOT NULL,
    `diamonds_paid` INT NOT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

INSERT INTO `diamonds_store_items`
    (`item_key`, `name`, `description`, `icon`, `price`, `special_price`, `vip_days`, `enabled`, `sort_order`)
VALUES
    ('vip_token_31', 'VIP Token (31 days)', 'Redeem from your backpack to activate 31 days of VIP.', 'vip-token-gold', 500, NULL, 31, 1, 1),
    ('vip_token_14', 'VIP Token (14 days)', 'Redeem from your backpack to activate 14 days of VIP.', 'vip-token-silver', 250, NULL, 14, 1, 2);

INSERT IGNORE INTO `server_settings` (`key`, `value`) VALUES ('vip.stipend.daily', '5');

-- The VIP badge must exist in badge_definitions or BadgeManager.GiveBadge
-- silently refuses to grant it.
INSERT IGNORE INTO `badge_definitions` (`code`, `required_right`) VALUES ('SVIP', '');
```

- [ ] **Step 3: Apply to the local dev DB**

Find the local DB service in `compose.yaml` (service name + credentials, same env vars the emulator uses), then:
Run: `docker compose exec -T <db-service> mysql -u<user> -p<pass> <database> < emulator/Resources/SQLs/Updates/29_AddVipSystem.sql`
Expected: no errors. Verify: `... -e "SELECT item_key, price, vip_days FROM diamonds_store_items"` shows both rows.
(Beta/prod get this automatically: the deploy workflow applies new files in `Updates/` and records them in `_applied_sql_updates`.)

- [ ] **Step 4: Commit (emulator submodule)**

```bash
cd emulator && git add Resources/SQLs/Updates/29_AddVipSystem.sql && git commit -m "feat: VIP system schema (vip_expire, diamonds store tables, seeds)"
```

---

### Task 2: Emulator — VIP state on Habbo

**Files:**
- Modify: `emulator/HabboHotel/Users/Habbo.cs:110` (VipRank)
- Modify: `emulator/HabboHotel/Users/UserData/UserDataFactory.cs:55` (SELECT)
- Modify: `emulator/Communication/RCON/Commands/User/ReloadUserVIPRankCommand.cs`

**Interfaces:**
- Consumes: Task 1's columns.
- Produces: `Habbo.VipExpire` (`long`, settable), `Habbo.VipLastStipend` (`DateTime?`, settable), `Habbo.IsVip` (`bool`, computed), `Habbo.VipRank` (`int`, computed `IsVip ? 1 : 0`). Every later task uses `habbo.IsVip`.

- [ ] **Step 1: Replace the static VipRank with derived VIP state**

In `Habbo.cs`, replace `public int VipRank { get; set; }` (L110) with:

```csharp
// pixelrp: VIP is time-based. vip_expire (unix seconds) is the source of
// truth; rank_vip is no longer read. VipRank is derived so every legacy
// VipRank gate (permissions_subscriptions, catalog min_vip, respect
// allowance) keys off live VIP status.
public long VipExpire { get; set; }
public DateTime? VipLastStipend { get; set; }
public bool IsVip => VipExpire > DateTimeOffset.UtcNow.ToUnixTimeSeconds();
public int VipRank => IsVip ? 1 : 0;
```

- [ ] **Step 2: Update the Dapper load query**

In `UserDataFactory.cs` (the big SELECT around L55): remove the alias `u.`rank_vip` as VipRank` and add `u.`vip_expire` as VipExpire, u.`vip_last_stipend` as VipLastStipend` in its place. (A computed property with no setter makes Dapper fail if the alias stays.)

- [ ] **Step 3: Fix every remaining VipRank assignment**

Run: `grep -rn "VipRank" emulator --include='*.cs' | grep -v "\.claude"`
Reads (PermissionManager, ProcessComponent, CheckCreditsTimer, catalog gates, SSOTicketEvent, name-change tiers) compile unchanged. The known write is `ReloadUserVIPRankCommand.cs` — replace its `TryExecute` body with:

```csharp
    public Task<bool> TryExecute(string[] parameters)
    {
        if (!int.TryParse(parameters[0], out var userId))
            return Task.FromResult(false);
        var client = _gameClientManager.GetClientByUserId(userId);
        if (client == null || client.GetHabbo() == null)
            return Task.FromResult(false);
        using (var dbClient = _database.GetQueryReactor())
        {
            dbClient.SetQuery("SELECT `vip_expire` FROM `users` WHERE `id` = @userId LIMIT 1");
            dbClient.AddParameter("userId", userId);
            client.GetHabbo().VipExpire = Convert.ToInt64(dbClient.GetString());
        }
        client.GetHabbo().Permissions = new(_permissionManager.GetPermissionsForPlayer(client.GetHabbo()), _permissionManager.GetCommandsForPlayer(client.GetHabbo()));
        return Task.FromResult(true);
    }
```

Add `Plus.HabboHotel.Permissions` using, an `IPermissionManager _permissionManager` field, and the ctor parameter (mirror the existing `_database` field style). Fix any other assignment sites the grep surfaces the same way (load `vip_expire`, never write `VipRank`).

- [ ] **Step 4: Build**

Run: `cd emulator && dotnet build "Plus Emulator.sln"`
Expected: build succeeds, 0 errors.

- [ ] **Step 5: Commit (emulator submodule)**

```bash
cd emulator && git add -A && git commit -m "feat: time-based VIP state on Habbo (vip_expire, derived VipRank)"
```

---

### Task 3: Emulator — real club level and subscription info

**Files:**
- Modify: `emulator/Communication/Packets/Outgoing/Handshake/UserRightsComposer.cs`
- Modify: `emulator/Communication/Packets/Outgoing/Users/ScrSendUserInfoComposer.cs`
- Modify: `emulator/Communication/Packets/Incoming/Users/ScrGetUserInfoEvent.cs`
- Modify: `emulator/Communication/Packets/Incoming/Handshake/SSOTicketEvent.cs:105,139`
- Modify: `emulator/Communication/Packets/Incoming/Users/UpdateFigureDataEvent.cs:30`
- Modify: `emulator/Communication/Packets/Incoming/Avatar/SaveWardrobeOutfitEvent.cs:25`
- Modify: `emulator/HabboHotel/Rooms/Chat/Commands/User/Fun/FacelessCommand.cs:45`

**Interfaces:**
- Consumes: `Habbo.IsVip`, `Habbo.VipExpire` (Task 2).
- Produces: `UserRightsComposer(int clubLevel, int rank, bool isAmbassador)`; `ScrSendUserInfoComposer(Habbo habbo, int responseType = 1)` (responseType 1 = login/poll, 2 = purchase). Tasks 6 and 7 send both.

- [ ] **Step 1: Parameterize UserRightsComposer**

Replace the class body so the club level is a ctor argument (this is the value `SessionDataManager.clubLevel` and every client HC gate keys off):

```csharp
public class UserRightsComposer : IServerPacket
{
    private readonly int _clubLevel;
    private readonly int _rank;
    private readonly bool _isAmbassador;

    public uint MessageId => ServerPacketHeader.UserRightsComposer;

    public UserRightsComposer(int clubLevel, int rank, bool isAmbassador)
    {
        _clubLevel = clubLevel;
        _rank = rank;
        _isAmbassador = isAmbassador;
    }

    public void Compose(IOutgoingPacket packet)
    {
        packet.WriteInteger(_clubLevel); // 2 = VIP, 0 = none
        packet.WriteInteger(_rank);
        packet.WriteBoolean(_isAmbassador);
    }
}
```

Update the call site `SSOTicketEvent.cs:105` to:

```csharp
session.Send(new UserRightsComposer(session.GetHabbo().IsVip ? 2 : 0, session.GetHabbo().Rank, session.GetHabbo().IsAmbassador));
```

- [ ] **Step 2: Implement ScrSendUserInfoComposer**

Replace the stub. Field order is ground truth from the client's `UserSubscriptionParser` (string, int, int, int, int, bool, bool, int, int, int):

```csharp
using Plus.HabboHotel.Users;

namespace Plus.Communication.Packets.Outgoing.Users;

// pixelrp: real subscription info for the purse HC chip and HC Center.
// Field order must match the client's UserSubscriptionParser exactly.
public class ScrSendUserInfoComposer : IServerPacket
{
    private readonly Habbo _habbo;
    private readonly int _responseType;

    public uint MessageId => ServerPacketHeader.ScrSendUserInfoComposer;

    public ScrSendUserInfoComposer(Habbo habbo, int responseType = 1)
    {
        _habbo = habbo;
        _responseType = responseType;
    }

    public void Compose(IOutgoingPacket packet)
    {
        var now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        var secondsLeft = Math.Max(0, _habbo.VipExpire - now);
        var daysLeft = (int)Math.Ceiling(secondsLeft / 86400.0);
        packet.WriteString("habbo_club");
        packet.WriteInteger(daysLeft);                       // daysToPeriodEnd
        packet.WriteInteger(_habbo.IsVip ? 1 : 0);           // memberPeriods
        packet.WriteInteger(0);                              // periodsSubscribedAhead
        packet.WriteInteger(_responseType);                  // 1 = login, 2 = purchase
        packet.WriteBoolean(_habbo.VipExpire > 0);           // hasEverBeenMember
        packet.WriteBoolean(_habbo.IsVip);                   // isVip
        packet.WriteInteger(0);                              // pastClubDays
        packet.WriteInteger(0);                              // pastVipDays
        packet.WriteInteger((int)Math.Min(int.MaxValue, secondsLeft / 60)); // minutesUntilExpiration
    }
}
```

(Purse note: the client's `Purse.clubLevel` getter returns VIP when `clubDays > 0 && isVip` — these fields produce exactly that for active VIPs and NO_CLUB for everyone else.)

Update `ScrGetUserInfoEvent.cs` (13 lines) so its send passes the habbo: `session.Send(new ScrSendUserInfoComposer(session.GetHabbo()));`. The client polls this every 50s once `hc.disabled` is false — it is the live channel for purse day counts.

- [ ] **Step 3: Real figure validation (soft lapse)**

At each of the four `ProcessFigure(..., true)` call sites listed above, change the final literal `true` to `session.GetHabbo().IsVip`. Validation only runs when an outfit is saved/processed, so lapsed VIPs keep their current look until they change clothes — this IS the soft-lapse behavior; add no extra stripping anywhere.

- [ ] **Step 4: Build, commit**

Run: `cd emulator && dotnet build "Plus Emulator.sln"` — expect success.

```bash
cd emulator && git add -A && git commit -m "feat: real club level, subscription info, and VIP figure validation"
```

---

### Task 4: Emulator — Diamonds Store manager and packets

**Files:**
- Create: `emulator/HabboHotel/DiamondsStore/DiamondsStoreItem.cs`
- Create: `emulator/HabboHotel/DiamondsStore/IDiamondsStoreManager.cs`
- Create: `emulator/HabboHotel/DiamondsStore/DiamondsStoreManager.cs`
- Create: `emulator/Communication/Packets/Outgoing/Users/DiamondsStoreComposer.cs`
- Create: `emulator/Communication/Packets/Outgoing/Users/DiamondsStorePurchaseResultComposer.cs`
- Create: `emulator/Communication/Packets/Incoming/Users/GetDiamondsStoreEvent.cs`
- Create: `emulator/Communication/Packets/Incoming/Users/PurchaseDiamondsStoreItemEvent.cs`
- Modify: `emulator/Communication/Packets/Outgoing/ServerPacketHeader.cs` (pixelrp block, ~L166)
- Modify: `emulator/Communication/Packets/Incoming/ClientPacketHeader.cs` (pixelrp block, ~L396)
- Modify: `emulator/Resources/Revisions/1.6.6.json` (both custom blocks)
- Modify: `emulator/Program.cs` (DI), `emulator/HabboHotel/Game.cs` (+Init call)

**Interfaces:**
- Consumes: `diamonds_store_items` (Task 1), `Habbo.Diamonds`, `Habbo.AddRpItem(string)`, `Habbo.LoadRpInventory()`, `RpInventoryComposer`, `HabboActivityPointNotificationComposer(balance, notify, type: 5)`.
- Produces: `IDiamondsStoreManager` with `Task Init()`, `IReadOnlyList<DiamondsStoreItem> Items`, `bool TryGetItem(string itemKey, out DiamondsStoreItem item)`; `DiamondsStoreItem { ItemKey, Name, Description, Icon, Price, SpecialPrice (int?), VipDays, SortOrder, EffectivePrice }`. Task 6 injects the manager into `RpUseItemEvent`. Wire formats consumed by Task 10's client parsers.

- [ ] **Step 1: Verify wire ids are free**

Run: `grep -nE "3925|3926|3929|3930" emulator/Resources/Revisions/1.6.6.json`
Expected: no matches. If any id is taken, pick the next free id ≥ 3929 and use it consistently here and in Task 10.

- [ ] **Step 2: Headers + revision map**

`ServerPacketHeader.cs`, append inside the pixelrp block:

```csharp
public const uint DiamondsStoreComposer = 3925;
public const uint DiamondsStorePurchaseResultComposer = 3926;
```

`ClientPacketHeader.cs`, append inside the pixelrp block:

```csharp
public const uint GetDiamondsStoreEvent = 3929;
public const uint PurchaseDiamondsStoreItemEvent = 3930;
```

`Resources/Revisions/1.6.6.json`: add `"GetDiamondsStoreEvent": 3929, "PurchaseDiamondsStoreItemEvent": 3930` to the custom incoming block (~L277-289) and `"DiamondsStoreComposer": 3925, "DiamondsStorePurchaseResultComposer": 3926` to the custom outgoing block (~L559-565), matching the existing entries' JSON shape exactly.

- [ ] **Step 3: Manager (mirrors SubscriptionManager)**

`DiamondsStoreItem.cs`:

```csharp
namespace Plus.HabboHotel.DiamondsStore;

public class DiamondsStoreItem
{
    public int Id { get; set; }
    public string ItemKey { get; set; }
    public string Name { get; set; }
    public string Description { get; set; }
    public string Icon { get; set; }
    public int Price { get; set; }
    public int? SpecialPrice { get; set; }
    public int VipDays { get; set; }
    public int SortOrder { get; set; }

    public int EffectivePrice => SpecialPrice ?? Price;
}
```

`IDiamondsStoreManager.cs`:

```csharp
namespace Plus.HabboHotel.DiamondsStore;

public interface IDiamondsStoreManager
{
    Task Init();
    IReadOnlyList<DiamondsStoreItem> Items { get; }
    bool TryGetItem(string itemKey, out DiamondsStoreItem item);
}
```

`DiamondsStoreManager.cs` (copy `SubscriptionManager.cs`'s structure: `IDatabase` + `ILogger<T>` ctor, Dapper query in `Init`):

```csharp
using Dapper;
using Microsoft.Extensions.Logging;
using Plus.Database;

namespace Plus.HabboHotel.DiamondsStore;

// pixelrp: in-game Store tab listings (VIP tokens and future diamond items).
// special_price, when non-NULL, overrides price and renders as a sale.
public class DiamondsStoreManager : IDiamondsStoreManager
{
    private readonly IDatabase _database;
    private readonly ILogger<DiamondsStoreManager> _logger;
    private List<DiamondsStoreItem> _items = new();

    public DiamondsStoreManager(IDatabase database, ILogger<DiamondsStoreManager> logger)
    {
        _database = database;
        _logger = logger;
    }

    public IReadOnlyList<DiamondsStoreItem> Items => _items;

    public async Task Init()
    {
        using var connection = _database.Connection();
        _items = (await connection.QueryAsync<DiamondsStoreItem>(
            "SELECT `id`, `item_key` AS ItemKey, `name`, `description`, `icon`, `price`, `special_price` AS SpecialPrice, `vip_days` AS VipDays, `sort_order` AS SortOrder " +
            "FROM `diamonds_store_items` WHERE `enabled` = 1 ORDER BY `sort_order`")).ToList();
        _logger.LogInformation("Loaded " + _items.Count + " diamonds store items.");
    }

    public bool TryGetItem(string itemKey, out DiamondsStoreItem item)
    {
        item = _items.FirstOrDefault(candidate => candidate.ItemKey == itemKey);
        return item != null;
    }
}
```

DI + boot: `grep -n "ISubscriptionManager" emulator/Program.cs emulator/HabboHotel/Game.cs`. Add `services.AddSingleton<IDiamondsStoreManager, DiamondsStoreManager>();` next to the SubscriptionManager registration in `Program.cs`, an `IDiamondsStoreManager` ctor field in `Game.cs`, and `await _diamondsStoreManager.Init();` next to the SubscriptionManager `Init()` call in `Game.Init`.

- [ ] **Step 4: Listing packets**

`DiamondsStoreComposer.cs` (write order = Task 10's parser read order):

```csharp
using Plus.HabboHotel.DiamondsStore;

namespace Plus.Communication.Packets.Outgoing.Users;

public class DiamondsStoreComposer : IServerPacket
{
    private readonly IReadOnlyList<DiamondsStoreItem> _items;

    public uint MessageId => ServerPacketHeader.DiamondsStoreComposer;

    public DiamondsStoreComposer(IReadOnlyList<DiamondsStoreItem> items)
    {
        _items = items;
    }

    public void Compose(IOutgoingPacket packet)
    {
        packet.WriteInteger(_items.Count);
        foreach (var item in _items)
        {
            packet.WriteString(item.ItemKey);
            packet.WriteString(item.Name);
            packet.WriteString(item.Description);
            packet.WriteString(item.Icon);
            packet.WriteInteger(item.Price);
            packet.WriteInteger(item.SpecialPrice ?? -1); // -1 = no sale
            packet.WriteInteger(item.VipDays);
        }
    }
}
```

`DiamondsStorePurchaseResultComposer.cs` — same shape, fields `int _status` (0 = ok, 1 = not enough diamonds, 2 = backpack full), `string _itemKey`; `Compose` writes `WriteInteger(_status)` then `WriteString(_itemKey)`.

`GetDiamondsStoreEvent.cs`:

```csharp
using Plus.HabboHotel.DiamondsStore;
using Plus.HabboHotel.GameClients;
using Plus.Communication.Packets.Outgoing.Users;

namespace Plus.Communication.Packets.Incoming.Users;

internal class GetDiamondsStoreEvent : IPacketEvent
{
    private readonly IDiamondsStoreManager _storeManager;

    public GetDiamondsStoreEvent(IDiamondsStoreManager storeManager) => _storeManager = storeManager;

    public Task Parse(GameClient session, IIncomingPacket packet)
    {
        session.Send(new DiamondsStoreComposer(_storeManager.Items));
        return Task.CompletedTask;
    }
}
```

- [ ] **Step 5: Purchase packet**

`PurchaseDiamondsStoreItemEvent.cs`. Order matters: the item lands in the backpack first (its `AddRpItem` is the authority on stacking/free slots), then diamonds are deducted — a DB failure can under-charge but never charge-without-delivering:

```csharp
using Plus.Communication.Packets.Outgoing.Inventory.Purse;
using Plus.Communication.Packets.Outgoing.Users;
using Plus.HabboHotel.DiamondsStore;
using Plus.HabboHotel.GameClients;

namespace Plus.Communication.Packets.Incoming.Users;

// pixelrp: buy a Store-tab item with diamonds. Delivery is into the RP
// backpack; failures never charge.
internal class PurchaseDiamondsStoreItemEvent : IPacketEvent
{
    private readonly IDiamondsStoreManager _storeManager;

    public PurchaseDiamondsStoreItemEvent(IDiamondsStoreManager storeManager) => _storeManager = storeManager;

    public Task Parse(GameClient session, IIncomingPacket packet)
    {
        var itemKey = packet.ReadString();
        var habbo = session.GetHabbo();
        if (habbo == null || !_storeManager.TryGetItem(itemKey, out var item))
            return Task.CompletedTask;
        if (habbo.Diamonds < item.EffectivePrice)
        {
            session.Send(new DiamondsStorePurchaseResultComposer(1, itemKey));
            return Task.CompletedTask;
        }
        var slot = habbo.AddRpItem(item.ItemKey);
        if (slot == -1)
        {
            session.Send(new DiamondsStorePurchaseResultComposer(2, itemKey));
            return Task.CompletedTask;
        }
        habbo.Diamonds -= item.EffectivePrice;
        using (var dbClient = PlusEnvironment.DatabaseManager.GetQueryReactor())
        {
            dbClient.SetQuery("UPDATE `users` SET `vip_points` = @diamonds WHERE `id` = @id LIMIT 1");
            dbClient.AddParameter("diamonds", habbo.Diamonds);
            dbClient.AddParameter("id", habbo.Id);
            dbClient.RunQuery();
            dbClient.SetQuery("INSERT INTO `diamonds_store_purchases` (`user_id`, `item_key`, `diamonds_paid`) VALUES (@id, @itemKey, @paid)");
            dbClient.AddParameter("id", habbo.Id);
            dbClient.AddParameter("itemKey", item.ItemKey);
            dbClient.AddParameter("paid", item.EffectivePrice);
            dbClient.RunQuery();
        }
        session.Send(new HabboActivityPointNotificationComposer(habbo.Diamonds, 0, 5));
        session.Send(new RpInventoryComposer(habbo.LoadRpInventory()));
        session.Send(new DiamondsStorePurchaseResultComposer(0, itemKey));
        return Task.CompletedTask;
    }
}
```

(Match the query-reactor idiom to `Habbo.EnsureRpStatsLoaded` — if `RunQuery` is named differently there, e.g. `RunQuery()` vs `GetResult()`, copy the existing pattern.) Neither event is `[StaffOnly]` — these are player packets.

- [ ] **Step 6: Build, commit**

Run: `cd emulator && dotnet build "Plus Emulator.sln"` — expect success (PacketManager auto-registers both events by class-name reflection; no manual wiring).

```bash
cd emulator && git add -A && git commit -m "feat: diamonds store manager and purchase packets"
```

---

### Task 5: Emulator — VIP-aware backpack capacity

**Files:**
- Modify: `emulator/HabboHotel/Users/Habbo.cs:295-360` (RpCarrySlots, AddRpItem)

**Interfaces:**
- Consumes: `Habbo.IsVip` (Task 2).
- Produces: `Habbo.RpCarrySlots = 12` (absolute max, used by `RpUseItemEvent`'s bounds check), `Habbo.RpCarrySlotsBase = 10`, `Habbo.RpUnlockedSlots` (`int`, 12 while VIP else 10). `AddRpItem` only ever places into slots `1..RpUnlockedSlots`.

- [ ] **Step 1: Split the slot constants**

Replace `public const int RpCarrySlots = 10;` with:

```csharp
// pixelrp: 12 physical slots (the client renders 12); the last two unlock
// while VIP is active. Soft lapse: items already in 11-12 stay usable and
// consumable after expiry, but nothing new can be placed there.
public const int RpCarrySlots = 12;
public const int RpCarrySlotsBase = 10;
public int RpUnlockedSlots => IsVip ? RpCarrySlots : RpCarrySlotsBase;
```

- [ ] **Step 2: Gate placement in AddRpItem**

Inside `AddRpItem` (L313): the stacking branch must only stack onto a slot `<= RpUnlockedSlots`, and the free-slot search `Enumerable.Range(1, RpCarrySlots)` becomes `Enumerable.Range(1, RpUnlockedSlots)`. Do NOT change `ConsumeRpItem` or `LoadRpInventory` — consumption from 11-12 stays allowed after lapse. `RpUseItemEvent`'s bounds check (`slot > Habbo.RpCarrySlots`) now allows 1-12 by virtue of the constant change; leave it as is.

- [ ] **Step 3: Build, commit**

Run: `cd emulator && dotnet build "Plus Emulator.sln"` — expect success.

```bash
cd emulator && git add -A && git commit -m "feat: VIP-gated backpack slots 11-12"
```

---

### Task 6: Emulator — token redemption

**Files:**
- Modify: `emulator/Communication/Packets/Incoming/Users/RpUseItemEvent.cs`

**Interfaces:**
- Consumes: `IDiamondsStoreManager.TryGetItem` (Task 4), `Habbo.VipExpire`/`SaveKey` (Task 2), `IPermissionManager.GetPermissionsForPlayer/GetCommandsForPlayer`, `ISubscriptionManager.TryGetSubscriptionData(1, out var subData)`, `IBadgeManager.GiveBadge`, `UserRightsComposer`/`ScrSendUserInfoComposer` (Task 3).
- Produces: redeeming `vip_token_31` / `vip_token_14` extends VIP and refreshes the client instantly.

- [ ] **Step 1: Inject dependencies and make Parse async**

Add ctor injection to `RpUseItemEvent` (it currently has none):

```csharp
private readonly IDiamondsStoreManager _storeManager;
private readonly IPermissionManager _permissionManager;
private readonly ISubscriptionManager _subscriptionManager;
private readonly IBadgeManager _badgeManager;

public RpUseItemEvent(IDiamondsStoreManager storeManager, IPermissionManager permissionManager,
    ISubscriptionManager subscriptionManager, IBadgeManager badgeManager)
{
    _storeManager = storeManager;
    _permissionManager = permissionManager;
    _subscriptionManager = subscriptionManager;
    _badgeManager = badgeManager;
}
```

Change the signature to `public async Task Parse(GameClient session, IIncomingPacket packet)`; every `return Task.CompletedTask;` becomes `return;` and the trailing one is removed.

- [ ] **Step 2: Add the token cases to the switch**

After the `case "smoothie":` block (preserving its peek-before-consume discipline — the item was already peeked into `item` before the switch):

```csharp
case "vip_token_31":
case "vip_token_14":
{
    // pixelrp: VIP token. Stacks: extending from whichever is later of
    // now / current expiry. Permissions rebuild BEFORE the badge grant
    // (GiveBadge checks required rights against the live component).
    if (!_storeManager.TryGetItem(item, out var storeItem) || storeItem.VipDays <= 0)
        return;
    habbo.ConsumeRpItem(slot);
    var now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
    habbo.VipExpire = Math.Max(now, habbo.VipExpire) + storeItem.VipDays * 86400L;
    habbo.SaveKey("vip_expire", habbo.VipExpire.ToString());
    habbo.Permissions = new(_permissionManager.GetPermissionsForPlayer(habbo), _permissionManager.GetCommandsForPlayer(habbo));
    if (_subscriptionManager.TryGetSubscriptionData(1, out var subData) && !string.IsNullOrEmpty(subData.Badge)
        && !habbo.Inventory.Badges.HasBadge(subData.Badge))
        await _badgeManager.GiveBadge(habbo, subData.Badge);
    session.Send(new UserRightsComposer(2, habbo.Rank, habbo.IsAmbassador));
    session.Send(new ScrSendUserInfoComposer(habbo, 2));
    var vipRoomUser = habbo.CurrentRoom?.GetRoomUserManager()?.GetRoomUserByHabbo(habbo.Id);
    vipRoomUser?.OnChat(5, "*redeems a VIP token - VIP membership active!*", true);
    if (vipRoomUser == null)
        session.SendWhisper($"VIP activated - {storeItem.VipDays} days added.");
    break;
}
```

Add usings for `Plus.HabboHotel.DiamondsStore`, `Plus.HabboHotel.Permissions`, `Plus.HabboHotel.Subscriptions`, `Plus.HabboHotel.Badges`, `Plus.Communication.Packets.Outgoing.Handshake`. The method's existing tail (`session.Send(new RpInventoryComposer(habbo.LoadRpInventory()))`) already refreshes the backpack.

- [ ] **Step 3: Build, commit**

Run: `cd emulator && dotnet build "Plus Emulator.sln"` — expect success.

```bash
cd emulator && git add -A && git commit -m "feat: VIP token redemption from the backpack"
```

---

### Task 7: Emulator — live expiry demotion

**Files:**
- Modify: `emulator/HabboHotel/IGame.cs`, `emulator/HabboHotel/Game.cs`
- Modify: `emulator/HabboHotel/Users/Process/ProcessComponent.cs`

**Interfaces:**
- Consumes: `Habbo.IsVip`, `UserRightsComposer`, `ScrSendUserInfoComposer`, `BadgesComposer(int userId, ... badges)`, managers via `PlusEnvironment.GetGame()`.
- Produces: `IGame.PermissionManager` and `IGame.BadgeManager` properties (obsolete-attributed, like the existing `SubscriptionManager`); online players demote within 60s of expiry.

- [ ] **Step 1: Expose the managers on IGame/Game**

`IGame.cs`, next to the `SubscriptionManager` line (copy its exact attribute style):

```csharp
[Obsolete("Use dependency injection instead.")] IPermissionManager PermissionManager { get; }
[Obsolete("Use dependency injection instead.")] IBadgeManager BadgeManager { get; }
```

`Game.cs` already has `_permissionManager` and `_badgeManager` fields — add, next to `public ISubscriptionManager SubscriptionManager => _subscriptionManager;` (L173):

```csharp
public IPermissionManager PermissionManager => _permissionManager;
public IBadgeManager BadgeManager => _badgeManager;
```

(Confirm the static accessor name with `grep -rn "PlusEnvironment.GetGame()" emulator --include='*.cs' | head -3` — if the codebase uses a different accessor, e.g. `PlusEnvironment.Game`, use that in Step 2.)

- [ ] **Step 2: Demotion check in the per-user cycle**

`ProcessComponent.cs`: add a field `private bool _vipWasActive;`, set `_vipWasActive = player.IsVip;` in `Init` (after `_player` is assigned). Inside `Run`, immediately before the `// END CODE` marker (L111):

```csharp
// pixelrp: VIP expiry crossed while online - demote live. Soft lapse:
// the figure and items in slots 11-12 are untouched.
if (_vipWasActive && !_player.IsVip)
{
    var game = PlusEnvironment.GetGame();
    _player.Permissions = new(game.PermissionManager.GetPermissionsForPlayer(_player), game.PermissionManager.GetCommandsForPlayer(_player));
    if (game.SubscriptionManager.TryGetSubscriptionData(1, out var subData) && !string.IsNullOrEmpty(subData.Badge)
        && _player.Inventory.Badges.HasBadge(subData.Badge))
    {
        game.BadgeManager.RemoveBadge(_player, subData.Badge).GetAwaiter().GetResult();
        _player.Client?.Send(new BadgesComposer(_player.Id, _player.Inventory.Badges.Badges));
    }
    _player.Client?.Send(new UserRightsComposer(0, _player.Rank, _player.IsAmbassador));
    _player.Client?.Send(new ScrSendUserInfoComposer(_player));
    _player.Client?.SendWhisper("Your VIP has expired - visit the Diamonds Store to renew.");
}
_vipWasActive = _player.IsVip;
```

Add usings (`Plus.Communication.Packets.Outgoing.Handshake`, `Plus.Communication.Packets.Outgoing.Users`, `Plus.Communication.Packets.Outgoing.Inventory.Badges`). Mirror `BadgesComposer`'s ctor from its use in `BadgeManager.GiveBadge` (`new BadgesComposer(habbo.Id, habbo.Inventory.Badges.Badges)`). Note `Run` swallows all exceptions — keep this block self-contained. Offline expiry needs nothing: the next login computes fresh state.

- [ ] **Step 3: Build, commit**

Run: `cd emulator && dotnet build "Plus Emulator.sln"` — expect success.

```bash
cd emulator && git add -A && git commit -m "feat: live VIP expiry demotion in the user process cycle"
```

---

### Task 8: Emulator — daily diamond stipend

**Files:**
- Modify: `emulator/Communication/Packets/Incoming/Handshake/SSOTicketEvent.cs` (after `await _rewardManager.CheckRewards(session);`, ~L151)

**Interfaces:**
- Consumes: `Habbo.IsVip`, `Habbo.VipLastStipend`, `Habbo.Diamonds`, `_settingsManager` (already injected), `HabboActivityPointNotificationComposer`.
- Produces: first login of each calendar day while VIP grants `vip.stipend.daily` diamonds.

- [ ] **Step 1: Add the stipend block**

Immediately after the `CheckRewards` line, following the file's established pattern of wrapping DB-touching login extras in try/catch:

```csharp
// pixelrp: daily VIP stipend - once per calendar day while VIP is active.
try
{
    var habbo = session.GetHabbo();
    if (habbo.IsVip && (!habbo.VipLastStipend.HasValue || habbo.VipLastStipend.Value.Date != DateTime.Today))
    {
        var stipend = Convert.ToInt32(_settingsManager.TryGetValue("vip.stipend.daily"));
        if (stipend > 0)
        {
            habbo.Diamonds += stipend;
            habbo.VipLastStipend = DateTime.Today;
            using (var dbClient = PlusEnvironment.DatabaseManager.GetQueryReactor())
            {
                dbClient.SetQuery("UPDATE `users` SET `vip_points` = @diamonds, `vip_last_stipend` = CURDATE() WHERE `id` = @id LIMIT 1");
                dbClient.AddParameter("diamonds", habbo.Diamonds);
                dbClient.AddParameter("id", habbo.Id);
                dbClient.RunQuery();
            }
            session.Send(new HabboActivityPointNotificationComposer(habbo.Diamonds, stipend, 5));
            session.SendWhisper($"VIP stipend: {stipend} diamonds added to your wallet.");
        }
    }
}
catch (Exception e)
{
    ExceptionLogger.LogException(e);
}
```

(`TryGetValue` returns the string `"0"` for missing keys, so `Convert.ToInt32` is safe; match the query-reactor idiom to the file's existing usage.)

- [ ] **Step 2: Build, commit**

Run: `cd emulator && dotnet build "Plus Emulator.sln"` — expect success.

```bash
cd emulator && git add -A && git commit -m "feat: daily VIP diamond stipend on login"
```

---

### Task 9: Emulator — perk gates (camera, bubbles, icons, effects)

**Files:**
- Create: `emulator/Communication/Attributes/VipOnlyAttribute.cs`
- Modify: `emulator/Communication/Packets/PacketManager.cs`
- Modify: `emulator/Communication/Packets/Incoming/Camera/InitCameraEvent.cs`, `RenderRoomEvent.cs`, `RenderRoomThumbnailEvent.cs`, `PublishPhotoEvent.cs`, `PurchasePhotoEvent.cs`, `PhotoCompetitionEvent.cs`, `RpSaveScreenshotEvent.cs`
- Modify: `emulator/Communication/Packets/Incoming/Preferences/SetChatStylePreferenceEvent.cs`
- Modify: `emulator/Communication/Packets/Incoming/Users/RpSaveUiSettingsEvent.cs`
- Modify: `emulator/HabboHotel/Rooms/Chat/Commands/User/Fun/EnableCommand.cs:49`

**Interfaces:**
- Consumes: `Habbo.IsVip`, `Habbo.IsStaff`, `IChatStyleManager.TryGetStyle`.
- Produces: `[VipOnly]` attribute enforced by PacketManager (allowed when `IsStaff || IsVip`).

- [ ] **Step 1: VipOnly attribute + enforcement**

`VipOnlyAttribute.cs` — copy `StaffOnlyAttribute.cs` verbatim with the class renamed:

```csharp
namespace Plus.Communication.Attributes;

// pixelrp: packets a player may only send with active VIP (staff always pass).
public class VipOnlyAttribute : Attribute
{
}
```

`PacketManager.cs`: mirror the `_staffOnlyPackets` machinery exactly — a `private readonly List<Type> _vipOnlyPackets = new();`, populated in the ctor alongside the StaffOnly registration (`if (packet.GetType().GetCustomAttribute<VipOnlyAttribute>() != null) _vipOnlyPackets.Add(packet.GetType());`), and enforced next to the StaffOnly check in the dispatch path (L71-80):

```csharp
if (_vipOnlyPackets.Contains(packet.GetType()) && !(session.GetHabbo().IsStaff || session.GetHabbo().IsVip))
{
    _logger.LogWarning("Non-VIP {username} tried to send VIP-only packet {packet}.", session.GetHabbo().Username, packet.GetType().Name);
    return;
}
```

(Copy the surrounding StaffOnly block's exact shape — variable names, log style, early-return — and adapt.)

- [ ] **Step 2: Gate camera capture packets**

Add `[VipOnly]` (with `using Plus.Communication.Attributes;`) to the seven capture/save/publish classes listed in Files. Deliberately NOT gated (soft lapse — lapsed VIPs keep managing existing photos): `RpPhotoListEvent`, `RpDeletePhotoEvent`, `RpUpdatePhotoEvent`.

- [ ] **Step 3: Close the chat-style preference hole**

`SetChatStylePreferenceEvent.cs` currently persists any bubble id unvalidated, and `CustomBubbleId != 0` overrides the per-message validated style — any client can claim a VIP bubble today. Inject `IChatStyleManager` (ctor, mirroring `ChatEvent`'s) and validate:

```csharp
var chatBubbleId = packet.ReadInt();
if (chatBubbleId != 0 && (!_chatStyleManager.TryGetStyle(chatBubbleId, out var style)
    || style.RequiredRight.Length > 0 && !session.GetHabbo().Permissions.HasRight(style.RequiredRight)))
    return Task.CompletedTask;
session.GetHabbo().CustomBubbleId = chatBubbleId;
session.GetHabbo().SaveChatBubble(chatBubbleId.ToString());
```

VIP-only bubbles are then pure data: `room_chat_styles` rows with `required_right = 'silver_vip'` (which bubbles get flagged is a content decision, applied later via DB — see Task 14 notes).

- [ ] **Step 4: VIP-reserved username icons**

`RpSaveUiSettingsEvent.cs`, after the existing `IconClass()` regex validation of `icon`:

```csharp
// pixelrp: image icons named vip-*.png (stored as "img-vip-...") are
// VIP-exclusive.
if (icon.StartsWith("img-vip-") && !session.GetHabbo().IsVip)
    return Task.CompletedTask;
```

- [ ] **Step 5: VIP effects**

`EnableCommand.cs:49`: change the effect-178 gate from `HasRight("gold_vip") || HasRight("events_staff")` to `HasRight("silver_vip") || HasRight("gold_vip") || HasRight("events_staff")`.

- [ ] **Step 6: Build, commit**

Run: `cd emulator && dotnet build "Plus Emulator.sln"` — expect success.

```bash
cd emulator && git add -A && git commit -m "feat: VIP perk gates (camera, chat styles, username icons, effects)"
```

---

### Task 10: Client — renderer patch (new packets)

**Files:**
- Modify: `client/.yarn/patches/@nitrots-nitro-renderer-npm-1.6.6-c15ae4be91.patch` (via `yarn patch` / `yarn patch-commit`, never by hand)
- Modify: `client/package.json` + `client/yarn.lock` (updated by patch-commit)

**Interfaces:**
- Consumes: wire formats from Task 4 (listing: `int total`, then per item `string itemKey, string name, string description, string icon, int price, int specialPrice (-1 = no sale), int vipDays`; result: `int status, string itemKey`).
- Produces (importable from `@nitrots/nitro-renderer`): `DiamondsStoreEvent` (`getParser().items: DiamondsStoreListing[]` with fields `itemKey, name, description, icon, price, specialPrice, vipDays`), `DiamondsStorePurchaseResultEvent` (`getParser().status: number`, `.itemKey: string`), `GetDiamondsStoreComposer()` (no args), `PurchaseDiamondsStoreItemComposer(itemKey: string)`.

- [ ] **Step 1: Open the patch workdir**

```bash
cd client && yarn patch @nitrots/nitro-renderer
```

Note the printed workdir path. **Verify the workdir contains the existing customizations before editing** (the reseal trap — an unpatched workdir would silently drop every prior Rp packet): `grep -rl "RpInventoryEvent" <workdir>/src | head -1` must match. If it doesn't, stop and re-run `yarn install` first, then `yarn patch` again.

- [ ] **Step 2: Add header ids**

In the workdir, find the header files (`grep -rn "RP_INVENTORY = 3904" <workdir>/src` / `"RP_USE_ITEM = 3905"`). Append to the PixelRP block in `IncomingHeader.ts`:

```ts
    public static DIAMONDS_STORE = 3925;
    public static DIAMONDS_STORE_PURCHASE_RESULT = 3926;
```

and to the PixelRP block in `OutgoingHeader.ts`:

```ts
    public static GET_DIAMONDS_STORE = 3929;
    public static PURCHASE_DIAMONDS_STORE_ITEM = 3930;
```

- [ ] **Step 3: Add the event/parser and composer files**

Locate the folder holding `RpInventoryEvent.ts` and `RpUseItemComposer.ts` — new files go alongside them, copying their import paths and class boilerplate exactly (same `MessageEvent`/`IMessageEvent` extends, same `IMessageParser` shape, same no-op `dispose()` composer pattern).

`DiamondsStoreEvent.ts` — parser + event in one file, mirroring `RpInventoryEvent.ts`:

```ts
export interface DiamondsStoreListing
{
    itemKey: string;
    name: string;
    description: string;
    icon: string;
    price: number;
    specialPrice: number; // -1 = no sale; >= 0 overrides price
    vipDays: number;
}
```

Parser `parse()` body (read order matches the emulator composer exactly):

```ts
if(!wrapper) return false;

this._items = [];

const total = wrapper.readInt();

for(let i = 0; i < total; i++)
{
    const itemKey = wrapper.readString();
    const name = wrapper.readString();
    const description = wrapper.readString();
    const icon = wrapper.readString();
    const price = wrapper.readInt();
    const specialPrice = wrapper.readInt();
    const vipDays = wrapper.readInt();

    this._items.push({ itemKey, name, description, icon, price, specialPrice, vipDays });
}

return true;
```

`DiamondsStorePurchaseResultEvent.ts` — parser reads `this._status = wrapper.readInt(); this._itemKey = wrapper.readString();` with getters `status` / `itemKey`.

`GetDiamondsStoreComposer.ts` — copy `RpUseItemComposer.ts`, ctor `constructor() { this._data = []; }`, header `OutgoingHeader.GET_DIAMONDS_STORE`.

`PurchaseDiamondsStoreItemComposer.ts` — ctor `constructor(itemKey: string) { this._data = [ itemKey ]; }`, header `OutgoingHeader.PURCHASE_DIAMONDS_STORE_ITEM`. (Never pass undefined — EvaWire writes it as 2 junk bytes.)

- [ ] **Step 4: Register and export**

In the workdir's `NitroMessages.ts`: add the two events to the PIXELRP block in `registerEvents()` (`this._events.set(IncomingHeader.DIAMONDS_STORE, DiamondsStoreEvent);` etc.) and the two composers next to the existing Rp composers in `registerComposers()`, with direct-path imports matching the existing Rp import style. Add `export * from './...';` lines for all four files to the same barrel `index.ts` files that export the Rp classes.

- [ ] **Step 5: Reseal and verify the patch**

```bash
yarn patch-commit -s <workdir>
yarn install
```

Then verify no prior hunks were lost: `git diff .yarn/patches/` must show ONLY additions (the four new files + header/registration/barrel additions); every existing `Rp*` hunk must still be present in the patch file. Check content, not just the file list.

- [ ] **Step 6: Verify the client still builds, commit (client submodule)**

Run: `cd client && yarn build` — expect a successful Vite build.

```bash
cd client && git add package.json yarn.lock .yarn/patches && git commit -m "feat: diamonds store packets in renderer patch"
```

---

### Task 11: Client — Store tab UI

**Files:**
- Modify: `client/src/components/diamonds-store/DiamondsStoreView.tsx`
- Modify: `client/src/components/diamonds-store/DiamondsStoreView.scss`

**Interfaces:**
- Consumes: Task 10's four renderer classes; `useMessageEvent` from `../../hooks`; `SendMessageComposer` from `../../api`.
- Produces: a data-driven Store tab with sale rendering and purchase flow.

- [ ] **Step 1: State, events, and request-on-open**

In `DiamondsStoreView.tsx` add imports (`DiamondsStoreEvent, DiamondsStorePurchaseResultEvent, GetDiamondsStoreComposer, PurchaseDiamondsStoreItemComposer, DiamondsStoreListing` from `@nitrots/nitro-renderer`; `useMessageEvent` from `../../hooks`; `SendMessageComposer` from `../../api`) and state:

```tsx
type StoreViewState = 'list' | 'confirm' | 'success' | 'error';

const [ listings, setListings ] = useState<DiamondsStoreListing[]>([]);
const [ storeState, setStoreState ] = useState<StoreViewState>('list');
const [ selectedListing, setSelectedListing ] = useState<DiamondsStoreListing>(null);
const [ storeError, setStoreError ] = useState('');

useMessageEvent<DiamondsStoreEvent>(DiamondsStoreEvent, event =>
{
    setListings(event.getParser().items);
});

useMessageEvent<DiamondsStorePurchaseResultEvent>(DiamondsStorePurchaseResultEvent, event =>
{
    const parser = event.getParser();

    if(parser.status === 0)
    {
        setStoreState('success');
        return;
    }

    setStoreError((parser.status === 1) ? 'Not enough diamonds - top up in the Buy Diamonds tab.' : 'Your backpack is full - free a slot and try again.');
    setStoreState('error');
});

// Request fresh listings whenever the Store tab comes on screen, so sale
// prices are always current.
useEffect(() =>
{
    if(!isVisible || (currentTab !== 'store')) return;

    SendMessageComposer(new GetDiamondsStoreComposer());
}, [ isVisible, currentTab ]);
```

Extend the existing `[ isVisible ]` reset effect to also `setStoreState('list'); setStoreError('');` so reopening never resumes a stale confirm/result screen.

- [ ] **Step 2: Replace the Store tab placeholder with the listing UI**

Replace the `diamonds-store-empty` block (currently the whole store tab) with:

```tsx
{ (currentTab === 'store') && (storeState === 'list') &&
    <div className="diamonds-store-listings">
        { (listings.length === 0) &&
            <div className="diamonds-store-empty">
                Nothing here yet - diamond items are coming soon.
            </div> }
        { listings.map(listing =>
        {
            const onSale = (listing.specialPrice >= 0);

            return (
                <div key={ listing.itemKey } className="diamonds-store-listing" onClick={ () => { setSelectedListing(listing); setStoreState('confirm'); } }>
                    <div className={ `diamonds-store-listing-icon icon-${ listing.icon }` } />
                    <div className="diamonds-store-listing-info">
                        <div className="diamonds-store-listing-name">{ listing.name }</div>
                        <div className="diamonds-store-listing-desc">{ listing.description }</div>
                    </div>
                    <div className="diamonds-store-listing-price">
                        { onSale && <span className="diamonds-store-price-was">{ listing.price }</span> }
                        <span className="diamonds-store-price-now">{ onSale ? listing.specialPrice : listing.price }</span>
                        { onSale && <span className="diamonds-store-sale-tag">SALE</span> }
                    </div>
                </div>);
        }) }
    </div> }
{ (currentTab === 'store') && (storeState === 'confirm') && selectedListing &&
    <div className="diamonds-store-result">
        <div className="diamonds-store-result-message">
            { `Buy ${ selectedListing.name } for ${ (selectedListing.specialPrice >= 0) ? selectedListing.specialPrice : selectedListing.price } diamonds?` }
        </div>
        <Button fullWidth variant="success" onClick={ () => SendMessageComposer(new PurchaseDiamondsStoreItemComposer(selectedListing.itemKey)) }>Buy</Button>
        <Button fullWidth variant="secondary" onClick={ () => setStoreState('list') }>Cancel</Button>
    </div> }
{ (currentTab === 'store') && (storeState === 'success') &&
    <div className="diamonds-store-result">
        <div className="diamonds-store-result-message">Purchased - check your backpack!</div>
        <Button fullWidth variant="success" onClick={ () => setStoreState('list') }>Done</Button>
    </div> }
{ (currentTab === 'store') && (storeState === 'error') &&
    <div className="diamonds-store-result">
        <div className="diamonds-store-result-message diamonds-store-result-error">{ storeError }</div>
        <Button fullWidth variant="secondary" onClick={ () => setStoreState('list') }>Back</Button>
    </div> }
```

- [ ] **Step 3: Styles**

Append inside the `.nitro-diamonds-store` root block in `DiamondsStoreView.scss`, matching the file's conventions (flat `diamonds-store-` names, `is-*` modifiers, SCSS color vars, pixelated icons at native size):

```scss
.diamonds-store-listings {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.diamonds-store-listing {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px;
    border-radius: $border-radius;
    background: rgba(0, 0, 0, .05);
    cursor: pointer;

    &:hover {
        background: rgba(0, 0, 0, .1);
    }
}

.diamonds-store-listing-icon {
    flex-shrink: 0;
    width: 40px;
    height: 40px;
    background-repeat: no-repeat;
    background-position: center;
    background-size: auto;
    image-rendering: pixelated;

    &.icon-vip-token-gold { background-image: url('@/assets/images/rp-items/vip-token-gold.png'); }
    &.icon-vip-token-silver { background-image: url('@/assets/images/rp-items/vip-token-silver.png'); }
}

.diamonds-store-listing-info {
    flex: 1;
    min-width: 0;
}

.diamonds-store-listing-name {
    font-size: 12px;
    font-weight: 700;
}

.diamonds-store-listing-desc {
    font-size: 11px;
    color: rgba(0, 0, 0, .6);
}

.diamonds-store-listing-price {
    display: flex;
    align-items: center;
    gap: 5px;
    font-weight: 700;
}

.diamonds-store-price-was {
    text-decoration: line-through;
    color: rgba(0, 0, 0, .45);
    font-weight: 400;
    font-size: 11px;
}

.diamonds-store-sale-tag {
    padding: 1px 4px;
    border-radius: $border-radius;
    background: $success;
    color: $white;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
}
```

- [ ] **Step 4: Lint + build, commit (client submodule)**

Run: `cd client && yarn eslint && yarn build` — expect both clean.

```bash
cd client && git add src/components/diamonds-store && git commit -m "feat: diamonds store Store tab with VIP tokens and sale pricing"
```

---

### Task 12: Client — backpack tokens and VIP slots

**Files:**
- Modify: `client/src/components/rp-inventory/RpInventoryView.tsx`
- Modify: `client/src/components/rp-inventory/RpInventoryView.scss`
- Create: `client/src/assets/images/rp-items/vip-token-gold.png`, `client/src/assets/images/rp-items/vip-token-silver.png` (supplied by Ry)

**Interfaces:**
- Consumes: `HasHabboVip` from `../../api` (reads the real club level once Task 3 + the ui-config flip land); item keys `vip_token_31` / `vip_token_14` from Task 4's seeds.
- Produces: tokens render and are click-redeemable; slots 11-12 unlock with VIP; a lapsed VIP's items in 11-12 stay clickable.

- [ ] **Step 1: Token PNGs**

**GATE:** the two icons (gold = 31 days, silver = 14 days) must exist at the paths above. If missing, STOP and ask Ry for the files — do not substitute placeholders.

- [ ] **Step 2: Register the items**

In `RpInventoryView.tsx`, extend `ITEMS`:

```tsx
const ITEMS: Record<string, { name: string, cls: string }> = {
    smoothie: { name: 'Passive Smoothie', cls: 'rp-item-smoothie' },
    vip_token_31: { name: 'VIP Token (31 days)', cls: 'rp-item-vip-token-gold' },
    vip_token_14: { name: 'VIP Token (14 days)', cls: 'rp-item-vip-token-silver' },
};
```

`RpInventoryView.scss`, next to the smoothie line:

```scss
&.rp-item-vip-token-gold { background-image: url('@/assets/images/rp-items/vip-token-gold.png'); }
&.rp-item-vip-token-silver { background-image: url('@/assets/images/rp-items/vip-token-silver.png'); }
```

- [ ] **Step 3: VIP-aware slot locking**

Import `HasHabboVip` from `../../api`. Inside the component body (before the return):

```tsx
// VIP unlocks carry slots 11-12. Soft lapse: a slot past the unlock that
// still holds an item stays usable (consume/inspect) - it just won't accept
// anything new (the server enforces placement).
const unlockedSlots = (HasHabboVip() ? CARRY_SLOTS.length : UNLOCKED_SLOTS);
```

Change the lock branch from `if(slot > UNLOCKED_SLOTS)` to `if((slot > unlockedSlots) && !items.get(slot))`. (Re-render freshness: every redemption triggers an `RpInventoryEvent`, which re-renders after the server's club-level update has landed.)

- [ ] **Step 4: Lint + build, commit (client submodule)**

Run: `cd client && yarn eslint && yarn build` — expect both clean.

```bash
cd client && git add src/components/rp-inventory src/assets/images/rp-items && git commit -m "feat: VIP tokens in backpack, VIP-gated slots 11-12"
```

---

### Task 13: Client — toolbar camera and HC Center retarget

**Files:**
- Modify: `client/src/components/toolbar/ToolbarView.tsx:85-86`
- Modify: `client/src/components/hc-center/HcCenterView.tsx:137-141`

**Interfaces:**
- Consumes: `HasHabboVip` from `../../api`; the diamonds store's `diamonds-store/show` link event.
- Produces: camera button for staff or VIP; HC Center's extend/buy opens the Diamonds Store.

- [ ] **Step 1: Camera button**

`ToolbarView.tsx`: import `HasHabboVip` from `../../api` and change the camera block to:

```tsx
{ (isInRoom && (isMod || HasHabboVip())) &&
    <Base pointer className="navigation-item icon icon-camera" onClick={ event => CreateLinkEvent('camera/toggle') } /> }
```

- [ ] **Step 2: HC Center extend/buy**

`HcCenterView.tsx:138`: the button currently fires `CreateLinkEvent('catalog/open/' + GetConfiguration('catalog.links')['hc.buy_hc'])` — the catalog is unreachable for players. Replace the onClick with `event => CreateLinkEvent('diamonds-store/show')` (keep the `hccenter.btn.extend` / `hccenter.btn.buy` label logic). Remove the now-unused `GetConfiguration`/catalog-links usage if nothing else in the file needs it.

- [ ] **Step 3: Lint + build, commit (client submodule)**

Run: `cd client && yarn eslint && yarn build` — expect both clean.

```bash
cd client && git add src/components/toolbar src/components/hc-center && git commit -m "feat: VIP camera access and HC Center store retarget"
```

---

### Task 14: Superproject — config flip, changelog, bumps, manual test

**Files:**
- Modify: `nitro/ui-config.json`, `nitro/ui-config.prod.json`, `client/public/ui-config.json`
- Modify: `CHANGELOG.md`
- Modify: submodule pointers `emulator`, `client`

**Interfaces:**
- Consumes: everything above.
- Produces: the deployable feature on `feat/vip`.

- [ ] **Step 1: Flip HC on in the shipped ui-configs**

In `nitro/ui-config.json` AND `nitro/ui-config.prod.json` (these overwrite the built client's config at deploy; `client/public/ui-config.json` is dev-only and already `false`): set `"hc.disabled": false`. In all three files, in the `hc.center` block set `"payday.info": false` and `"gift.info": false` (payday/gifts are out of scope; the emulator's gift data is a hardcoded fake). This flip is the moment "free HC for everyone" ends — non-VIPs keep current outfits (soft lapse) but lose HC clothing/bubble/dance access until they buy VIP.

- [ ] **Step 2: Changelog**

Add a player-facing entry at the top of `CHANGELOG.md`, following the existing entry format, covering: VIP membership (tokens in the Diamonds Store's Store tab, redeemed from the Backpack; 31d/500 and 14d/250), perks (HC clothing/dances/bubbles, camera, backpack slots 11-12, 5 diamonds/day stipend, VIP badge), and the note that HC-style perks now require VIP. Plain hyphens only.

- [ ] **Step 3: Bump submodules and commit**

```bash
git add emulator client nitro/ui-config.json nitro/ui-config.prod.json client/public/ui-config.json CHANGELOG.md
git commit -m "feat: VIP system (bump emulator, client)"
```

Do NOT push or merge to `beta` — that is Ry's call (beta auto-deploys).

- [ ] **Step 4: Hand off for manual in-game testing (Ry, ClaudeTest on local dev)**

Checklist to hand over:

1. Store tab lists both tokens with prices; setting a `special_price` in DB shows strikethrough + SALE after reopening the tab.
2. Buying with insufficient diamonds refuses without charging; with a full backpack refuses without charging; success delivers the token and updates the purse diamond count.
3. Redeeming a token: club level flips (HC clothing/palettes appear in the avatar editor, HC bubbles selectable, `:dance` 1-4 work), SVIP badge granted, purse HC chip shows the day count, HC Center opens from the chip and its button opens the Diamonds Store.
4. Redeeming a second token stacks (day count extends, doesn't reset).
5. Backpack slots 11-12 unlock; camera button appears and the camera works.
6. Stipend: next-calendar-day login grants 5 diamonds once (whisper + purse update).
7. Expiry (set `vip_expire` to now+120 in DB, relog): within ~60s of expiry the whisper arrives, badge disappears, club level drops (bubbles/dances lock), current outfit with HC parts SURVIVES; changing outfit strips HC parts; an item left in slot 11 is still clickable but the slot accepts nothing new.
8. Non-VIP regression: smoothie still buyable-by-staff-spawn/consumable, chat fine, no camera button, no console/packet errors in the emulator log.

## Deferred / follow-ups (not in this plan)

- VIP-flagging specific clothing sets, chat bubbles (`room_chat_styles.required_right = 'silver_vip'` rows), and `vip-*.png` username icons — content/data decisions, applied via DB + asset drops (remember: DB rows and gamedata don't ship via deploy — apply to beta/prod manually, changelog each).
- Filament admin resource for `diamonds_store_items`.
- Client-side picker lock/labels for VIP username icons (server gate ships now; no `img-vip-*` icons exist yet).
