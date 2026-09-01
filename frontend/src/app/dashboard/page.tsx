"use client";

import { useEffect, useMemo, useState } from "react";
import { BarChart3, ReceiptText, ShoppingBag } from "lucide-react";
import RequireAuth from "@/components/auth/RequireAuth";
import { apiFetch } from "@/lib/api";
import styles from "./dashboard.module.css";

type Order = { id: string; total_amount: string | number; created_at: string };
const currency = new Intl.NumberFormat("en-MY", { style: "currency", currency: "MYR", maximumFractionDigits: 0 });

function DashboardContent() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void apiFetch("/api/v1/orders").then((data) => setOrders(data as Order[])).catch(() => setOrders([])).finally(() => setLoading(false));
  }, []);

  const months = useMemo(() => Array.from({ length: 6 }, (_, offset) => {
    const date = new Date();
    date.setMonth(date.getMonth() - (5 - offset), 1);
    const key = `${date.getFullYear()}-${date.getMonth()}`;
    return { key, label: date.toLocaleDateString("en-MY", { month: "short" }), count: 0 };
  }), []);
  const activity = useMemo(() => months.map((month) => ({ ...month, count: orders.filter((order) => {
    const date = new Date(order.created_at);
    return `${date.getFullYear()}-${date.getMonth()}` === month.key;
  }).length })), [months, orders]);
  const maxOrders = Math.max(1, ...activity.map((item) => item.count));
  const spend = orders.reduce((total, order) => total + Number(order.total_amount), 0);

  return <main className={styles.page}>
    <div className={styles.kicker}>Purchase dashboard</div>
    <h1>Your shopping rhythm</h1>
    <p className={styles.intro}>A clear view of how often you buy and what you have spent with Shopy.</p>
    <section className={styles.metrics}>
      <article><ShoppingBag size={20} /><span>Orders placed</span><strong>{loading ? "—" : orders.length}</strong></article>
      <article><ReceiptText size={20} /><span>Total spent</span><strong>{loading ? "—" : currency.format(spend)}</strong></article>
      <article><BarChart3 size={20} /><span>Most active month</span><strong>{loading ? "—" : activity.reduce((best, item) => item.count > best.count ? item : best, activity[0]).label}</strong></article>
    </section>
    <section className={styles.chart}>
      <div><h2>Purchase frequency</h2><p>Orders placed each month over the last six months.</p></div>
      <div className={styles.bars} aria-label="Purchase frequency for the last six months">
        {activity.map((month) => <div className={styles.barColumn} key={month.key}><span className={styles.value}>{month.count}</span><div className={styles.barTrack}><i style={{ height: `${Math.max(month.count ? 16 : 4, (month.count / maxOrders) * 100)}%` }} /></div><span>{month.label}</span></div>)}
      </div>
    </section>
  </main>;
}

export default function DashboardPage() { return <RequireAuth><DashboardContent /></RequireAuth>; }
