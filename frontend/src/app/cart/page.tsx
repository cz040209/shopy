"use client";

import Link from "next/link";
import {
  Minus,
  Plus,
  ShieldCheck,
  ShoppingBag,
  Trash2,
} from "lucide-react";
import Button from "@/components/ui/Button";
import RequireAuth from "@/components/auth/RequireAuth";
import { useCart } from "@/features/cart/cart-context";
import ProductImage from "@/features/products/components/ProductImage";
import styles from "./cart.module.css";

const currency = new Intl.NumberFormat("en-MY", {
  currency: "MYR",
  style: "currency",
  maximumFractionDigits: 0,
});

function CartContent() {
  const { cartItems, subtotal, updateQuantity, removeFromCart } = useCart();
  const service = cartItems.length > 0 ? 24 : 0;
  const total = subtotal + service;

  return (
    <div className={styles.cart}>
      <section>
        <div>
          <h1>Shopping Cart</h1>
          <p>
            Review your mission payload, adjust quantities, and move into a
            secure checkout flow without losing your orbit.
          </p>
        </div>

      </section>

      {cartItems.length === 0 ? (
        <section className="rounded-lg bg-white/[0.03] p-10 text-center">
          <ShoppingBag className="mx-auto mb-4 text-cyan-400" size={36} />
          <h2 className="text-white">Your cart is clear</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-[#8892a4]">
            Add a few products from the shop and your checkout route will be
            ready.
          </p>
          <Link href="/shop" className="mt-6 inline-flex">
            <Button variant="primary">Explore shop</Button>
          </Link>
        </section>
      ) : (
        <section className="grid gap-6 lg:grid-cols-[1fr_380px]">
          <div className="space-y-4">
            {cartItems.map((item) => (
              <article
                key={item.id}
                className={`${styles.cartItem} grid min-w-0 gap-5 rounded-lg bg-white/[0.03] p-5 transition md:grid-cols-[96px_1fr_auto] lg:p-6`}
              >
                <Link href={`/product/${item.id}`} className="flex items-center justify-center overflow-hidden rounded-xl bg-slate-100" style={{ width: 96, height: 96 }}>
                  <ProductImage
                    src={item.image}
                    alt={item.name}
                    width={160}
                    height={160}
                    style={{ width: "100%", height: "100%", objectFit: "contain", padding: 10 }}
                    fallback={<span aria-label={item.name} role="img" className="text-4xl">{item.emoji}</span>}
                  />
                </Link>

                <div className="min-w-0">
                  <p className="text-[0.65rem] font-semibold uppercase tracking-[0.16em] text-cyan-400">
                    {item.category} / {item.brand}
                  </p>
                  <Link
                    href={`/product/${item.id}`}
                    className="mt-1 block text-lg font-semibold text-white transition hover:text-cyan-400"
                  >
                    {item.name}
                  </Link>
                  <p
                    className="mt-2 line-clamp-2 max-w-xl text-sm text-[#8892a4]"
                    style={{ fontSize: "14px", lineHeight: "1.65", color: "#b4bfd1" }}
                  >
                    {item.desc}
                  </p>
                </div>

                <div className={`${styles.itemControls} flex min-w-0 flex-wrap items-center justify-between gap-5 md:flex-col md:items-end`}>
                  <p
                    className={styles.itemTotal}
                    style={{ color: "#f8fafc", fontSize: "16px", fontWeight: 800 }}
                  >
                    {currency.format(item.price * item.quantity)}
                  </p>
                  <div className={styles.quantityControls}>
                    <div className={styles.quantityStepper} aria-label={`${item.name} quantity`}>
                      <button
                        onClick={() => updateQuantity(item.cartItemId, item.quantity - 1)}
                        className={styles.quantityButton}
                        aria-label={`Decrease ${item.name} quantity`}
                      >
                        <Minus size={16} />
                      </button>
                      <span className={styles.quantityValue}>{item.quantity}</span>
                      <button
                        onClick={() => updateQuantity(item.cartItemId, item.quantity + 1)}
                        className={styles.quantityButton}
                        aria-label={`Increase ${item.name} quantity`}
                      >
                        <Plus size={16} />
                      </button>
                    </div>
                    <span className={styles.controlDivider} aria-hidden="true" />
                    <button
                      onClick={() => removeFromCart(item.cartItemId)}
                      className={styles.removeButton}
                      aria-label={`Remove ${item.name}`}
                      title={`Remove ${item.name}`}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>

          <aside className={`${styles.summary} h-fit rounded-lg bg-white/[0.03] p-6 lg:p-7`}>
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-cyan-400">
              Order telemetry
            </p>
            <div className="mt-6 space-y-3 pb-5">
              <div className="flex justify-between text-sm">
                <span className="text-[#8892a4]">Subtotal</span>
                <span className="text-white">{currency.format(subtotal)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-[#8892a4]">Priority handling</span>
                <span className="text-white">{currency.format(service)}</span>
              </div>
            </div>
            <div className="mt-5 flex items-end justify-between">
              <span className="text-sm uppercase tracking-widest text-[#8892a4]">
                Total
              </span>
              <span className="text-2xl font-bold text-white">
                {currency.format(total)}
              </span>
            </div>
            <div className={styles.summaryActions}>
              <Link href="/checkout">
                <Button variant="primary" fullWidth className={styles.checkoutButton}>
                  Proceed to checkout
                </Button>
              </Link>
              <Link href="/shop">
                <Button variant="outline" fullWidth className={styles.continueButton}>
                  Continue shopping
                </Button>
              </Link>
            </div>
            <div className="security-note mt-5">
              <ShieldCheck size={18} className="mt-0.5 shrink-0 text-cyan-400" />
              AI fraud checks and encrypted payment routing are active.
            </div>
          </aside>
        </section>
      )}
    </div>
  );
}

export default function Cart() {
  return <RequireAuth><CartContent /></RequireAuth>;
}
