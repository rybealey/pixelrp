# In-Game Discord Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Settings → Social → Discord subpage load without flashing the unlinked state, and move Discord disconnect fully in-game with an instant status push after connect.

**Architecture:** The emulator gains a widened status packet (3952 carries `linkedAt`) and a new unlink packet (3956) that clears the link in-game and hands Discord-side role cleanup to the CMS via the existing `discord_sync_queue`. The CMS pushes status back into an open client over the existing RCON bridge after OAuth completes, so the "check again" link disappears. The CMS `/discord` status page is retired; `/discord/callback` becomes a self-contained result page.

**Tech Stack:** C# 7 / .NET 7 (emulator, Dapper), Laravel 11 + Pest 4 (CMS), React + TypeScript + SCSS (client), yarn patch (nitro-renderer).

**Spec:** `docs/superpowers/specs/2026-08-29-discord-settings-in-game-design.md`

## Global Constraints

- **Player-facing copy uses plain hyphens, never em-dashes.** Habbo fonts render `—` as a music note. Applies to every string that reaches the game client.
- **The emulator never calls the Discord API.** It only reads/writes `users.discord_id` and enqueues into `discord_sync_queue`; the CMS makes every Discord REST call.
- **Discord identity details never reach the game client.** The wire carries a boolean and a timestamp only — never a handle, avatar, or Discord id.
- **Wire ids must be checked against BOTH header files' existing VALUES before use.** New incoming packets take a `439xx` internal constant with a `//39xx` wire comment. The wire id in `revisions/1.6.6.json` and the renderer must match; the internal `.cs` constant value may differ.
- **`emulator/`, `cms/`, `client/` and `imager/` are ALL git submodules** of the `plus` superproject (`rybealey/PlusEMU`, `rybealey/atomcms`, `rybealey/nitro-react` on branch `pixelrp`, `rybealey/nitro-imager`). Every task's commit lands INSIDE the relevant submodule: `cd emulator && git add <paths relative to emulator/> && git commit`. The commit commands in the task steps show superproject-relative paths for readability — strip the leading component and run them from inside the submodule. Each submodule must be pushed, and its pointer bumped in `plus`, in Task 7. A green deploy with an unbumped pointer ships nothing.
- **Before any renderer patch reseal: run `yarn install` first**, and after resealing diff patch *content* against the prior layer, not just the file list.
- **Deploy via `gh workflow run deploy.yml`**, never a manual SSH deploy.
- There is **no test runner for the client or the emulator** (`emulator/Tests` is empty, `client/package.json` has no test script). CMS tests are Pest, run through Docker from the `plus/` root (`docker compose run --rm --no-deps -T cms ./vendor/bin/pest`) - the `db` host only resolves inside the compose network, so a bare `./vendor/bin/pest` cannot reach the database. For client and emulator work the gate is a clean build plus the manual in-game test in Task 7.

---

### Task 1: Emulator — schema, widened status packet, unlink event

**Files:**
- Create: `emulator/Resources/SQLs/Updates/46_DiscordUnlink.sql`
- Create: `emulator/Communication/Packets/Incoming/Users/RpDiscordUnlinkEvent.cs`
- Modify: `emulator/HabboHotel/Discord/DiscordSyncUtility.cs`
- Modify: `emulator/Communication/Packets/Outgoing/Users/RpDiscordStatusComposer.cs`
- Modify: `emulator/Communication/Packets/Incoming/Users/RpGetDiscordStatusEvent.cs`
- Modify: `emulator/Communication/Packets/Incoming/ClientPacketHeader.cs:403`
- Modify: `emulator/Resources/Revisions/1.6.6.json:283`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `DiscordSyncUtility.GetLinkState(int userId) -> DiscordLinkState` (public class with `string? DiscordId`, `int DiscordLinkedAt`); `DiscordSyncUtility.Unlink(int userId) -> DiscordLinkState?`; `RpDiscordStatusComposer(bool linked, int linkedAt = 0)`. Task 2 uses `GetLinkState` and the widened composer.

Wire id `3956` was verified free on the incoming side: `3954` is burned (stock collision), `3955` is stock `ModerationTradeLockEvent`, `3960` is `RefreshCampaignEvent`. Internal constant is `43956`.

- [ ] **Step 1: Write the migration**

Create `emulator/Resources/SQLs/Updates/46_DiscordUnlink.sql`:

```sql
-- In-game Discord disconnect (Settings > Social > Verification > Discord).
-- An unlink row must remember WHICH Discord account to strip, because the
-- emulator clears `users.discord_id` the moment the player disconnects and
-- `discord:sweep` only ever iterates users that are still linked - this
-- queue row is the only cleanup path there is.

ALTER TABLE `discord_sync_queue`
  ADD COLUMN `discord_id` varchar(32) NULL DEFAULT NULL;
```

- [ ] **Step 2: Register the packet header**

In `emulator/Communication/Packets/Incoming/ClientPacketHeader.cs`, directly below line 403 (`RpGetDiscordStatusEvent = 43953; //3953`):

```csharp
    public const uint RpDiscordUnlinkEvent = 43956; //3956
```

- [ ] **Step 3: Register the wire id in the revisions map**

In `emulator/Resources/Revisions/1.6.6.json`, directly below line 283 (`"RpGetDiscordStatusEvent": 3953,`):

```json
    "RpDiscordUnlinkEvent": 3956,
```

The revisions map keys by constant NAME and carries the WIRE id — this is the authority, not the header constant's value.

- [ ] **Step 4: Extend DiscordSyncUtility**

