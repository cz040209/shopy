"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowUpRight, Banknote, Check, CheckCircle2, Clock3, CreditCard, Landmark, LoaderCircle, LockKeyhole, Plus, ReceiptText, ShieldCheck, WalletCards } from "lucide-react";
import { useCart } from "@/features/cart/cart-context";
import RequireAuth from "@/components/auth/RequireAuth";
import { apiFetch } from "@/lib/api";
import { getSessionShippingFee } from "@/lib/checkout";
import styles from "./shopy-pay.module.css";

const quickAmounts = [50, 100, 200, 500];
const paymentSources = ["FPX Online Banking", "Visa ending 4242", "DuitNow Transfer"];
type WalletTransaction = { id: string; title: string; description: string; amount: number; type: "credit" | "debit"; status: "Completed" | "Pending"; date: string };
type WalletApiTransaction = { id: string; reference: string; type: "top_up" | "purchase" | "refund" | "cashback" | "adjustment"; status: "completed" | "pending" | "failed" | "reversed"; amount: string; description: string | null; created_at: string };
type WalletApiResponse = { balance: string; daily_limit: string; monthly_limit: string; transactions: WalletApiTransaction[] };
const currency = new Intl.NumberFormat("en-MY", { currency: "MYR", style: "currency", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const SST_RATE = 0.06;

function roundUpToFiveSen(value: number) {
  return Math.ceil((value - Number.EPSILON) * 20) / 20;
}

function walletTransactions(records: WalletApiTransaction[]): WalletTransaction[] {
  return records.map((record) => ({
    id: record.reference,
    title: record.type === "top_up" ? "Top up" : record.type === "purchase" ? "ShopyPay purchase" : record.type.replaceAll("_", " "),
    description: record.description ?? "Wallet transaction",
    amount: Number(record.amount),
    type: record.type === "purchase" ? "debit" : "credit",
    status: record.status === "completed" ? "Completed" : "Pending",
    date: new Date(record.created_at).toLocaleString("en-MY", { day: "2-digit", hour: "numeric", minute: "2-digit", month: "short" }),
  }));
}

function ShopyPayContent() {
  const { cartItems, subtotal } = useCart();
  const [balance, setBalance] = useState(0);
  const [topUpAmount, setTopUpAmount] = useState("100");
  const [source, setSource] = useState(paymentSources[0]);
  const [transactions, setTransactions] = useState<WalletTransaction[]>([]);
  const [dailyLimit, setDailyLimit] = useState(3000);
  const [monthlyLimit, setMonthlyLimit] = useState(12000);
  const [topUpStage, setTopUpStage] = useState<"idle" | "processing" | "success">("idle");
  const successTimer = useRef<number | null>(null);
  useEffect(() => {
    let isCurrent = true;

    void apiFetch("/api/v1/wallet").then((wallet) => {
      if (!isCurrent) return;
      const record = wallet as WalletApiResponse;
      setBalance(Number(record.balance));
      setDailyLimit(Number(record.daily_limit));
      setMonthlyLimit(Number(record.monthly_limit));
      setTransactions(walletTransactions(record.transactions));
    }).catch((error) => console.error("Wallet load failed", error));
    return () => { isCurrent = false; };
  }, []);
  useEffect(() => {
    const requestedTopUp = Number(new URLSearchParams(window.location.search).get("top_up"));
    if (Number.isFinite(requestedTopUp) && requestedTopUp >= 10) {
      const id = window.setTimeout(() => setTopUpAmount(String(Math.ceil(requestedTopUp))), 0);
      return () => window.clearTimeout(id);
    }
  }, []);
  useEffect(() => () => {
    if (successTimer.current !== null) window.clearTimeout(successTimer.current);
  }, []);
  const amount = Number(topUpAmount);
  const cartSignature = useMemo(() => cartItems.map((item) => `${item.id}:${item.quantity}`).sort().join("|"), [cartItems]);
  const shippingFee = useMemo(() => getSessionShippingFee(cartSignature), [cartSignature]);
  const shippingSst = roundUpToFiveSen(shippingFee * SST_RATE);
  const checkoutTotal = subtotal + shippingFee + shippingSst;
  const availableAfterCart = balance - checkoutTotal;
  const dailyUsed = transactions.filter((item) => item.type === "credit").reduce((sum, item) => sum + item.amount, 0);
  const dailyRemaining = Math.max(dailyLimit - dailyUsed, 0);
  const topUpIsValid = Number.isFinite(amount) && amount >= 10 && amount <= dailyRemaining;
  const walletHealth = useMemo(() => [["Verification", "Verified"], ["Daily limit left", currency.format(dailyRemaining)], ["Monthly limit", currency.format(monthlyLimit)]], [dailyRemaining, monthlyLimit]);
  async function handleTopUp(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!topUpIsValid) return;
    setTopUpStage("processing");
    try {
      await new Promise<void>((resolve) => window.setTimeout(resolve, 2000));
      const wallet = await apiFetch("/api/v1/wallet/top-ups", { method: "POST", body: JSON.stringify({ amount: amount.toFixed(2), payment_source: source }) }) as WalletApiResponse;
      setBalance(Number(wallet.balance));
      setDailyLimit(Number(wallet.daily_limit));
      setMonthlyLimit(Number(wallet.monthly_limit));
      setTransactions(walletTransactions(wallet.transactions));
      setTopUpAmount("100");
      setTopUpStage("success");
      successTimer.current = window.setTimeout(() => setTopUpStage("idle"), 2200);
    } catch (error) {
      console.error("Wallet top-up failed", error);
      setTopUpStage("idle");
    }
  }
  return (
    <main className={styles.page}>
      {topUpStage !== "idle" && <div className={styles.topUpOverlay} role="status" aria-live="assertive"><div className={styles.topUpDialog}>{topUpStage === "processing" ? <><span className={styles.topUpStateIcon}><LoaderCircle size={28} /></span><p>Secure wallet transfer</p><h2>Confirming your top up</h2><span>We’re adding {currency.format(amount)} to your ShopyPay wallet.</span></> : <><span className={`${styles.topUpStateIcon} ${styles.topUpSuccessIcon}`}><CheckCircle2 size={30} /></span><p>Top up successful</p><h2>Your wallet is ready.</h2><span>{currency.format(amount)} has been added to your available balance.</span></>}</div></div>}
      <div className={styles.intro}><div><div className={styles.kicker}>Shopy wallet</div><div className={styles.title}>ShopyPay</div><div className={styles.subtitle}>A simpler way to pay, earn rewards, and keep track of every purchase.</div></div><div className={styles.secure}><ShieldCheck size={17} /> Secure wallet</div></div>
      <section className={styles.dashboard}>
        <div className={styles.balanceCard}><div className={styles.cardTop}><div className={styles.cardBrand}><WalletCards size={20} /> ShopyPay</div><div className={styles.cardChip} /></div><div className={styles.balanceLabel}>Available balance</div><div className={styles.balance}>{currency.format(balance)}</div><div className={styles.cardBottom}><div><div className={styles.cardSmall}>Wallet account</div><div className={styles.cardNumber}>•••• 8942</div></div><div className={styles.cardSmall}>MYR</div></div></div>
        <div className={styles.overview}><div className={styles.sectionHead}><div><div className={styles.sectionTitle}>Wallet overview</div><div className={styles.sectionCopy}>Your account is ready for checkout.</div></div><CheckCircle2 className={styles.verifiedIcon} size={27} /></div><div className={styles.healthList}>{walletHealth.map(([label, value]) => <div className={styles.healthRow} key={label}><div>{label}</div><strong>{value}</strong></div>)}</div><div className={styles.cartSummary}><div><div>Checkout total</div><strong>{currency.format(checkoutTotal)}</strong></div><div><div>After this checkout</div><strong className={availableAfterCart >= 0 ? styles.positive : styles.negative}>{currency.format(availableAfterCart)}</strong></div></div><Link href="/checkout" className={styles.payLink}>Pay with ShopyPay <ArrowUpRight size={17} /></Link></div>
      </section>
      <section className={styles.contentGrid}>
        <form onSubmit={handleTopUp} className={styles.topUp}><div className={styles.sectionHead}><div><div className={styles.sectionTitle}>Top up your wallet</div><div className={styles.sectionCopy}>Funds are available immediately after payment.</div></div><div className={styles.iconTile}><Plus size={20} /></div></div><label className={styles.formLabel} htmlFor="top-up-amount">Top-up amount</label><div className={styles.amountField}><span>RM</span><input id="top-up-amount" inputMode="numeric" min="10" type="number" value={topUpAmount} onChange={(event) => setTopUpAmount(event.target.value)} /></div><div className={styles.quickAmounts}>{quickAmounts.map((quickAmount) => <button key={quickAmount} type="button" onClick={() => setTopUpAmount(String(quickAmount))} className={topUpAmount === String(quickAmount) ? styles.amountActive : styles.amountOption}>{currency.format(quickAmount)}</button>)}</div><label className={styles.formLabel} htmlFor="payment-source">Pay with</label><div className={styles.selectWrap}><Landmark size={18} /><select id="payment-source" value={source} onChange={(event) => setSource(event.target.value)}>{paymentSources.map((item) => <option key={item} value={item}>{item}</option>)}</select></div><div className={styles.topUpTotal}><div><span>Processing fee</span><strong>RM0</strong></div><div><span>New wallet balance</span><strong>{topUpIsValid ? currency.format(balance + amount) : "--"}</strong></div></div>{!topUpIsValid && <div className={styles.error}>Enter RM10 or more, within your remaining daily limit.</div>}<button className={styles.confirmButton} type="submit" disabled={!topUpIsValid || topUpStage !== "idle"}>{topUpStage === "processing" ? <>Confirming top up <LoaderCircle className={styles.topUpSpinner} size={17} /></> : <>Confirm top up <ArrowUpRight size={17} /></>}</button></form>
        <div className={styles.activity}><div className={styles.sectionHead}><div><div className={styles.sectionTitle}>Recent activity</div><div className={styles.sectionCopy}>Your latest wallet payments and rewards.</div></div><div className={styles.ledger}><ReceiptText size={15} /> Live</div></div><div className={styles.transactionList}>{transactions.map((transaction) => { const isCredit = transaction.type === "credit"; return <article className={styles.transaction} key={transaction.id}><div className={styles.transactionIcon + " " + (isCredit ? styles.credit : styles.debit)}>{isCredit ? <Banknote size={19} /> : <CreditCard size={19} />}</div><div className={styles.transactionInfo}><div className={styles.transactionTitle}>{transaction.title} <span className={transaction.status === "Completed" ? styles.completed : styles.pending}>{transaction.status}</span></div><div className={styles.transactionDesc}>{transaction.description}</div><div className={styles.transactionDate}><Clock3 size={12} /> {transaction.date}</div></div><div className={styles.transactionAmount}><strong className={isCredit ? styles.positive : ""}>{isCredit ? "+" : "-"}{currency.format(transaction.amount)}</strong><div>{transaction.id}</div></div></article>; })}</div></div>
      </section>
      <section className={styles.controls}><div className={styles.controlsIntro}><div className={styles.iconTile}><ShieldCheck size={20} /></div><div><div className={styles.sectionTitle}>Wallet protection</div><div className={styles.sectionCopy}>Your balance is monitored around the clock.</div></div></div><div className={styles.controlList}>{[["Two-factor approval", "Required for payments above RM500"], ["Instant refund routing", "Eligible refunds return directly to ShopyPay"], ["Spending alerts", "Notifications are turned on for every payment"]].map(([title, copy]) => <div className={styles.controlItem} key={title}><div><strong>{title}</strong><span>{copy}</span></div><Check size={18} /></div>)}</div><div className={styles.securityNote}><LockKeyhole size={17} /> Card information is not stored in your ShopyPay wallet.</div></section>
    </main>
  );
}

export default function ShopyPay() {
  return <RequireAuth><ShopyPayContent /></RequireAuth>;
}
