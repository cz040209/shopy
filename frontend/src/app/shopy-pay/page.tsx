"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowUpRight, Banknote, Check, CheckCircle2, Clock3, CreditCard, Landmark, LockKeyhole, Plus, ReceiptText, ShieldCheck, WalletCards } from "lucide-react";
import { useCart } from "@/features/cart/cart-context";
import styles from "./shopy-pay.module.css";

const STORAGE_KEY = "shopy-pay-wallet";
const INITIAL_BALANCE = 420;
const dailyLimit = 3000;
const monthlyLimit = 12000;
const quickAmounts = [50, 100, 200, 500];
const paymentSources = ["FPX Online Banking", "Visa ending 4242", "DuitNow Transfer"];
type WalletTransaction = { id: string; title: string; description: string; amount: number; type: "credit" | "debit"; status: "Completed" | "Pending"; date: string };
type StoredWallet = { balance: number; transactions: WalletTransaction[] };
const initialTransactions: WalletTransaction[] = [
  { id: "SP-1007", title: "Checkout reserve", description: "Reserved for order security validation", amount: 128, type: "debit", status: "Pending", date: "Today, 10:45 AM" },
  { id: "SP-1006", title: "Top up", description: "FPX Online Banking", amount: 300, type: "credit", status: "Completed", date: "Yesterday, 8:12 PM" },
  { id: "SP-1005", title: "Cashback earned", description: "Shopy member reward", amount: 18, type: "credit", status: "Completed", date: "24 Jun, 2:30 PM" },
];
const currency = new Intl.NumberFormat("en-MY", { currency: "MYR", style: "currency", maximumFractionDigits: 0 });

function readStoredWallet(): StoredWallet | null {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (!stored) return null;
    const parsed = JSON.parse(stored) as Partial<StoredWallet>;
    return typeof parsed.balance === "number" && Array.isArray(parsed.transactions) ? { balance: parsed.balance, transactions: parsed.transactions } : null;
  } catch { return null; }
}

