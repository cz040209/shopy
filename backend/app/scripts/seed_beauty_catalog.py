"""Seed a structured skincare and makeup catalog.

Run with: ``poetry run python -m app.scripts.seed_beauty_catalog``
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


# sku, category, brand, name, price, size, suitable_for, formula/finish,
# ingredients or key details, function, shade/colour choices, use guidance, image, badge
BEAUTY_PRODUCTS = [
    ("BEAUTY-001", "Skincare", "PureGlow", "PureGlow Gentle Cleanser", "39.00", "150 ml", "Normal, dry and sensitive skin", "Low-foam gel; pH 5.5; fragrance-free", "Ceramides, glycerin", "Daily cleansing without a tight after-feel", ["Clear"], "Use morning and evening on damp skin; rinse well.", "https://images.unsplash.com/photo-1556229010-6c3f2c9ca5f8?auto=format&fit=crop&w=900&q=85", "new"),
    ("BEAUTY-002", "Skincare", "ClearWave", "ClearWave Salicylic Cleanser", "45.00", "120 ml", "Oily and acne-prone skin", "Clarifying gel cleanser; low foam", "1% salicylic acid, betaine", "Helps remove excess oil and daily buildup", ["Clear"], "Begin once daily; avoid the eye area and follow with moisturiser.", "https://images.unsplash.com/photo-1556228720-195a672e8a03?auto=format&fit=crop&w=900&q=85", None),
    ("BEAUTY-003", "Skincare", "HydraRice", "HydraRice Balancing Toner", "42.00", "150 ml", "Normal, combination and dehydrated skin", "Watery, alcohol-free essence toner", "Rice extract, hyaluronic acid", "Adds a first layer of hydration after cleansing", ["Translucent"], "Pat onto clean skin with hands morning and evening.", "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?auto=format&fit=crop&w=900&q=85", None),
    ("BEAUTY-004", "Skincare", "CalmLeaf", "CalmLeaf Centella Toner", "49.00", "150 ml", "Sensitive, reactive and combination skin", "Lightweight, alcohol-free toner", "Centella asiatica, panthenol, allantoin", "Comfort-focused hydration for a simplified routine", ["Translucent"], "Apply after cleansing; patch test before first use.", "https://images.unsplash.com/photo-1611930022073-b7a4ba5fcccd?auto=format&fit=crop&w=900&q=85", "new"),
    ("BEAUTY-005", "Skincare", "BrightDrop", "BrightDrop Vitamin C Serum", "69.00", "30 ml", "Normal, dry and dull-looking skin", "Lightweight water serum", "10% vitamin C derivative, ferulic acid", "Antioxidant serum for a brighter-looking routine", ["Pale Amber"], "Use in the morning, then apply sunscreen; store away from heat.", "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?auto=format&fit=crop&w=900&q=85", "hot"),
    ("BEAUTY-006", "Skincare", "AquaBoost", "AquaBoost HA Serum", "59.00", "30 ml", "All skin types, especially dehydrated skin", "Fast-absorbing water gel serum", "Multi-weight hyaluronic acid, panthenol", "Layerable hydration support", ["Clear"], "Apply to slightly damp skin before moisturiser.", "https://images.unsplash.com/photo-1608248597279-f99d160bfcbc?auto=format&fit=crop&w=900&q=85", None),
    ("BEAUTY-007", "Skincare", "ClearSkin", "ClearSkin Niacinamide Serum", "55.00", "30 ml", "Oily and combination skin", "Lightweight, non-sticky serum", "10% niacinamide, zinc PCA", "Balances the look of shine and uneven texture", ["Clear"], "Use once daily at first; layer under moisturiser.", "https://images.unsplash.com/photo-1556229010-6c3f2c9ca5f8?auto=format&fit=crop&w=900&q=85", None),
    ("BEAUTY-008", "Skincare", "SmoothNight", "SmoothNight Retinol Serum", "89.00", "30 ml", "Experienced retinoid users; normal to dry skin", "Anhydrous night serum", "0.3% retinol, squalane, vitamin E", "Night-time smoothing routine step", ["Pale Yellow"], "Use 2-3 nights weekly at first; use sunscreen daily and avoid combining with strong exfoliants in the same routine.", "https://images.unsplash.com/photo-1608571423902-eed4a5ad8108?auto=format&fit=crop&w=900&q=85", "hot"),
    ("BEAUTY-009", "Skincare", "BarrierFix", "BarrierFix Ceramide Cream", "65.00", "50 ml", "Normal, dry and sensitive skin", "Rich fragrance-free cream", "Ceramides, cholesterol, fatty acids", "Comforting final moisturiser step", ["White"], "Apply after serums, morning and evening as needed.", "https://images.unsplash.com/photo-1571781926291-c477ebfd024b?auto=format&fit=crop&w=900&q=85", None),
    ("BEAUTY-010", "Skincare", "AquaGel", "AquaGel Lightweight Moisturizer", "52.00", "50 ml", "Oily and combination skin", "Oil-free gel cream", "Glycerin, green tea, beta-glucan", "Weightless daily hydration", ["Translucent Blue"], "Smooth over face and neck after serum.", "https://images.unsplash.com/photo-1556228720-195a672e8a03?auto=format&fit=crop&w=900&q=85", None),
    ("BEAUTY-011", "Skincare", "SunGuard", "SunGuard Aqua SPF50+", "48.00", "50 ml", "All skin types", "Lightweight fluid; no white cast", "SPF50+ PA++++ organic UV filters", "Daily broad-spectrum sun protection", ["Invisible Finish"], "Apply generously as the final morning skincare step; reapply according to the label.", "https://images.unsplash.com/photo-1556228578-0d85b1a4d571?auto=format&fit=crop&w=900&q=85", "sale"),
    ("BEAUTY-012", "Skincare", "SunShield", "SunShield Mineral SPF50", "55.00", "50 ml", "Sensitive skin and mineral-sunscreen preference", "Cream; soft satin finish", "Zinc oxide, bisabolol", "Mineral daily sun protection", ["Tinted Beige", "Sheer"], "Shake before use; apply generously and reapply according to the label.", "https://images.unsplash.com/photo-1556228852-80a0f6e5e2b4?auto=format&fit=crop&w=900&q=85", "new"),
    ("BEAUTY-013", "Skincare", "CalmSpot", "CalmSpot Acne Gel", "35.00", "15 ml", "Oily and blemish-prone skin", "Clear targeted gel", "2% salicylic acid, centella asiatica", "Targeted treatment for individual blemish-prone areas", ["Clear"], "Apply a small amount to affected areas; avoid broken skin and eye area.", "https://images.unsplash.com/photo-1598440947619-2c35fc9aa908?auto=format&fit=crop&w=900&q=85", None),
    ("BEAUTY-014", "Skincare", "Overnight Repair", "Overnight Repair Sleeping Mask", "58.00", "70 ml", "Normal, dry and dehydrated skin", "Cushiony leave-on gel mask", "Ceramide complex, panthenol, beta-glucan", "Overnight moisture-sealing step", ["White"], "Use as the final evening step 2-4 times per week.", "https://images.unsplash.com/photo-1570194065650-d99fb4bedf0a?auto=format&fit=crop&w=900&q=85", "sale"),
    ("BEAUTY-015", "Skincare", "GlowClay", "GlowClay Detox Mask", "45.00", "80 g", "Oily and combination skin", "Rinse-off clay mask", "Kaolin, charcoal, glycerin", "Weekly oil-absorbing mask", ["Charcoal Gray"], "Apply a thin layer for 10 minutes once weekly; rinse before fully dry.", "https://images.unsplash.com/photo-1596755389378-c31d21fd1273?auto=format&fit=crop&w=900&q=85", None),
    ("BEAUTY-016", "Makeup", "SkinPerfect", "SkinPerfect Liquid Foundation", "79.00", "30 ml", "Normal and combination skin", "Medium coverage; natural finish", "12 flexible shades; buildable pigment", "Even-looking base makeup", ["12 shades from Fair N to Deep W"], "Apply with fingers, sponge or brush and build in thin layers.", "https://images.unsplash.com/photo-1599733589046-10c005739efb?auto=format&fit=crop&w=900&q=85", "new"),
    ("BEAUTY-017", "Makeup", "MatteLock", "MatteLock Foundation", "85.00", "30 ml", "Oily and combination skin", "Full coverage; soft-matte finish", "Oil-control powders; 10 shades", "Long-wear matte base makeup", ["10 shades from Light N to Deep W"], "Apply sparingly and blend outward; set where preferred.", "https://images.unsplash.com/photo-1599733589046-10c005739efb?auto=format&fit=crop&w=900&q=85", "hot"),
    ("BEAUTY-018", "Makeup", "GlowSkin", "GlowSkin Cushion Foundation", "89.00", "15 g refill", "Normal, dry and combination skin", "Light-medium coverage; dewy finish", "SPF35; moisturizing cushion base; 8 shades", "Quick portable complexion touch-ups", ["8 shades from 01 Porcelain to 08 Honey"], "Press the puff lightly into the cushion and pat onto skin.", "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?auto=format&fit=crop&w=900&q=85", "new"),
    ("BEAUTY-019", "Makeup", "CoverPro", "CoverPro Concealer", "45.00", "6 ml", "All skin types", "Medium-high coverage; natural matte", "Flexible pigments; 10 shades", "Spot and under-eye coverage", ["10 shades from Fair C to Deep N"], "Dot onto areas of coverage and blend promptly.", "https://images.unsplash.com/photo-1631730359585-38a4935cbec4?auto=format&fit=crop&w=900&q=85", None),
    ("BEAUTY-020", "Makeup", "SoftFlush", "SoftFlush Cream Blush", "39.00", "5 g", "All skin types", "Blendable cream; natural finish", "Sheer-to-buildable pigment; 6 shades", "Soft cheek colour", ["Peach", "Rose", "Berry", "Coral", "Mauve", "Terracotta"], "Tap onto cheeks with fingers, sponge or brush.", "https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9?auto=format&fit=crop&w=900&q=85", None),
    ("BEAUTY-021", "Makeup", "VelvetTouch", "VelvetTouch Powder Blush", "42.00", "6 g", "Normal, oily and combination skin", "Powder; matte-to-satin finish", "Finely milled pigment; 8 shades", "Buildable powder cheek colour", ["8 shades from Soft Pink to Cinnamon"], "Sweep lightly over cheeks and blend toward temples.", "https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9?auto=format&fit=crop&w=900&q=85", None),
    ("BEAUTY-022", "Makeup", "GlowBeam", "GlowBeam Highlighter", "49.00", "7 g", "All skin types", "Baked powder; luminous finish", "Light-reflecting pearls; 3 tone options", "Targeted glow on high points", ["Champagne", "Rose Gold", "Warm Gold"], "Apply lightly to cheekbones, brow bone or inner corners.", "https://images.unsplash.com/photo-1512496015851-a90fb38ba796?auto=format&fit=crop&w=900&q=85", "new"),
    ("BEAUTY-023", "Makeup", "SculptEase", "SculptEase Contour Stick", "52.00", "7 g", "All skin types", "Cream stick; natural matte finish", "Blendable emollient base; 4 shades", "Easy cream contour and definition", ["Fair", "Light-Medium", "Medium-Tan", "Deep"], "Apply beneath cheekbones or along the perimeter, then blend.", "https://images.unsplash.com/photo-1591360236480-4ed861025fa1?auto=format&fit=crop&w=900&q=85", None),
    ("BEAUTY-024", "Makeup", "LashLift", "LashLift Volume Mascara", "45.00", "8 ml", "All users seeking volume", "Waterproof volumising mascara", "Buildable black pigment; curved brush", "Defined, fuller-looking lashes", ["Black"], "Wiggle from lash roots to tips; use an eye makeup remover to remove.", "https://images.unsplash.com/photo-1631214540553-30432527a21a?auto=format&fit=crop&w=900&q=85", "hot"),
    ("BEAUTY-025", "Makeup", "LengthPro", "LengthPro Mascara", "42.00", "8 ml", "All users seeking length", "Smudge-resistant lengthening mascara", "Flexible film-forming formula; slim brush", "Separated, lengthened lash look", ["Black", "Brown Black"], "Comb upward from roots to tips; allow each coat to set.", "https://images.unsplash.com/photo-1631214540553-30432527a21a?auto=format&fit=crop&w=900&q=85", None),
    ("BEAUTY-026", "Makeup", "PrecisionLine", "PrecisionLine Eyeliner", "35.00", "0.4 ml", "All eye looks", "Waterproof liquid liner; ultra-fine brush tip", "Carbon-black pigment; quick-dry formula", "Precise lines and winged looks", ["Black", "Brown"], "Shake gently and apply along the lash line; recap firmly.", "https://images.unsplash.com/photo-1583241800698-e8ab01830a14?auto=format&fit=crop&w=900&q=85", None),
    ("BEAUTY-027", "Makeup", "BrowDefine", "BrowDefine Pencil", "32.00", "0.08 g", "All brow types", "Retractable micro-tip pencil with spoolie", "Five neutral brow shades", "Hair-like brow definition", ["Taupe", "Soft Brown", "Medium Brown", "Deep Brown", "Black Brown"], "Use short strokes through sparse areas, then brush with spoolie.", "https://images.unsplash.com/photo-1512496015851-a90fb38ba796?auto=format&fit=crop&w=900&q=85", None),
    ("BEAUTY-028", "Makeup", "VelvetMatte", "VelvetMatte Lipstick", "38.00", "3.5 g", "All lip looks", "Comfortable matte; long-wear finish", "Rich colour payoff; 10 shades", "Velvety matte lip colour", ["10 shades from Nude Rose to Deep Berry"], "Apply directly from bullet; use lip liner for added definition.", "https://images.unsplash.com/photo-1586495777744-4413f21062fa?auto=format&fit=crop&w=900&q=85", "sale"),
    ("BEAUTY-029", "Makeup", "GlassGlow", "GlassGlow Lip Tint", "35.00", "4 ml", "All lip looks", "Glossy lightweight lip tint", "Sheer buildable colour; 8 shades", "Comfortable glossy wash of colour", ["8 shades from Peach Tea to Plum Glass"], "Swipe onto bare lips; layer for more colour.", "https://images.unsplash.com/photo-1586495777744-4413f21062fa?auto=format&fit=crop&w=900&q=85", None),
    ("BEAUTY-030", "Makeup", "ProBlend", "ProBlend Brush Set", "69.00", "10-piece set", "Face and eye makeup users", "Synthetic-fibre face and eye brush set", "Cruelty-free synthetic bristles; travel pouch", "Base, cheek and eye blending tools", ["Black", "Cream", "Rose Gold"], "Wash regularly with mild brush cleanser and dry flat.", "https://images.unsplash.com/photo-1512496015851-a90fb38ba796?auto=format&fit=crop&w=900&q=85", "new"),
]

RATINGS = [4.5, 4.3, 4.2, 4.6, 4.4, 4.5, 4.3, 4.1, 4.7, 4.2, 4.4, 4.3, 4.0, 4.5, 4.2, 4.4, 4.3, 4.5, 4.2, 4.6, 4.4, 4.5, 4.3, 4.4, 4.1, 4.2, 4.4, 4.5, 4.3, 4.6]
REVIEWS = [286, 194, 165, 219, 173, 304, 257, 121, 365, 238, 489, 142, 176, 203, 98, 312, 278, 205, 351, 167, 146, 131, 109, 276, 198, 235, 322, 414, 267, 156]
INVENTORY = [85, 71, 92, 64, 58, 96, 78, 42, 53, 88, 117, 73, 69, 61, 47, 82, 59, 66, 101, 93, 74, 56, 68, 110, 105, 119, 128, 136, 121, 45]


def run() -> int:
    with SessionLocal() as db:
        sellers: dict[str, Seller] = {}
        categories: dict[str, Category] = {}
        for position, item in enumerate(BEAUTY_PRODUCTS):
            sku, category_name, brand, name, price, size, suitable_for, formula, details, function, colours, guidance, image_url, badge = item
            seller_name = f"{brand} Beauty Store"
            seller_slug = slugify(seller_name)
            seller = sellers.get(seller_slug) or db.scalar(select(Seller).where(Seller.slug == seller_slug))
            if seller is None:
                seller = Seller(name=seller_name, slug=seller_slug, description=f"Beauty catalog merchant profile for {brand}.", status=SellerStatus.ACTIVE)
                db.add(seller); db.flush()
            else:
                seller.status = SellerStatus.ACTIVE
            sellers[seller_slug] = seller

            category_slug = slugify(category_name)
            category = categories.get(category_slug) or db.scalar(select(Category).where(Category.slug == category_slug))
            if category is None:
                category = Category(name=category_name, slug=category_slug, description=f"Beauty: {category_name}.", sort_order=500 + position, is_active=True)
                db.add(category); db.flush()
            categories[category_slug] = category

            product = db.scalar(select(Product).where(Product.sku == sku))
            values = {
                "seller": seller, "category": category, "slug": slugify(name), "name": name, "brand": brand,
                "description": f"{function}. {formula}. {details}", "price": Decimal(price), "compare_at_price": None, "currency": "MYR",
                "status": ProductStatus.ACTIVE, "badge": ProductBadge(badge) if badge else None, "inventory_quantity": INVENTORY[position],
                "reserved_quantity": 0, "emoji": "🧴" if category_name == "Skincare" else "💄",
                "specs": [
                    {"label": "Product type", "value": name.replace(brand, "").strip()}, {"label": "Size", "value": size},
                    {"label": "Suitable for", "value": suitable_for}, {"label": "Formula / finish", "value": formula},
                    {"label": "Key details", "value": details}, {"label": "Function", "value": function},
                    {"label": "Shades / colours", "value": ", ".join(colours)}, {"label": "How to use", "value": guidance},
                    {"label": "Safety note", "value": "Patch test new products. Follow the product label and discontinue use if irritation occurs."},
                ],
                "attributes": {"department": "beauty", "beauty_category": category_name.lower(), "size": size, "suitable_for": suitable_for, "formula_finish": formula, "key_details": details, "function": function, "colors_or_shades": colours, "usage": guidance},
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
    print(f"Beauty catalog seed complete: {len(BEAUTY_PRODUCTS)} products upserted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
