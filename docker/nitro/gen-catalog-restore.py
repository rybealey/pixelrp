#!/usr/bin/env python3
"""Restore the catalog to the emulator's default state (2026-09-07).

Undoes the 2026-08-27 rebuild/reorg (33_CatalogRebuild + 39_CatalogReorg, the
generated >= 920000 tree) and puts back the catalog that ships in
`emulator/Resources/SQLs/Original Database.sql` - the dump MySQL seeds a fresh
install from, so it *is* this stack's default.

Reads:  emulator/Resources/SQLs/Original Database.sql  (catalog_pages,
        catalog_items and furniture, all three straight out of the base dump)
Emits:  emulator/Resources/SQLs/Updates/81_CatalogRestoreDefault.sql

Exceptions to a literal restore, all asked for by Ry:

  Builders      The custom Builders tab (root caption 'Builders', id 912362 on
                beta) and every descendant is a KEEP set resolved *live* by the
                SQL - 912364-912375 are data-only pages that exist on the server
                and in no migration, so they can never be hardcoded. Its pages
                and items survive the wipe untouched. The default's own public
                'Furni > Builders Club' section (9027 + 34 children, 1595 items)
                is NOT restored: builders furni stays exclusive to that tab.
                Neither is the Bots page (id 9), which beta has re-parented into
                Builders - bots are sold from there and nowhere else, so the
                frontpage blurb drops its dead 'or a Bot' link too.
  Duckets       No item may charge them. Every restored row folds cost_pixels
                into cost_credits (the convention 33_CatalogRebuild set) and
                ships with cost_pixels = 0; a final sweep catches any row that
                still charges duckets, Builders included - "never charge
                Duckets" is an economy-wide rule, and a price update cannot
                restructure the tab.
  Clothing      Sellable clothing never enters the standard catalog (the rule
                37_RemoveClothingFromCatalog set). Clothing rows are dropped at
                generation time and swept again on apply; pages left with
                nothing but clothing (the 'Clothing' root and the two seasonal
                clothing pages) are not restored at all. The Clothing Store
                (`catalog_clothing`, :zara) is a different subsystem and is not
                touched by a single statement here.
  Jukebox       The default sells jukebox*1 from Staff > Other Furni > System
                (rank 5). It moves to Builders > Corporations > Cafe, resolved
                by caption at apply time. Only the catalog row moves: the
                furniture row, its interaction and the room jukebox/YouTube
                player are untouched, so it still plays audio.
  Branding      'Habboon' -> 'PixelRP' in captions and page blurbs, and the
                habboon.com / easybuy.pw currency links -> pixelrp.co. Official
                Habbo line names (Habboween, HabboWood) are product names and
                stay as they are.
  Icons         16 default pages point at Habboon custom icon ids (3009, 9990,
                9991, ...) that never existed in our asset set - the official
                1..369 icons synced from habbo-downloader are all we ship. Those
                16 are remapped to close official equivalents so no page renders
                a missing icon; every other page keeps its default icon.

Also dropped: the 196 default rows sitting on page ids that no page defines.

Restored pages take FRESH ids from PAGE_BASE, they do not reuse the dump's.
The first run of this migration died on `Duplicate entry '9' for key
catalog_pages.PRIMARY`: beta's Builders tab has the default's Bots page (id 9)
re-parented into it, so a dump id can and does collide with a KEEP page. Nothing
outside this table keys on a catalog page id - the emulator and the frontpage
blurbs address pages by `page_link` - so remapping is free, and it makes the
collision impossible instead of unlikely. Items are inserted without ids and
take AUTO_INCREMENT values, which start above whatever Builders kept. The rows
also land in staging tables first and are filtered against the KEEP set on the
way in, so a page a future Builders tab happens to hold can never be clobbered
or duplicated by id.

Idempotent: the emitted SQL rebuilds the whole non-Builders catalog from
scratch, so it can be re-applied at any time.
"""
import re
import sys

SRC = 'emulator/Resources/SQLs/Original Database.sql'
OUT = 'emulator/Resources/SQLs/Updates/81_CatalogRestoreDefault.sql'

PAGE_COLS = ['id', 'parent_id', 'caption', 'icon_image', 'visible', 'enabled',
             'min_rank', 'min_vip', 'order_num', 'page_link', 'page_layout',
             'page_strings_1', 'page_strings_2']
ITEM_COLS = ['id', 'page_id', 'item_id', 'catalog_name', 'cost_credits',
             'cost_pixels', 'cost_diamonds', 'amount', 'limited_sells',
             'limited_stack', 'offer_active', 'extradata', 'badge', 'offer_id']
