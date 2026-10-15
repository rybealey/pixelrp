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
    CatalogLookup.FindFurniture(pages, 42, wall, staff, rank, vip).Item;
CatalogLocateStatus Status(bool wall = false, bool staff = true, int rank = 5, int vip = 0) =>
    CatalogLookup.FindFurniture(pages, 42, wall, staff, rank, vip).Status;

Check(Find() == chair, "Missing asset offer IDs must not hide purchasable furniture");
Check(Find(wall: true) == null, "Floor and wall sprite IDs are separate namespaces");
Check(Find(staff: false) == null, "Staff catalog permission must be preserved");
Check(CatalogLookup.FindFurniture(pages, 999, false, true, 5, 0).Item == null,
    "Locate uses the renderer sprite ID, not the database definition ID");
Check(Status() == CatalogLocateStatus.Found, "A resolved shelf reports itself found");
Check(Status(staff: false) == CatalogLocateStatus.NotPermitted, "The staff-only shop says so rather than going quiet");
Check(Status(wall: true) == CatalogLocateStatus.NotSold, "Nothing selling this sprite reads as unsold");
Check(CatalogLookup.ResolveSelection(shelf, 100) == 100, "Real item ID must be selected");
shelf.ItemOffers.Add(200, chair);
Check(CatalogLookup.ResolveSelection(shelf, 200) == 100, "Legacy offer maps to actual item ID");
Check(CatalogLookup.ResolveSelection(shelf, 500) == -1, "Missing selection must not select another item");

shelf.Visible = false;
Check(Find() == null, "Hidden shelf must not resolve");
Check(Status() == CatalogLocateStatus.NotReachable, "Stock on an unreachable shelf is a shop problem, not an unsold item");
shelf.Visible = true;
shelf.Enabled = false; Check(Find() == null, "Disabled shelf must not resolve"); shelf.Enabled = true;
root.MinimumRank = 6;
Check(Find() == null, "Ancestor permissions must apply");
Check(Status() == CatalogLocateStatus.NotReachable, "An ancestor out of rank puts the shelf out of reach");
root.MinimumRank = 0;

// CHANGED DELIBERATELY. This asked for the opposite, and it was hiding Buy on
// furniture the search box returns. CatalogIndexComposer writes an invisible
// parent into the tree along with its children, getNodeById walks past the
// visible flag, and GetCatalogPageEvent serves the child page - so the link
// lands. Refusing it here removed a working button and nothing else. Ancestors
// are still held to rank and VIP, which DO decide whether the node is written.
root.Visible = false;
Check(Find() == chair, "An invisible ancestor still leaves its shelf linkable");
root.Visible = true;
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
Check(Status() == CatalogLocateStatus.NotSold, "An empty catalog reads as unsold, not as unreachable");

// The two rules answer DIFFERENT questions, and briefly making them one rule
// emptied the search box: this catalog holds stock on pages whose chain to the
// root does not survive the ancestor walk.
//
//   IsOpenable  - can this player BUY from this shelf? The search box's test,
//                 and the only thing GetCatalogPageEvent asks before serving.
//   IsShoppable - can a LINK land on this shelf? Adds the ancestors, because
//                 the navigation tree is built by walking down from a root.
//
// Keep them apart. A search hit only has to be purchasable.
chair.PageId = 2; shelf.Items.Add(chair.Id, chair);
var index = CatalogLookup.Index(pages);
Check(CatalogLookup.IsOpenable(shelf, 5, 0), "A plain shelf is one the shop will serve");
Check(CatalogLookup.IsShoppable(index, shelf, 5, 0), "A plain shelf is also one a link can land on");
root.MinimumRank = 6;
Check(CatalogLookup.IsOpenable(shelf, 5, 0), "An out-of-rank ancestor must NOT hide the shelf from the search box");
Check(!CatalogLookup.IsShoppable(index, shelf, 5, 0), "...but a link still has nowhere to land");
root.MinimumRank = 0;
// A parent_id pointing at a row that is gone ends the walk instead of failing
// it. This catalog is full of them, and refusing hid the Buy button on
// furniture that sells fine - there is no gate above a parent that does not
// exist, and the client loads a page the tree never listed. A CYCLE is still
// refused, which the "cyclic tree" case above covers.
shelf.ParentId = 404;
Check(CatalogLookup.IsOpenable(shelf, 5, 0), "Stock on a shelf orphaned from the tree is still findable and still sells");
Check(CatalogLookup.IsShoppable(index, shelf, 5, 0), "...and is still linkable: a missing parent is no gate");
root.MinimumRank = 9;
Check(CatalogLookup.IsShoppable(index, shelf, 5, 0), "A gate on a page the broken chain never reaches cannot apply");
root.MinimumRank = 0;
shelf.ParentId = 1;
root.MinimumRank = 9;
Check(!CatalogLookup.IsShoppable(index, shelf, 5, 0), "An ancestor the chain DOES reach still gates the link");
root.MinimumRank = 0;

Console.WriteLine("Catalog regressions passed: identity, permissions, reasons, missing offers, moves, duplicates, selection and both shelf rules.");
