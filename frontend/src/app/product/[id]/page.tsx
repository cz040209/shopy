"use client";
import Link from "next/link";
import { notFound } from "next/navigation";
import { useEffect, useState, use } from "react";
import { ChevronLeft, Heart, Minus, Plus, ShieldCheck, ShoppingBag, Star, Truck } from "lucide-react";
import ProductCard from "@/features/products/components/ProductCard";
import ProductImage from "@/features/products/components/ProductImage";
import Toast from "@/components/ui/Toast";
import { apiFetch } from "@/lib/api";
import { toProduct, type ApiProduct, type Product } from "@/features/products/types";
import { useCart } from "@/features/cart/cart-context";
import styles from "./product.module.css";

export default function ProductPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [notFoundProduct, setNotFoundProduct] = useState(false);
  useEffect(() => {
    void apiFetch(`/api/v1/products/${id}`)
      .then((product: ApiProduct) => setSelectedProduct(toProduct(product)))
      .catch(() => setNotFoundProduct(true));
  }, [id]);
  if (notFoundProduct) notFound();

  const { addToCart } = useCart();
  const [qty, setQty] = useState(1);
  const [toast, setToast] = useState(false);

  const related: Product[] = [];

  function handleAdd() {
    void addToCart(selectedProduct!, qty).then(() => {
      setToast(true);
      setTimeout(() => setToast(false), 2200);
    });
  }

  if (!selectedProduct) return <main className={styles.productPage}>Loading product…</main>;
  const stars = Math.round(selectedProduct.rating);

  return (
    <main className={styles.productPage}>
      {toast && <Toast message={`${selectedProduct.emoji} Added to cart`} />}

      <Link href="/shop" className={styles.backLink}>
        <ChevronLeft size={17} /> All products
      </Link>

      <section className={styles.productLayout}>
        <div className={styles.gallery}>
          <div className={styles.imageStage}>
            <span className={styles.imageLabel}>Featured product</span>
            <ProductImage
              src={selectedProduct.image}
              alt={selectedProduct.name}
              fill
              preload
              sizes="(max-width: 960px) 100vw, 52vw"
              className={styles.productImage}
              fallback={<span className={styles.emoji}>{selectedProduct.emoji}</span>}
            />
          </div>
          <div className={styles.deliveryStrip}><Truck size={17} /><span>Fast delivery across Malaysia</span><span className={styles.deliveryDot} /> <span>Easy returns</span></div>
        </div>

        <div className={styles.details}>
          <div className={styles.productIntro}>
            <p className={styles.category}>{selectedProduct.category} <span /> {selectedProduct.brand}</p>
            <h1>{selectedProduct.name}</h1>
            <div className={styles.rating}><span className={styles.stars}>{Array.from({ length: 5 }, (_, index) => <Star key={index} size={16} fill={index < stars ? "currentColor" : "none"} />)}</span><strong>{selectedProduct.rating.toFixed(1)}</strong><span>{selectedProduct.reviews.toLocaleString()} reviews</span></div>
          </div>

          <div className={styles.priceRow}><span>Price</span><strong>RM {selectedProduct.price.toLocaleString()}</strong></div>
          <p className={styles.description}>{selectedProduct.desc}</p>

          <div className={styles.specs}>
            {selectedProduct.specs.map((spec) => <div key={spec.label}><span>{spec.label}</span><strong>{spec.value}</strong></div>)}
          </div>

          <div className={`${styles.stock} ${selectedProduct.stock ? styles.inStock : styles.outOfStock}`}><i />{selectedProduct.stock ? "In stock · ready to dispatch" : "Currently out of stock"}</div>

          <div className={styles.purchaseRow}>
            {selectedProduct.stock && <div className={styles.quantity} aria-label="Quantity"><button onClick={() => setQty(Math.max(1, qty - 1))} aria-label="Decrease quantity"><Minus size={16} /></button><span>{qty}</span><button onClick={() => setQty(qty + 1)} aria-label="Increase quantity"><Plus size={16} /></button></div>}
            <button className={styles.addButton} onClick={handleAdd} disabled={!selectedProduct.stock}><ShoppingBag size={19} />{selectedProduct.stock ? "Add to cart" : "Out of stock"}</button>
            <button className={styles.wishlistButton} aria-label="Add to wishlist"><Heart size={20} /></button>
          </div>
          <div className={styles.protection}><ShieldCheck size={18} /><span>Secure checkout with protected payment processing.</span></div>
        </div>
      </section>

      <section className={styles.related}>
        <div className={styles.relatedHeading}><div><p>Discover more</p><h2>You may also like</h2></div><Link href="/shop">View all products</Link></div>
        <div className={styles.relatedGrid}>
          {related.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      </section>
    </main>
  );
}