export default function ShopyPay() {
  const { subtotal } = useCart();
  const [balance, setBalance] = useState(INITIAL_BALANCE);
  const [topUpAmount, setTopUpAmount] = useState("100");
  const [source, setSource] = useState(paymentSources[0]);
  const [transactions, setTransactions] = useState<WalletTransaction[]>(initialTransactions);
  useEffect(() => { const id = window.setTimeout(() => { const stored = readStoredWallet(); if (stored) { setBalance(stored.balance); setTransactions(stored.transactions); } }, 0); return () => window.clearTimeout(id); }, []);
  useEffect(() => { window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ balance, transactions })); }, [balance, transactions]);
  const amount = Number(topUpAmount);
  const service = subtotal > 0 ? 24 : 0;
  const checkoutTotal = subtotal + service + Math.round(subtotal * .06);
  const availableAfterCart = balance - checkoutTotal;
  const dailyUsed = transactions.filter((item) => item.type === "credit").reduce((sum, item) => sum + item.amount, 0);
  const dailyRemaining = Math.max(dailyLimit - dailyUsed, 0);
  const topUpIsValid = Number.isFinite(amount) && amount >= 10 && amount <= dailyRemaining;
  const walletHealth = useMemo(() => [["Verification", "Verified"], ["Daily limit left", currency.format(dailyRemaining)], ["Monthly limit", currency.format(monthlyLimit)]], [dailyRemaining]);
  function handleTopUp(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!topUpIsValid) return;
    const nextTransaction: WalletTransaction = { id: "SP-" + Date.now().toString().slice(-6), title: "Top up", description: source, amount, type: "credit", status: "Completed", date: new Date().toLocaleString("en-MY", { day: "2-digit", hour: "numeric", minute: "2-digit", month: "short" }) };
    setBalance((current) => current + amount); setTransactions((current) => [nextTransaction, ...current].slice(0, 8)); setTopUpAmount("100");
  }
  return (
    <main className={styles.page}>
      <div className={styles.intro}><div><div className={styles.kicker}>Shopy wallet</div><div className={styles.title}>ShopyPay</div><div className={styles.subtitle}>A simpler way to pay, earn rewards, and keep track of every purchase.</div></div><div className={styles.secure}><ShieldCheck size={17} /> Secure wallet</div></div>
      <section className={styles.dashboard}>
        <div className={styles.balanceCard}><div className={styles.cardTop}><div className={styles.cardBrand}><WalletCards size={20} /> ShopyPay</div><div className={styles.cardChip} /></div><div className={styles.balanceLabel}>Available balance</div><div className={styles.balance}>{currency.format(balance)}</div><div className={styles.cardBottom}><div><div className={styles.cardSmall}>Wallet account</div><div className={styles.cardNumber}>•••• 8942</div></div><div className={styles.cardSmall}>MYR</div></div></div>
        <div className={styles.overview}><div className={styles.sectionHead}><div><div className={styles.sectionTitle}>Wallet overview</div><div className={styles.sectionCopy}>Your account is ready for checkout.</div></div><CheckCircle2 className={styles.verifiedIcon} size={27} /></div><div className={styles.healthList}>{walletHealth.map(([label, value]) => <div className={styles.healthRow} key={label}><div>{label}</div><strong>{value}</strong></div>)}</div><div className={styles.cartSummary}><div><div>Checkout total</div><strong>{currency.format(checkoutTotal)}</strong></div><div><div>After this checkout</div><strong className={availableAfterCart >= 0 ? styles.positive : styles.negative}>{currency.format(availableAfterCart)}</strong></div></div><Link href="/checkout" className={styles.payLink}>Pay with ShopyPay <ArrowUpRight size={17} /></Link></div>
      </section>
      <section className={styles.contentGrid}>
        <form onSubmit={handleTopUp} className={styles.topUp}><div className={styles.sectionHead}><div><div className={styles.sectionTitle}>Top up your wallet</div><div className={styles.sectionCopy}>Funds are available immediately after payment.</div></div><div className={styles.iconTile}><Plus size={20} /></div></div><label className={styles.formLabel} htmlFor="top-up-amount">Top-up amount</label><div className={styles.amountField}><span>RM</span><input id="top-up-amount" inputMode="numeric" min="10" type="number" value={topUpAmount} onChange={(event) => setTopUpAmount(event.target.value)} /></div><div className={styles.quickAmounts}>{quickAmounts.map((quickAmount) => <button key={quickAmount} type="button" onClick={() => setTopUpAmount(String(quickAmount))} className={topUpAmount === String(quickAmount) ? styles.amountActive : styles.amountOption}>{currency.format(quickAmount)}</button>)}</div><label className={styles.formLabel} htmlFor="payment-source">Pay with</label><div className={styles.selectWrap}><Landmark size={18} /><select id="payment-source" value={source} onChange={(event) => setSource(event.target.value)}>{paymentSources.map((item) => <option key={item} value={item}>{item}</option>)}</select></div><div className={styles.topUpTotal}><div><span>Processing fee</span><strong>RM0</strong></div><div><span>New wallet balance</span><strong>{topUpIsValid ? currency.format(balance + amount) : "--"}</strong></div></div>{!topUpIsValid && <div className={styles.error}>Enter RM10 or more, within your remaining daily limit.</div>}<button className={styles.confirmButton} type="submit" disabled={!topUpIsValid}>Confirm top up <ArrowUpRight size={17} /></button></form>
        <div className={styles.activity}><div className={styles.sectionHead}><div><div className={styles.sectionTitle}>Recent activity</div><div className={styles.sectionCopy}>Your latest wallet payments and rewards.</div></div><div className={styles.ledger}><ReceiptText size={15} /> Live</div></div><div className={styles.transactionList}>{transactions.map((transaction) => { const isCredit = transaction.type === "credit"; return <article className={styles.transaction} key={transaction.id}><div className={styles.transactionIcon + " " + (isCredit ? styles.credit : styles.debit)}>{isCredit ? <Banknote size={19} /> : <CreditCard size={19} />}</div><div className={styles.transactionInfo}><div className={styles.transactionTitle}>{transaction.title} <span className={transaction.status === "Completed" ? styles.completed : styles.pending}>{transaction.status}</span></div><div className={styles.transactionDesc}>{transaction.description}</div><div className={styles.transactionDate}><Clock3 size={12} /> {transaction.date}</div></div><div className={styles.transactionAmount}><strong className={isCredit ? styles.positive : ""}>{isCredit ? "+" : "-"}{currency.format(transaction.amount)}</strong><div>{transaction.id}</div></div></article>; })}</div></div>
      </section>
      <section className={styles.controls}><div className={styles.controlsIntro}><div className={styles.iconTile}><ShieldCheck size={20} /></div><div><div className={styles.sectionTitle}>Wallet protection</div><div className={styles.sectionCopy}>Your balance is monitored around the clock.</div></div></div><div className={styles.controlList}>{[["Two-factor approval", "Required for payments above RM500"], ["Instant refund routing", "Eligible refunds return directly to ShopyPay"], ["Spending alerts", "Notifications are turned on for every payment"]].map(([title, copy]) => <div className={styles.controlItem} key={title}><div><strong>{title}</strong><span>{copy}</span></div><Check size={18} /></div>)}</div><div className={styles.securityNote}><LockKeyhole size={17} /> Card information is not stored in your ShopyPay wallet.</div></section>
    </main>
  );
}