FURNI_COLS = ['id', 'item_name', 'public_name', 'type', 'width', 'length',
              'stack_height', 'can_stack', 'can_sit', 'is_walkable', 'sprite_id',
              'allow_recycle', 'allow_trade', 'allow_marketplace_sell',
              'allow_gift', 'allow_inventory_stack', 'interaction_type',
              'behaviour_data', 'interaction_modes_count', 'vending_ids',
              'height_adjustable', 'effect_id', 'wired_id', 'is_rare',
              'clothing_id', 'extra_rot']

BUILDERS_CLUB = '9027'      # default's public Furni > Builders Club root
BOTS_PAGE = '9'             # stays in Builders, not restored publicly
PAGE_BASE = 930000          # restored pages get fresh ids from here (see above)
JUKEBOX = 'jukebox*1'       # relocated to Builders > Corporations > Cafe

# --- Furni tab restructuring (Ry, 2026-09-07) -------------------------------
# Pages (and everything under them) that no longer exist anywhere.
DROP_SUBTREES = {
    '9210': 'Badges (Badge Shop, Badge Of The Week)',
    '50': 'Duckets Shop (Room Promo, Stacktiles)',
    '6': 'Silver VIP',
    '912347': 'Gold VIP',
    '9170': 'Event Staff',
}
# Pages that keep their contents but hang somewhere else.
REPARENT = {
    '57895': '14',    # Pet Horse       -> Pet Shop
    '9056': '14',     # Baby Pets Shop  -> Pet Shop
    '503': '9225',    # Game Shop       -> Staff
}
# Subtrees that collapse into one new page. The Builders ones are created by
# the SQL itself, against a parent it resolves live.
FLATTEN_STAFF = ('13', 'Exchange', 197, 1)      # PixelRP Exchange -> Staff > Exchange
FLATTEN_BUILDERS = [
    # source subtree, caption, icon, where the SQL puts it
    ('5', 'Club', 172, 'cartier'),              # PixelRP Club  -> Builders > Club
    ('9036', 'Turfs', 268, 'bots'),             # PixelRP Groups -> Builders > Turfs
]

# Habboon custom icon id -> closest official icon (see docker/nitro/gen-catalog.py
# for the curated caption->icon picks these come from).
ICON_FIX = {
    '22': 274,    # New Years 2015
    '91': 6,      # Other Furni
    '92': 28,     # Rare Furni
    '9041': 63,   # Video TVs
    '9064': 311,  # Alphabet
    '9132': 344,  # Infobus
    '9168': 233,  # Paris
    '9201': 101,  # Payments
    '9202': 189,  # Popular Packages
    '9203': 28, '9204': 28, '9205': 28, '9206': 28,  # Rare Package 1-4
    '9207': 91,   # Dragon Sets
    '9208': 28,   # ICM Sets
    '9209': 261,  # Birdbath Sets
}


def parse_values(s):
    """Split one dump row's `VALUES (...)` body, keeping backslash escapes."""
    out, i, n = [], 0, len(s)
    while i < n:
        while i < n and s[i] in ' ,':
            i += 1
        if i >= n:
            break
        if s.startswith('NULL', i):
            out.append(None)
            i += 4
            continue
        assert s[i] == "'", s[max(0, i - 30):i + 30]
        i += 1
        buf = []
        while True:
            c = s[i]
            if c == '\\':
                buf.append(s[i:i + 2])
                i += 2
            elif c == "'":
                i += 1
                break
            else:
                buf.append(c)
                i += 1
        out.append(''.join(buf))
    return out


def read(table, cols):
    rows, prefix = [], 'INSERT INTO `%s` VALUES (' % table
    for line in open(SRC, encoding='utf-8', errors='replace'):
        if line.startswith(prefix):
            body = line.rstrip()[len(prefix):]
            rows.append(dict(zip(cols, parse_values(body[:body.rindex(')')]))))
    return rows


def rebrand(text):
    # The Bots page lives in Builders now, so the frontpage must not send
    # players to a page they cannot open.
    text = text.replace(
        ' or a <a href=\\"event:catalog/open/bots\\">Bot</a>', '')
    text = text.replace(
        '<li>Join <a href=\\"event:catalog/open/habbo_club\\">Habboon Club</a></li>', '')
    text = text.replace('Upgrade your clothing with Habboon Club, adopt a pet',
                        'Adopt a pet')
    text = text.replace('easybuy.pw/packages/currency', 'pixelrp.co')
    text = text.replace('habboon.com', 'pixelrp.co')
    text = text.replace('Habboon', 'PixelRP').replace('habboon', 'pixelrp')
    return text


