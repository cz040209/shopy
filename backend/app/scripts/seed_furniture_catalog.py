"""Seed an idempotent, room-focused furniture catalog.

Run with: ``poetry run python -m app.scripts.seed_furniture_catalog``
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from re import sub

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Category, Product, ProductBadge, ProductImage, ProductStatus, Seller, SellerStatus


def slugify(value: str) -> str:
    return sub(r"(^-|-$)", "", sub(r"[^a-z0-9]+", "-", value.lower()))


# sku, name, brand, category, seller, price, description, materials, dimensions,
# colors, rooms, placement, image, badge
FURNITURE_PRODUCTS = [
    ("FURNITURE-001", "Haven 3-Seat Sofa", "Oak & Loom", "Living Room Seating", "Oak & Loom Home", "1890.00", "Deep, supportive three-seat sofa with removable cushions for a relaxed living room anchor.", "Performance polyester, kiln-dried hardwood", "W 218 × D 91 × H 84 cm", ["Oatmeal", "Moss", "Slate Blue"], ["Living room", "Studio"], "Against a main wall", "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?auto=format&fit=crop&w=900&q=85", "hot"),
    ("FURNITURE-002", "Nook Accent Chair", "Oak & Loom", "Living Room Seating", "Oak & Loom Home", "690.00", "Compact reading chair with rounded arms and a supportive foam seat.", "Bouclé upholstery, solid ash legs", "W 76 × D 78 × H 81 cm", ["Cream", "Terracotta", "Olive"], ["Living room", "Bedroom", "Reading nook"], "Beside a window or floor lamp", "https://images.unsplash.com/photo-1550226891-ef816aed4a98?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-003", "Arc Floor Lamp", "Luma House", "Lighting", "Luma House", "329.00", "Arched floor lamp that brings warm overhead light to a sofa or lounge chair.", "Powder-coated steel, linen shade", "Base Ø 36 × H 178 cm", ["Matte Black", "Brass", "White"], ["Living room", "Bedroom"], "Behind seating", "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=900&q=85", "new"),
    ("FURNITURE-004", "Sable Coffee Table", "Oak & Loom", "Tables", "Oak & Loom Home", "540.00", "Low oval coffee table with softened edges for smaller living rooms.", "Oak veneer, solid rubberwood", "W 120 × D 60 × H 38 cm", ["Natural Oak", "Walnut", "Black"], ["Living room"], "Centered in front of sofa", "https://images.unsplash.com/photo-1532372320572-cda25653a26d?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-005", "Grid Media Console", "Forma Living", "Storage", "Forma Living", "890.00", "Cable-managed TV console with sliding doors and open media shelf.", "Laminated engineered wood, steel pulls", "W 180 × D 42 × H 54 cm", ["Oak", "Walnut", "White"], ["Living room", "Bedroom"], "Below wall-mounted or tabletop TV", "https://images.unsplash.com/photo-1593359677879-a4bb92f829d1?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-006", "Cloudline Area Rug", "Weave Studio", "Rugs", "Weave Studio", "420.00", "Soft low-pile rug that defines a seating zone without overwhelming a small room.", "Wool 60%, recycled polyester 40%", "160 × 230 cm", ["Ivory Sand", "Pebble Gray", "Sage"], ["Living room", "Bedroom"], "Under front legs of seating", "https://images.unsplash.com/photo-1600166898405-da9535204843?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-007", "Frame Full-Length Mirror", "Luma House", "Mirrors & Decor", "Luma House", "359.00", "Tall leaner mirror that adds light and depth to an entryway or bedroom.", "Aluminum frame, safety glass", "W 60 × D 3 × H 170 cm", ["Black", "Brass", "Oak"], ["Bedroom", "Entryway", "Living room"], "Leaning against a wall", "https://images.unsplash.com/photo-1618220179428-22790b461013?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-008", "Platform Queen Bed", "Restwell", "Bedroom Furniture", "Restwell Sleep", "1490.00", "Low-profile queen bed frame with upholstered headboard and hidden center support.", "Linen blend, solid pine", "W 163 × L 214 × H 102 cm", ["Warm Gray", "Oat", "Navy"], ["Bedroom"], "Centered on longest bedroom wall", "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=900&q=85", "hot"),
    ("FURNITURE-009", "Marlow 2-Drawer Nightstand", "Restwell", "Bedroom Furniture", "Restwell Sleep", "319.00", "Slim two-drawer bedside table with soft-close storage and cable notch.", "Oak veneer, solid wood legs", "W 48 × D 40 × H 56 cm", ["Natural Oak", "Walnut", "White"], ["Bedroom"], "Either side of bed", "https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-010", "Quiet Corner Desk", "Forma Living", "Office Furniture", "Forma Living", "649.00", "Compact work desk with drawer, cable tray, and generous laptop surface.", "Oak veneer, powder-coated steel", "W 120 × D 60 × H 75 cm", ["Oak White", "Walnut Black"], ["Home office", "Bedroom", "Living room"], "Against a wall near outlet", "https://images.unsplash.com/photo-1518455027359-f3f8164ba6bd?auto=format&fit=crop&w=900&q=85", "new"),
    ("FURNITURE-011", "Ergo Mesh Task Chair", "Forma Living", "Office Furniture", "Forma Living", "579.00", "Breathable adjustable task chair with lumbar support and height-adjustable arms.", "Mesh, nylon, aluminum base", "W 66 × D 64 × H 98-108 cm", ["Black", "Fog Gray"], ["Home office", "Study"], "At desk", "https://images.unsplash.com/photo-1505843490538-5133c6c6d0e1?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-012", "Ladder Bookcase", "Oak & Loom", "Storage", "Oak & Loom Home", "449.00", "Open five-shelf bookcase for books, baskets, plants, and framed objects.", "Bamboo shelves, steel frame", "W 80 × D 35 × H 185 cm", ["Natural Black", "Walnut Black", "White Oak"], ["Living room", "Home office", "Bedroom"], "Against wall", "https://images.unsplash.com/photo-1594620302200-9a762244a156?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-013", "Round Dining Table for 4", "Forma Living", "Dining Furniture", "Forma Living", "799.00", "Space-efficient round dining table with a pedestal base for easy chair placement.", "MDF veneer top, steel pedestal", "Ø 100 × H 75 cm", ["Oak", "Walnut", "White"], ["Dining room", "Open-plan living"], "Center of dining zone", "https://images.unsplash.com/photo-1617806118233-18e1de247200?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-014", "Cane Dining Chair", "Oak & Loom", "Dining Furniture", "Oak & Loom Home", "249.00", "Lightweight dining chair with curved back and breathable woven cane panel.", "Rubberwood, natural cane", "W 48 × D 53 × H 82 cm", ["Natural", "Black", "Walnut"], ["Dining room", "Desk"], "Around dining table", "https://images.unsplash.com/photo-1503602642458-232111445657?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-015", "Entryway Storage Bench", "Northline Home", "Entryway Furniture", "Northline Home", "479.00", "Padded bench with two open shoe shelves for a tidy entrance.", "Oak veneer, polyester cushion", "W 100 × D 38 × H 48 cm", ["Oak Beige", "Walnut Charcoal"], ["Entryway", "Bedroom"], "Near entry door", "https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-016", "Lift-Top Storage Ottoman", "Northline Home", "Living Room Seating", "Northline Home", "389.00", "Multifunction ottoman with hidden blanket storage and a tray-friendly top.", "Woven polyester, engineered wood", "W 100 × D 55 × H 43 cm", ["Taupe", "Navy", "Olive"], ["Living room", "Bedroom"], "In front of sofa or bed", "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-017", "Breeze Ceiling Fan", "Luma House", "Lighting", "Luma House", "499.00", "Quiet three-blade ceiling fan with dimmable integrated LED light.", "ABS blades, steel motor housing", "Ø 132 × H 32 cm", ["White Oak", "Matte Black", "Brass White"], ["Bedroom", "Living room"], "Ceiling center", "https://images.unsplash.com/photo-1524484485831-a92ffc0de03f?auto=format&fit=crop&w=900&q=85", "new"),
    ("FURNITURE-018", "Plant Stand Trio", "Weave Studio", "Mirrors & Decor", "Weave Studio", "159.00", "Three nesting plant stands for adding layered greenery to unused corners.", "Powder-coated steel", "H 45 / 60 / 75 cm", ["Black", "White", "Terracotta"], ["Living room", "Balcony", "Bedroom"], "Bright corner or window", "https://images.unsplash.com/photo-1485955900006-10f4d324d411?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-019", "Modular Wardrobe Rail", "Northline Home", "Storage", "Northline Home", "699.00", "Open wardrobe with hanging rail, shelves, and fabric drawer for compact bedrooms.", "Powder-coated steel, engineered wood", "W 120 × D 45 × H 180 cm", ["White Oak", "Black Walnut"], ["Bedroom", "Studio"], "Along bedroom wall", "https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?auto=format&fit=crop&w=900&q=85", "sale"),
    ("FURNITURE-020", "Nest Side Table Set", "Weave Studio", "Tables", "Weave Studio", "279.00", "Pair of nesting side tables that can separate for flexible small-room surfaces.", "Tempered glass, powder-coated steel", "Large Ø 45 × H 50 cm; small Ø 35 × H 44 cm", ["Black Smoke", "Brass Clear", "White"], ["Living room", "Bedroom"], "Beside sofa or bed", "https://images.unsplash.com/photo-1494438639946-1ebd1d20bf85?auto=format&fit=crop&w=900&q=85", None),
]


# One additional product for each room-fill type.  The overlap with the core
# catalog is intentional: it gives the planner real price and specification
# alternatives instead of a single forced recommendation per need.
ROOM_FILL_PRODUCTS = [
    ("FURNITURE-021", "Nova Compact 2-Seat Sofa", "Forma Living", "Living Room Seating", "Forma Living", "1290.00", "Apartment-scale two-seat sofa with reversible back cushions and raised legs for easier cleaning.", "Textured polyester, solid eucalyptus frame", "W 168 × D 84 × H 82 cm", ["Pebble Gray", "Forest Green", "Warm Beige"], ["Living room", "Studio"], "Against a main wall", "https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e?auto=format&fit=crop&w=900&q=85", "sale"),
    ("FURNITURE-022", "Elm Lounge Chair", "Oak & Loom", "Living Room Seating", "Oak & Loom Home", "849.00", "Generously padded lounge chair with a low profile, oak armrests and a relaxed reading angle.", "Linen-blend upholstery, solid oak", "W 79 × D 83 × H 76 cm", ["Oat", "Olive", "Rust"], ["Living room", "Bedroom", "Reading nook"], "Beside a floor lamp", "https://images.unsplash.com/photo-1592078615290-033ee584e267?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-023", "Flexi Ergo Office Chair", "Workwell", "Office Furniture", "Workwell Studio", "899.00", "Fully adjustable task chair with synchronized recline, 3D armrests and pronounced lumbar support.", "Mesh back, moulded foam seat, aluminum base", "W 68 × D 66 × H 100-112 cm", ["Graphite", "Fog Gray", "Ocean Blue"], ["Home office", "Study"], "At desk with 70 cm clearance", "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?auto=format&fit=crop&w=900&q=85", "hot"),
    ("FURNITURE-024", "Cora Upholstered Dining Chair", "Weave Studio", "Dining Furniture", "Weave Studio", "329.00", "Supportive dining chair with a curved upholstered back and wipeable performance fabric.", "Performance polyester, rubberwood legs", "W 50 × D 57 × H 80 cm", ["Sand", "Charcoal", "Sage"], ["Dining room", "Home office"], "Around a dining table", "https://images.unsplash.com/photo-1549497538-303791108f95?auto=format&fit=crop&w=900&q=85", "new"),
    ("FURNITURE-025", "Halo Round Coffee Table", "Weave Studio", "Tables", "Weave Studio", "690.00", "Round fluted coffee table with a hidden shelf for remotes and magazines.", "Oak veneer, engineered wood", "Ø 90 × H 38 cm", ["Natural Oak", "Dark Walnut"], ["Living room"], "Centered in front of sofa", "https://images.unsplash.com/photo-1494438639946-1ebd1d20bf85?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-026", "Frame C-Shape Side Table", "Northline Home", "Tables", "Northline Home", "189.00", "Slim C-shape side table that slides under a sofa for a laptop, drink or remote.", "Powder-coated steel, oak veneer top", "W 35 × D 45 × H 60 cm", ["Matte Black", "White Oak", "Walnut"], ["Living room", "Bedroom"], "Tucked beside seating", "https://images.unsplash.com/photo-1530018607912-eff2daa1bac4?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-027", "Harbor Extendable Dining Table", "Oak & Loom", "Dining Furniture", "Oak & Loom Home", "1690.00", "Six-to-eight-seat dining table with a concealed butterfly leaf for flexible hosting.", "Solid rubberwood, oak veneer", "W 160-210 × D 90 × H 75 cm", ["Natural Oak", "Walnut"], ["Dining room", "Open-plan living"], "Center of dining zone", "https://images.unsplash.com/photo-1604578762246-41134e37f9cc?auto=format&fit=crop&w=900&q=85", "hot"),
    ("FURNITURE-028", "Axis Cable-Ready Office Desk", "Workwell", "Office Furniture", "Workwell Studio", "759.00", "Wide work desk with two drawers, a cable grommet and a rear power-strip shelf.", "Laminated MDF, powder-coated steel", "W 140 × D 70 × H 75 cm", ["Oak White", "Walnut Black"], ["Home office", "Study"], "Against a wall near an outlet", "https://images.unsplash.com/photo-1497215728101-856f4ea42174?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-029", "Rise Electric Standing Desk", "Workwell", "Office Furniture", "Workwell Studio", "1599.00", "Dual-motor sit-stand desk with memory presets, anti-collision sensor and integrated cable tray.", "Bamboo top, steel frame", "W 140 × D 70 × H 72-120 cm", ["Natural Bamboo", "Black", "White"], ["Home office", "Study"], "At least 20 cm from wall", "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=900&q=85", "new"),
    ("FURNITURE-030", "Oakline King Bed Frame", "Restwell", "Bedroom Furniture", "Restwell Sleep", "1990.00", "King bed frame with a padded channel-tufted headboard, slatted base and central support legs.", "Bouclé upholstery, solid pine slats", "W 193 × L 214 × H 110 cm", ["Cream", "Warm Gray", "Navy"], ["Bedroom"], "Centered on the longest wall", "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-031", "RestCore Hybrid Queen Mattress", "Restwell", "Bedroom Furniture", "Restwell Sleep", "1299.00", "Medium-firm queen mattress combining pocket springs, responsive foam and a washable cooling cover.", "Pocket springs, memory foam, knit cover", "W 152 × L 190 × H 28 cm", ["White", "Gray Trim"], ["Bedroom"], "On a queen bed frame", "https://images.unsplash.com/photo-1631049307264-da0ec9d70304?auto=format&fit=crop&w=900&q=85", "sale"),
    ("FURNITURE-032", "Drift Open Bedside Table", "Northline Home", "Bedroom Furniture", "Northline Home", "229.00", "Compact bedside table with an open shelf, soft-close drawer and cable pass-through.", "Oak veneer, solid wood legs", "W 42 × D 38 × H 54 cm", ["Natural Oak", "Walnut", "White"], ["Bedroom"], "Either side of bed", "https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-033", "Alder 3-Door Wardrobe", "Northline Home", "Storage", "Northline Home", "1899.00", "Freestanding three-door wardrobe with a full-height hanging rail, shelves and soft-close doors.", "Laminated engineered wood, aluminum rail", "W 150 × D 58 × H 200 cm", ["White Oak", "Walnut", "Matte White"], ["Bedroom"], "Against a clear bedroom wall", "https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?auto=format&fit=crop&w=900&q=85", "new"),
    ("FURNITURE-034", "Loft 6-Shelf Bookcase", "Forma Living", "Storage", "Forma Living", "629.00", "Tall six-shelf bookcase with adjustable shelves for books, storage boxes and display objects.", "Powder-coated steel, MDF veneer shelves", "W 90 × D 34 × H 190 cm", ["Black Oak", "White Oak", "Walnut Black"], ["Living room", "Home office", "Bedroom"], "Anchored against a wall", "https://images.unsplash.com/photo-1594620302200-9a762244a156?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-035", "Linea Sliding Storage Cabinet", "Forma Living", "Storage", "Forma Living", "799.00", "Low storage cabinet with adjustable shelves, sliding doors and a top suitable for framed decor.", "Laminated engineered wood, steel legs", "W 120 × D 40 × H 82 cm", ["Oak", "Walnut", "Matte White"], ["Living room", "Dining room", "Home office"], "Along a wall or behind dining table", "https://images.unsplash.com/photo-1595428774223-ef52624120d2?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-036", "Modu Mobile Drawer Unit", "Workwell", "Office Furniture", "Workwell Studio", "369.00", "Lockable three-drawer mobile pedestal with file drawer and removable pencil tray.", "Powder-coated steel", "W 39 × D 50 × H 60 cm", ["White", "Graphite", "Sage"], ["Home office", "Study"], "Under or beside desk", "https://images.unsplash.com/photo-1593642532744-d377ab507dc8?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-037", "Slate Low TV Console", "Oak & Loom", "Storage", "Oak & Loom Home", "1090.00", "Low-profile TV console with ventilated media bays, sliding doors and rear cable cut-outs.", "Oak veneer, solid rubberwood base", "W 200 × D 42 × H 50 cm", ["Natural Oak", "Walnut", "Black"], ["Living room", "Bedroom"], "Below TV on main wall", "https://images.unsplash.com/photo-1593359677879-a4bb92f829d1?auto=format&fit=crop&w=900&q=85", "hot"),
    ("FURNITURE-038", "Entry Tilt-Out Shoe Cabinet", "Northline Home", "Entryway Furniture", "Northline Home", "549.00", "Slim tilt-out shoe cabinet storing up to 18 pairs without crowding a narrow hallway.", "Laminated engineered wood", "W 90 × D 24 × H 110 cm", ["White", "Oak", "Walnut"], ["Entryway", "Bedroom"], "Near entrance, secured to wall", "https://images.unsplash.com/photo-1600269452121-4f2416e55c28?auto=format&fit=crop&w=900&q=85", "sale"),
    ("FURNITURE-039", "Beacon Reading Floor Lamp", "Luma House", "Lighting", "Luma House", "419.00", "Dimmable floor lamp with an adjustable reading arm and warm 2700K LED bulb included.", "Powder-coated steel, aluminum", "Base Ø 28 × H 155 cm", ["Matte Black", "Brushed Brass", "White"], ["Living room", "Bedroom", "Study"], "Behind or beside seating", "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-040", "Halo Touch Desk Lamp", "Luma House", "Lighting", "Luma House", "159.00", "Touch-dimmable desk lamp with three colour temperatures, USB-C charging port and swivelling head.", "Aluminum, ABS", "Base Ø 16 × H 45 cm", ["White", "Matte Black", "Blush"], ["Home office", "Bedroom"], "Desk or bedside table", "https://images.unsplash.com/photo-1534274988757-a28bf1a57c17?auto=format&fit=crop&w=900&q=85", "new"),
    ("FURNITURE-041", "Aura Glass Pendant Light", "Luma House", "Lighting", "Luma House", "589.00", "Adjustable-height pendant light with an opal glass shade and warm ambient glow.", "Opal glass, brushed steel", "Shade Ø 32 × H 28 cm; drop 40-150 cm", ["Opal Brass", "Smoke Black"], ["Dining room", "Kitchen", "Home office"], "Centered above table or desk", "https://images.unsplash.com/photo-1513506003901-1e6a229e2d15?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-042", "Woven Geo Area Rug", "Weave Studio", "Rugs", "Weave Studio", "699.00", "Dense low-pile geometric rug that softens hard floors and anchors a seating or office zone.", "Wool 70%, recycled polyester 30%", "200 × 300 cm", ["Sand Charcoal", "Sage Ivory", "Terracotta Cream"], ["Living room", "Bedroom", "Home office"], "Under front furniture legs", "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=900&q=85", "hot"),
    ("FURNITURE-043", "Linen Blackout Curtain Pair", "Weave Studio", "Window Treatments", "Weave Studio", "269.00", "Pair of room-darkening curtains with thermal lining, hidden back tabs and generous 1.5× fullness.", "Linen-look polyester, blackout lining", "W 140 × L 240 cm each panel", ["Oatmeal", "Fog Gray", "Navy"], ["Bedroom", "Living room", "Home office"], "Mounted 15 cm above window", "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-044", "Arch Wall Mirror", "Luma House", "Mirrors & Decor", "Luma House", "429.00", "Arched wall mirror with a slim metal frame to reflect daylight in compact rooms.", "Aluminum frame, safety glass", "W 70 × H 100 cm", ["Matte Black", "Brass", "White"], ["Entryway", "Bedroom", "Living room"], "Above a console or dresser", "https://images.unsplash.com/photo-1618220179428-22790b461013?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-045", "Abstract Gallery Wall Art Set", "Canvas Lane", "Mirrors & Decor", "Canvas Lane", "299.00", "Set of three framed abstract prints in muted earth tones, ready to hang with included hardware.", "Giclée paper print, polystyrene frame", "3 × W 40 × H 50 cm", ["Sand Terracotta", "Sage Blue", "Black White"], ["Living room", "Bedroom", "Home office"], "Centered above sofa, bed or desk", "https://images.unsplash.com/photo-1577083552431-6e5fd01988f7?auto=format&fit=crop&w=900&q=85", "new"),
    ("FURNITURE-046", "Fiddle Leaf Fig with Ceramic Pot", "Green Corner", "Mirrors & Decor", "Green Corner", "239.00", "Live indoor fiddle leaf fig supplied in a drainage pot and matte ceramic cover pot.", "Live ficus plant, ceramic pot", "Plant H 100-120 cm; pot Ø 24 cm", ["Green / White Pot", "Green / Charcoal Pot"], ["Living room", "Bedroom", "Home office"], "Bright indirect-light corner", "https://images.unsplash.com/photo-1485955900006-10f4d324d411?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-047", "Terrain Throw Pillow Set", "Weave Studio", "Soft Furnishings", "Weave Studio", "139.00", "Set of two textured 50 cm throw pillows with removable covers and feather-alternative inserts.", "Cotton blend cover, recycled fibre fill", "2 × 50 × 50 cm", ["Rust", "Olive", "Cream", "Navy"], ["Living room", "Bedroom"], "Layered on sofa, lounge chair or bed", "https://images.unsplash.com/photo-1584100936595-c0654b55a2e2?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-048", "Washed Cotton Queen Bedding Set", "Restwell", "Soft Furnishings", "Restwell Sleep", "249.00", "Four-piece queen bedding set with duvet cover, fitted sheet and two pillowcases in breathable washed cotton.", "Cotton 100%, 300 thread count", "Queen: fitted sheet 152 × 190 × 35 cm", ["White", "Sage", "Clay", "Slate Blue"], ["Bedroom"], "On queen bed", "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=900&q=85", "sale"),
    ("FURNITURE-049", "Lift Aluminum Monitor Stand", "Workwell", "Office Accessories", "Workwell Studio", "119.00", "Ventilated desktop riser that raises a monitor or laptop and creates storage space below.", "Anodized aluminum, silicone feet", "W 40 × D 24 × H 11 cm", ["Silver", "Space Gray", "Black"], ["Home office", "Study"], "Centered on desk", "https://images.unsplash.com/photo-1497215728101-856f4ea42174?auto=format&fit=crop&w=900&q=85", None),
    ("FURNITURE-050", "Cable Tidy Extension Hub", "Workwell", "Office Accessories", "Workwell Studio", "89.00", "Six-outlet extension hub with two USB-C ports, overload protection and a weighted cable-management tray.", "Flame-retardant polycarbonate, copper wiring", "W 31 × D 12 × H 4 cm; 2 m cable", ["White", "Black"], ["Home office", "Living room", "Bedroom"], "Under desk or beside media console", "https://images.unsplash.com/photo-1558002038-1055907df827?auto=format&fit=crop&w=900&q=85", "new"),
]

# Stable catalog ratings make product comparisons realistic while keeping this
# idempotent seed deterministic across environments and future reruns.
FURNITURE_RATINGS = {
    "FURNITURE-001": Decimal("4.80"), "FURNITURE-002": Decimal("4.30"),
    "FURNITURE-003": Decimal("4.70"), "FURNITURE-004": Decimal("3.90"),
    "FURNITURE-005": Decimal("4.50"), "FURNITURE-006": Decimal("3.60"),
    "FURNITURE-007": Decimal("4.10"), "FURNITURE-008": Decimal("4.60"),
    "FURNITURE-009": Decimal("3.80"), "FURNITURE-010": Decimal("4.40"),
    "FURNITURE-011": Decimal("4.70"), "FURNITURE-012": Decimal("3.70"),
    "FURNITURE-013": Decimal("3.40"), "FURNITURE-014": Decimal("4.20"),
    "FURNITURE-015": Decimal("3.50"), "FURNITURE-016": Decimal("4.00"),
    "FURNITURE-017": Decimal("4.60"), "FURNITURE-018": Decimal("3.00"),
    "FURNITURE-019": Decimal("3.30"), "FURNITURE-020": Decimal("4.10"),
    "FURNITURE-021": Decimal("4.40"), "FURNITURE-022": Decimal("4.60"),
    "FURNITURE-023": Decimal("4.70"), "FURNITURE-024": Decimal("4.20"),
    "FURNITURE-025": Decimal("4.30"), "FURNITURE-026": Decimal("4.00"),
    "FURNITURE-027": Decimal("4.80"), "FURNITURE-028": Decimal("4.40"),
    "FURNITURE-029": Decimal("4.50"), "FURNITURE-030": Decimal("4.70"),
    "FURNITURE-031": Decimal("4.50"), "FURNITURE-032": Decimal("4.10"),
    "FURNITURE-033": Decimal("4.30"), "FURNITURE-034": Decimal("4.20"),
    "FURNITURE-035": Decimal("4.00"), "FURNITURE-036": Decimal("4.40"),
    "FURNITURE-037": Decimal("4.60"), "FURNITURE-038": Decimal("4.10"),
    "FURNITURE-039": Decimal("4.50"), "FURNITURE-040": Decimal("4.30"),
    "FURNITURE-041": Decimal("4.40"), "FURNITURE-042": Decimal("4.60"),
    "FURNITURE-043": Decimal("4.20"), "FURNITURE-044": Decimal("4.50"),
    "FURNITURE-045": Decimal("4.10"), "FURNITURE-046": Decimal("3.90"),
    "FURNITURE-047": Decimal("4.30"), "FURNITURE-048": Decimal("4.40"),
    "FURNITURE-049": Decimal("4.20"), "FURNITURE-050": Decimal("4.00"),
}

# Review volume and stock are seed facts, not values generated at request time,
# so product ranking has stable, realistic signals across every environment.
FURNITURE_REVIEW_COUNTS = {
    "FURNITURE-021": 142, "FURNITURE-022": 87, "FURNITURE-023": 216, "FURNITURE-024": 63,
    "FURNITURE-025": 98, "FURNITURE-026": 151, "FURNITURE-027": 54, "FURNITURE-028": 127,
    "FURNITURE-029": 73, "FURNITURE-030": 66, "FURNITURE-031": 188, "FURNITURE-032": 109,
    "FURNITURE-033": 47, "FURNITURE-034": 91, "FURNITURE-035": 68, "FURNITURE-036": 84,
    "FURNITURE-037": 105, "FURNITURE-038": 132, "FURNITURE-039": 77, "FURNITURE-040": 164,
    "FURNITURE-041": 58, "FURNITURE-042": 139, "FURNITURE-043": 203, "FURNITURE-044": 71,
    "FURNITURE-045": 44, "FURNITURE-046": 32, "FURNITURE-047": 119, "FURNITURE-048": 176,
    "FURNITURE-049": 246, "FURNITURE-050": 318,
}

FURNITURE_INVENTORY = {
    "FURNITURE-021": 18, "FURNITURE-022": 12, "FURNITURE-023": 29, "FURNITURE-024": 64,
    "FURNITURE-025": 21, "FURNITURE-026": 76, "FURNITURE-027": 9, "FURNITURE-028": 23,
    "FURNITURE-029": 14, "FURNITURE-030": 8, "FURNITURE-031": 34, "FURNITURE-032": 41,
    "FURNITURE-033": 11, "FURNITURE-034": 26, "FURNITURE-035": 19, "FURNITURE-036": 37,
    "FURNITURE-037": 15, "FURNITURE-038": 33, "FURNITURE-039": 42, "FURNITURE-040": 67,
    "FURNITURE-041": 25, "FURNITURE-042": 20, "FURNITURE-043": 83, "FURNITURE-044": 31,
    "FURNITURE-045": 38, "FURNITURE-046": 16, "FURNITURE-047": 93, "FURNITURE-048": 58,
    "FURNITURE-049": 112, "FURNITURE-050": 147,
}


def run() -> int:
    with SessionLocal() as db:
        sellers: dict[str, Seller] = {}
        categories: dict[str, Category] = {}
        for position, entry in enumerate([*FURNITURE_PRODUCTS, *ROOM_FILL_PRODUCTS], start=1):
            sku, name, brand, category_name, seller_name, price, description, materials, dimensions, colors, rooms, placement, image_url, badge = entry
            seller_slug = slugify(seller_name)
            seller = sellers.get(seller_slug) or db.scalar(select(Seller).where(Seller.slug == seller_slug))
            if seller is None:
                seller = Seller(name=seller_name, slug=seller_slug, description=f"Furniture merchant profile for {seller_name}.", status=SellerStatus.ACTIVE)
                db.add(seller); db.flush()
            else:
                seller.status = SellerStatus.ACTIVE
            sellers[seller_slug] = seller
            category_slug = slugify(category_name)
            category = categories.get(category_slug) or db.scalar(select(Category).where(Category.slug == category_slug))
            if category is None:
                category = Category(name=category_name, slug=category_slug, description=f"Furniture: {category_name}.", sort_order=200 + position, is_active=True)
                db.add(category); db.flush()
            categories[category_slug] = category
            product = db.scalar(select(Product).where(Product.sku == sku))
            values = {
                "seller": seller, "category": category, "slug": slugify(name), "name": name, "brand": brand, "description": description,
                "price": Decimal(price), "compare_at_price": None, "currency": "MYR", "status": ProductStatus.ACTIVE,
                "badge": ProductBadge(badge) if badge else None,
                "inventory_quantity": FURNITURE_INVENTORY.get(sku, 15 + position), "reserved_quantity": 0, "emoji": "🛋️",
                "specs": [{"label": "Materials", "value": materials}, {"label": "Dimensions", "value": dimensions}, {"label": "Color variants", "value": ", ".join(colors)}, {"label": "Best rooms", "value": ", ".join(rooms)}, {"label": "Placement", "value": placement}, {"label": "Seller", "value": seller_name}],
                "attributes": {"colors": colors, "materials": materials, "dimensions": dimensions, "rooms": rooms, "placement": placement, "department": "furniture"},
                "rating_average": FURNITURE_RATINGS[sku], "review_count": FURNITURE_REVIEW_COUNTS.get(sku, 20 + position), "published_at": datetime.now(timezone.utc),
            }
            if product is None:
                product = Product(sku=sku, **values); db.add(product)
            else:
                for field, value in values.items(): setattr(product, field, value)
            db.flush()
            # Update the primary image in place on reruns. Clearing and adding
            # a new sort-order-zero row in one flush violates the per-product
            # image ordering constraint in PostgreSQL.
            primary_image = min(product.images, key=lambda item: item.sort_order) if product.images else None
            if primary_image is None:
                product.images.append(ProductImage(url=image_url, alt_text=name, sort_order=0))
            else:
                primary_image.url = image_url
                primary_image.alt_text = name
                primary_image.sort_order = 0
        db.commit()
    print(f"Furniture catalog seed complete: {len(FURNITURE_PRODUCTS) + len(ROOM_FILL_PRODUCTS)} products upserted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