In `emulator/HabboHotel/Discord/DiscordSyncUtility.cs`, replace the `IsLinked` method with the following (keep the existing `Enqueue` method and the file's using/namespace lines untouched):

```csharp
    /// <summary>
    /// Link state for the Settings page. DiscordId is null when unlinked.
    /// </summary>
    public sealed class DiscordLinkState
    {
        public string? DiscordId { get; set; }
        public int DiscordLinkedAt { get; set; }
    }

    public static DiscordLinkState GetLinkState(int userId)
    {
        using var connection = PlusEnvironment.DatabaseManager.Connection();
        return connection.QueryFirstOrDefault<DiscordLinkState>(
            "SELECT `discord_id` AS `DiscordId`, `discord_linked_at` AS `DiscordLinkedAt` " +
            "FROM `users` WHERE `id` = @userId LIMIT 1",
            new { userId }) ?? new DiscordLinkState();
    }

    /// <summary>
    /// Clears the link in-game and queues the Discord-side cleanup for the
    /// CMS scheduler. Both writes share one transaction: `discord:sweep`
    /// only reconciles users that are still linked, so a lost queue row
    /// would strand the player's roles forever.
    /// Returns the resulting link state so the caller needs no second
    /// query: an unguarded follow-up read would throw out of the packet
    /// handler, and PacketManager disconnects the session on a faulted
    /// Parse - kicking a player out of the game for clicking Disconnect.
    /// Null means the state could not be determined at all; the caller
    /// sends nothing and the client's own refresh recovers.
    /// </summary>
    public static DiscordLinkState? Unlink(int userId)
    {
        try
        {
            using var connection = PlusEnvironment.DatabaseManager.Connection();
            connection.Open();

            using var transaction = connection.BeginTransaction();

            var discordId = connection.ExecuteScalar<string>(
                "SELECT `discord_id` FROM `users` WHERE `id` = @userId LIMIT 1",
                new { userId }, transaction);

            if (string.IsNullOrEmpty(discordId))
            {
                transaction.Rollback();
                return false;
            }

            connection.Execute(
                "UPDATE `users` SET `discord_id` = NULL, `discord_linked_at` = 0 WHERE `id` = @userId",
                new { userId }, transaction);

            connection.Execute(
                "INSERT INTO `discord_sync_queue` (`user_id`, `discord_id`, `reason`, `created_at`) " +
                "VALUES (@userId, @discordId, 'unlink', UNIX_TIMESTAMP())",
                new { userId, discordId }, transaction);

            transaction.Commit();
            return true;
        }
        catch
        {
            // Never let a disconnect attempt take the session down; the
            // player sees the unchanged state and can retry.
            return false;
        }
    }
```

If `connection.Open()` conflicts with how `PlusEnvironment.DatabaseManager.Connection()` hands back its connection (it may already be open), drop the explicit `Open()` call — `BeginTransaction()` requires an open connection and nothing else.

- [ ] **Step 5: Widen the status composer**

Replace the body of `emulator/Communication/Packets/Outgoing/Users/RpDiscordStatusComposer.cs` (keep the `using` and `namespace` lines):

```csharp
/// <summary>
/// pixelrp: whether the session user's Discord account is linked, plus the
/// unix timestamp it was linked at (0 when unlinked). Deliberately carries
/// no Discord identity - those details are never shared in-game.
/// </summary>
public class RpDiscordStatusComposer : IServerPacket
{
    private readonly bool _linked;
    private readonly int _linkedAt;

    public uint MessageId => ServerPacketHeader.RpDiscordStatusComposer;

    public RpDiscordStatusComposer(bool linked, int linkedAt = 0)
    {
        _linked = linked;
        _linkedAt = linkedAt;
    }

    public void Compose(IOutgoingPacket packet)
    {
        packet.WriteInteger(_linked ? 1 : 0);
        packet.WriteInteger(_linked ? _linkedAt : 0);
    }
}
```

- [ ] **Step 6: Feed linkedAt into the status reply**

In `emulator/Communication/Packets/Incoming/Users/RpGetDiscordStatusEvent.cs`, replace the `session.Send(...)` line:

```csharp
        var state = DiscordSyncUtility.GetLinkState(session.GetHabbo().Id);
        session.Send(new RpDiscordStatusComposer(!string.IsNullOrEmpty(state.DiscordId), state.DiscordLinkedAt));
```

- [ ] **Step 7: Add the unlink event**

Create `emulator/Communication/Packets/Incoming/Users/RpDiscordUnlinkEvent.cs`:

```csharp
using Plus.HabboHotel.Discord;
using Plus.HabboHotel.GameClients;
using Plus.Communication.Packets.Outgoing.Users;

namespace Plus.Communication.Packets.Incoming.Users;

/// <summary>
/// pixelrp: the player disconnected their Discord account from the Settings
/// window. The link is cleared here and now; the CMS scheduler strips the
/// Discord roles when it drains the queue.
/// </summary>
internal class RpDiscordUnlinkEvent : IPacketEvent
{
    public Task Parse(GameClient session, IIncomingPacket packet)
    {
        if (session.GetHabbo() == null)
            return Task.CompletedTask;

        // Unlink reports the resulting state itself. A second, unguarded
        // read here would throw out of Parse on a DB blip, and PacketManager
        // disconnects the session on a faulted Parse - a player must never
        // be kicked from the game for clicking Disconnect.
        var state = DiscordSyncUtility.Unlink(session.GetHabbo().Id);

        // Null means the state is genuinely unknown; say nothing rather than
        // report a link status that might be wrong.
        if (state != null)
            session.Send(new RpDiscordStatusComposer(!string.IsNullOrEmpty(state.DiscordId), state.DiscordLinkedAt));

        return Task.CompletedTask;
    }
}
```

Packet events are auto-registered by Scrutor assembly scanning — the class name must match the `ClientPacketHeader` constant name added in Step 2, which it does. No manual registration.

- [ ] **Step 8: Build the emulator**

Run: `cd emulator && dotnet build "Plus Emulator.sln"`
Expected: build succeeds, 0 errors. A duplicate-key `ArgumentException` at DI resolution would mean the internal id `43956` collides — it was verified free, but if it appears, pick another `439xx`.

- [ ] **Step 9: Commit**

```bash
git add emulator/Resources/SQLs/Updates/46_DiscordUnlink.sql \
        emulator/Communication/Packets/Incoming/Users/RpDiscordUnlinkEvent.cs \
        emulator/HabboHotel/Discord/DiscordSyncUtility.cs \
        emulator/Communication/Packets/Outgoing/Users/RpDiscordStatusComposer.cs \
        emulator/Communication/Packets/Incoming/Users/RpGetDiscordStatusEvent.cs \
        emulator/Communication/Packets/Incoming/ClientPacketHeader.cs \
        emulator/Resources/Revisions/1.6.6.json
git commit -m "feat(discord): in-game unlink packet 3956 + linkedAt on status 3952"
```

---

### Task 2: Emulator — RCON status push command

**Files:**
- Create: `emulator/Communication/RCON/Commands/User/ReloadUserDiscordCommand.cs`
- Modify: `emulator/Communication/RCON/Commands/CommandManager.cs` (the `ParseJson` switch)

**Interfaces:**
- Consumes: `DiscordSyncUtility.GetLinkState`, `RpDiscordStatusComposer(bool, int)` from Task 1.
- Produces: RCON command key `reload_user_discord`, reachable from the CMS as JSON key `syncdiscord` with `{"user_id": <int>}`. Task 4 calls it.

- [ ] **Step 1: Add the command**

Create `emulator/Communication/RCON/Commands/User/ReloadUserDiscordCommand.cs`:

```csharp
using Plus.Communication.Packets.Outgoing.Users;
using Plus.HabboHotel.Discord;
using Plus.HabboHotel.GameClients;

namespace Plus.Communication.RCON.Commands.User;

/// <summary>
/// Pushes the user's current Discord link status into their open client, so
/// the Settings window updates the instant the CMS finishes OAuth instead of
/// waiting for the player to reopen the page.
/// </summary>
internal class ReloadUserDiscordCommand : IRconCommand
{
    private readonly IGameClientManager _gameClientManager;

    public string Description => "This command pushes the user's Discord link status to their client.";

    public string Key => "reload_user_discord";
    public string Parameters => "%userId%";

    public ReloadUserDiscordCommand(IGameClientManager gameClientManager)
    {
        _gameClientManager = gameClientManager;
    }

    public Task<bool> TryExecute(string[] parameters)
    {
        if (!int.TryParse(parameters[0], out var userId))
            return Task.FromResult(false);

        var client = _gameClientManager.GetClientByUserId(userId);

        // Offline is a normal outcome, not a failure: the client re-requests
        // status when the Discord page next opens.
        if (client == null || client.GetHabbo() == null)
            return Task.FromResult(true);

        var state = DiscordSyncUtility.GetLinkState(userId);
        client.Send(new RpDiscordStatusComposer(!string.IsNullOrEmpty(state.DiscordId), state.DiscordLinkedAt));

        return Task.FromResult(true);
    }
}
```

Commands are auto-registered by Scrutor via `IRconCommand`; `CommandManager` keys them by the `Key` property. No manual registration.

- [ ] **Step 2: Map the CMS-dialect key**

In `emulator/Communication/RCON/Commands/CommandManager.cs`, inside the `ParseJson` switch on `cmsKey`, add a case alongside the existing ones (the `"disconnect"` case is a good neighbour to copy the shape from):

```csharp
                case "syncdiscord":
                {
                    if (!hasData || !TryGetPositionalString(data, "user_id", out var userId))
                    {
                        response = BuildResponse(1, "Invalid parameters for 'syncdiscord'");
                        return false;
                    }

                    pluCommandKey = "reload_user_discord";
                    parameters = new[] { userId };
                    break;
                }
```

- [ ] **Step 3: Build the emulator**

Run: `cd emulator && dotnet build "Plus Emulator.sln"`
Expected: build succeeds, 0 errors.

- [ ] **Step 4: Commit**

```bash
git add emulator/Communication/RCON/Commands/User/ReloadUserDiscordCommand.cs \
        emulator/Communication/RCON/Commands/CommandManager.cs
git commit -m "feat(discord): RCON reload_user_discord to push link status live"
```

---

### Task 3: CMS — unlink by id and unlink queue rows

**Files:**
- Create: `cms/database/migrations/2026_08_30_000000_plus_discord_link_columns.php`
- Modify: `cms/app/Services/Discord/DiscordSyncService.php:82-114`
- Modify: `cms/app/Console/Commands/DiscordProcessQueue.php`
- Test: `cms/tests/Feature/Discord/DiscordProcessQueueTest.php`

**Interfaces:**
- Consumes: the `discord_sync_queue.discord_id` column from Task 1.
- Produces: `DiscordSyncService::unlinkById(string $discordId): void`. Task 4 does not use it; only the queue command does.

`unlinkUser(User $user)` is called from exactly one place — `DiscordController::unlink()`, which Task 4 deletes — so it is replaced outright rather than kept alongside.

- [ ] **Step 0: Mirror the emulator's Discord schema for the Laravel-managed test database**

The CMS test suite runs `migrate:fresh` (`RefreshDatabase` in `cms/tests/TestCase.php`), so its schema comes from Laravel migrations only. The Discord columns are owned by the emulator's SQL updates (`45_DiscordLink.sql`, `46_DiscordUnlink.sql`), which never run against the `testing` database — so without this step every test in this task fails on a missing table, not on the behaviour under test.

The established house pattern for exactly this is `cms/database/migrations/2014_10_12_300000_plus_users_compatibility_columns.php`: a migration guarded on the emulator driver that adds emulator-owned columns only when they are absent. Follow it exactly.

Create `cms/database/migrations/2026_08_30_000000_plus_discord_link_columns.php`:

```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Mirrors the emulator-owned Discord schema (PlusEMU's 45_DiscordLink.sql and
 * 46_DiscordUnlink.sql) into the Laravel-managed schema, so the test database
 * - which is built by migrate:fresh and never sees the emulator's SQL updates
 * - has the columns the Discord services read and write.
 *
 * Every add is guarded, so this is a no-op on beta and prod where the
 * emulator's own SQL updates already applied the same schema.
 */
return new class extends Migration
{
    public function up(): void
    {
        if (config('emulator.driver') !== 'plus') {
            return;
        }

        Schema::table('users', function (Blueprint $table) {
            if (! Schema::hasColumn('users', 'discord_id')) {
                $table->string('discord_id', 32)->nullable()->default(null)->unique('idx_users_discord_id');
            }

            if (! Schema::hasColumn('users', 'discord_linked_at')) {
                $table->integer('discord_linked_at')->default(0);
            }
        });

        if (! Schema::hasTable('discord_sync_queue')) {
            Schema::create('discord_sync_queue', function (Blueprint $table) {
                $table->increments('id');
                $table->integer('user_id');
                $table->string('discord_id', 32)->nullable()->default(null);
                $table->string('reason', 24)->default('');
                $table->integer('created_at')->default(0);

                $table->index('user_id', 'idx_dsq_user');
            });

            return;
        }

        // The table predates 46_DiscordUnlink.sql on this database.
        if (! Schema::hasColumn('discord_sync_queue', 'discord_id')) {
            Schema::table('discord_sync_queue', function (Blueprint $table) {
                $table->string('discord_id', 32)->nullable()->default(null)->after('user_id');
            });
        }
    }

    public function down(): void
    {
    }
};
```

Verify it takes effect before writing any test: `docker compose run --rm --no-deps -T cms php artisan migrate:fresh --env=testing` must complete, and `discord_sync_queue` must then exist with a `discord_id` column.

- [ ] **Step 1: Write the failing test**

Create `cms/tests/Feature/Discord/DiscordProcessQueueTest.php`:

```php
<?php

use App\Models\User;
use App\Services\Discord\DiscordApi;
use App\Services\Discord\DiscordSyncService;
use Illuminate\Support\Facades\DB;

it('strips roles for unlink rows using the queued discord id', function () {
    $api = Mockery::mock(DiscordApi::class);
    $api->shouldReceive('configured')->andReturnTrue();
    app()->instance(DiscordApi::class, $api);

    $sync = Mockery::mock(DiscordSyncService::class);
    $sync->shouldReceive('unlinkById')->once()->with('99887766554433221');
    $sync->shouldNotReceive('syncUser');
    app()->instance(DiscordSyncService::class, $sync);

    DB::table('discord_sync_queue')->insert([
        'user_id' => 1,
        'discord_id' => '99887766554433221',
        'reason' => 'unlink',
        'created_at' => time(),
    ]);

    $this->artisan('discord:process')->assertSuccessful();

    expect(DB::table('discord_sync_queue')->count())->toBe(0);
});

it('still syncs ordinary rows for linked users', function () {
    $api = Mockery::mock(DiscordApi::class);
    $api->shouldReceive('configured')->andReturnTrue();
    app()->instance(DiscordApi::class, $api);

    $user = User::factory()->create(['discord_id' => '11223344556677889']);

    $sync = Mockery::mock(DiscordSyncService::class);
    $sync->shouldReceive('syncUser')->once();
    $sync->shouldNotReceive('unlinkById');
    app()->instance(DiscordSyncService::class, $sync);

    DB::table('discord_sync_queue')->insert([
        'user_id' => $user->id,
        'discord_id' => null,
        'reason' => 'login',
        'created_at' => time(),
    ]);

    $this->artisan('discord:process')->assertSuccessful();

    expect(DB::table('discord_sync_queue')->count())->toBe(0);
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose run --rm --no-deps -T cms ./vendor/bin/pest tests/Feature/Discord/DiscordProcessQueueTest.php`
Expected: FAIL — `unlinkById` does not exist on `DiscordSyncService`, and the queue command ignores the `reason` column.

- [ ] **Step 3: Split unlinkUser into unlinkById**

In `cms/app/Services/Discord/DiscordSyncService.php`, replace the whole `unlinkUser` method with:

```php
    public function unlinkUser(User $user): void
    {
        if (! $user->discord_id) {
            return;
        }

        $this->unlinkById($user->discord_id);
    }

    /**
     * Strip the bot-managed roles and nickname from a Discord account that is
     * no longer linked. Takes a raw id because the in-game disconnect clears
     * `users.discord_id` before this ever runs - the queue row carries the id.
     */
    public function unlinkById(string $discordId): void
    {
        if (! $this->api->configured()) {
            return;
        }

        try {
            $member = $this->api->getMember($discordId);

            if ($member !== null) {
                $managed = array_filter(config('services.discord.roles'));
                $kept = array_values(array_diff($member['roles'] ?? [], $managed));

                // diff() above removed Unverified with the rest of the
                // managed set, so this append can never duplicate it.
                $unverified = config('services.discord.roles.unverified');

                if ($unverified) {
                    $kept[] = $unverified;
                }

                $this->api->updateMember($discordId, [
                    'nick' => null,
                    'roles' => $kept,
                ]);
            }
        } catch (Throwable $e) {
            Log::warning('Discord unlink cleanup failed.', [
                'discord_id' => $discordId,
                'error' => $e->getMessage(),
            ]);
        }
    }
```

- [ ] **Step 4: Teach the queue command about unlink rows**

In `cms/app/Console/Commands/DiscordProcessQueue.php`, replace everything from the `$userIds = ...` assignment through the `DB::table('discord_sync_queue')->where('id', '<=', $maxId)->delete();` line with:

```php
        $rows = DB::table('discord_sync_queue')
            ->where('id', '<=', $maxId)
            ->get();

        $synced = 0;

        // Unlink rows carry their own discord_id: the emulator already
        // cleared users.discord_id, so there is nothing left to look up.
        $unlinkIds = $rows->where('reason', 'unlink')
            ->pluck('discord_id')
            ->filter()
            ->unique();

        foreach ($unlinkIds as $discordId) {
            $sync->unlinkById((string) $discordId);
            $synced++;
        }

        $userIds = $rows->where('reason', '!=', 'unlink')
            ->pluck('user_id')
            ->unique();

        foreach (User::query()->whereIn('id', $userIds)->whereNotNull('discord_id')->get() as $user) {
            $sync->syncUser($user);
            $synced++;
        }

        DB::table('discord_sync_queue')->where('id', '<=', $maxId)->delete();
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `docker compose run --rm --no-deps -T cms ./vendor/bin/pest tests/Feature/Discord/DiscordProcessQueueTest.php`
Expected: PASS, 2 tests.

- [ ] **Step 6: Commit**

```bash
git add cms/app/Services/Discord/DiscordSyncService.php \
        cms/app/Console/Commands/DiscordProcessQueue.php \
        cms/tests/Feature/Discord/DiscordProcessQueueTest.php
git commit -m "feat(discord): process unlink queue rows by stored discord id"
```

---

### Task 4: CMS — RCON push, self-contained callback page, retire the status page

**Files:**
- Modify: `cms/app/Contracts/Rcon.php`
- Modify: `cms/app/Services/RconService.php`
- Modify: `cms/app/Services/FakeRcon.php`
- Modify: `cms/app/Http/Controllers/User/DiscordController.php`
- Modify: `cms/routes/web.php:126-130`
- Create: `cms/resources/views/discord/result.blade.php`
- Delete: `cms/resources/views/discord/status.blade.php`
- Test: `cms/tests/Feature/Discord/DiscordCallbackTest.php`

**Interfaces:**
- Consumes: RCON JSON key `syncdiscord` from Task 2.
- Produces: `Rcon::syncDiscordStatus(User $user): void`; the `discord.result` view accepting `state` (`'success'|'error'`), `message` (string), and `autoClose` (bool).

- [ ] **Step 1: Write the failing test**

Create `cms/tests/Feature/Discord/DiscordCallbackTest.php`:

```php
<?php

use App\Contracts\Rcon;
use App\Models\User;
use App\Services\Discord\DiscordApi;
use App\Services\Discord\DiscordSyncService;
use App\Services\FakeRcon;

it('links the account and pushes status over rcon on a successful callback', function () {
    $rcon = new FakeRcon(connected: true);
    app()->instance(Rcon::class, $rcon);

    $api = Mockery::mock(DiscordApi::class);
    $api->shouldReceive('configured')->andReturnTrue();
    $api->shouldReceive('exchangeCode')->once()->andReturn(['access_token' => 'tok']);
    $api->shouldReceive('identify')->once()->with('tok')->andReturn(['id' => '12345678901234567']);
    $api->shouldReceive('joinGuild')->once();
    app()->instance(DiscordApi::class, $api);

    $sync = Mockery::mock(DiscordSyncService::class);
    $sync->shouldReceive('syncUser')->once();
    app()->instance(DiscordSyncService::class, $sync);

    $user = User::factory()->create(['discord_id' => null]);

    $response = $this->actingAs($user)
        ->withSession(['discord_oauth_state' => 'state-token'])
        ->get('/discord/callback?code=abc&state=state-token');

    $response->assertOk()->assertSee('Discord connected');

    expect($user->fresh()->discord_id)->toBe('12345678901234567')
        ->and(collect($rcon->calls)->pluck('method'))->toContain('syncDiscordStatus');
});

it('reports an error inline when the oauth state does not match', function () {
    app()->instance(Rcon::class, new FakeRcon(connected: true));

    $user = User::factory()->create(['discord_id' => null]);

    $this->actingAs($user)
        ->withSession(['discord_oauth_state' => 'state-token'])
        ->get('/discord/callback?code=abc&state=wrong-token')
        ->assertOk()
        ->assertSee('Something went wrong');

    expect($user->fresh()->discord_id)->toBeNull();
});

it('no longer exposes the discord status page or unlink form', function () {
    $user = User::factory()->create();

    $this->actingAs($user)->get('/discord')->assertNotFound();
    $this->actingAs($user)->post('/discord/unlink')->assertNotFound();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose run --rm --no-deps -T cms ./vendor/bin/pest tests/Feature/Discord/DiscordCallbackTest.php`
Expected: FAIL — `syncDiscordStatus` is not on `FakeRcon`, and `/discord` still returns 200.

- [ ] **Step 3: Add syncDiscordStatus to the RCON contract and ALL FOUR implementations**

There are four classes implementing `Rcon`. Adding the interface method without implementing it in every one of them is a fatal PHP error, so all four change together:

| Class | Role |
|-------|------|
| `RconService` | Arcturus dialect (JSON) |
| `PlusRconService` | **PlusEMU dialect — what production resolves to**, since PixelRP runs `EMULATOR_DRIVER=plus` |
| `AfterCommitRcon` | Decorator that defers sends until the surrounding DB transaction commits |
| `FakeRcon` | Test double |

In `cms/app/Contracts/Rcon.php`, add below `alertUser`:

```php
    /**
     * Push the user's current Discord link status into their open game
     * client, so the Settings window updates without a manual refresh.
     */
    public function syncDiscordStatus(User $user): void;
```

In **both** `cms/app/Services/RconService.php` and `cms/app/Services/PlusRconService.php`, add alongside the other command wrappers (both classes use the same CMS-dialect `dispatchCommand` shape and translate internally):

```php
    public function syncDiscordStatus(User $user): void
    {
        $this->dispatchCommand('syncdiscord', [
            'user_id' => $user->id,
        ]);
    }
```

In `cms/app/Services/AfterCommitRcon.php`, follow the decorator's deferral pattern:

```php
    public function syncDiscordStatus(User $user): void
    {
        $this->defer(fn () => $this->inner->syncDiscordStatus($user));
    }
```

In `cms/app/Services/FakeRcon.php`, add alongside the other recorded methods:

```php
    public function syncDiscordStatus(User $user): void
    {
        $this->record(__FUNCTION__, ['user' => $user->id]);
    }
```

Deferring the push until after commit is correct here: the callback links the account and saves the user inside the request, and a push that fired before a rolled-back save would tell the client it is linked when it is not.

- [ ] **Step 4: Create the result page**

Create `cms/resources/views/discord/result.blade.php`. It must be self-contained — it is the only page left in the flow, and it renders inside a popup:

```blade
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ $state === 'success' ? __('Discord connected') : __('Discord') }}</title>
    <style>
        body {
            margin: 0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #1e2124;
            color: #f4f4f5;
            font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
            text-align: center;
            padding: 24px;
        }
        .card { max-width: 380px; }
        h1 { font-size: 20px; margin: 0 0 12px; }
        p { font-size: 14px; line-height: 1.5; color: #b9bbbe; margin: 0; }
        .ok { color: #43b581; }
        .bad { color: #f04747; }
    </style>
</head>
<body>
    <div class="card">
        <h1 class="{{ $state === 'success' ? 'ok' : 'bad' }}">
            {{ $state === 'success' ? __('Discord connected') : __('Something went wrong') }}
        </h1>
        <p>{{ $message }}</p>
    </div>

    @if ($autoClose)
        <script>
            // Opened from the game client, so closing is permitted. If the
            // page was reached some other way, the close is a no-op and the
            // message above stands on its own.
            setTimeout(() => window.close(), 1200);
        </script>
    @endif
</body>
</html>
```

- [ ] **Step 5: Rewrite the controller**

Replace the whole of `cms/app/Http/Controllers/User/DiscordController.php`:

```php
<?php

namespace App\Http\Controllers\User;

use App\Contracts\Rcon;
use App\Http\Controllers\Controller;
use App\Models\User;
use App\Services\Discord\DiscordApi;
use App\Services\Discord\DiscordSyncService;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Str;
use Illuminate\View\View;

/**
 * Discord account linking. The game client opens `/discord/connect` in a
 * popup that shares the CMS session, so `auth` middleware covers identity.
 * The user's OAuth token is used once (identify + guilds.join) and never
 * stored.
 *
 * Disconnecting happens in-game (wire 3956), not here. The callback is the
 * only page in this flow: it reports the outcome and closes itself.
 */
class DiscordController extends Controller
{
    public function __construct(
        private readonly DiscordApi $api,
        private readonly DiscordSyncService $sync,
        private readonly Rcon $rcon,
    ) {}

    public function connect(Request $request): RedirectResponse|View
    {
        if (! $this->api->configured()) {
            return $this->result('error', __('Discord linking is not available right now. Please try again later.'));
        }

        if ($request->user()->discord_id) {
            return $this->result('success', __('Your Discord account is already connected.'));
        }

        $state = Str::random(40);
        $request->session()->put('discord_oauth_state', $state);

        return redirect()->away($this->api->authorizeUrl(route('discord.callback'), $state));
    }

    public function callback(Request $request): View
    {
        $state = $request->session()->pull('discord_oauth_state');

        if (! $state || ! hash_equals($state, (string) $request->query('state', ''))) {
            return $this->result('error', __('The Discord link attempt expired or was invalid. Please try again from the game.'));
        }

        $code = (string) $request->query('code', '');

        if ($code === '') {
            // User hit "Cancel" on the consent screen.
            return $this->result('error', __('Discord linking was cancelled.'));
        }

        $token = $this->api->exchangeCode($code, route('discord.callback'));
        $identity = $token ? $this->api->identify($token['access_token']) : null;

        if (! $identity || empty($identity['id'])) {
            return $this->result('error', __('Discord did not confirm the link. Please try again from the game.'));
        }

        $user = $request->user();
        $discordId = (string) $identity['id'];

        // One Discord account per game account - hard uniqueness (also
        // enforced by the DB unique index as a race backstop).
        $taken = User::query()
            ->where('discord_id', $discordId)
            ->where('id', '!=', $user->id)
            ->exists();

        if ($taken) {
            return $this->result('error', __('That Discord account is already linked to a different PixelRP account.'));
        }

        $user->discord_id = $discordId;
        $user->discord_linked_at = time();
        $user->save();

        // Auto-join the guild (no-op if already a member), then converge
        // nickname + roles right away.
        $this->api->joinGuild($discordId, $token['access_token']);
        $this->sync->syncUser($user->fresh());

        // Best effort: push the new status straight into the open client so
        // the Settings window updates without the player doing anything.
        $this->rcon->syncDiscordStatus($user);

        return $this->result('success', __('You can close this window. Your Settings page has already updated.'));
    }

    private function result(string $state, string $message): View
    {
        return view('discord.result', [
            'state' => $state,
            'message' => $message,
            'autoClose' => ($state === 'success'),
        ]);
    }
}
```

- [ ] **Step 6: Retire the status page and unlink route**

In `cms/routes/web.php`, replace the four Discord routes (lines 127-130) with:

```php
            // Disconnecting happens in-game (wire 3956); the callback is the
            // only page this flow still needs.
            Route::get('/connect', [DiscordController::class, 'connect'])->middleware('throttle:10,1')->name('discord.connect');
            Route::get('/callback', [DiscordController::class, 'callback'])->middleware('throttle:10,1')->name('discord.callback');
```

Then delete the old view:

```bash
rm cms/resources/views/discord/status.blade.php
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `docker compose run --rm --no-deps -T cms ./vendor/bin/pest tests/Feature/Discord/`
Expected: PASS, 5 tests across both files (3 callback + 2 queue).

- [ ] **Step 8: Run the full CMS suite for regressions**

Run: `docker compose run --rm --no-deps -T cms ./vendor/bin/pest`
Expected: PASS. Any failure naming `discord.show` is a leftover reference to the retired route — fix it.

- [ ] **Step 9: Commit**

```bash
git add cms/app/Contracts/Rcon.php cms/app/Services/RconService.php \
        cms/app/Services/FakeRcon.php \
        cms/app/Http/Controllers/User/DiscordController.php \
        cms/routes/web.php cms/resources/views/discord/ \
        cms/tests/Feature/Discord/DiscordCallbackTest.php
git commit -m "feat(discord): push status over RCON after OAuth; retire status page"
```

---

### Task 5: Renderer patch — widened status parser and unlink composer

**Files (inside the yarn patch extract):**
- Modify: `src/nitro/communication/messages/incoming/RpDiscordStatusEvent.ts`
- Create: `src/nitro/communication/messages/outgoing/RpDiscordUnlinkComposer.ts`
- Modify: `src/nitro/communication/messages/outgoing/OutgoingHeader.ts`
- Modify: `src/nitro/communication/messages/outgoing/index.ts`
- Modify: `src/nitro/communication/NitroMessages.ts`

**Interfaces:**
- Consumes: wire ids 3952 (widened) and 3956 from Task 1.
- Produces: `RpDiscordStatusParser.linkedAt: number` and `RpDiscordUnlinkComposer` (no constructor args), both importable from `@nitrots/nitro-renderer`. Task 6 uses them.

- [ ] **Step 1: Install before extracting**

Run: `cd client && yarn install`
Expected: completes cleanly. **This must run before the extract** — resealing from stale `node_modules` silently reverts earlier patch fixes.

- [ ] **Step 2: Extract the current patch**

Run: `cd client && yarn patch -u @nitrots/nitro-renderer`

With this many stacked patches that errors as ambiguous and lists descriptors. Grab the last one and re-run:

```bash
cd client
DESC=$(yarn patch -u @nitrots/nitro-renderer 2>&1 | grep '^- ' | tail -1 | sed 's/^- //')
yarn patch -u "$DESC"
```

Expected: prints a temp extract directory with ALL current patches applied. Confirm before editing:

```bash
grep -c "AUTH_MOVE_ENTER" <extract-dir>/src/room/renderer/PixelRPMovementAuthority.ts
```
Expected: non-zero. A zero here means the extract is not the patched tree — stop and re-extract.

- [ ] **Step 3: Widen the status parser**

In `<extract-dir>/src/nitro/communication/messages/incoming/RpDiscordStatusEvent.ts`, update `RpDiscordStatusParser` so it reads the second int:

```typescript
export class RpDiscordStatusParser implements IMessageParser
{
    private _linked: boolean;
    private _linkedAt: number;

    public flush(): boolean
    {
        this._linked = false;
        this._linkedAt = 0;

        return true;
    }

    public parse(wrapper: IMessageDataWrapper): boolean
    {
        if(!wrapper) return false;

        this._linked = (wrapper.readInt() === 1);
        this._linkedAt = wrapper.readInt();

        return true;
    }

    public get linked(): boolean
    {
        return this._linked;
    }

    // Unix seconds the account was linked at; 0 when unlinked.
    public get linkedAt(): number
    {
        return this._linkedAt;
    }
}
```

Leave the `RpDiscordStatusEvent` class below it untouched.

- [ ] **Step 4: Add the unlink composer**

Create `<extract-dir>/src/nitro/communication/messages/outgoing/RpDiscordUnlinkComposer.ts`:

```typescript
import { IMessageComposer } from '../../../../api';

// PixelRP: disconnect the session user's Discord account.
export class RpDiscordUnlinkComposer implements IMessageComposer<ConstructorParameters<typeof RpDiscordUnlinkComposer>>
{
    private _data: ConstructorParameters<typeof RpDiscordUnlinkComposer>;

    constructor()
    {
        this._data = [];
    }

    public getMessageArray()
    {
        return this._data;
    }

    public dispose(): void
    {
        return;
    }
}
```

- [ ] **Step 5: Register the header, export, and message mapping**

In `<extract-dir>/src/nitro/communication/messages/outgoing/OutgoingHeader.ts`, below `public static RP_GET_DISCORD_STATUS = 3953;`:

```typescript
    public static RP_DISCORD_UNLINK = 3956;
```

In `<extract-dir>/src/nitro/communication/messages/outgoing/index.ts`, beside the other `Rp*Composer` exports:

```typescript
export * from './RpDiscordUnlinkComposer';
```

In `<extract-dir>/src/nitro/communication/NitroMessages.ts`, add the import beside the existing `RpGetDiscordStatusComposer` import:

```typescript
import { RpDiscordUnlinkComposer } from './messages/outgoing/RpDiscordUnlinkComposer';
```

and register it directly below the `RP_GET_DISCORD_STATUS` composer line:

```typescript
        this._composers.set(OutgoingHeader.RP_DISCORD_UNLINK, RpDiscordUnlinkComposer);
```

- [ ] **Step 6: Reseal as a new stacked delta**

Run: `cd client && yarn patch-commit -s <extract-dir>`
Expected: a new `client/.yarn/patches/@nitrots-nitro-renderer-patch-<hash>.patch` appears and `package.json` chains it after `081847e595`.

- [ ] **Step 7: Verify the reseal did not revert anything**

```bash
cd client
NEW=$(git status --porcelain .yarn/patches | grep '^??' | awk '{print $2}')
grep '^+++' .yarn/patches/@nitrots-nitro-renderer-patch-081847e595.patch | sort > /tmp/old-files.txt
grep '^+++' "$NEW" | sort > /tmp/new-files.txt
diff /tmp/old-files.txt /tmp/new-files.txt
```

Expected: the new delta touches ONLY the five files listed at the top of this task. Then confirm the sentinels of earlier work survive:

```bash
yarn install
grep -c "AUTH_MOVE_ENTER" node_modules/@nitrots/nitro-renderer/src/room/renderer/PixelRPMovementAuthority.ts
grep -c "RP_MOVEMENT_CYCLE" node_modules/@nitrots/nitro-renderer/src/nitro/communication/messages/incoming/IncomingHeader.ts
grep -c "RP_DISCORD_UNLINK" node_modules/@nitrots/nitro-renderer/src/nitro/communication/messages/outgoing/OutgoingHeader.ts
```
Expected: all three non-zero. A zero on either of the first two means the reseal captured a stale tree — discard the delta and start the task over from Step 1.

- [ ] **Step 8: Commit inside the client submodule**

```bash
cd client
git add package.json yarn.lock .yarn/patches
git commit -m "feat(discord): renderer patch - linkedAt on 3952, unlink composer 3956"
```

Do not push or bump the pointer yet; Task 6 adds to the same submodule.

---

### Task 6: Client — skeleton, linked, unlinked and pending states

**Files:**
- Modify: `client/src/components/rp-settings/RpSettingsView.tsx` (imports at line 1; state near line 38; effects near line 81; render block at lines 349-364)
- Modify: `client/src/components/rp-settings/RpSettingsView.scss:65-90`

**Interfaces:**
- Consumes: `RpDiscordStatusParser.linkedAt` and `RpDiscordUnlinkComposer` from Task 5.
- Produces: the finished subpage. No later task consumes it.

There is no test runner in this package; the gate is `tsc` plus the build, then the manual in-game test in Task 7.

- [ ] **Step 1: Update the imports**

In `client/src/components/rp-settings/RpSettingsView.tsx` line 1, add `RpDiscordUnlinkComposer` to the existing `@nitrots/nitro-renderer` import list (keep it alphabetical with its neighbours):

```typescript
import { AvatarFigurePartType, AvatarScaleType, AvatarSetType, ILinkEventTracker, RpDiscordStatusEvent, RpDiscordUnlinkComposer, RpGetDiscordStatusComposer, RpUiSettingsEvent } from '@nitrots/nitro-renderer';
```

- [ ] **Step 2: Add the linkedAt and pending state**

Replace the `discordLinked` state declaration (around line 37-38) with:

```typescript
    // null = unknown/loading; refreshed every time the Discord page opens
    const [ discordLinked, setDiscordLinked ] = useState<boolean>(null);
    const [ discordLinkedAt, setDiscordLinkedAt ] = useState<number>(0);
    // 'connect' while the OAuth popup is open, 'unlink' while a disconnect
    // is in flight, null otherwise.
    const [ discordPending, setDiscordPending ] = useState<string>(null);
    const [ confirmUnlink, setConfirmUnlink ] = useState<boolean>(false);
```

- [ ] **Step 3: Clear pending state when status arrives**

Replace the `useMessageEvent<RpDiscordStatusEvent>` line (around line 81) with:

```typescript
    useMessageEvent<RpDiscordStatusEvent>(RpDiscordStatusEvent, event =>
    {
        const parser = event.getParser();

        setDiscordLinked(parser.linked);
        setDiscordLinkedAt(parser.linkedAt);
        // Any authoritative answer ends whatever was in flight.
        setDiscordPending(null);
        setConfirmUnlink(false);
    });
```

- [ ] **Step 4: Reset transient state when the page opens, and bound the pending state**

Replace the existing "Refresh link status" effect (around lines 83-90) with:

```typescript
    // Refresh link status whenever the Discord page comes on screen.
    useEffect(() =>
    {
        if(!isVisible || (currentTab !== 'Social') || (socialPage !== 'Discord')) return;

        setDiscordPending(null);
        setConfirmUnlink(false);
        SendMessageComposer(new RpGetDiscordStatusComposer());
    }, [ isVisible, currentTab, socialPage ]);

    // A player who cancels at Discord's consent screen, or just closes the
    // popup, sends nothing back - never leave the panel stuck in pending.
    useEffect(() =>
    {
        if(!discordPending) return;

        const timeout = setTimeout(() =>
        {
            setDiscordPending(null);
            SendMessageComposer(new RpGetDiscordStatusComposer());
        }, 90000);

        return () => clearTimeout(timeout);
    }, [ discordPending ]);
```

- [ ] **Step 5: Add the action handlers**

Add these beside the other handlers in the component (anywhere above the return):

```typescript
    const connectDiscord = () =>
    {
        setDiscordPending('connect');
        window.open('/discord/connect', '_blank', 'noopener,noreferrer');
    }

    const disconnectDiscord = () =>
    {
        setDiscordPending('unlink');
        setConfirmUnlink(false);
        SendMessageComposer(new RpDiscordUnlinkComposer());
    }

    // "Connected since 4 March 2026" - linkedAt is unix seconds, 0 when unlinked.
    const discordLinkedSince = (discordLinkedAt > 0)
        ? new Date(discordLinkedAt * 1000).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })
        : null;
```

- [ ] **Step 6: Replace the render block**

Replace the whole `{ (socialPage === 'Discord') && ... }` block (lines 349-364) with:

```tsx
                                { (socialPage === 'Discord') &&
                                <Column center fullHeight gap={ 2 } className="rp-settings-discord">
                                    <i className="fa-brands fa-discord rp-settings-discord-mark" aria-hidden="true" />
                                    <Text bold>Discord</Text>
                                    { (discordLinked === null) && <>
                                        <div className="rp-settings-skeleton rp-settings-skeleton--line" />
                                        <div className="rp-settings-skeleton rp-settings-skeleton--block" />
                                        <div className="rp-settings-skeleton rp-settings-skeleton--btn" />
                                    </> }
                                    { (discordLinked === true) && <>
                                        <Text className="rp-settings-discord-linked">Your Discord account is connected.</Text>
                                        <Text small className="text-muted">Your name in the PixelRP server matches your in-game name, and you carry the Verified role.</Text>
                                        { discordLinkedSince &&
                                            <Text small className="text-muted">Connected since { discordLinkedSince }.</Text> }
                                        { !confirmUnlink && (discordPending !== 'unlink') &&
                                            <div className="rp-settings-discord-btn rp-settings-discord-btn--danger"
                                                onClick={ () => setConfirmUnlink(true) }>Disconnect</div> }
                                        { confirmUnlink && (discordPending !== 'unlink') && <>
                                            <Text small className="text-muted">Disconnect this account? You will lose the Verified role.</Text>
                                            <Flex center gap={ 2 }>
                                                <div className="rp-settings-discord-btn rp-settings-discord-btn--danger"
                                                    onClick={ disconnectDiscord }>Yes, disconnect</div>
                                                <Text small underline pointer className="text-muted"
                                                    onClick={ () => setConfirmUnlink(false) }>Cancel</Text>
                                            </Flex>
                                        </> }
                                        { (discordPending === 'unlink') &&
                                            <Text small className="text-muted">Disconnecting. Your Discord roles are removed shortly.</Text> }
                                    </> }
                                    { (discordLinked === false) && <>
                                        <Text small className="text-muted">Link your Discord account to get the Verified role and an in-game Discord badge. Your Discord details are never shown in-game.</Text>
                                        { (discordPending !== 'connect') &&
                                            <div className="rp-settings-discord-btn" onClick={ connectDiscord }>Connect Discord</div> }
                                        { (discordPending === 'connect') &&
                                            <Text small className="text-muted">Waiting for Discord. Finish in the window that opened, then come back here.</Text> }
                                    </> }
                                </Column> }
```

Note the `rp-settings-placeholder` class is gone — this page no longer borrows the empty-state layout. Every string uses plain hyphens, no em-dashes.

- [ ] **Step 7: Add the styles**

In `client/src/components/rp-settings/RpSettingsView.scss`, replace the `.rp-settings-discord` rule at line 65 and add the new rules beside the existing `.rp-settings-discord-btn`:

```scss
    .rp-settings-discord {
        max-width: 320px;
        margin: 0 auto;
        text-align: center;
    }

    .rp-settings-discord-mark {
        font-size: 34px;
        color: #5865f2;
        line-height: 1;
    }

    .rp-settings-discord-btn--danger {
        background: #b23b3b;
    }

    .rp-settings-skeleton {
        border-radius: 6px;
        background: linear-gradient(90deg, rgba(0, 0, 0, 0.06) 25%, rgba(0, 0, 0, 0.12) 37%, rgba(0, 0, 0, 0.06) 63%);
        background-size: 400% 100%;
        animation: rp-settings-skeleton-shimmer 1.4s ease infinite;

        &--line {
            width: 70%;
            height: 12px;
        }

        &--block {
            width: 100%;
            height: 34px;
        }

        &--btn {
            width: 132px;
            height: 26px;
            border-radius: 14px;
        }
    }

    @keyframes rp-settings-skeleton-shimmer {
        0% { background-position: 100% 50%; }
        100% { background-position: 0 50%; }
    }
```

The subpage is a light surface (`text-black` on a light panel), so plain rgba tints are correct here — the `--prp-chrome-*` requirement applies to dark chrome surfaces, which this is not.

- [ ] **Step 8: Type-check and build**

```bash
cd client
npx tsc --noEmit
yarn build
```
Expected: no type errors, build succeeds. A "Property 'linkedAt' does not exist" error means Task 5's `yarn install` did not take — re-run it.

- [ ] **Step 9: Commit inside the client submodule**

```bash
cd client
git add src/components/rp-settings/RpSettingsView.tsx src/components/rp-settings/RpSettingsView.scss
git commit -m "feat(discord): skeleton loading + in-game disconnect in Settings"
```

---

### Task 7: Ship to beta

**Files:**
- Modify: `CHANGELOG.md`
- Modify: the `client` submodule pointer in `plus`

**Interfaces:**
- Consumes: everything from Tasks 1-6.
- Produces: the change live on beta, ready for the manual in-game test.

- [ ] **Step 1: Push all three touched submodules**

```bash
cd emulator && git push origin HEAD:$(git rev-parse --abbrev-ref HEAD) && cd ..
cd cms && git push origin HEAD:$(git rev-parse --abbrev-ref HEAD) && cd ..
cd client && git push origin HEAD:pixelrp && cd ..
```
Expected: Tasks 1-2 land in `emulator`, Tasks 3-4 in `cms`, Tasks 5-6 in `client`. Skipping any of these ships unchanged code while the deploy still reports green. Confirm each with `git -C <sub> status` showing nothing ahead of its remote.

- [ ] **Step 2: Add the changelog entry**

In `CHANGELOG.md`, add under the current unreleased heading (match the surrounding bullet style exactly):

```markdown
- Discord settings no longer flash the "not connected" screen while loading, and you can now connect and disconnect your Discord account without leaving the game.
```

- [ ] **Step 3: Bump the pointer and commit**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
git add emulator cms client CHANGELOG.md
git commit -m "feat(discord): in-game connect/disconnect + skeleton settings (bump submodules)"
git push origin beta
```

Verify all three pointers moved before pushing: `git diff --cached --submodule=short` must show a new commit for `emulator`, `cms` and `client`.

- [ ] **Step 4: Deploy**

Run: `gh workflow run deploy.yml --ref beta`
Expected: the workflow starts. Watch it with `gh run watch`. Migration `46_DiscordUnlink.sql` auto-applies (tracked in `_applied_sql_updates`); no manual DB step is needed for this change.

- [ ] **Step 5: Confirm the client bundle actually changed**

Load beta with devtools open and check that the `nitro-renderer-*.js` bundle hash differs from before the deploy. An unchanged hash means the submodule push in Step 1 did not land.

- [ ] **Step 6: Hand off for the manual in-game test**

Report to the user, asking them to check on beta:

1. Open Settings → Social → Discord with an account that is already linked. The unlinked pitch must never appear; a skeleton shows briefly, then the connected card.
2. Disconnect from in-game. The card flips to unlinked immediately, no browser opens. Within a minute the Discord roles drop and the nickname resets.
3. Connect from in-game. Only Discord's consent screen appears — no PixelRP web page — the popup closes itself, and the Settings card updates without touching anything.
4. Cancel at Discord's consent screen and close the popup. The panel must fall back to the unlinked state, not sit in "Waiting for Discord" forever.

Do not screenshot-drive the Nitro client to verify these; hand off and wait.

---

## Notes for the implementer

- **`/discord` is gone.** If you find any remaining reference to `route('discord.show')` anywhere in the CMS, it is a bug from this change — the callback result page replaced it.
- **The unlink queue row is the only cleanup path.** `discord:sweep` iterates `whereNotNull('discord_id')` users only, so it will never notice an unlinked account. That is why Task 1's clear-and-enqueue is a single transaction.
- **Offline players are a normal case.** The RCON push returning "user not online" is success, not failure; the client re-requests status on page open.
- **Prod is out of scope.** Beta only, per the spec. Prod needs its own env vars and a prod redirect URI registered in the Discord app.
