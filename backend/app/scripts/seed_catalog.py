"""Import and update the legacy frontend catalog in PostgreSQL.

The TypeScript file is deliberately treated as an import source during this
transition. Products are upserted by stable SKU so references from carts,
wishlists, recommendations, and orders remain valid across repeated seeds.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from re import sub

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Category, Product, ProductBadge, ProductImage, ProductStatus, Seller, SellerStatus


ROOT = Path(__file__).resolve().parents[3]
CATALOG_FILE = ROOT / "frontend/src/features/products/data/products.ts"
TYPESCRIPT_FILE = ROOT / "frontend/node_modules/typescript/lib/typescript.js"


def slugify(value: str) -> str:
    return sub(r"(^-|-$)", "", sub(r"[^a-z0-9]+", "-", value.lower()))


def load_legacy_catalog() -> list[dict[str, object]]:
    if not TYPESCRIPT_FILE.exists():
        raise RuntimeError("TypeScript is required to import the legacy catalog. Install frontend dependencies first.")
    runner = """
const fs = require('fs'); const vm = require('vm'); const ts = require(process.argv[1]);
const source = fs.readFileSync(process.argv[2], 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
const module = { exports: {} }; vm.runInNewContext(compiled, { module, exports: module.exports });
process.stdout.write(JSON.stringify(module.exports.PRODUCTS));
"""
    result = subprocess.run(
        ["node", "-e", runner, str(TYPESCRIPT_FILE), str(CATALOG_FILE)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def extract_seller_name(specs: object) -> str | None:
    if not isinstance(specs, list):
        return None
    for item in specs:
        if not isinstance(item, dict):
            continue
        if str(item.get("label", "")).strip().lower() != "seller":
            continue
        value = str(item.get("value", "")).strip()
        return value or None
    return None


def run() -> int:
    legacy_products = load_legacy_catalog()
    with SessionLocal() as db:
        existing_by_sku = {
            product.sku: product
            for product in db.scalars(select(Product).where(Product.sku.like("LEGACY-%"))).all()
        }

        seller_cache: dict[str, Seller] = {}

        def resolve_seller(name: str) -> Seller:
            seller_slug = slugify(name)
            seller = seller_cache.get(seller_slug) or db.scalar(select(Seller).where(Seller.slug == seller_slug))
            if seller is None:
                seller = Seller(
                    name=name,
                    slug=seller_slug,
                    description=f"Catalog merchant profile for {name}.",
                    status=SellerStatus.ACTIVE,
                )
                db.add(seller)
                db.flush()
            elif seller.status != SellerStatus.ACTIVE:
                seller.status = SellerStatus.ACTIVE
            seller_cache[seller_slug] = seller
            return seller

        categories: dict[str, Category] = {}
        created = 0
        updated = 0
        for position, entry in enumerate(legacy_products, start=1):
            category_name = str(entry["category"])
            category_slug = slugify(category_name)
            category = categories.get(category_slug) or db.scalar(select(Category).where(Category.slug == category_slug))
            if category is None:
                category = Category(name=category_name, slug=category_slug, sort_order=position, is_active=True)
                db.add(category)
                db.flush()
            categories[category_slug] = category

            legacy_id = int(entry["id"])
            sku = f"LEGACY-{legacy_id:04d}"
            specs = entry.get("specs") or []
            seller_name = extract_seller_name(specs) or "Shopy Catalog"
            seller = resolve_seller(seller_name)
            badge = entry.get("badge")
            values = {
                "seller": seller, "category": category, "slug": f"{slugify(str(entry['name']))}-{legacy_id}",
                "name": str(entry["name"]), "brand": str(entry["brand"]), "description": str(entry["desc"]),
                "price": Decimal(str(entry["price"])), "currency": "MYR", "status": ProductStatus.ACTIVE,
                "badge": ProductBadge(badge) if badge else None, "inventory_quantity": 100 if entry.get("stock") else 0,
                "emoji": str(entry.get("emoji") or ""), "specs": specs,
                "attributes": {"legacy_product_id": legacy_id}, "rating_average": Decimal(str(entry.get("rating", 0))),
                "review_count": int(entry.get("reviews", 0)), "published_at": datetime.now(timezone.utc),
            }
            product = existing_by_sku.get(sku)
            if product is None:
                product = Product(sku=sku, **values)
                db.add(product)
                created += 1
            else:
                # Never replace the row: its UUID may already be referenced by
                # carts, orders, wishlists, reviews, and AI recommendations.
                for field, value in values.items():
                    setattr(product, field, value)
                updated += 1
            db.flush()

            image_url = entry.get("image")
            if image_url:
                image = next((candidate for candidate in product.images if candidate.sort_order == 0), None)
                if image is None:
                    product.images.append(ProductImage(url=str(image_url), alt_text=product.name, sort_order=0))
                else:
                    image.url, image.alt_text = str(image_url), product.name
        db.commit()
    print(f"Catalog seed complete: {created} products created, {updated} updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
