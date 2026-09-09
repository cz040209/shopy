"use client";

import Link from "next/link";
import { BellRing, Check, ShoppingBag, Sparkles, Star, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useCart } from "@/features/cart/cart-context";
import ProductImage from "@/features/products/components/ProductImage";
import { toProduct, type ApiProduct, type Product } from "@/features/products/types";
import { apiFetch } from "@/lib/api";
import { AUTH_CHANGE_EVENT } from "@/lib/auth";
import { BEHAVIORAL_REMINDER_REFRESH_EVENT } from "@/lib/recommendations";
import styles from "./PersonalizedProductReminder.module.css";

type ReminderProduct = { product: ApiProduct; reason: string };
type ReminderResponse = { message: string; products: ReminderProduct[] };
type DisplayProduct = { product: Product; reason: string };

const sessionKey = "shopy:behavioral-reminder-shown";

export default function PersonalizedProductReminder() {
  const { addToCart } = useCart();
  const requestInFlight = useRef(false);
  const revealTimer = useRef<number | null>(null);
  const [message, setMessage] = useState("");
  const [products, setProducts] = useState<DisplayProduct[]>([]);
  const [visible, setVisible] = useState(false);
  const [addingId, setAddingId] = useState<string | null>(null);
  const [addedIds, setAddedIds] = useState<string[]>([]);

  useEffect(() => {
    const requestReminder = () => {
      if (requestInFlight.current || window.sessionStorage.getItem(sessionKey) === "1") return;
      requestInFlight.current = true;
      void apiFetch("/api/v1/recommendations/reminder", { method: "POST" })
        .then((payload) => {
          const reminder = payload as ReminderResponse;
          if (!reminder.products.length) return;
          setMessage(reminder.message);
          setProducts(reminder.products.map((item) => ({ product: toProduct(item.product), reason: item.reason })));
          window.sessionStorage.setItem(sessionKey, "1");
          revealTimer.current = window.setTimeout(() => setVisible(true), 1200);
        })
        .catch(() => {
          // Personalized reminders are optional and must not interrupt shopping.
        })
        .finally(() => { requestInFlight.current = false; });
    };

    const initialTimer = window.setTimeout(requestReminder, 2400);
    const handleAuthChange = () => {
      window.sessionStorage.removeItem(sessionKey);
      requestReminder();
    };
    window.addEventListener(BEHAVIORAL_REMINDER_REFRESH_EVENT, requestReminder);
    window.addEventListener(AUTH_CHANGE_EVENT, handleAuthChange);
    return () => {
      window.clearTimeout(initialTimer);
      window.removeEventListener(BEHAVIORAL_REMINDER_REFRESH_EVENT, requestReminder);
      window.removeEventListener(AUTH_CHANGE_EVENT, handleAuthChange);
      if (revealTimer.current !== null) window.clearTimeout(revealTimer.current);
    };
  }, []);

  async function handleAdd(product: Product) {
    if (addingId || addedIds.includes(product.id)) return;
    setAddingId(product.id);
    try {
      await addToCart(product);
      setAddedIds((current) => [...current, product.id]);
    } catch {
      // Keep the recommendation available if the cart request cannot complete.
    } finally {
      setAddingId(null);
    }
  }

  if (!visible || !products.length) return null;

  return (
    <aside className={styles.reminder} role="dialog" aria-modal="false" aria-labelledby="personalized-reminder-title">
      <div className={styles.glow} />
      <header className={styles.header}>
        <div className={styles.icon}><BellRing size={19} /></div>
        <div>
          <div className={styles.eyebrow}><Sparkles size={12} /> Picked for you</div>
          <h2 id="personalized-reminder-title">Something you may like</h2>
        </div>
        <button type="button" className={styles.close} onClick={() => setVisible(false)} aria-label="Dismiss recommendations"><X size={18} /></button>
      </header>
      <p className={styles.message}>{message}</p>

      <div className={styles.products}>
        {products.map(({ product, reason }) => {
          const added = addedIds.includes(product.id);
          return (
            <article className={styles.product} key={product.id}>
              <Link className={styles.productLink} href={`/product/${product.id}`} onClick={() => setVisible(false)}>
                <div className={styles.media}>
                  <ProductImage src={product.image} alt={product.name} width={112} height={112} className={styles.productImage} fallback={<span>{product.emoji}</span>} />
                </div>
                <div className={styles.details}>
                  <div className={styles.reason}>{reason}</div>
                  <h3>{product.name}</h3>
                  <div className={styles.meta}><span>{product.brand}</span><span><Star size={11} fill="currentColor" /> {product.rating.toFixed(1)}</span></div>
                  <strong>RM {product.price.toLocaleString("en-MY", { minimumFractionDigits: 2 })}</strong>
                </div>
              </Link>
              <button type="button" className={`${styles.add} ${added ? styles.added : ""}`} onClick={() => void handleAdd(product)} disabled={addingId === product.id || added} aria-label={`Add ${product.name} to cart`}>
                {added ? <Check size={16} /> : <ShoppingBag size={16} />}
              </button>
            </article>
          );
        })}
      </div>

      <div className={styles.footer}><span>Based on this session only</span><Link href="/shop" onClick={() => setVisible(false)}>Explore more</Link></div>
    </aside>
  );
}
