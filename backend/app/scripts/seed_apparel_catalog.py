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


# These additions deliberately include comparable products at different price
# points (for example polos, blazers, shoes and socks).  They are kept as
# structured records so the agent can filter on audience, occasion, care, and
# style rather than trying to infer those details from marketing copy.
ADDITIONAL_APPAREL_PRODUCTS = [
    {"sku": "APPAREL-015", "name": "Metro Pique Polo", "brand": "Harbor & Thread", "category": "Polo Shirts", "seller": "Harbor & Thread Menswear", "price": "89.00", "compare_at_price": "109.00", "description": "Breathable short-sleeve pique polo with a two-button collar for smart-casual office days.", "material": "Cotton 96%, elastane 4%", "fit": "Regular", "sizes": "S-XXL", "colors": ["Navy", "White", "Burgundy"], "audience": "Men", "style": "Smart casual", "occasion": "Office and weekend", "care": "Machine wash cold; reshape while damp", "inventory": 86, "rating": "4.30", "review_count": 118, "image_url": "https://images.unsplash.com/photo-1625910513413-5fcf1d0f4e91?auto=format&fit=crop&w=900&q=85", "badge": "sale"},
    {"sku": "APPAREL-016", "name": "Heritage Knit Polo", "brand": "Cedar Row", "category": "Polo Shirts", "seller": "Cedar Row Clothiers", "price": "149.00", "compare_at_price": None, "description": "Fine-gauge knitted polo with a textured collar and shell buttons for polished dinner or work styling.", "material": "Cotton 70%, viscose 30%", "fit": "Tailored", "sizes": "S-XL", "colors": ["Oatmeal", "Ink", "Olive"], "audience": "Men", "style": "Refined", "occasion": "Office and dinner", "care": "Hand wash or gentle cycle; dry flat", "inventory": 31, "rating": "4.60", "review_count": 74, "image_url": "https://images.unsplash.com/photo-1617137968427-85924c800a22?auto=format&fit=crop&w=900&q=85", "badge": "new"},
    {"sku": "APPAREL-017", "name": "Silk Touch Work Blouse", "brand": "Atelier Nine", "category": "Blouses", "seller": "Atelier Nine", "price": "159.00", "compare_at_price": None, "description": "Draped V-neck blouse with soft cuffs and a longer back hem for easy workwear layering.", "material": "Tencel 55%, rayon 45%", "fit": "Relaxed", "sizes": "XS-XL", "colors": ["Ivory", "Dusty Rose", "Black"], "audience": "Women", "style": "Workwear", "occasion": "Office and events", "care": "Cold gentle wash; iron on low", "inventory": 42, "rating": "4.40", "review_count": 163, "image_url": "https://images.unsplash.com/photo-1605763240000-7e93b172d754?auto=format&fit=crop&w=900&q=85", "badge": None},
    {"sku": "APPAREL-018", "name": "Everyday Rib Crop Tee", "brand": "Mira Basics", "category": "T-Shirts", "seller": "Mira Basics", "price": "49.00", "compare_at_price": None, "description": "Soft ribbed crop T-shirt with a crew neck and close, stretchy fit for casual layering.", "material": "Organic cotton 95%, elastane 5%", "fit": "Slim", "sizes": "XS-L", "colors": ["White", "Espresso", "Sage", "Lilac"], "audience": "Women", "style": "Casual", "occasion": "Everyday", "care": "Machine wash cold inside out", "inventory": 124, "rating": "4.10", "review_count": 291, "image_url": "https://images.unsplash.com/photo-1503341504253-dff4815485f1?auto=format&fit=crop&w=900&q=85", "badge": None},
    {"sku": "APPAREL-019", "name": "Transit Zip Hoodie", "brand": "Northline", "category": "Hoodies", "seller": "Northline Outdoor", "price": "169.00", "compare_at_price": "199.00", "description": "Midweight full-zip hoodie with a brushed interior, hidden phone pocket and adjustable hood.", "material": "Cotton 80%, recycled polyester 20%", "fit": "Relaxed", "sizes": "XS-XXL", "colors": ["Heather Gray", "Black", "Pine"], "audience": "Unisex", "style": "Streetwear", "occasion": "Travel and everyday", "care": "Machine wash cold; tumble dry low", "inventory": 58, "rating": "4.70", "review_count": 208, "image_url": "https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&w=900&q=85", "badge": "hot"},
    {"sku": "APPAREL-020", "name": "French Terry Crew Sweatshirt", "brand": "Mira Basics", "category": "Sweatshirts", "seller": "Mira Basics", "price": "109.00", "compare_at_price": None, "description": "Loopback French-terry crew sweatshirt with ribbed trims and an easy oversized silhouette.", "material": "Cotton 100%", "fit": "Oversized", "sizes": "XS-XXL", "colors": ["Stone", "Cobalt", "Cherry Red"], "audience": "Unisex", "style": "Casual", "occasion": "Everyday", "care": "Machine wash cold inside out", "inventory": 73, "rating": "4.20", "review_count": 96, "image_url": "https://images.unsplash.com/photo-1578768079052-aa76e52ff62e?auto=format&fit=crop&w=900&q=85", "badge": None},
    {"sku": "APPAREL-021", "name": "Utility Cargo Pants", "brand": "Northline", "category": "Cargo Pants", "seller": "Northline Outdoor", "price": "179.00", "compare_at_price": None, "description": "Hard-wearing tapered cargo pants with articulated knees, six pockets and an adjustable hem.", "material": "Cotton 97%, elastane 3%", "fit": "Tapered", "sizes": "28-40", "colors": ["Olive", "Black", "Sand"], "audience": "Unisex", "style": "Utility", "occasion": "Travel and outdoor", "care": "Machine wash cold; do not bleach", "inventory": 37, "rating": "4.50", "review_count": 67, "image_url": "https://images.unsplash.com/photo-1517438476312-10d79c077509?auto=format&fit=crop&w=900&q=85", "badge": None},
    {"sku": "APPAREL-022", "name": "Pleated Midi Skirt", "brand": "Atelier Nine", "category": "Skirts", "seller": "Atelier Nine", "price": "139.00", "compare_at_price": "169.00", "description": "Fluid knife-pleated midi skirt with an elasticated back waist and opaque lining.", "material": "Recycled polyester 100%; lining: polyester", "fit": "A-line", "sizes": "XS-XL", "colors": ["Black", "Champagne", "Emerald"], "audience": "Women", "style": "Elegant", "occasion": "Office and occasion", "care": "Gentle wash in a mesh bag; hang dry", "inventory": 24, "rating": "4.30", "review_count": 54, "image_url": "https://images.unsplash.com/photo-1583496661160-fb5886a0aaaa?auto=format&fit=crop&w=900&q=85", "badge": "sale"},
    {"sku": "APPAREL-023", "name": "Runner Knit Joggers", "brand": "Pulse Form", "category": "Joggers", "seller": "Pulse Form", "price": "129.00", "compare_at_price": None, "description": "Tapered performance joggers with quick-dry knit fabric, zipped pockets and reflective logo.", "material": "Recycled polyester 88%, elastane 12%", "fit": "Tapered", "sizes": "XS-XXL", "colors": ["Graphite", "Navy", "Mauve"], "audience": "Unisex", "style": "Athleisure", "occasion": "Training and travel", "care": "Machine wash cold; avoid fabric softener", "inventory": 65, "rating": "4.60", "review_count": 143, "image_url": "https://images.unsplash.com/photo-1517836357463-d25dfeac3438?auto=format&fit=crop&w=900&q=85", "badge": None},
    {"sku": "APPAREL-024", "name": "Wool Blend Travel Blazer", "brand": "Cedar Row", "category": "Blazers", "seller": "Cedar Row Clothiers", "price": "349.00", "compare_at_price": None, "description": "Unstructured two-button blazer with a soft shoulder, patch pockets and crease-resistant weave.", "material": "Wool 52%, polyester 44%, elastane 4%", "fit": "Tailored", "sizes": "S-XXL", "colors": ["Charcoal", "Navy"], "audience": "Men", "style": "Formal", "occasion": "Work and travel", "care": "Dry clean recommended", "inventory": 18, "rating": "4.80", "review_count": 39, "image_url": "https://images.unsplash.com/photo-1507679799987-c73779587ccf?auto=format&fit=crop&w=900&q=85", "badge": "new"},
    {"sku": "APPAREL-025", "name": "Sculpted Single-Button Blazer", "brand": "Atelier Nine", "category": "Blazers", "seller": "Atelier Nine", "price": "259.00", "compare_at_price": "299.00", "description": "Lined single-button blazer with light shoulder structure and a waist-defining cut.", "material": "Viscose 68%, polyester 28%, elastane 4%", "fit": "Tailored", "sizes": "XS-XL", "colors": ["Black", "Ivory", "Cobalt"], "audience": "Women", "style": "Formal", "occasion": "Office and formal events", "care": "Dry clean only", "inventory": 21, "rating": "4.50", "review_count": 87, "image_url": "https://images.unsplash.com/photo-1591369822096-ffd140ec948f?auto=format&fit=crop&w=900&q=85", "badge": "sale"},
    {"sku": "APPAREL-026", "name": "Classic Denim Jacket", "brand": "Morrow Denim", "category": "Outerwear", "seller": "Morrow Denim Studio", "price": "219.00", "compare_at_price": None, "description": "Medium-wash denim jacket with a slightly dropped shoulder and adjustable back tabs.", "material": "Cotton denim 100%", "fit": "Relaxed", "sizes": "XS-XXL", "colors": ["Mid Blue", "Washed Black"], "audience": "Unisex", "style": "Casual", "occasion": "Everyday", "care": "Wash separately in cold water", "inventory": 46, "rating": "4.40", "review_count": 126, "image_url": "https://images.unsplash.com/photo-1523205771623-e0faa4d281b5?auto=format&fit=crop&w=900&q=85", "badge": None},
    {"sku": "APPAREL-027", "name": "Lightweight Bomber Jacket", "brand": "Northline", "category": "Outerwear", "seller": "Northline Outdoor", "price": "239.00", "compare_at_price": None, "description": "Water-repellent bomber jacket with recycled insulation, ribbed collar and interior zip pocket.", "material": "Recycled nylon shell, recycled polyester fill", "fit": "Regular", "sizes": "S-XXL", "colors": ["Black", "Sage", "Rust"], "audience": "Men", "style": "Streetwear", "occasion": "Commute and travel", "care": "Machine wash gentle; tumble dry low", "inventory": 29, "rating": "4.20", "review_count": 48, "image_url": "https://images.unsplash.com/photo-1548883354-7622d03aca27?auto=format&fit=crop&w=900&q=85", "badge": None},
    {"sku": "APPAREL-028", "name": "Belted Trench Coat", "brand": "Atelier Nine", "category": "Outerwear", "seller": "Atelier Nine", "price": "399.00", "compare_at_price": "459.00", "description": "Double-breasted belted trench with a storm flap, removable belt and lightweight water-resistant finish.", "material": "Cotton 62%, polyester 38%", "fit": "Relaxed", "sizes": "XS-XL", "colors": ["Camel", "Stone", "Black"], "audience": "Women", "style": "Classic", "occasion": "Work and travel", "care": "Dry clean recommended", "inventory": 13, "rating": "4.70", "review_count": 32, "image_url": "https://images.unsplash.com/photo-1485230895905-ec40ba36b9bc?auto=format&fit=crop&w=900&q=85", "badge": "hot"},
    {"sku": "APPAREL-029", "name": "Floral Wrap Maxi Dress", "brand": "Mira Basics", "category": "Dresses", "seller": "Mira Basics", "price": "189.00", "compare_at_price": None, "description": "Adjustable wrap maxi dress with flutter sleeves, a V-neck and a soft floral print.", "material": "Viscose 100%", "fit": "Wrap", "sizes": "XS-XL", "colors": ["Navy Floral", "Terracotta Floral"], "audience": "Women", "style": "Feminine", "occasion": "Weekend and holiday", "care": "Cold gentle wash; hang dry", "inventory": 33, "rating": "4.30", "review_count": 111, "image_url": "https://images.unsplash.com/photo-1515372039744-b8f02a3ae446?auto=format&fit=crop&w=900&q=85", "badge": None},
    {"sku": "APPAREL-030", "name": "Crepe Evening Midi Dress", "brand": "Atelier Nine", "category": "Dresses", "seller": "Atelier Nine", "price": "279.00", "compare_at_price": None, "description": "Lined crepe midi dress with a square neckline, fitted bodice and adjustable shoulder straps.", "material": "Polyester crepe 95%, elastane 5%; lining: polyester", "fit": "Bodycon", "sizes": "XS-L", "colors": ["Black", "Sapphire", "Berry"], "audience": "Women", "style": "Formal", "occasion": "Dinner and formal events", "care": "Dry clean or hand wash cold", "inventory": 16, "rating": "4.60", "review_count": 59, "image_url": "https://images.unsplash.com/photo-1566174053879-31528523f8ae?auto=format&fit=crop&w=900&q=85", "badge": "new"},
    {"sku": "APPAREL-031", "name": "Leather Penny Loafer", "brand": "Cedar Row", "category": "Shoes", "seller": "Cedar Row Clothiers", "price": "329.00", "compare_at_price": None, "description": "Leather penny loafer with cushioned leather insole and grippy rubber forefoot for long office days.", "material": "Leather upper and lining, rubber sole", "fit": "True to size", "sizes": "EU 39-45", "colors": ["Dark Brown", "Black"], "audience": "Men", "style": "Formal", "occasion": "Office and events", "care": "Wipe clean; condition leather regularly", "inventory": 27, "rating": "4.50", "review_count": 82, "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=85", "badge": None},
    {"sku": "APPAREL-032", "name": "Pointed Slingback Heel", "brand": "Atelier Nine", "category": "Shoes", "seller": "Atelier Nine", "price": "249.00", "compare_at_price": "289.00", "description": "Pointed-toe slingback heel with an adjustable strap and 5 cm block heel for comfortable event wear.", "material": "Microfibre upper, synthetic lining, rubber sole", "fit": "True to size", "sizes": "EU 35-41", "colors": ["Black", "Nude", "Silver"], "audience": "Women", "style": "Formal", "occasion": "Office and occasion", "care": "Wipe with a soft dry cloth", "inventory": 19, "rating": "4.00", "review_count": 36, "image_url": "https://images.unsplash.com/photo-1543163521-1bf539c55dd2?auto=format&fit=crop&w=900&q=85", "badge": "sale"},
    {"sku": "APPAREL-033", "name": "Trail Grip Hiking Boot", "brand": "Stride Supply", "category": "Shoes", "seller": "Stride Supply", "price": "359.00", "compare_at_price": None, "description": "Mid-cut hiking boot with a waterproof membrane, padded ankle collar and lugged trail outsole.", "material": "Synthetic leather and mesh upper, rubber sole", "fit": "True to size", "sizes": "EU 36-46", "colors": ["Brown Orange", "Black Gray"], "audience": "Unisex", "style": "Outdoor", "occasion": "Hiking and wet weather", "care": "Brush off dirt; air dry away from direct heat", "inventory": 22, "rating": "4.70", "review_count": 94, "image_url": "https://images.unsplash.com/photo-1542840410-3092f99611a3?auto=format&fit=crop&w=900&q=85", "badge": "hot"},
    {"sku": "APPAREL-034", "name": "Cloud Slide Sandal", "brand": "Stride Supply", "category": "Shoes", "seller": "Stride Supply", "price": "79.00", "compare_at_price": None, "description": "Water-friendly contoured slide sandal with soft EVA foam and a textured footbed.", "material": "EVA foam", "fit": "True to size", "sizes": "EU 36-45", "colors": ["Black", "Bone", "Sea Blue"], "audience": "Unisex", "style": "Casual", "occasion": "Pool and everyday", "care": "Rinse with water and air dry", "inventory": 102, "rating": "3.90", "review_count": 173, "image_url": "https://images.unsplash.com/photo-1603487742131-4160ec999306?auto=format&fit=crop&w=900&q=85", "badge": None},
    {"sku": "APPAREL-035", "name": "Metro Commuter Backpack", "brand": "Northline", "category": "Bags", "seller": "Northline Outdoor", "price": "199.00", "compare_at_price": None, "description": "18 L commuter backpack with padded 15-inch laptop sleeve, bottle pocket and luggage pass-through.", "material": "Recycled polyester 600D", "fit": "18 L capacity", "sizes": "One size", "colors": ["Black", "Navy", "Moss"], "audience": "Unisex", "style": "Utility", "occasion": "Commute and travel", "care": "Spot clean with a damp cloth", "inventory": 45, "rating": "4.60", "review_count": 154, "image_url": "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=900&q=85", "badge": None},
    {"sku": "APPAREL-036", "name": "Crescent Crossbody Bag", "brand": "Mira Basics", "category": "Bags", "seller": "Mira Basics", "price": "119.00", "compare_at_price": "139.00", "description": "Compact crescent crossbody with an adjustable webbing strap, zip closure and internal card pocket.", "material": "Recycled nylon with polyester lining", "fit": "2.5 L capacity", "sizes": "One size", "colors": ["Black", "Olive", "Lilac"], "audience": "Women", "style": "Casual", "occasion": "Everyday and travel", "care": "Spot clean only", "inventory": 57, "rating": "4.20", "review_count": 203, "image_url": "https://images.unsplash.com/photo-1584917865442-de89df76afd3?auto=format&fit=crop&w=900&q=85", "badge": "sale"},
    {"sku": "APPAREL-037", "name": "Reversible Leather Belt", "brand": "Cedar Row", "category": "Accessories", "seller": "Cedar Row Clothiers", "price": "99.00", "compare_at_price": None, "description": "Reversible leather belt with a brushed metal swivel buckle; black on one side and brown on the other.", "material": "Genuine leather, zinc-alloy buckle", "fit": "Adjustable", "sizes": "S-XL", "colors": ["Black / Brown"], "audience": "Unisex", "style": "Formal", "occasion": "Office and everyday", "care": "Wipe clean; avoid prolonged moisture", "inventory": 68, "rating": "4.40", "review_count": 71, "image_url": "https://images.unsplash.com/photo-1624222247344-550fb60583dc?auto=format&fit=crop&w=900&q=85", "badge": None},
    {"sku": "APPAREL-038", "name": "Minimal Steel Watch", "brand": "Tempo Works", "category": "Accessories", "seller": "Tempo Works", "price": "229.00", "compare_at_price": None, "description": "Three-hand quartz watch with sapphire-coated mineral glass, 40 mm case and removable mesh bracelet.", "material": "Stainless steel case and mesh strap", "fit": "Adjustable bracelet", "sizes": "40 mm case", "colors": ["Silver", "Black"], "audience": "Unisex", "style": "Minimal", "occasion": "Office and occasion", "care": "Wipe with a soft cloth; splash resistant", "inventory": 34, "rating": "4.30", "review_count": 65, "image_url": "https://images.unsplash.com/photo-1524805444758-089113d48a6d?auto=format&fit=crop&w=900&q=85", "badge": None},
    {"sku": "APPAREL-039", "name": "Polarized Square Sunglasses", "brand": "Tempo Works", "category": "Accessories", "seller": "Tempo Works", "price": "139.00", "compare_at_price": "159.00", "description": "Lightweight square-frame sunglasses with UV400 polarized lenses and a protective hard case.", "material": "Acetate frame, polarized polycarbonate lenses", "fit": "One size", "sizes": "One size", "colors": ["Tortoise", "Matte Black", "Clear Gray"], "audience": "Unisex", "style": "Contemporary", "occasion": "Travel and everyday", "care": "Use the supplied microfibre cloth", "inventory": 77, "rating": "4.10", "review_count": 187, "image_url": "https://images.unsplash.com/photo-1511499767150-a48a237f0083?auto=format&fit=crop&w=900&q=85", "badge": "sale"},
    {"sku": "APPAREL-040", "name": "Tempo Support Sports Bra", "brand": "Pulse Form", "category": "Activewear", "seller": "Pulse Form", "price": "99.00", "compare_at_price": None, "description": "Medium-support sports bra with removable pads, racerback straps and a sweat-wicking underband.", "material": "Nylon 78%, elastane 22%", "fit": "Medium support", "sizes": "XS-XL", "colors": ["Black", "Plum", "Mist Blue"], "audience": "Women", "style": "Sportswear", "occasion": "Gym and studio", "care": "Machine wash cold; remove pads before washing", "inventory": 61, "rating": "4.50", "review_count": 132, "image_url": "https://images.unsplash.com/photo-1518611012118-696072aa579a?auto=format&fit=crop&w=900&q=85", "badge": "new"},
    {"sku": "APPAREL-041", "name": "Endurance Training Shorts", "brand": "Pulse Form", "category": "Activewear", "seller": "Pulse Form", "price": "89.00", "compare_at_price": None, "description": "7-inch training shorts with a quick-dry outer layer, liner phone pocket and split hem for movement.", "material": "Recycled polyester 90%, elastane 10%", "fit": "Athletic", "sizes": "S-XXL", "colors": ["Black", "Slate", "Electric Blue"], "audience": "Men", "style": "Sportswear", "occasion": "Gym and running", "care": "Machine wash cold; do not iron", "inventory": 92, "rating": "4.40", "review_count": 176, "image_url": "https://images.unsplash.com/photo-1517836357463-d25dfeac3438?auto=format&fit=crop&w=900&q=85", "badge": None},
    {"sku": "APPAREL-042", "name": "Heritage Baju Melayu Set", "brand": "Riang Raya", "category": "Traditional Wear", "seller": "Riang Raya Studio", "price": "299.00", "compare_at_price": None, "description": "Modern Baju Melayu set with a cekak musang collar, concealed buttons and matching slim-cut trousers.", "material": "Cotton satin 65%, polyester 35%", "fit": "Regular", "sizes": "S-XXL", "colors": ["Sage", "Midnight Blue", "Maroon"], "audience": "Men", "style": "Traditional Malaysian", "occasion": "Raya and weddings", "care": "Cold gentle wash; iron inside out", "inventory": 26, "rating": "4.80", "review_count": 58, "image_url": "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?auto=format&fit=crop&w=900&q=85", "badge": "hot"},
    {"sku": "APPAREL-043", "name": "Modern Baju Kurung Set", "brand": "Riang Raya", "category": "Traditional Wear", "seller": "Riang Raya Studio", "price": "329.00", "compare_at_price": "369.00", "description": "Two-piece Baju Kurung with a soft stand collar, side slits and a matching flowing skirt.", "material": "Textured crepe 96%, elastane 4%", "fit": "Relaxed", "sizes": "XS-XXL", "colors": ["Dusty Pink", "Emerald", "Navy"], "audience": "Women", "style": "Traditional Malaysian", "occasion": "Raya, weddings and family events", "care": "Hand wash cold; steam on low", "inventory": 23, "rating": "4.70", "review_count": 46, "image_url": "https://images.unsplash.com/photo-1529139574466-a303027c1d8b?auto=format&fit=crop&w=900&q=85", "badge": "new"},
    {"sku": "APPAREL-044", "name": "Performance Running Sock 3-Pack", "brand": "Stride Supply", "category": "Socks", "seller": "Stride Supply", "price": "45.00", "compare_at_price": None, "description": "Targeted-cushion running socks with arch compression, seamless toe and breathable mesh zones.", "material": "Nylon 58%, polyester 37%, elastane 5%", "fit": "Crew", "sizes": "EU 36-46", "colors": ["White / Lime", "Black / Gray", "Navy / Orange"], "audience": "Unisex", "style": "Sportswear", "occasion": "Running and training", "care": "Machine wash warm; do not use bleach", "inventory": 118, "rating": "4.60", "review_count": 319, "image_url": "https://images.unsplash.com/photo-1582966772680-860e372bb558?auto=format&fit=crop&w=900&q=85", "badge": "hot"},
]


