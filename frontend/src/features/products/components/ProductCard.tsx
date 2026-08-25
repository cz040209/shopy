"use client";

import Link from "next/link";
import { ShoppingBag, Star } from "lucide-react";
import { useState } from "react";
import type { Product } from "@/features/products/data/products";
import { useCart } from "@/features/cart/cart-context";
import Toast from "@/components/ui/Toast";
import ProductImage from "./ProductImage";
import styles from "./ProductCard.module.css";

type Props = { product: Product };

export default function ProductCard({ product }: Props) {
  const { addToCart } = useCart();
  const [toast, setToast] = useState(false);

  function handleAdd(event: React.MouseEvent) {
    event.preventDefault();
    event.stopPropagation();
    addToCart(product);
    setToast(true);
    setTimeout(() => setToast(false), 2200);
  }

  return (
    <>
      {toast && <Toast message={`${product.emoji} Added to cart`} />}
      <Link href={`/product/${product.id}`} className={styles.cardLink}>
        <article className={styles.card}>
          <div className={styles.media}>
            {product.badge && <div className={`${styles.badge} ${styles[product.badge]}`}>{product.badge}</div>}
            <ProductImage
              src={product.image}
              alt={product.name}
              width={420}
              height={360}
              className={styles.image}
              fallback={<div className={styles.emoji}>{product.emoji}</div>}
            />
          </div>

          <div className={styles.content}>
            <div className={styles.meta}>
              <div className={styles.category}>{product.category}</div>
              <div className={styles.brand}>{product.brand}</div>
            </div>
            <div className={styles.name}>{product.name}</div>
            <div className={styles.description}>{product.desc}</div>

            <div className={styles.footer}>
              <div>
                <div className={styles.price}>RM {product.price.toLocaleString()}</div>
                <div className={styles.rating}>
                  <Star size={13} fill="currentColor" /> {product.rating} <span>({product.reviews.toLocaleString()})</span>
                </div>
              </div>
              {product.stock ? (
                <button onClick={handleAdd} className={styles.addButton} aria-label={`Add ${product.name} to cart`}>
                  <ShoppingBag size={17} />
                  <span>Add</span>
                </button>
              ) : (
                <div className={styles.soldOut}>Sold out</div>
              )}
            </div>
          </div>
        </article>
      </Link>
    </>
  );
}