pages = read('catalog_pages', PAGE_COLS)
items = read('catalog_items', ITEM_COLS)
furni = {f['id']: f for f in read('furniture', FURNI_COLS)}

by_id = {p['id']: p for p in pages}
children = {}
for p in pages:
    children.setdefault(p['parent_id'], []).append(p['id'])


def subtree(root):
    out, stack = set(), [root]
    while stack:
        pid = stack.pop()
        if pid in out:
            continue
        out.add(pid)
        stack.extend(children.get(pid, []))
    return out


def is_clothing(item):
    f = furni.get(item['item_id'])
    return bool(f) and (f['item_name'].startswith('clothing_')
                        or f['interaction_type'] == 'purchasable_clothing')


drop = subtree(BUILDERS_CLUB) | subtree(BOTS_PAGE)
for gone in DROP_SUBTREES:
    drop |= subtree(gone)

# The flattened subtrees lose their pages; their stock is re-homed below.
flat_src = {src: subtree(src)
            for src in [FLATTEN_STAFF[0]] + [f[0] for f in FLATTEN_BUILDERS]}
for pages_gone in flat_src.values():
    drop |= pages_gone

for page, parent in REPARENT.items():
    by_id[page]['parent_id'] = parent

# Pages whose whole stock is clothing (and that parent nothing) go with it.
on_page = {}
for it in items:
    on_page.setdefault(it['page_id'], []).append(it)
for p in pages:
    stock = on_page.get(p['id'], [])
    if stock and not children.get(p['id']) and all(is_clothing(i) for i in stock):
        drop |= subtree(p['id'])

kept_pages = [p for p in pages if p['id'] not in drop]

# Staff > Exchange takes the old PixelRP Exchange stock. It is an ordinary
# restored page - only the Builders ones need a parent resolved on the server.
_src, _caption, _icon, _order = FLATTEN_STAFF
EXCHANGE = 'exchange'
kept_pages.append({
    'id': EXCHANGE, 'parent_id': '9225', 'caption': _caption, 'icon_image': str(_icon),
    'visible': '1', 'enabled': '1', 'min_rank': '5', 'min_vip': '0',
    'order_num': str(_order), 'page_link': '', 'page_layout': 'default_3x3',
    'page_strings_1': '', 'page_strings_2': '',
})
kept_ids = {p['id'] for p in kept_pages}
jukebox_fid = next((fid for fid, f in furni.items() if f['item_name'] == JUKEBOX), None)
if jukebox_fid is None:
    sys.exit('jukebox*1 is missing from the base dump')

# Fresh page ids, assigned in dump order. Parents outside the map (the dump's
# five pages whose parent never existed) keep their number and stay orphaned,
# exactly as they are in the default.
page_id = {p['id']: str(PAGE_BASE + n + 1) for n, p in enumerate(kept_pages)}
# Builders > Club and Builders > Turfs are inserted by the SQL against a live
# parent, so they sit just past the staged range; their stock is staged like
# any other row and lands on them.
builders_pages = []
for n, (src, caption, icon, anchor) in enumerate(FLATTEN_BUILDERS):
    pid = str(PAGE_BASE + len(kept_pages) + n + 1)
    page_id[src] = pid
    builders_pages.append((pid, caption, icon, anchor))

# Every page of a flattened subtree routes its stock to that subtree's new page.
for src, subtree_ids in flat_src.items():
    for old_page in subtree_ids:
        page_id[old_page] = page_id[EXCHANGE] if src == FLATTEN_STAFF[0] else page_id[src]

kept_items, dropped = [], {'page': 0, 'clothing': 0, 'jukebox': 0}
flattened = {pg for ids in flat_src.values() for pg in ids}
for it in items:
    if it['page_id'] not in kept_ids and it['page_id'] not in flattened:
        dropped['page'] += 1          # Builders Club, clothing pages, orphans
    elif is_clothing(it):
        dropped['clothing'] += 1
    elif it['item_id'] == jukebox_fid:
        dropped['jukebox'] += 1       # re-emitted against the Cafe page below
    else:
        kept_items.append(it)


def esc(v):
    return "'%s'" % v


