"""Seed an idempotent apparel catalog alongside the main product catalog.

Run with: ``poetry run python -m app.scripts.seed_apparel_catalog``
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


# Each entry deliberately exposes variants as both displayable specs and
# machine-readable attributes so catalog search and the shopping agent can use
# colors, materials, fits, and size ranges as verified product facts.
APPAREL_PRODUCTS = [
    ("APPAREL-001", "Linen Ease Camp Collar Shirt", "Harbor & Thread", "Shirts", "Harbor & Thread Menswear", "129.00", "Linen-blend short-sleeve shirt with a relaxed resort fit.", "Linen 55%, cotton 45%", "Relaxed", "S-XXL", ["Sand", "Sage", "Sky Blue"], "https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?auto=format&fit=crop&w=900&q=85", "new"),
    ("APPAREL-002", "Everyday Heavyweight Tee", "Harbor & Thread", "T-Shirts", "Harbor & Thread Menswear", "69.00", "Soft heavyweight jersey T-shirt for daily layering.", "Organic cotton", "Regular", "XS-XXL", ["White", "Charcoal", "Rust", "Forest Green"], "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=900&q=85", None),
    ("APPAREL-003", "High Rise Straight Jeans", "Morrow Denim", "Jeans", "Morrow Denim Studio", "189.00", "Structured high-rise denim with a straight leg and cropped ankle.", "Cotton 99%, elastane 1%", "Straight", "24-34", ["Indigo", "Washed Black", "Vintage Blue"], "https://images.unsplash.com/photo-1542272604-787c3835535d?auto=format&fit=crop&w=900&q=85", "hot"),
    ("APPAREL-004", "Relaxed Carpenter Jeans", "Morrow Denim", "Jeans", "Morrow Denim Studio", "199.00", "Roomy carpenter jeans with utility pockets and reinforced seams.", "Cotton denim", "Relaxed", "28-40", ["Mid Blue", "Ecru", "Black"], "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?auto=format&fit=crop&w=900&q=85", None),
    ("APPAREL-005", "Tailored Wide Leg Trousers", "Atelier Nine", "Trousers", "Atelier Nine", "169.00", "Fluid wide-leg trousers with a clean front and adjustable waist tabs.", "Tencel 65%, rayon 35%", "Wide leg", "XS-XL", ["Black", "Stone", "Cocoa"], "https://images.unsplash.com/photo-1594633312681-425c7b97ccd1?auto=format&fit=crop&w=900&q=85", "new"),
    ("APPAREL-006", "Flex Taper Chinos", "Harbor & Thread", "Pants", "Harbor & Thread Menswear", "139.00", "Stretch cotton chinos designed for commuting and weekend wear.", "Cotton 97%, elastane 3%", "Tapered", "28-40", ["Navy", "Khaki", "Olive", "Slate"], "https://images.unsplash.com/photo-1473966968600-fa801b869a1a?auto=format&fit=crop&w=900&q=85", None),
    ("APPAREL-007", "Cloud Knit Cardigan", "Atelier Nine", "Knitwear", "Atelier Nine", "149.00", "Button-front cardigan with a soft brushed finish.", "Recycled polyester 50%, wool 50%", "Relaxed", "XS-XL", ["Cream", "Lilac", "Navy"], "https://images.unsplash.com/photo-1434389677669-e08b4cac3105?auto=format&fit=crop&w=900&q=85", "sale"),
    ("APPAREL-008", "Core Crew Sock 3-Pack", "Stride Supply", "Socks", "Stride Supply", "39.00", "Cushioned everyday crew socks with breathable ribbing.", "Cotton 78%, polyester 19%, elastane 3%", "Crew", "EU 35-46", ["White", "Black", "Heather Gray"], "https://images.unsplash.com/photo-1582966772680-860e372bb558?auto=format&fit=crop&w=900&q=85", None),
    ("APPAREL-009", "Trail Runner 2", "Stride Supply", "Shoes", "Stride Supply", "259.00", "Lightweight trail running shoe with grippy rubber outsole.", "Mesh upper, rubber sole", "True to size", "EU 36-46", ["Black Lime", "Sand Orange", "Cloud Blue"], "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=85", "hot"),
    ("APPAREL-010", "Court Leather Sneaker", "Stride Supply", "Shoes", "Stride Supply", "229.00", "Minimal leather sneaker with padded collar and cupsole.", "Leather upper, rubber sole", "True to size", "EU 36-45", ["White Green", "White Navy", "Black Gum"], "https://images.unsplash.com/photo-1549298916-b41d501d3772?auto=format&fit=crop&w=900&q=85", None),
    ("APPAREL-011", "Packable Rain Shell", "Northline", "Outerwear", "Northline Outdoor", "219.00", "Water-resistant shell that folds into its own pocket.", "Recycled nylon", "Regular", "XS-XXL", ["Moss", "Navy", "Coral"], "https://images.unsplash.com/photo-1548883354-7622d03aca27?auto=format&fit=crop&w=900&q=85", "new"),
    ("APPAREL-012", "Studio Rib Midi Dress", "Atelier Nine", "Dresses", "Atelier Nine", "179.00", "Sleeveless rib-knit midi dress with a soft sculpted fit.", "Viscose 70%, nylon 30%", "Slim", "XS-XL", ["Black", "Wine", "Oat"], "https://images.unsplash.com/photo-1539008835657-9e8e9680c956?auto=format&fit=crop&w=900&q=85", None),
    ("APPAREL-013", "Motion Pocket Leggings", "Pulse Form", "Activewear", "Pulse Form", "119.00", "High-rise training leggings with side phone pockets.", "Nylon 75%, elastane 25%", "Compression", "XS-XXL", ["Black", "Plum", "Deep Teal"], "https://images.unsplash.com/photo-1506629905607-d405b7a30db1?auto=format&fit=crop&w=900&q=85", None),
    ("APPAREL-014", "Everyday Canvas Tote", "Northline", "Accessories", "Northline Outdoor", "59.00", "Sturdy market tote with interior pocket and long shoulder straps.", "Cotton canvas", "One size", "One size", ["Natural", "Navy", "Olive"], "https://images.unsplash.com/photo-1594223274512-ad4803739b7c?auto=format&fit=crop&w=900&q=85", None),
]


def run() -> int:
    with SessionLocal() as db:
        sellers: dict[str, Seller] = {}
        categories: dict[str, Category] = {}
        for position, entry in enumerate(APPAREL_PRODUCTS, start=1):
            sku, name, brand, category_name, seller_name, price, description, material, fit, sizes, colors, image_url, badge = entry
            seller_slug = slugify(seller_name)
            seller = sellers.get(seller_slug) or db.scalar(select(Seller).where(Seller.slug == seller_slug))
            if seller is None:
                seller = Seller(name=seller_name, slug=seller_slug, description=f"Apparel merchant profile for {seller_name}.", status=SellerStatus.ACTIVE)
                db.add(seller)
                db.flush()
            else:
                seller.status = SellerStatus.ACTIVE
            sellers[seller_slug] = seller

            category_slug = slugify(category_name)
            category = categories.get(category_slug) or db.scalar(select(Category).where(Category.slug == category_slug))
            if category is None:
                category = Category(name=category_name, slug=category_slug, description=f"Apparel: {category_name}.", sort_order=100 + position, is_active=True)
                db.add(category)
                db.flush()
            categories[category_slug] = category

            product = db.scalar(select(Product).where(Product.sku == sku))
            values = {
                "seller": seller, "category": category, "slug": slugify(name), "name": name, "brand": brand,
                "description": description, "price": Decimal(price), "compare_at_price": None, "currency": "MYR",
                "status": ProductStatus.ACTIVE, "badge": ProductBadge(badge) if badge else None, "inventory_quantity": 40 + position,
                "reserved_quantity": 0, "emoji": "👕", "specs": [
                    {"label": "Material", "value": material}, {"label": "Fit", "value": fit},
                    {"label": "Size range", "value": sizes}, {"label": "Color variants", "value": ", ".join(colors)},
                    {"label": "Seller", "value": seller_name},
                ],
                "attributes": {"colors": colors, "material": material, "fit": fit, "sizes": sizes, "department": "apparel"},
                "rating_average": Decimal("4.50"), "review_count": 12 + position, "published_at": datetime.now(timezone.utc),
            }
            if product is None:
                product = Product(sku=sku, **values)
                db.add(product)
            else:
                for field, value in values.items():
                    setattr(product, field, value)
            db.flush()
            product.images.clear()
            product.images.append(ProductImage(url=image_url, alt_text=name, sort_order=0))
        db.commit()
    print(f"Apparel catalog seed complete: {len(APPAREL_PRODUCTS)} products upserted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
