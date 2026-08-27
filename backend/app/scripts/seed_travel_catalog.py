"""Seed a comparison-ready travel catalog.

Run with: ``poetry run python -m app.scripts.seed_travel_catalog``.
The seed is idempotent: records are matched by their stable ``TRAVEL-*`` SKU.
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


# sku, type, brand, model, price, key specification, feature summary, best for,
# colour options, capacity / dimensions, image URL, badge
TRAVEL_PRODUCTS = [
    ("TRAVEL-001", "Cabin Luggage", "American Tourister", 'Curio 20-inch', "429.00", "20-inch, ~35 L", "Polycarbonate shell, TSA lock and four spinner wheels.", "Short trips", ["Black", "Rose Gold", "Navy"], "55 × 36 × 23 cm", "https://images.unsplash.com/photo-1553531889-56c31ff2f1ce?auto=format&fit=crop&w=900&q=85", "hot"),
    ("TRAVEL-002", "Cabin Luggage", "Xiaomi", '20-inch Carry-On', "299.00", "20-inch, ~36 L", "Lightweight polycarbonate shell, TSA lock and 360° wheels.", "Budget travellers", ["Space Gray", "Silver", "Blue"], "55 × 37 × 22 cm", "https://images.unsplash.com/photo-1522199710521-72d69614c702?auto=format&fit=crop&w=900&q=85", "sale"),
    ("TRAVEL-003", "Medium Luggage", "Samsonite", 'Upscape 25-inch', "799.00", "25-inch, ~70 L", "Expandable shock-resistant shell with TSA lock.", "5–7 day trips", ["Black", "Climbing Ivy", "Blue Nights"], "68 × 47 × 28 cm", "https://images.unsplash.com/photo-1581553680321-4fffae59fccd?auto=format&fit=crop&w=900&q=85", None),
    ("TRAVEL-004", "Large Luggage", "American Tourister", 'Maxivo 28-inch', "599.00", "28-inch, ~100 L", "Expandable four-wheel spinner with TSA lock.", "Long vacations", ["Graphite", "Deep Blue", "Burgundy"], "78 × 52 × 31 cm", "https://images.unsplash.com/photo-1565026057447-bc90a3dceb87?auto=format&fit=crop&w=900&q=85", "sale"),
    ("TRAVEL-005", "Travel Backpack", "Thule", "Aion 28L", "699.00", "28 L", "Water-resistant carry-on backpack with laptop compartment and expandable section.", "Premium carry-on travel", ["Nutria Brown", "Black"], "47 × 28 × 23 cm", "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=900&q=85", "new"),
    ("TRAVEL-006", "Travel Backpack", "CabinZero", "Classic 36L", "399.00", "36 L", "Lightweight cabin-friendly backpack with lockable zips.", "Budget airlines", ["Absolute Black", "Navy", "Georgian Khaki"], "45 × 31 × 20 cm", "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=900&q=85", None),
    ("TRAVEL-007", "Laptop Travel Backpack", "Samsonite", "GuardIT 2.0", "269.00", "15.6-inch laptop fit", "Organiser pockets and padded shoulder straps for business essentials.", "Work travel", ["Black", "Iron Gray"], "44 × 30 × 20 cm", "https://images.unsplash.com/photo-1491637639811-60e2756cc1c7?auto=format&fit=crop&w=900&q=85", None),
    ("TRAVEL-008", "Packable Daypack", "Decathlon", "NH Escape 16L", "69.00", "16 L", "Lightweight packable daypack with bottle pockets.", "Sightseeing", ["Black", "Sage Green", "Sand"], "40 × 28 × 15 cm", "https://images.unsplash.com/photo-1622260614153-03223fb72052?auto=format&fit=crop&w=900&q=85", "sale"),
    ("TRAVEL-009", "Packing Organiser", "BAGSMART", "6-Piece Packing Cubes Set", "79.00", "Six sizes", "Mesh panels and compression zips keep luggage organised.", "Organising luggage", ["Black", "Beige", "Dusty Blue"], "6-piece set", "https://images.unsplash.com/photo-1585914924626-15adac1e6402?auto=format&fit=crop&w=900&q=85", None),
    ("TRAVEL-010", "Packing Organiser", "Eagle Creek", "Pack-It Isolate Compression Set", "189.00", "Compression design", "Lightweight ripstop compression cubes for maximising luggage space.", "Maximising luggage space", ["Black", "Blue Dawn", "Sahara"], "3-piece set", "https://images.unsplash.com/photo-1553531889-56c31ff2f1ce?auto=format&fit=crop&w=900&q=85", "new"),
    ("TRAVEL-011", "Universal Travel Adapter", "UGREEN", "65W Travel Adapter", "169.00", "65 W USB-C PD", "Multi-country plugs with USB-C PD and USB-A charging.", "Laptop and phone charging", ["Black", "White"], "Universal plug format", "https://images.unsplash.com/photo-1583863788434-e58a36330cf0?auto=format&fit=crop&w=900&q=85", "hot"),
    ("TRAVEL-012", "Universal Travel Adapter", "Baseus", "20W Travel Adapter", "79.00", "20 W output", "Universal sockets with USB-C and USB-A ports.", "Phones and accessories", ["Black", "White"], "Universal plug format", "https://images.unsplash.com/photo-1583863788434-e58a36330cf0?auto=format&fit=crop&w=900&q=85", "sale"),
    ("TRAVEL-013", "Power Bank", "Anker", "737 24,000mAh", "599.00", "24,000 mAh, 140 W", "High-output USB-C power bank with a status display and laptop charging.", "Heavy users", ["Black", "Silver"], "24,000 mAh", "https://images.unsplash.com/photo-1609592424824-7c2dcea7a2c5?auto=format&fit=crop&w=900&q=85", "hot"),
    ("TRAVEL-014", "Power Bank", "Xiaomi", "10,000mAh 22.5W", "89.00", "10,000 mAh, 22.5 W", "Compact fast-charging power bank.", "Day trips", ["Midnight Blue", "Silver"], "10,000 mAh", "https://images.unsplash.com/photo-1609592424824-7c2dcea7a2c5?auto=format&fit=crop&w=900&q=85", None),
    ("TRAVEL-015", "Power Bank", "Baseus", "Blade 20,000mAh 100W", "299.00", "20,000 mAh, 100 W", "Slim USB-C PD power bank with a digital display for laptop travel.", "Laptop travel", ["Black", "Blue"], "20,000 mAh", "https://images.unsplash.com/photo-1609592424824-7c2dcea7a2c5?auto=format&fit=crop&w=900&q=85", "new"),
    ("TRAVEL-016", "GaN Charger", "UGREEN", "Nexode 65W", "139.00", "65 W GaN", "Compact charger with two USB-C ports and one USB-A port.", "Multi-device travellers", ["Space Gray", "White"], "65 W maximum output", "https://images.unsplash.com/photo-1583863788434-e58a36330cf0?auto=format&fit=crop&w=900&q=85", None),
    ("TRAVEL-017", "GaN Charger", "Anker", "735 65W", "229.00", "65 W", "Compact three-port charger with two USB-C and one USB-A port.", "Premium charging", ["Black", "White"], "65 W maximum output", "https://images.unsplash.com/photo-1583863788434-e58a36330cf0?auto=format&fit=crop&w=900&q=85", "hot"),
    ("TRAVEL-018", "Charging Cable", "Anker", "543 USB-C Cable", "49.00", "1.8 m, 100 W", "Braided USB-C cable built for laptop and phone charging.", "Laptop and phone", ["Black", "White", "Blue"], "1.8 m", "https://images.unsplash.com/photo-1558050032-160f36233a07?auto=format&fit=crop&w=900&q=85", None),
    ("TRAVEL-019", "Travel Pillow", "Cabeau", "Evolution S3", "249.00", "Memory foam", "Support straps, washable cover and contoured neck support.", "Long-haul flights", ["Charcoal", "Navy", "Berry"], "One size", "https://images.unsplash.com/photo-1542296332-2e4473faf563?auto=format&fit=crop&w=900&q=85", "new"),
    ("TRAVEL-020", "Travel Pillow", "Decathlon", "Travel 100", "39.00", "Compact foam", "Lightweight foam travel pillow for occasional journeys.", "Budget travel", ["Gray", "Blue"], "One size", "https://images.unsplash.com/photo-1542296332-2e4473faf563?auto=format&fit=crop&w=900&q=85", "sale"),
    ("TRAVEL-021", "Sleep Accessory", "Manta", "Sleep Mask", "199.00", "Full blackout", "Adjustable eye cups and a washable design prevent light pressure.", "Long flights", ["Black", "Slate Blue"], "Adjustable fit", "https://images.unsplash.com/photo-1510414842594-a61c69b5ae57?auto=format&fit=crop&w=900&q=85", None),
    ("TRAVEL-022", "Travel Blanket", "Cocoon", "CoolMax Blanket", "179.00", "Lightweight and breathable", "Packable CoolMax blanket for cool flights and transport.", "Flights and cold transport", ["Navy", "Charcoal", "Teal"], "180 × 140 cm", "https://images.unsplash.com/photo-1452421822248-d4c2b47f0c81?auto=format&fit=crop&w=900&q=85", None),
    ("TRAVEL-023", "Noise-Cancelling Headphones", "Sony", "WH-1000XM5", "1599.00", "~30-hour battery", "Premium ANC headphones with Bluetooth and multipoint pairing.", "Flights and premium travel", ["Black", "Silver", "Midnight Blue"], "Over-ear", "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=900&q=85", "hot"),
    ("TRAVEL-024", "Noise-Cancelling Earbuds", "Soundcore", "Liberty 4 NC", "399.00", "~10-hour earbud battery", "Compact ANC earbuds with a charging case.", "Mid-range travel", ["Black", "White", "Sky Blue"], "In-ear", "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?auto=format&fit=crop&w=900&q=85", None),
    ("TRAVEL-025", "Toiletry Organiser", "BAGSMART", "Hanging Toiletry Bag", "89.00", "Hanging hook", "Water-resistant compartments and multiple pockets for hotel stays.", "Hotel stays", ["Black", "Blush Pink", "Navy"], "Folded: 25 × 18 × 9 cm", "https://images.unsplash.com/photo-1583947582886-f40ec95dd752?auto=format&fit=crop&w=900&q=85", None),
    ("TRAVEL-026", "Toiletry Bottles", "MUJI", "Refillable Bottle Set", "49.00", "TSA-friendly sizes", "Refillable bottles in multiple carry-on compliant sizes.", "Carry-on liquids", ["Clear", "Frosted White"], "6-piece set, 30–100 ml", "https://images.unsplash.com/photo-1556228578-8c89e6adf883?auto=format&fit=crop&w=900&q=85", "sale"),
    ("TRAVEL-027", "Luggage Scale", "Etekcity", "EL11", "59.00", "Up to 50 kg", "Compact digital luggage scale with clear display.", "Avoiding baggage fees", ["Black", "Silver"], "50 kg capacity", "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?auto=format&fit=crop&w=900&q=85", None),
    ("TRAVEL-028", "Travel Umbrella", "UNIQLO", "Compact Umbrella", "79.00", "UV protection", "Lightweight folding umbrella for city travel.", "City travel", ["Black", "Navy", "Olive", "Beige"], "Folded length: 28 cm", "https://images.unsplash.com/photo-1519692933481-e162a57d6721?auto=format&fit=crop&w=900&q=85", None),
    ("TRAVEL-029", "Portable Water Bottle", "Hydro Flask", "Trail 24oz", "199.00", "~710 ml", "Lightweight insulated stainless-steel bottle for hot climates and outdoor travel.", "Outdoor and hot climates", ["Black", "Alpine", "White"], "710 ml", "https://images.unsplash.com/photo-1602143407151-7111542de6e8?auto=format&fit=crop&w=900&q=85", "new"),
    ("TRAVEL-030", "Luggage Tracker", "Apple", "AirTag", "149.00", "Bluetooth and UWB", "Replaceable-battery tracker for luggage location.", "Luggage tracking", ["White / Silver"], "31.9 mm diameter", "https://images.unsplash.com/photo-1603791440384-56cd371ee9a7?auto=format&fit=crop&w=900&q=85", "hot"),
]

RATINGS = [4.6, 4.1, 4.7, 4.3, 4.8, 4.5, 4.0, 4.2, 4.4, 4.7, 4.5, 3.8, 4.8, 4.2, 4.6, 4.5, 4.7, 4.4, 4.6, 3.9, 4.5, 4.1, 4.9, 4.3, 4.4, 4.0, 4.2, 3.0, 4.6, 4.8]
REVIEW_COUNTS = [318, 207, 184, 126, 242, 391, 104, 287, 453, 169, 322, 88, 641, 510, 226, 305, 417, 692, 172, 94, 205, 133, 1287, 476, 385, 218, 143, 109, 257, 842]
INVENTORY = [28, 45, 16, 22, 19, 38, 34, 61, 76, 31, 41, 58, 14, 66, 29, 47, 32, 94, 25, 73, 46, 35, 18, 52, 63, 81, 57, 49, 26, 67]

EMOJI_BY_TYPE = {
    "Cabin Luggage": "🧳", "Medium Luggage": "🧳", "Large Luggage": "🧳", "Travel Backpack": "🎒", "Laptop Travel Backpack": "🎒", "Packable Daypack": "🎒",
    "Packing Organiser": "🗂️", "Universal Travel Adapter": "🔌", "Power Bank": "🔋", "GaN Charger": "🔌", "Charging Cable": "🔗", "Travel Pillow": "🛏️",
    "Sleep Accessory": "😴", "Travel Blanket": "🧣", "Noise-Cancelling Headphones": "🎧", "Noise-Cancelling Earbuds": "🎧", "Toiletry Organiser": "🧴", "Toiletry Bottles": "🧴",
    "Luggage Scale": "⚖️", "Travel Umbrella": "☂️", "Portable Water Bottle": "💧", "Luggage Tracker": "📍",
}


def run() -> int:
    with SessionLocal() as db:
        sellers: dict[str, Seller] = {}
        categories: dict[str, Category] = {}
        for position, item in enumerate(TRAVEL_PRODUCTS):
            sku, type_name, brand, model, price, key_spec, features, best_for, colors, capacity, image_url, badge = item
            seller_name = f"{brand} Travel Store"
            seller_slug = slugify(seller_name)
            seller = sellers.get(seller_slug) or db.scalar(select(Seller).where(Seller.slug == seller_slug))
            if seller is None:
                seller = Seller(name=seller_name, slug=seller_slug, description=f"Travel catalogue profile for {brand}.", status=SellerStatus.ACTIVE)
                db.add(seller)
                db.flush()
            else:
                seller.status = SellerStatus.ACTIVE
            sellers[seller_slug] = seller

            category_slug = slugify(type_name)
            category = categories.get(category_slug) or db.scalar(select(Category).where(Category.slug == category_slug))
            if category is None:
                category = Category(name=type_name, slug=category_slug, description=f"Travel essentials: {type_name}.", sort_order=600 + position, is_active=True)
                db.add(category)
                db.flush()
            categories[category_slug] = category

            product = db.scalar(select(Product).where(Product.sku == sku))
            compare_at_price = (Decimal(price) * Decimal("1.12")).quantize(Decimal("0.01")) if badge == "sale" else None
            values = {
                "seller": seller,
                "category": category,
                "slug": slugify(f"{brand} {model}"),
                "name": f"{brand} {model}",
                "brand": brand,
                "description": f"{features} Designed for {best_for.lower()}.",
                "price": Decimal(price),
                "compare_at_price": compare_at_price,
                "currency": "MYR",
                "status": ProductStatus.ACTIVE,
                "badge": ProductBadge(badge) if badge else None,
                "inventory_quantity": INVENTORY[position],
                "reserved_quantity": 0,
                "emoji": EMOJI_BY_TYPE[type_name],
                "specs": [
                    {"label": "Travel type", "value": type_name},
                    {"label": "Key specification", "value": key_spec},
                    {"label": "Capacity / dimensions", "value": capacity},
                    {"label": "Key features", "value": features},
                    {"label": "Best for", "value": best_for},
                    {"label": "Colour options", "value": ", ".join(colors)},
                    {"label": "Configuration note", "value": "Regional variants and included accessories may differ; verify the seller listing before purchase."},
                ],
                "attributes": {
                    "department": "travel",
                    "travel_type": type_name.lower(),
                    "key_specification": key_spec,
                    "capacity_or_dimensions": capacity,
                    "features": features,
                    "best_for": best_for,
                    "colors": colors,
                    "regional_variant_note": True,
                },
                "rating_average": Decimal(str(RATINGS[position])),
                "review_count": REVIEW_COUNTS[position],
                "published_at": datetime.now(timezone.utc),
            }
            if product is None:
                product = Product(sku=sku, **values)
                db.add(product)
            else:
                for field, value in values.items():
                    setattr(product, field, value)
            db.flush()
            primary_image = min(product.images, key=lambda image: image.sort_order) if product.images else None
            if primary_image is None:
                product.images.append(ProductImage(url=image_url, alt_text=f"{brand} {model}", sort_order=0))
            else:
                primary_image.url = image_url
                primary_image.alt_text = f"{brand} {model}"
                primary_image.sort_order = 0
        db.commit()
    print(f"Travel catalog seed complete: {len(TRAVEL_PRODUCTS)} products upserted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
