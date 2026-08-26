"""Seed a comparison-ready mock car-care catalog.

Run with: ``poetry run python -m app.scripts.seed_car_care_catalog``
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


# These are mock catalog listings. Pack size, finish, application and surface
# compatibility are structured so the agent can build a sensible car-care kit.
# sku, category, brand, name, price, pack, compatible surfaces, feature, use,
# application, durability/frequency, safety/care, image, badge
CAR_CARE_PRODUCTS = [
    ("CAR-001", "Car Shampoo", "Meguiar's", "Gold Class Car Wash Shampoo", "49.00", "1.42 L", "Clear-coated paint, glass and exterior trim", "pH-balanced, high-foam and wax-safe concentrate", "Regular exterior wash", "Dilute 30 ml in 10 L water; wash from top down with a mitt", "Every 1-2 weeks", "Do not wash in direct sun; rinse thoroughly.", "https://images.unsplash.com/photo-1607860108855-64acf2078ed9?auto=format&fit=crop&w=900&q=85", "hot"),
    ("CAR-002", "Car Shampoo", "Turtle Wax", "Hybrid Solutions Ceramic Wash", "59.00", "1.42 L", "Clear-coated paint and exterior trim", "Ceramic polymers for a hydrophobic finish", "Wash plus short-term protection", "Dilute 30 ml in 10 L water; rinse well and dry with microfibre", "Every 2-3 weeks", "Avoid use on hot panels; do not allow product to dry.", "https://images.unsplash.com/photo-1607860108855-64acf2078ed9?auto=format&fit=crop&w=900&q=85", "new"),
    ("CAR-003", "Car Shampoo", "Soft99", "Neutral Creamy Shampoo", "42.00", "1 L", "Coated and waxed paintwork", "Gentle neutral formula with dense foam", "Ceramic-coated vehicles", "Dilute according to label; use a clean wash mitt", "Routine wash", "Rinse fully; keep out of reach of children.", "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?auto=format&fit=crop&w=900&q=85", None),
    ("CAR-004", "Spray Wax", "Meguiar's", "Ultimate Quik Wax", "69.00", "473 ml", "Gloss paint, clear coat and plastic trim", "Fast spray wax with water-beading finish", "Quick maintenance between washes", "Mist one panel at a time and wipe with clean microfibre", "Up to 2-3 weeks", "Do not apply to hot surfaces or unpainted rubber.", "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?auto=format&fit=crop&w=900&q=85", "sale"),
    ("CAR-005", "Paint Protection", "Turtle Wax", "Hybrid Ceramic Spray Coating", "89.00", "500 ml", "Clear-coated paint, glass and exterior plastic", "SiO₂ ceramic protection and water repellency", "Longer-lasting paint protection", "Spray sparingly onto a cool clean panel; level immediately with microfibre", "Up to 3 months per application", "Avoid overspray on brakes and tyres; use gloves.", "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?auto=format&fit=crop&w=900&q=85", "hot"),
    ("CAR-006", "Hard Wax", "Soft99", "Fusso Coat 12 Months", "99.00", "200 g", "Clear-coated paintwork", "Fluoropolymer hard wax with strong water repellency", "Enthusiast detailing and seasonal protection", "Apply an ultra-thin layer to clean dry paint, haze, then buff", "Up to 12 months under suitable conditions", "Ventilate the area; avoid matte or unpainted surfaces.", "https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=900&q=85", "hot"),
    ("CAR-007", "Paint Correction", "Meguiar's", "Ultimate Compound", "75.00", "450 ml", "Clear-coated gloss paint", "Fine abrasive compound for oxidation and light defects", "Paint restoration before protection", "Work a small test area by hand or dual-action polisher, then wipe clean", "Use as needed before wax or coating", "Test first; avoid matte paint and trim.", "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?auto=format&fit=crop&w=900&q=85", None),
    ("CAR-008", "Scratch Treatment", "3M", "Scratch Remover", "39.00", "236 ml", "Clear-coated gloss paint", "Fine abrasive hand-polish compound", "Small scratches and scuffs", "Apply a small amount with a foam applicator, then buff with microfibre", "Spot use only", "Test an inconspicuous area; not for deep scratches through paint.", "https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=900&q=85", None),
    ("CAR-009", "Decontamination", "Mothers", "California Gold Clay Bar Kit", "85.00", "2 × 80 g bars + lubricant", "Gloss paint, glass and chrome", "Lifts bonded surface contaminants", "Pre-wax preparation", "Use with included lubricant on a clean cool surface; knead clay often", "Every 6-12 months as needed", "Discard clay if dropped; do not use on matte paint.", "https://images.unsplash.com/photo-1493238792000-8113da705763?auto=format&fit=crop&w=900&q=85", "new"),
    ("CAR-010", "Tire Care", "Armor All", "Extreme Tire Shine", "35.00", "510 g aerosol", "Rubber tyre sidewalls", "High-gloss spray finish", "Cosmetic tyre finish", "Spray evenly on a clean dry sidewall and allow to dry", "Up to 1-2 weeks", "Keep off tread, brakes and painted surfaces; use outdoors.", "https://images.unsplash.com/photo-1504215680853-026ed2a45def?auto=format&fit=crop&w=900&q=85", None),
    ("CAR-011", "Tire Care", "Meguiar's", "Endurance Tire Gel", "55.00", "473 ml", "Rubber tyre sidewalls", "Long-lasting gel dressing with adjustable sheen", "Premium tyre dressing", "Apply with a tyre applicator; wipe excess before driving", "Up to 3-4 weeks", "Keep off tread and brake components.", "https://images.unsplash.com/photo-1504215680853-026ed2a45def?auto=format&fit=crop&w=900&q=85", "sale"),
    ("CAR-012", "Wheel Cleaner", "Sonax", "Wheel Cleaner Plus", "65.00", "750 ml", "Clear-coated alloy, steel and chrome wheels", "Acid-free brake-dust cleaner with colour-change indicator", "Alloy wheels", "Spray on cool wheels, wait per label, agitate if necessary and rinse", "Every 2-4 weeks", "Do not use on hot wheels; avoid prolonged contact with bare metal.", "https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=900&q=85", "new"),
    ("CAR-013", "Glass Care", "Rain-X", "Original Glass Water Repellent", "45.00", "207 ml", "Exterior automotive glass", "Hydrophobic rain-repellent coating", "Windscreen protection in wet weather", "Apply to clean dry exterior glass, haze, then buff clear", "Reapply every 4-8 weeks", "Exterior glass only; do not use on plastic lenses.", "https://images.unsplash.com/photo-1493238792000-8113da705763?auto=format&fit=crop&w=900&q=85", None),
    ("CAR-014", "Glass Polish", "Soft99", "Glaco Glass Compound Roll On", "48.00", "100 ml", "Exterior windscreen glass", "Roll-on polish to remove oil film and old coating", "Windscreen preparation", "Work onto wet glass, rinse thoroughly and dry before coating", "Before applying glass coating", "Avoid painted surfaces and rubber trim; do not use on plastic.", "https://images.unsplash.com/photo-1493238792000-8113da705763?auto=format&fit=crop&w=900&q=85", None),
    ("CAR-015", "Glass Cleaner", "Meguiar's", "Perfect Clarity Glass Cleaner", "39.00", "710 ml", "Interior and exterior automotive glass", "Streak-free, tint-safe glass cleaner", "Routine glass cleaning", "Spray onto a glass microfibre cloth and wipe in straight passes", "As needed", "Avoid overspray on electronics; use a separate cloth for final buff.", "https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?auto=format&fit=crop&w=900&q=85", None),
    ("CAR-016", "Interior Cleaner", "Armor All", "Multi-Purpose Interior Cleaner", "32.00", "473 ml", "Dashboard, plastic, vinyl and fabric", "Multi-surface cabin cleaner", "General cabin cleaning", "Spray onto cloth, wipe surface, then dry with a clean towel", "Weekly or as needed", "Test colourfastness on fabric; do not saturate electronics.", "https://images.unsplash.com/photo-1525609004556-c46c7d6cf023?auto=format&fit=crop&w=900&q=85", None),
    ("CAR-017", "Interior Detailer", "Turtle Wax", "Inside Job Interior Detailer", "46.00", "500 ml", "Dashboard, interior plastic and vinyl", "UV protection, deodorising and anti-dust finish", "Dashboard and trim maintenance", "Mist on a cloth and wipe evenly; buff dry", "Every 2-4 weeks", "Do not use on steering wheel, pedals, screens or glass.", "https://images.unsplash.com/photo-1525609004556-c46c7d6cf023?auto=format&fit=crop&w=900&q=85", "new"),
    ("CAR-018", "Leather Care", "Chemical Guys", "Leather Cleaner & Conditioner Kit", "95.00", "2 × 473 ml", "Coated automotive leather and vinyl", "Paired cleaner and conditioner", "Leather seats and interior trim", "Clean with a soft brush or cloth, wipe dry, then apply conditioner sparingly", "Every 1-3 months", "Test first; not for suede, nubuck or perforated leather without checking label.", "https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=900&q=85", "hot"),
    ("CAR-019", "Car Vacuum", "Baseus", "A2 Pro Cordless Car Vacuum", "159.00", "70 ml bin", "Carpet, seats, mats and crevices", "Cordless compact vacuum; USB-C charging; multi-nozzle", "Interior cleaning", "Select the suitable nozzle and empty bin after use", "Up to 25 minutes per charge", "Keep dry; do not vacuum liquids, hot ash or sharp debris.", "https://images.unsplash.com/photo-1609521263047-f8f205293f24?auto=format&fit=crop&w=900&q=85", "hot"),
    ("CAR-020", "Tire Inflator", "Xiaomi", "Portable Electric Air Compressor 2", "189.00", "2,000 mAh battery", "Car, motorcycle, bicycle and ball valves with supplied adaptors", "Digital PSI display, auto-stop and rechargeable battery", "Emergency tyre inflation", "Set target pressure, attach securely and start; check vehicle placard for correct PSI", "Recharge as required", "Allow the unit to cool after extended use; do not exceed recommended tyre pressure.", "https://images.unsplash.com/photo-1551830820-330a71b99659?auto=format&fit=crop&w=900&q=85", "new"),
]

RATINGS = [4.6, 4.5, 4.3, 4.6, 4.5, 4.7, 4.4, 4.1, 4.5, 4.2, 4.5, 4.4, 4.3, 4.2, 4.4, 4.1, 4.3, 4.6, 4.4, 4.7]
REVIEWS = [324, 271, 142, 298, 205, 179, 187, 116, 132, 243, 219, 164, 355, 126, 279, 188, 153, 196, 141, 237]
INVENTORY = [83, 64, 51, 57, 43, 29, 48, 72, 31, 96, 68, 45, 89, 53, 102, 77, 59, 36, 25, 41]


def run() -> int:
    with SessionLocal() as db:
        sellers: dict[str, Seller] = {}
        categories: dict[str, Category] = {}
        for position, item in enumerate(CAR_CARE_PRODUCTS):
            sku, category_name, brand, name, price, pack_size, compatible_surfaces, feature, best_for, application, frequency, care, image_url, badge = item
            seller_name = f"{brand} Auto Care"
            seller_slug = slugify(seller_name)
            seller = sellers.get(seller_slug) or db.scalar(select(Seller).where(Seller.slug == seller_slug))
            if seller is None:
                seller = Seller(name=seller_name, slug=seller_slug, description=f"Mock automotive care catalog profile for {brand}.", status=SellerStatus.ACTIVE)
                db.add(seller); db.flush()
            else:
                seller.status = SellerStatus.ACTIVE
            sellers[seller_slug] = seller

            category_slug = slugify(category_name)
            category = categories.get(category_slug) or db.scalar(select(Category).where(Category.slug == category_slug))
            if category is None:
                category = Category(name=category_name, slug=category_slug, description=f"Car care: {category_name}.", sort_order=600 + position, is_active=True)
                db.add(category); db.flush()
            categories[category_slug] = category

            product = db.scalar(select(Product).where(Product.sku == sku))
            values = {
                "seller": seller, "category": category, "slug": slugify(name), "name": name, "brand": brand,
                "description": f"{feature}. Best for {best_for.lower()}.", "price": Decimal(price), "compare_at_price": None, "currency": "MYR",
                "status": ProductStatus.ACTIVE, "badge": ProductBadge(badge) if badge else None, "inventory_quantity": INVENTORY[position], "reserved_quantity": 0, "emoji": "🚗",
                "specs": [
                    {"label": "Product type", "value": category_name}, {"label": "Pack size", "value": pack_size},
                    {"label": "Compatible surfaces", "value": compatible_surfaces}, {"label": "Key features", "value": feature},
                    {"label": "Best for", "value": best_for}, {"label": "Application", "value": application},
                    {"label": "Maintenance interval", "value": frequency}, {"label": "Care and safety", "value": care},
                ],
                "attributes": {"department": "automotive", "car_care_category": category_name, "pack_size": pack_size, "compatible_surfaces": compatible_surfaces, "features": feature, "best_for": best_for, "application": application, "maintenance_interval": frequency, "care": care, "mock_catalog_listing": True},
                "rating_average": Decimal(str(RATINGS[position])), "review_count": REVIEWS[position], "published_at": datetime.now(timezone.utc),
            }
            if product is None:
                product = Product(sku=sku, **values); db.add(product)
            else:
                for field, value in values.items(): setattr(product, field, value)
            db.flush()
            primary_image = min(product.images, key=lambda image: image.sort_order) if product.images else None
            if primary_image is None:
                product.images.append(ProductImage(url=image_url, alt_text=name, sort_order=0))
            else:
                primary_image.url = image_url
                primary_image.alt_text = name
                primary_image.sort_order = 0
        db.commit()
    print(f"Car-care catalog seed complete: {len(CAR_CARE_PRODUCTS)} products upserted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
