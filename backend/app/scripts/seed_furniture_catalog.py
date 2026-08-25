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


def run() -> int:
    with SessionLocal() as db:
        sellers: dict[str, Seller] = {}
        categories: dict[str, Category] = {}
        for position, entry in enumerate(FURNITURE_PRODUCTS, start=1):
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
                "badge": ProductBadge(badge) if badge else None, "inventory_quantity": 15 + position, "reserved_quantity": 0, "emoji": "🛋️",
                "specs": [{"label": "Materials", "value": materials}, {"label": "Dimensions", "value": dimensions}, {"label": "Color variants", "value": ", ".join(colors)}, {"label": "Best rooms", "value": ", ".join(rooms)}, {"label": "Placement", "value": placement}, {"label": "Seller", "value": seller_name}],
                "attributes": {"colors": colors, "materials": materials, "dimensions": dimensions, "rooms": rooms, "placement": placement, "department": "furniture"},
                "rating_average": Decimal("4.60"), "review_count": 20 + position, "published_at": datetime.now(timezone.utc),
            }
            if product is None:
                product = Product(sku=sku, **values); db.add(product)
            else:
                for field, value in values.items(): setattr(product, field, value)
            db.flush(); product.images.clear(); product.images.append(ProductImage(url=image_url, alt_text=name, sort_order=0))
        db.commit()
    print(f"Furniture catalog seed complete: {len(FURNITURE_PRODUCTS)} products upserted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
