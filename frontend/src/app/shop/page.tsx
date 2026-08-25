import { getProducts } from "@/features/products/catalog";
import ProductCard from "@/features/products/components/ProductCard";
import styles from "./shop.module.css";

export default async function Shop({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q = "" } = await searchParams;
  const filteredProducts = await getProducts(q.trim());

  return (
    <div className={styles.shop}>
      <section className={styles.catalog}>
        <div className={styles.catalogHeader}>
          <div>
            <p className={styles.eyebrow}>Shopy collection</p>
            <h1>Products</h1>
            <p className={styles.catalogCopy}>
              Thoughtfully selected essentials for work, home, and everyday life.
            </p>
            <p className={styles.productCount}>
              {filteredProducts.length} item{filteredProducts.length === 1 ? "" : "s"}
              {q.trim() ? ` matching "${q}"` : " available"}
            </p>
          </div>
          <div className={styles.statuses} aria-label="Product availability">
            <span>Curated selection</span>
            <span>Ready to ship</span>
          </div>
        </div>

        {filteredProducts.length > 0 ? (
          <div
            className="grid gap-5 lg:gap-6"
            style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 260px), 1fr))" }}
          >
            {filteredProducts.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        ) : (
          <div className="rounded-lg bg-white/[0.05] p-10 text-center">
            <h2 className="text-white">No products found</h2>
            <p className="mt-2 text-sm text-[#8892a4]">
              Try a different product, brand, or category in the search bar.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
