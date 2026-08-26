"""Seed a comparison-ready catalog of named phones, laptops, keyboards and monitors.

Run with: ``poetry run python -m app.scripts.seed_device_catalog``

Regional variants can differ in available colours, RAM/storage options, radio
bands and bundle pricing.  Each row therefore identifies the exact catalog
configuration being offered rather than claiming to represent every variant.
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


# sku, category, brand, model, MYR price, level, processor / switch, RAM,
# storage, display / layout, key capabilities, colours, connectivity, image, badge
DEVICE_PRODUCTS = [
    ("DEVICE-001", "Phones", "Apple", "iPhone 16", "3999.00", "Flagship everyday", "A18", "8 GB", "128 GB", "6.1 in Super Retina XDR OLED, 60 Hz", "48 MP Fusion camera; MagSafe; IP68", ["Black", "White", "Pink", "Teal", "Ultramarine"], "5G, Wi-Fi 7, Bluetooth 5.3, USB-C", "https://images.unsplash.com/photo-1592286927505-4cde7e815e0b?auto=format&fit=crop&w=900&q=85", "new"),
    ("DEVICE-002", "Phones", "Apple", "iPhone 16 Pro", "4999.00", "Pro camera / creator", "A18 Pro", "8 GB", "128 GB", "6.3 in Super Retina XDR OLED, ProMotion 120 Hz", "48 MP camera system; 5× optical zoom; USB 3", ["Black Titanium", "White Titanium", "Natural Titanium", "Desert Titanium"], "5G, Wi-Fi 7, Bluetooth 5.3, USB-C", "https://images.unsplash.com/photo-1695048133142-1a20484d2569?auto=format&fit=crop&w=900&q=85", "hot"),
    ("DEVICE-003", "Phones", "Samsung", "Galaxy S25", "3999.00", "Android flagship", "Snapdragon 8 Elite for Galaxy", "12 GB", "256 GB", "6.2 in Dynamic AMOLED 2X, 120 Hz", "50 MP triple camera; Galaxy AI; IP68", ["Navy", "Icyblue", "Mint", "Silver Shadow"], "5G, Wi-Fi 7, Bluetooth 5.4, USB-C", "https://images.unsplash.com/photo-1610945415295-d9bbf067e59c?auto=format&fit=crop&w=900&q=85", None),
    ("DEVICE-004", "Phones", "Samsung", "Galaxy S25 Ultra", "5999.00", "Ultra flagship", "Snapdragon 8 Elite for Galaxy", "12 GB", "256 GB", "6.9 in Dynamic AMOLED 2X, 120 Hz", "200 MP camera; S Pen; titanium frame; IP68", ["Titanium Black", "Titanium Gray", "Titanium Whitesilver", "Titanium Silverblue"], "5G, Wi-Fi 7, Bluetooth 5.4, USB-C", "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?auto=format&fit=crop&w=900&q=85", "hot"),
    ("DEVICE-005", "Phones", "Google", "Pixel 9", "3799.00", "AI photography", "Google Tensor G4", "12 GB", "128 GB", "6.3 in Actua OLED, 60-120 Hz", "50 MP + 48 MP cameras; 4,700 mAh battery; IP68", ["Obsidian", "Porcelain", "Wintergreen", "Peony"], "5G, Wi-Fi 7, Bluetooth 5.3, USB-C", "https://images.unsplash.com/photo-1598327105666-5b89351aff97?auto=format&fit=crop&w=900&q=85", "new"),
    ("DEVICE-006", "Phones", "Xiaomi", "Xiaomi 15", "3499.00", "Compact flagship", "Snapdragon 8 Elite", "12 GB", "256 GB", "6.36 in CrystalRes AMOLED, 1-120 Hz", "Leica 50 MP triple camera; 5,240 mAh; 90 W charging", ["Black", "White", "Green", "Liquid Silver"], "5G, Wi-Fi 7, Bluetooth 5.4, USB-C", "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=900&q=85", None),
    ("DEVICE-007", "Phones", "HONOR", "Magic7 Pro", "4599.00", "AI camera flagship", "Snapdragon 8 Elite", "12 GB", "512 GB", "6.8 in LTPO OLED, 1-120 Hz", "200 MP telephoto camera; 5,270 mAh battery; IP68/IP69", ["Lunar Shadow Grey", "Black", "Breeze Blue"], "5G, Wi-Fi 7, Bluetooth 5.4, USB-C", "https://images.unsplash.com/photo-1580910051074-3eb694886505?auto=format&fit=crop&w=900&q=85", "new"),
    ("DEVICE-008", "Phones", "OPPO", "Find X8 Pro", "4999.00", "Pro photography", "MediaTek Dimensity 9400", "16 GB", "512 GB", "6.78 in AMOLED, 1-120 Hz", "Hasselblad quad 50 MP cameras; 5,910 mAh; IP68/IP69", ["Space Black", "Pearl White"], "5G, Wi-Fi 7, Bluetooth 5.4, USB-C", "https://images.unsplash.com/photo-1603899122634-f086ca5f5ddd?auto=format&fit=crop&w=900&q=85", "hot"),
    ("DEVICE-009", "Laptops", "Apple", "MacBook Air M4 13-inch", "4999.00", "Student / mobile productivity", "Apple M4 10-core CPU", "16 GB unified", "256 GB SSD", "13.6 in Liquid Retina, 2560 × 1664", "Up to 18-hour battery; fanless; 12 MP Center Stage camera", ["Sky Blue", "Silver", "Starlight", "Midnight"], "2× Thunderbolt 4, MagSafe, Wi-Fi 6E", "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?auto=format&fit=crop&w=900&q=85", None),
    ("DEVICE-010", "Laptops", "Apple", "MacBook Pro 14-inch", "8499.00", "Developer / creative pro", "Apple M4 Pro 12-core CPU", "24 GB unified", "512 GB SSD", "14.2 in Liquid Retina XDR, 120 Hz", "ProMotion; SDXC; HDMI; 3 Thunderbolt 5 ports", ["Space Black", "Silver"], "Thunderbolt 5, HDMI, SDXC, Wi-Fi 6E", "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=900&q=85", "hot"),
    ("DEVICE-011", "Laptops", "ASUS", "ROG Zephyrus G14", "7999.00", "Portable gaming / creator", "AMD Ryzen 9 8945HS; RTX 4060", "16 GB", "1 TB SSD", "14 in OLED, 2880 × 1800, 120 Hz", "Dedicated RTX graphics; 3K OLED; vapour-chamber cooling", ["Platinum White", "Eclipse Gray"], "USB4, HDMI 2.1, Wi-Fi 6E, USB-C PD", "https://images.unsplash.com/photo-1603302576837-37561b2e2302?auto=format&fit=crop&w=900&q=85", "sale"),
    ("DEVICE-012", "Laptops", "ASUS", "Zenbook 14 OLED", "4999.00", "Premium everyday", "Intel Core Ultra 7 258V", "16 GB", "1 TB SSD", "14 in 3K OLED, 120 Hz", "OLED colour accuracy; lightweight metal chassis; AI NPU", ["Ponder Blue", "Foggy Silver"], "Thunderbolt 4, HDMI 2.1, Wi-Fi 7", "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=900&q=85", None),
    ("DEVICE-013", "Laptops", "Lenovo", "ThinkPad X1 Carbon", "8999.00", "Business professional", "Intel Core Ultra 7 258V", "32 GB", "1 TB SSD", "14 in 2.8K OLED, 120 Hz", "Carbon-fibre chassis; business security; TrackPoint", ["Deep Black"], "Thunderbolt 4, HDMI, Wi-Fi 7, optional 5G", "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=900&q=85", "new"),
    ("DEVICE-014", "Laptops", "Lenovo", "Legion 5", "6499.00", "Gaming / performance", "AMD Ryzen 7 8845HS; RTX 4060", "16 GB", "1 TB SSD", "15.6 in IPS, 2560 × 1440, 165 Hz", "RTX 4060 graphics; high-refresh display; cooling modes", ["Storm Gray"], "USB-C, HDMI 2.1, Ethernet, Wi-Fi 6E", "https://images.unsplash.com/photo-1587202372634-32705e3bf49c?auto=format&fit=crop&w=900&q=85", "sale"),
    ("DEVICE-015", "Laptops", "Acer", "Swift Go 14", "3699.00", "Value student", "Intel Core Ultra 5 125H", "16 GB", "512 GB SSD", "14 in OLED, 2880 × 1800, 90 Hz", "Lightweight OLED laptop; 1440p webcam; AI acceleration", ["Pure Silver"], "Thunderbolt 4, HDMI, Wi-Fi 6E", "https://images.unsplash.com/photo-1515879218367-8466d910aaa4?auto=format&fit=crop&w=900&q=85", None),
    ("DEVICE-016", "Laptops", "HP", "Spectre x360 14", "6999.00", "Premium convertible", "Intel Core Ultra 7 155H", "32 GB", "1 TB SSD", "14 in 2.8K OLED touch, 120 Hz", "360° convertible; pen support; 9 MP webcam", ["Nightfall Black", "Slate Blue"], "Thunderbolt 4, USB-A, Wi-Fi 7", "https://images.unsplash.com/photo-1505238680356-667803448bb6?auto=format&fit=crop&w=900&q=85", "new"),
    ("DEVICE-017", "Keyboards", "Logitech", "MX Keys S", "549.00", "Productivity", "Scissor switches", "N/A", "N/A", "Full-size low-profile, backlit", "Smart illumination; Easy-Switch for three devices; rechargeable", ["Graphite", "Pale Gray"], "Bluetooth Low Energy, Logi Bolt, USB-C charging", "https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=900&q=85", None),
    ("DEVICE-018", "Keyboards", "Logitech", "G Pro X TKL", "799.00", "Competitive gaming", "GX mechanical switches", "N/A", "Onboard profiles", "TKL mechanical, LIGHTSYNC RGB", "Tournament tenkeyless layout; volume roller; durable keycaps", ["Black", "White", "Magenta"], "LIGHTSPEED wireless, Bluetooth, USB-C", "https://images.unsplash.com/photo-1618384887929-16ec33fab9ef?auto=format&fit=crop&w=900&q=85", "hot"),
    ("DEVICE-019", "Keyboards", "Keychron", "K2 Pro", "429.00", "Typing / developer", "Hot-swappable K Pro switches", "N/A", "QMK/VIA profiles", "75% mechanical, double-shot PBT", "Programmable QMK/VIA; Mac and Windows keycaps included", ["White Backlight", "RGB", "Black"], "Bluetooth 5.1, USB-C", "https://images.unsplash.com/photo-1541140532154-b024d705b90a?auto=format&fit=crop&w=900&q=85", None),
    ("DEVICE-020", "Keyboards", "Keychron", "Q1 Max", "949.00", "Premium custom", "Gateron Jupiter hot-swappable switches", "N/A", "QMK/VIA profiles", "75% all-aluminum mechanical, gasket mount", "Double-gasket design; rotary knob; acoustic foam", ["Carbon Black", "Shell White", "Silver Gray"], "2.4 GHz, Bluetooth 5.1, USB-C", "https://images.unsplash.com/photo-1541140532154-b024d705b90a?auto=format&fit=crop&w=900&q=85", "new"),
    ("DEVICE-021", "Keyboards", "Razer", "BlackWidow V4", "799.00", "Gaming / streaming", "Razer Green mechanical switches", "N/A", "Onboard profiles", "Full-size mechanical, per-key RGB", "Dedicated macro keys; multi-function roller; wrist rest", ["Black"], "USB-A wired", "https://images.unsplash.com/photo-1511467687858-23d96c32e4ae?auto=format&fit=crop&w=900&q=85", "hot"),
    ("DEVICE-022", "Keyboards", "Corsair", "K70 RGB Pro", "699.00", "Gaming", "CHERRY MX Red switches", "N/A", "8 MB onboard profiles", "Full-size mechanical, per-key RGB", "Tournament switch; PBT keycaps; aluminum frame", ["Black", "White"], "USB-C wired", "https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=900&q=85", None),
    ("DEVICE-023", "Keyboards", "ASUS ROG", "Strix Scope II 96 Wireless", "899.00", "Gaming / productivity", "ROG NX Snow switches", "N/A", "Onboard profiles", "96% wireless mechanical, hot-swappable", "Full-size numpad in compact layout; dampening foam", ["Black", "Moonlight White"], "2.4 GHz, Bluetooth, USB-C", "https://images.unsplash.com/photo-1595225476474-87563907a212?auto=format&fit=crop&w=900&q=85", "new"),
    ("DEVICE-024", "Monitors", "Dell", "UltraSharp U2723QE", "2399.00", "Professional productivity", "IPS Black panel", "N/A", "N/A", "27 in 4K IPS Black, 60 Hz", "2,000:1 contrast; 98% DCI-P3; 90 W USB-C hub", ["Platinum Silver"], "USB-C 90 W, DisplayPort, HDMI, Ethernet, USB hub", "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?auto=format&fit=crop&w=900&q=85", "new"),
    ("DEVICE-025", "Monitors", "LG", "UltraGear 27GR83Q", "1899.00", "Competitive gaming", "Fast IPS panel", "N/A", "N/A", "27 in QHD IPS, 240 Hz", "1 ms GtG; G-SYNC Compatible; DisplayHDR 400", ["Black"], "2× HDMI 2.1, DisplayPort 1.4, USB hub", "https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=900&q=85", "hot"),
    ("DEVICE-026", "Monitors", "Samsung", "Odyssey G7", "2299.00", "Immersive gaming", "VA panel", "N/A", "N/A", "32 in QHD curved VA, 240 Hz", "1000R curvature; 1 ms response; HDR600", ["Black"], "DisplayPort 1.4, HDMI 2.0, USB hub", "https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=900&q=85", "sale"),
    ("DEVICE-027", "Monitors", "ASUS ROG", "Swift PG27AQDM", "4999.00", "OLED esports", "QD-OLED panel", "N/A", "N/A", "26.5 in QHD OLED, 240 Hz", "0.03 ms response; 99% DCI-P3; G-SYNC Compatible", ["Black"], "DisplayPort 1.4, 2× HDMI 2.0, USB hub", "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?auto=format&fit=crop&w=900&q=85", "hot"),
    ("DEVICE-028", "Monitors", "MSI", "MAG 274QRF QD E2", "1599.00", "Gaming / colour work", "Rapid IPS Quantum Dot", "N/A", "N/A", "27 in QHD Rapid IPS, 180 Hz", "Wide colour gamut; 1 ms GtG; height-adjustable stand", ["Black"], "DisplayPort 1.4, 2× HDMI 2.0b, USB-C 65 W", "https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=900&q=85", None),
    ("DEVICE-029", "Monitors", "Gigabyte", "M27Q", "1299.00", "Value work / gaming", "IPS panel", "N/A", "N/A", "27 in QHD IPS, 170 Hz", "KVM switch; 92% DCI-P3; 0.5 ms MPRT", ["Black"], "USB-C, DisplayPort 1.2, 2× HDMI 2.0, USB hub", "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=900&q=85", "sale"),
    ("DEVICE-030", "Monitors", "BenQ", "MOBIUZ EX2710Q", "1699.00", "Console / gaming", "IPS panel", "N/A", "N/A", "27 in QHD IPS, 165 Hz", "HDRi; built-in 2.1 speakers; 1 ms MPRT", ["Black"], "DisplayPort 1.4, 2× HDMI 2.0, USB hub", "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?auto=format&fit=crop&w=900&q=85", None),
]

RATINGS = [4.5, 4.7, 4.4, 4.6, 4.3, 4.4, 4.2, 4.5, 4.7, 4.8, 4.6, 4.5, 4.7, 4.5, 4.2, 4.4, 4.6, 4.5, 4.7, 4.8, 4.4, 4.3, 4.5, 4.7, 4.6, 4.4, 4.7, 4.5, 4.4, 4.3]
REVIEW_COUNTS = [412, 286, 369, 234, 176, 143, 89, 117, 248, 152, 91, 137, 68, 114, 72, 83, 719, 248, 306, 121, 267, 154, 198, 94, 132, 87, 56, 146, 231, 118]
INVENTORY = [42, 24, 38, 19, 27, 33, 16, 21, 31, 17, 12, 19, 9, 14, 26, 11, 47, 32, 58, 18, 24, 35, 29, 22, 26, 15, 8, 27, 39, 31]


def run() -> int:
    with SessionLocal() as db:
        sellers: dict[str, Seller] = {}
        categories: dict[str, Category] = {}
        for position, item in enumerate(DEVICE_PRODUCTS):
            sku, category_name, brand, model, price, level, processor, ram, storage, display, capabilities, colors, connectivity, image_url, badge = item
            seller_name = f"{brand} Authorized Store"
            seller_slug = slugify(seller_name)
            seller = sellers.get(seller_slug) or db.scalar(select(Seller).where(Seller.slug == seller_slug))
            if seller is None:
                seller = Seller(name=seller_name, slug=seller_slug, description=f"Authorized electronics catalog profile for {brand}.", status=SellerStatus.ACTIVE)
                db.add(seller); db.flush()
            else:
                seller.status = SellerStatus.ACTIVE
            sellers[seller_slug] = seller

            category_slug = slugify(category_name)
            category = categories.get(category_slug) or db.scalar(select(Category).where(Category.slug == category_slug))
            if category is None:
                category = Category(name=category_name, slug=category_slug, description=f"Electronics: {category_name}.", sort_order=400 + position, is_active=True)
                db.add(category); db.flush()
            categories[category_slug] = category

            product = db.scalar(select(Product).where(Product.sku == sku))
            values = {
                "seller": seller, "category": category, "slug": slugify(f"{brand} {model}"), "name": f"{brand} {model}", "brand": brand,
                "description": f"{level} configuration of {brand} {model}. {capabilities} Regional configuration and bundle contents may vary.",
                "price": Decimal(price), "compare_at_price": None, "currency": "MYR", "status": ProductStatus.ACTIVE,
                "badge": ProductBadge(badge) if badge else None, "inventory_quantity": INVENTORY[position], "reserved_quantity": 0, "emoji": "📱" if category_name == "Phones" else "💻",
                "specs": [
                    {"label": "Use level", "value": level}, {"label": "Processor / switches", "value": processor}, {"label": "RAM", "value": ram},
                    {"label": "Storage / profiles", "value": storage}, {"label": "Display / layout", "value": display}, {"label": "Key capabilities", "value": capabilities},
                    {"label": "Connectivity", "value": connectivity}, {"label": "Colour options", "value": ", ".join(colors)},
                    {"label": "Configuration note", "value": "Regional variants may differ; verify the seller listing before purchase."},
                ],
                "attributes": {"department": "electronics", "device_category": category_name.lower(), "level": level, "processor": processor, "ram": ram, "storage": storage, "display": display, "capabilities": capabilities, "connectivity": connectivity, "colors": colors, "regional_variant_note": True},
                "rating_average": Decimal(str(RATINGS[position])), "review_count": REVIEW_COUNTS[position], "published_at": datetime.now(timezone.utc),
            }
            if product is None:
                product = Product(sku=sku, **values); db.add(product)
            else:
                for field, value in values.items(): setattr(product, field, value)
            db.flush()
            primary_image = min(product.images, key=lambda image: image.sort_order) if product.images else None
            if primary_image is None:
                product.images.append(ProductImage(url=image_url, alt_text=f"{brand} {model}", sort_order=0))
            else:
                primary_image.url = image_url
                primary_image.alt_text = f"{brand} {model}"
                primary_image.sort_order = 0
        db.commit()
    print(f"Device catalog seed complete: {len(DEVICE_PRODUCTS)} products upserted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
