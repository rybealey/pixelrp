using Plus.HabboHotel.Catalog;
using Plus.HabboHotel.Catalog.Utilities;
using Plus.HabboHotel.Items;
using Plus.HabboHotel.Users.Inventory.Furniture;

static void Check(bool condition, string message)
{
    if (!condition) throw new Exception(message);
}

var root = new CatalogPage { Id = 1, ParentId = -1, Visible = true, Enabled = false };
var shelf = new CatalogPage { Id = 2, ParentId = 1, Visible = true, Enabled = true };
var movedShelf = new CatalogPage { Id = 3, ParentId = 1, Visible = true, Enabled = true };
var chair = new CatalogItem { Id = 100, PageId = 2, OfferId = -1, Amount = 1,
    Definition = new ItemDefinition { Id = 999, SpriteId = 42, Type = ItemType.Floor, ProductType = "s" } };
shelf.Items.Add(chair.Id, chair);
var pages = new List<CatalogPage> { root, shelf, movedShelf };
CatalogItem? Find(bool wall = false, bool staff = true, int rank = 5, int vip = 0) =>
    CatalogLookup.FindFurniture(pages, 42, wall, staff, rank, vip);

Check(Find() == chair, "Missing asset offer IDs must not hide purchasable furniture");
Check(Find(wall: true) == null, "Floor and wall sprite IDs are separate namespaces");
Check(Find(staff: false) == null, "Staff catalog permission must be preserved");
Check(CatalogLookup.FindFurniture(pages, 999, false, true, 5, 0) == null,
    "Locate uses the renderer sprite ID, not the database definition ID");
Check(CatalogLookup.ResolveSelection(shelf, 100) == 100, "Real item ID must be selected");
shelf.ItemOffers.Add(200, chair);
Check(CatalogLookup.ResolveSelection(shelf, 200) == 100, "Legacy offer maps to actual item ID");
Check(CatalogLookup.ResolveSelection(shelf, 500) == -1, "Missing selection must not select another item");

shelf.Visible = false; Check(Find() == null, "Hidden shelf must not resolve"); shelf.Visible = true;
shelf.Enabled = false; Check(Find() == null, "Disabled shelf must not resolve"); shelf.Enabled = true;
root.MinimumRank = 6; Check(Find() == null, "Ancestor permissions must apply"); root.MinimumRank = 0;
root.Visible = false; Check(Find() == null, "Hidden ancestor must not resolve"); root.Visible = true;
shelf.MinimumVip = 2; Check(Find(rank: 1) == null, "VIP restriction must apply"); shelf.MinimumVip = 0;
root.ParentId = 2; Check(Find() == null, "A cyclic tree must terminate without resolving"); root.ParentId = -1;

shelf.Items.Clear(); movedShelf.Items.Add(chair.Id, chair); chair.PageId = 3;
Check(Find()?.PageId == 3, "Moving furniture between catalog pages must update the link");
var soldOut = new CatalogItem { Id = 99, PageId = 2, OfferId = -1, Amount = 1,
    Definition = chair.Definition, IsLimited = true, LimitedEditionStack = 10, LimitedEditionSells = 10 };
shelf.Items.Add(soldOut.Id, soldOut);
Check(Find() == chair, "Prefer available stock over a sold-out duplicate");
movedShelf.Items.Clear(); shelf.Items.Clear();
Check(Find() == null, "Furniture removed from the catalog must have no Buy destination");
Console.WriteLine("Catalog regressions passed: identity, permissions, missing offers, moves, duplicates and selection.");
