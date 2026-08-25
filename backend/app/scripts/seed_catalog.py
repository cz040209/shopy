"""Import the legacy frontend catalog into PostgreSQL exactly once per product SKU.

The TypeScript file is deliberately treated as an import source during this
transition. After running this command, PostgreSQL is the storefront source of
truth and the frontend reads the catalog APIs instead of that file.
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


def run() -> int:
    legacy_products = load_legacy_catalog()
    with SessionLocal() as db:
        seller = db.scalar(select(Seller).where(Seller.slug == "shopy-catalog"))
        if seller is None:
            seller = Seller(name="Shopy Catalog", slug="shopy-catalog", description="Shopy’s curated product collection.", status=SellerStatus.ACTIVE)
            db.add(seller)
            db.flush()

        categories: dict[str, Category] = {}
        imported = 0
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
            product = db.scalar(select(Product).where(Product.sku == sku))
            badge = entry.get("badge")
            values = {
                "seller": seller, "category": category, "slug": f"{slugify(str(entry['name']))}-{legacy_id}",
                "name": str(entry["name"]), "brand": str(entry["brand"]), "description": str(entry["desc"]),
                "price": Decimal(str(entry["price"])), "currency": "MYR", "status": ProductStatus.ACTIVE,
                "badge": ProductBadge(badge) if badge else None, "inventory_quantity": 100 if entry.get("stock") else 0,
                "emoji": str(entry.get("emoji") or ""), "specs": entry.get("specs") or [],
                "attributes": {"legacy_product_id": legacy_id}, "rating_average": Decimal(str(entry.get("rating", 0))),
                "review_count": int(entry.get("reviews", 0)), "published_at": datetime.now(timezone.utc),
            }
            if product is None:
                product = Product(sku=sku, **values)
                db.add(product)
                db.flush()
                imported += 1
            else:
                for key, value in values.items():
                    setattr(product, key, value)

            image_url = entry.get("image")
            if image_url:
                image = next((candidate for candidate in product.images if candidate.sort_order == 0), None)
                if image is None:
                    product.images.append(ProductImage(url=str(image_url), alt_text=product.name, sort_order=0))
                else:
                    image.url, image.alt_text = str(image_url), product.name
        db.commit()
    print(f"Catalog seed complete: {len(legacy_products)} products processed, {imported} created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