ANCHORS = {
    # where a Builders page hangs, in terms the SQL resolves on the server
    'cartier': ('@builders', 'COALESCE(@cartier_order, 1001) + 1'),
    'bots': ('COALESCE(@bots_parent, @builders)', 'COALESCE(@bots_order, 1) - 1'),
}
builders_sql = ',\n'.join(
    "    (%s, %s, %s, %d, 2, 0, %s, '', 'default_3x3', '', '', b'1', b'1')"
    % (pid, ANCHORS[anchor][0], esc(caption), icon, ANCHORS[anchor][1])
    for pid, caption, icon, anchor in builders_pages) + ';'

with open(OUT, 'w', encoding='utf-8') as o:
    o.write("""\
-- PixelRP: restore the catalog to the emulator's default state.
--
-- Replaces the 2026-08-27 rebuild (33_CatalogRebuild) and reorg
-- (39_CatalogReorg) with the catalog that ships in
-- `emulator/Resources/SQLs/Original Database.sql` - the dump a fresh install is
-- seeded from. Generated by docker/nitro/gen-catalog-restore.py; that file
-- documents every deliberate departure from a literal restore. In short:
--   * the Builders tab and everything under it is never touched (the default's
--     own public 'Furni > Builders Club' section is not restored);
--   * nothing charges duckets - cost_pixels is folded into cost_credits;
--   * no sellable clothing, and the Clothing Store is left alone;
--   * the Jukebox moves to Builders > Corporations > Cafe, catalog row only;
--   * 'Habboon' branding is rewritten to PixelRP;
--   * restored pages take fresh ids (>= %d), because a dump id can collide with
--     a page the Builders tab holds - beta parents the default's Bots page
--     (id 9) under Builders, which is what killed the first run of this file.
--     Nothing outside this table keys on a page id; `page_link` is what the
--     emulator and the frontpage blurbs address pages by, and that is intact.
-- Idempotent: rebuilds the whole non-Builders catalog, safe to re-apply.

-- 1. KEEP set: the Builders tab and every descendant. Resolved live because
--    912364-912375 are data-only pages that exist in no migration. A plain
--    table, not TEMPORARY: MySQL cannot reference a temp table twice in one
--    statement, and the descent below does exactly that.
DROP TABLE IF EXISTS `_catalog_keep`;
CREATE TABLE `_catalog_keep` (`id` INT NOT NULL PRIMARY KEY) ENGINE=InnoDB;
INSERT INTO `_catalog_keep` (`id`)
    SELECT `id` FROM `catalog_pages` WHERE `parent_id` = -1 AND `caption` = 'Builders';
-- Descend one level per statement; the tab is 3 deep, five passes is slack.
INSERT IGNORE INTO `_catalog_keep` (`id`)
    SELECT c.`id` FROM `catalog_pages` c JOIN `_catalog_keep` k ON c.`parent_id` = k.`id`;
INSERT IGNORE INTO `_catalog_keep` (`id`)
    SELECT c.`id` FROM `catalog_pages` c JOIN `_catalog_keep` k ON c.`parent_id` = k.`id`;
INSERT IGNORE INTO `_catalog_keep` (`id`)
    SELECT c.`id` FROM `catalog_pages` c JOIN `_catalog_keep` k ON c.`parent_id` = k.`id`;
INSERT IGNORE INTO `_catalog_keep` (`id`)
    SELECT c.`id` FROM `catalog_pages` c JOIN `_catalog_keep` k ON c.`parent_id` = k.`id`;
INSERT IGNORE INTO `_catalog_keep` (`id`)
    SELECT c.`id` FROM `catalog_pages` c JOIN `_catalog_keep` k ON c.`parent_id` = k.`id`;

-- Club and Turfs (section 3) live under Builders once this has run, so a re-run
-- finds them in the KEEP set and would then collide with itself. Everything
-- this file generates is id >= %d and nothing else ever is, so lift that range
-- back out: the wipe clears the previous run's copies and rebuilds them.
DELETE FROM `_catalog_keep` WHERE `id` >= %d;

-- 2. Wipe everything else, orphaned items (rows whose page no longer exists)
--    included.
DELETE FROM `catalog_items` WHERE `page_id` NOT IN (SELECT `id` FROM `_catalog_keep`);
DELETE FROM `catalog_pages` WHERE `id` NOT IN (SELECT `id` FROM `_catalog_keep`);

-- 3. Two pages join the Builders tab, holding stock that used to sit in Furni:
--    Club (the old PixelRP Club - Buy Club, Club Shop, HC Executive) and Turfs
--    (the old Group Furni). Parent and order are resolved live, because every
--    page under Builders is data-only. Club goes under Cartier; Turfs goes
--    above Bots, wherever in the tab Bots has been put.
SET @builders := COALESCE(
    (SELECT `id` FROM `catalog_pages` WHERE `parent_id` = -1 AND `caption` = 'Builders' LIMIT 1),
    912362);
SET @cartier_order := (SELECT `order_num` FROM `catalog_pages`
                       WHERE `parent_id` = @builders AND `caption` = 'Cartier' LIMIT 1);
SET @bots := (SELECT p.`id` FROM `catalog_pages` p JOIN `_catalog_keep` k ON k.`id` = p.`id`
              WHERE p.`caption` = 'Bots' LIMIT 1);
SET @bots_parent := (SELECT `parent_id` FROM `catalog_pages` WHERE `id` = @bots);
SET @bots_order := (SELECT `order_num` FROM `catalog_pages` WHERE `id` = @bots);
INSERT INTO `catalog_pages`
    (`id`,`parent_id`,`caption`,`icon_image`,`min_rank`,`min_vip`,`order_num`,`page_link`,
     `page_layout`,`page_strings_1`,`page_strings_2`,`visible`,`enabled`)
VALUES
%s

-- 4. Stage the default catalog, then move it across filtered against the KEEP
--    set, so nothing the Builders tab holds can be clobbered or duplicated by
--    id no matter what it has been re-parented to hold.
DROP TABLE IF EXISTS `_catalog_new_pages`;
DROP TABLE IF EXISTS `_catalog_new_items`;
CREATE TABLE `_catalog_new_pages` LIKE `catalog_pages`;
CREATE TABLE `_catalog_new_items` LIKE `catalog_items`;

-- 5. The default pages. `visible`/`enabled` are bit(1) here (11_ChangeCatalog
--    PagesEnumToBit moved them to the end of the row), so these are written by
--    name, never positionally like the dump.
""" % (PAGE_BASE, PAGE_BASE, PAGE_BASE, builders_sql))
    for p in kept_pages:
        icon = ICON_FIX.get(p['id'], p['icon_image'])
        o.write(
            "INSERT INTO `_catalog_new_pages` (`id`,`parent_id`,`caption`,`icon_image`,`min_rank`,"
            "`min_vip`,`order_num`,`page_link`,`page_layout`,`page_strings_1`,`page_strings_2`,"
            "`visible`,`enabled`) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,b'%s',b'%s');\n" % (
                page_id[p['id']], page_id.get(p['parent_id'], p['parent_id']),
                esc(rebrand(p['caption'])), icon,
                p['min_rank'], p['min_vip'], p['order_num'],
                esc(p['page_link']), esc(p['page_layout']),
                esc(rebrand(p['page_strings_1'])), esc(rebrand(p['page_strings_2'])),
                p['visible'], p['enabled']))

    o.write("\n-- 6. The default items, duckets folded into credits and priced in coins only.\n"
            "--    No explicit ids: AUTO_INCREMENT hands out values above anything Builders\n"
            "--    kept, which is one more id collision that cannot happen.\n")
    head = ("INSERT INTO `_catalog_new_items` (`page_id`,`item_id`,`catalog_name`,`cost_credits`,"
            "`cost_pixels`,`cost_diamonds`,`amount`,`limited_sells`,`limited_stack`,`offer_active`,"
            "`extradata`,`badge`,`offer_id`) VALUES\n")
    for n, it in enumerate(kept_items):
        if n % 250 == 0:
            o.write(head)
        credits = int(it['cost_credits']) + int(it['cost_pixels'])
        o.write("(%s,%s,%s,%d,0,%s,%s,%s,%s,%s,%s,%s,%s)%s\n" % (
            page_id[it['page_id']], esc(it['item_id']), esc(rebrand(it['catalog_name'])),
            credits, it['cost_diamonds'], it['amount'], it['limited_sells'],
            it['limited_stack'], esc(it['offer_active']), esc(it['extradata']),
            esc(it['badge']), it['offer_id'],
            ';' if (n % 250 == 249 or n == len(kept_items) - 1) else ','))

    o.write("""
-- 7. Move the staged catalog in, KEEP set excluded on both tables.
INSERT INTO `catalog_pages`
    (`id`,`parent_id`,`caption`,`icon_image`,`min_rank`,`min_vip`,`order_num`,`page_link`,
     `page_layout`,`page_strings_1`,`page_strings_2`,`visible`,`enabled`)
SELECT `id`,`parent_id`,`caption`,`icon_image`,`min_rank`,`min_vip`,`order_num`,`page_link`,
       `page_layout`,`page_strings_1`,`page_strings_2`,`visible`,`enabled`
FROM `_catalog_new_pages` WHERE `id` NOT IN (SELECT `id` FROM `_catalog_keep`);
INSERT INTO `catalog_items`
    (`page_id`,`item_id`,`catalog_name`,`cost_credits`,`cost_pixels`,`cost_diamonds`,`amount`,
     `limited_sells`,`limited_stack`,`offer_active`,`extradata`,`badge`,`offer_id`)
SELECT `page_id`,`item_id`,`catalog_name`,`cost_credits`,`cost_pixels`,`cost_diamonds`,`amount`,
       `limited_sells`,`limited_stack`,`offer_active`,`extradata`,`badge`,`offer_id`
FROM `_catalog_new_items` WHERE `page_id` NOT IN (SELECT `id` FROM `_catalog_keep`);
DROP TABLE `_catalog_new_pages`;
DROP TABLE `_catalog_new_items`;

-- 8. The Jukebox moves to Builders > Corporations > Cafe (resolved by caption:
--    those pages are data-only). The catalog row is all that moves - the
--    furniture row and its interaction are untouched, so a placed jukebox keeps
--    playing audio.
SET @builders := (SELECT `id` FROM `catalog_pages` WHERE `parent_id` = -1 AND `caption` = 'Builders' LIMIT 1);
SET @corps    := (SELECT `id` FROM `catalog_pages` WHERE `parent_id` = @builders AND `caption` = 'Corporations' LIMIT 1);
SET @cafe     := (SELECT `id` FROM `catalog_pages` WHERE `parent_id` = @corps AND (`caption` = 'Cafe' OR `caption` LIKE 'Caf_') LIMIT 1);
-- Degrade gracefully - Cafe, else Corporations, else the Builders root, else
-- the restored default home (Staff > Other Furni > System) - so the Jukebox is
-- always buyable somewhere, even where Builders lacks those data-only pages.
SET @system   := (SELECT p.`id` FROM `catalog_pages` p JOIN `catalog_pages` par ON par.`id` = p.`parent_id`
                  WHERE p.`caption` = 'System' AND par.`caption` = 'Other Furni' LIMIT 1);
SET @cafe     := COALESCE(@cafe, @corps, @builders, @system);
SET @jukebox  := (SELECT `id` FROM `furniture` WHERE `item_name` = 'jukebox*1' LIMIT 1);
DELETE FROM `catalog_items` WHERE `item_id` = CAST(@jukebox AS CHAR);
INSERT INTO `catalog_items`
    (`page_id`,`item_id`,`catalog_name`,`cost_credits`,`cost_pixels`,`cost_diamonds`,
     `amount`,`limited_sells`,`limited_stack`,`offer_active`,`extradata`,`badge`,`offer_id`)
SELECT @cafe, CAST(@jukebox AS CHAR), 'Jukebox', 5, 0, 0, 1, 0, 0, '1', '', '', -1
FROM DUAL WHERE @cafe IS NOT NULL AND @jukebox IS NOT NULL;

-- 9. Sweeps. Duckets are hotel-wide policy, so this one covers Builders too - a
--    price update cannot restructure the tab. The clothing sweep is a net under
--    the generation-time filter and does leave Builders alone (its Corporations
--    > Clothing page sells dressing booths, not clothing boxes).
UPDATE `catalog_items` SET `cost_credits` = `cost_credits` + `cost_pixels`, `cost_pixels` = 0
    WHERE `cost_pixels` > 0;
DELETE ci FROM `catalog_items` ci
    JOIN `furniture` f ON f.`id` = CAST(ci.`item_id` AS UNSIGNED)
    WHERE (f.`item_name` LIKE 'clothing\\_%' OR f.`interaction_type` = 'purchasable_clothing')
      AND ci.`page_id` NOT IN (SELECT `id` FROM `_catalog_keep`);

DROP TABLE `_catalog_keep`;
""")

print('pages: %d of %d (dropped %d: Builders Club + clothing-only)'
      % (len(kept_pages), len(pages), len(pages) - len(kept_pages)))
print('items: %d of %d (dropped %d off-page/orphan, %d clothing, %d jukebox relocated)'
      % (len(kept_items), len(items), dropped['page'], dropped['clothing'], dropped['jukebox']))
print('de-ducketed at generation: %d rows' % sum(1 for i in kept_items if int(i['cost_pixels']) > 0))