def product_details(entry: tuple | dict[str, object], position: int) -> dict[str, object]:
    """Return a common, richly described product shape for legacy and new rows."""
    if isinstance(entry, dict):
        return entry
    sku, name, brand, category, seller, price, description, material, fit, sizes, colors, image_url, badge = entry
    return {
        "sku": sku, "name": name, "brand": brand, "category": category, "seller": seller, "price": price,
        "compare_at_price": None, "description": description, "material": material, "fit": fit, "sizes": sizes,
        "colors": colors, "image_url": image_url, "badge": badge, "inventory": 40 + position,
        "rating": "4.50", "review_count": 12 + position, "audience": "Unisex", "style": "Everyday",
        "occasion": "Everyday", "care": "Follow the garment care label",
    }


def run() -> int:
    with SessionLocal() as db:
        sellers: dict[str, Seller] = {}
        categories: dict[str, Category] = {}
        for position, entry in enumerate([*APPAREL_PRODUCTS, *ADDITIONAL_APPAREL_PRODUCTS], start=1):
            details = product_details(entry, position)
            sku = str(details["sku"])
            name = str(details["name"])
            brand = str(details["brand"])
            category_name = str(details["category"])
            seller_name = str(details["seller"])
            price = str(details["price"])
            description = str(details["description"])
            material = str(details["material"])
            fit = str(details["fit"])
            sizes = str(details["sizes"])
            colors = list(details["colors"])
            image_url = str(details["image_url"])
            badge = details["badge"]
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
                "description": description, "price": Decimal(price),
                "compare_at_price": Decimal(str(details["compare_at_price"])) if details["compare_at_price"] else None,
                "currency": "MYR", "status": ProductStatus.ACTIVE,
                "badge": ProductBadge(str(badge)) if badge else None, "inventory_quantity": int(details["inventory"]),
                "reserved_quantity": 0, "emoji": "👕", "specs": [
                    {"label": "Material", "value": material}, {"label": "Fit", "value": fit},
                    {"label": "Size range", "value": sizes}, {"label": "Color variants", "value": ", ".join(colors)},
                    {"label": "For", "value": str(details["audience"])},
                    {"label": "Style", "value": str(details["style"])},
                    {"label": "Best for", "value": str(details["occasion"])},
                    {"label": "Care", "value": str(details["care"])},
                    {"label": "Seller", "value": seller_name},
                ],
                "attributes": {
                    "colors": colors, "material": material, "fit": fit, "sizes": sizes, "department": "apparel",
                    "audience": details["audience"], "style": details["style"], "occasion": details["occasion"], "care": details["care"],
                },
                "rating_average": Decimal(str(details["rating"])), "review_count": int(details["review_count"]),
                "published_at": datetime.now(timezone.utc),
            }
            if product is None:
                product = Product(sku=sku, **values)
                db.add(product)
            else:
                for field, value in values.items():
                    setattr(product, field, value)
            db.flush()
            product.images.clear()
            # Flush the delete before inserting sort order 0 again.  Without
            # this, an existing product can violate the unique
            # (product_id, sort_order) constraint during an idempotent re-seed.
            db.flush()
            product.images.append(ProductImage(url=image_url, alt_text=name, sort_order=0))
        db.commit()
    print(f"Apparel catalog seed complete: {len(APPAREL_PRODUCTS) + len(ADDITIONAL_APPAREL_PRODUCTS)} products upserted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
