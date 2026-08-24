"use client";

import Link from "next/link";
import Image from "next/image";
import {
  Minus,
  Plus,
  ShieldCheck,
  ShoppingBag,
  Trash2,
  Truck,
} from "lucide-react";
import { useState } from "react";
import Button from "@/components/ui/Button";
import { useCart } from "@/features/cart/cart-context";
import styles from "./cart.module.css";

const currency = new Intl.NumberFormat("en-MY", {
  currency: "MYR",
  style: "currency",
  maximumFractionDigits: 0,
});

export default function Cart() {
  const { cartItems, subtotal, updateQuantity, removeFromCart } = useCart();
  const [failedImages, setFailedImages] = useState<number[]>([]);
  const service = cartItems.length > 0 ? 24 : 0;
  const total = subtotal + service;

  return (
    <div className={styles.cart}>
      <section className="grid gap-6 lg:grid-cols-[1fr_360px] lg:items-end">
        <div>
          <h1 className="max-w-3xl text-white title-fancy">Shopping Cart</h1>
          <p className="mt-4 max-w-2xl text-base text-[#8892a4] subtitle-fancy">
            Review your mission payload, adjust quantities, and move into a
            secure checkout flow without losing your orbit.
          </p>
        </div>

        <div className="rounded-lg bg-cyan-400/[0.05] p-6 lg:p-7">
          <div className="flex items-center gap-4">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-400/10 text-cyan-400">
              <Truck size={20} />
            </span>
            <div>
              <p className="text-sm font-semibold text-white">
                Priority dispatch
              </p>
              <p className="text-xs text-[#8892a4]">
                Malaysia delivery estimate: 24-48 hours
              </p>
            </div>
          </div>
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
                className="grid min-w-0 gap-5 rounded-lg bg-white/[0.03] p-5 transition md:grid-cols-[96px_1fr_auto] lg:p-6"
              >
                <Link href={`/product/${item.id}`} className="flex items-center justify-center overflow-hidden rounded-xl bg-slate-100" style={{ width: 96, height: 96 }}>
                  {item.image && !failedImages.includes(item.id) ? (
                    <Image
                      src={item.image}
                      alt={item.name}
                      width={160}
                      height={160}
                      style={{ width: "100%", height: "100%", objectFit: "contain", padding: 10 }}
                      onError={() => setFailedImages((current) => [...current, item.id])}
                    />
                  ) : (
                    <span aria-label={item.name} role="img" className="text-4xl">{item.emoji}</span>
                  )}
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
                  <p className="mt-2 line-clamp-2 max-w-xl text-sm text-[#8892a4]">
                    {item.desc}
                  </p>
                </div>

                <div className="flex min-w-0 flex-wrap items-center justify-between gap-5 md:flex-col md:items-end">
                  <p className="text-lg font-bold text-white">
                    {currency.format(item.price * item.quantity)}
                  </p>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => updateQuantity(item.id, item.quantity - 1)}
                      className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/5 text-[#8892a4] transition hover:bg-white/10 hover:text-cyan-400"
                      aria-label={`Decrease ${item.name} quantity`}
                    >
                      <Minus size={15} />
                    </button>
                    <span className="w-8 text-center text-sm font-semibold text-white">
                      {item.quantity}
                    </span>
                    <button
                      onClick={() => updateQuantity(item.id, item.quantity + 1)}
                      className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/5 text-[#8892a4] transition hover:bg-white/10 hover:text-cyan-400"
                      aria-label={`Increase ${item.name} quantity`}
                    >
                      <Plus size={15} />
                    </button>
                    <button
                      onClick={() => removeFromCart(item.id)}
                      className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-500/10 text-red-300 transition hover:bg-red-500/20"
                      aria-label={`Remove ${item.name}`}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>

          <aside className="h-fit rounded-lg bg-white/[0.03] p-6 lg:p-7">
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
            <Link href="/checkout" className="mt-6 block">
              <Button variant="primary" fullWidth>
                Proceed to checkout
              </Button>
            </Link>
            <Link href="/shop" className="mt-4 block">
              <Button variant="outline" fullWidth>
                Continue shopping
              </Button>
            </Link>
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
