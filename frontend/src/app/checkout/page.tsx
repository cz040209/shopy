"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { jsPDF } from "jspdf";
import {
  CreditCard,
  LockKeyhole,
  MapPin,
  Radio,
  ShieldCheck,
} from "lucide-react";
import Button from "@/components/ui/Button";
import RequireAuth from "@/components/auth/RequireAuth";
import { useCart } from "@/features/cart/cart-context";
import ProductImage from "@/features/products/components/ProductImage";
import styles from "./checkout.module.css";
import invoiceStyles from "./invoice.module.css";

const currency = new Intl.NumberFormat("en-MY", {
  currency: "MYR",
  style: "currency",
  maximumFractionDigits: 0,
});

const invoiceCardStyle = {
  borderRadius: "1rem",
  backgroundImage: "linear-gradient(135deg, #071019 0%, #061018 100%)",
  padding: "1px",
  boxShadow: "0 18px 44px rgba(0, 0, 0, 0.28)",
} as const;

const invoicePanelStyle = {
  borderRadius: "0.75rem",
  backgroundColor: "rgba(17, 21, 39, 0.92)",
  padding: "1.25rem",
} as const;

const invoiceDividerStyle = {
  borderTop: "1px solid rgba(255, 255, 255, 0.06)",
  paddingTop: "1rem",
  display: "flex",
  flexDirection: "column" as const,
  gap: "0.75rem",
} as const;

function CheckoutContent() {
  const invoiceRef = useRef<HTMLDivElement | null>(null);
  const [invoiceNumber, setInvoiceNumber] = useState("Pending");
  const [invoiceDate, setInvoiceDate] = useState("Pending");
  const [isExporting, setIsExporting] = useState(false);
  const { cartItems, subtotal, clearCart } = useCart();
  const tax = Math.round(subtotal * 0.06);
  const handling = cartItems.length > 0 ? 24 : 0;
  const total = subtotal + tax + handling;

  useEffect(() => {
    const id = window.setTimeout(() => {
      setInvoiceNumber(String(Math.floor(Math.random() * 900000 + 100000)));
      setInvoiceDate(new Date().toLocaleDateString());
    }, 0);

    return () => window.clearTimeout(id);
  }, []);

  const exportInvoicePdf = async () => {
    try {
      setIsExporting(true);

      const pdf = new jsPDF("p", "mm", "a4");
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const margin = 14;
      let y = 20;

      pdf.setFillColor(250, 245, 220);
      pdf.rect(0, 0, pageWidth, pageHeight, "F");

      pdf.setFillColor(240, 200, 90);
      pdf.roundedRect(margin - 2, 10, pageWidth - margin * 2 + 4, 32, 2, 2, "F");

      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(20);
      pdf.setTextColor(60, 46, 12);
      pdf.text("Shopy Invoice", margin, 22);

      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(10);
      pdf.setTextColor(95, 74, 30);
      pdf.text(`Invoice #${invoiceNumber}`, margin, 29);
      pdf.text(`Date: ${invoiceDate}`, pageWidth - margin - 38, 29);
      y = 42;

      pdf.setDrawColor(210, 185, 95);
      pdf.line(margin, y, pageWidth - margin, y);
      y += 8;

      pdf.setFillColor(255, 250, 232);
      pdf.roundedRect(margin, y - 3, pageWidth - margin * 2, 30, 2, 2, "F");
      pdf.setTextColor(70, 50, 10);
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(11);
      pdf.text("Billing details", margin + 2, y + 4);
      y += 8;

      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(10);
      pdf.text("Jeffrey Tan", margin + 2, y + 2);
      pdf.text("+60 12 345 6789", margin + 2, y + 8);
      pdf.text("Kuala Lumpur City Centre", margin + 2, y + 14);
      y += 20;

      pdf.setFont("helvetica", "bold");
      pdf.text("Items", margin, y + 6);
      y += 12;

      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(9);
      pdf.setTextColor(85, 66, 22);
      const col1X = margin;
      const col2X = pageWidth - margin - 50;
      const col3X = pageWidth - margin - 24;
      pdf.text("Description", col1X, y + 2);
      pdf.text("Qty", col2X, y + 2);
      pdf.text("Amount", col3X, y + 2);
      y += 6;
      pdf.setDrawColor(222, 201, 125);
      pdf.line(margin, y, pageWidth - margin, y);
      y += 4;

      for (const item of cartItems) {
        const name = `${item.name} (SKU ${item.id})`;
        const lines = pdf.splitTextToSize(name, col2X - col1X - 2);
        const lineCount = Math.max(1, lines.length);

        pdf.text(lines, col1X, y);
        pdf.text(String(item.quantity), col2X, y);
        pdf.text(currency.format(item.price * item.quantity), col3X, y);
        y += lineCount * 3.5;
      }

      y += 6;
      pdf.setDrawColor(222, 201, 125);
      pdf.line(margin, y, pageWidth - margin, y);
      y += 10;

      pdf.setFont("helvetica", "bold");
      pdf.text("Subtotal", margin, y);
      pdf.text(currency.format(subtotal), col3X, y);
      y += 5;
      pdf.text("SST estimate", margin, y);
      pdf.text(currency.format(tax), col3X, y);
      y += 5;
      pdf.text("Handling", margin, y);
      pdf.text(currency.format(handling), col3X, y);
      y += 16;
      pdf.setFontSize(12);
      pdf.setTextColor(60, 46, 12);
      pdf.text("Total", margin, y);
      pdf.text(currency.format(total), col3X, y);

      pdf.save(`shopy-invoice-${invoiceNumber}.pdf`);
    } catch (error) {
      console.error("Invoice export failed", error);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className={styles.checkout}>
      <section className="grid gap-6 lg:grid-cols-[1fr_360px] lg:items-end">
        <div>
          <h1 className="max-w-3xl text-white title-fancy">Order Summary</h1>
          <p className="mt-4 max-w-2xl text-base text-[#8892a4] subtitle-fancy">
            Confirm your delivery vector, payment method, and final amount
            before the order enters fulfillment.
          </p>
        </div>

        <div className="rounded-lg bg-white/[0.03] p-6 lg:p-7">
          <div className="flex items-center gap-4">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-400/10 text-emerald-300">
              <ShieldCheck size={20} />
            </span>
            <div>
              <p className="text-sm font-semibold text-white">
                Payment shield online
              </p>
              <p className="text-xs text-[#8892a4]">
                AI risk scoring runs before authorization.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1fr_380px]">
        <div className="space-y-6">
          <div className="rounded-lg bg-white/[0.03] p-6 lg:p-7">
            <div className="mb-6 flex items-center gap-4">
              <MapPin className="text-cyan-400" size={21} />
              <h2 className="text-white subtitle-fancy">Delivery Coordinates</h2>
            </div>
            <div className="grid gap-5 md:grid-cols-2">
              <div>
                <label htmlFor="name">Full name</label>
                <input id="name" className="input" defaultValue="Jeffrey Tan" />
              </div>
              <div>
                <label htmlFor="phone">Phone</label>
                <input id="phone" className="input" defaultValue="+60 12 345 6789" />
              </div>
              <div className="md:col-span-2">
                <label htmlFor="address">Address</label>
                <input
                  id="address"
                  className="input"
                  defaultValue="Kuala Lumpur City Centre"
                />
              </div>
            </div>
          </div>

          <div className="rounded-lg bg-white/[0.03] p-6 lg:p-7">
            <div className="mb-6 flex items-center gap-4">
              <CreditCard className="text-cyan-400" size={21} />
              <h2 className="text-white subtitle-fancy">Payment Method</h2>
            </div>
            <div className="grid gap-5 md:grid-cols-2">
              <div className="md:col-span-2">
                <label htmlFor="card">Card number</label>
                <input
                  id="card"
                  className="input"
                  defaultValue="4242 4242 4242 4242"
                />
              </div>
              <div>
                <label htmlFor="expiry">Expiry</label>
                <input id="expiry" className="input" defaultValue="08 / 29" />
              </div>
              <div>
                <label htmlFor="cvc">CVC</label>
                <input id="cvc" className="input" defaultValue="128" />
              </div>
            </div>
          </div>

          <div className="security-note">
            <LockKeyhole size={18} className="mt-0.5 shrink-0 text-cyan-400" />
            Checkout uses encrypted fields, velocity checks, and device
            fingerprint review before the final payment request.
          </div>
        </div>

        <aside className="h-fit rounded-lg bg-white/[0.03] p-6 lg:p-7">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-lg font-semibold text-white">Shopy Invoice</h3>
              <p className="text-xs text-[#93a6bd]">Order summary & receipt</p>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <button
                type="button"
                onClick={exportInvoicePdf}
                disabled={isExporting || cartItems.length === 0}
                className="inline-flex items-center gap-2 rounded-full bg-white/6 px-3 py-1 text-sm text-white transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isExporting ? "Preparing PDF..." : "Download PDF"}
              </button>
            </div>
          </div>

          <div className="invoice-print-area mt-4" ref={invoiceRef} style={{ width: "100%" }}>
            <div style={invoiceCardStyle}>
              <div style={invoicePanelStyle}>
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <p className="text-sm text-[#9aa8bf]">Invoice #</p>
                    <p className="text-sm font-medium text-white">#{invoiceNumber}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-[#9aa8bf]">Date</p>
                    <p className="text-sm font-medium text-white">{invoiceDate}</p>
                  </div>
                </div>

                <div className={invoiceStyles.tableWrap}>
                  <table className={invoiceStyles.table}>
                    <thead>
                      <tr className="text-[#93a6bd]">
                        <th className="text-left pb-3">Description</th>
                        <th className="text-right pb-3">Unit price</th>
                        <th className="text-right pb-3">Qty</th>
                        <th className="text-right pb-3">Amount</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cartItems.map((item) => (
                        <tr key={item.id} className="align-top">
                          <td className="py-4 pr-4">
                            <div className={invoiceStyles.productDetails}>
                              <div className={invoiceStyles.productImage}>
                                <ProductImage
                                  src={item.image}
                                  alt={item.name}
                                  width={112}
                                  height={112}
                                  sizes="56px"
                                  fallback={<span role="img" aria-label={item.name}>{item.emoji}</span>}
                                />
                              </div>
                              <div className={invoiceStyles.productCopy}>
                                <div className="text-white font-semibold">{item.name}</div>
                                <div className="text-xs text-[#9aa8bf]">SKU: {item.id} · {item.brand}</div>
                              </div>
                            </div>
                          </td>
                          <td className="py-4 text-right text-[#9aa8bf]">{currency.format(item.price)}</td>
                          <td className="py-4 text-right text-[#9aa8bf]">{item.quantity}</td>
                          <td className="py-4 text-right font-semibold text-white">{currency.format(item.price * item.quantity)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="mt-5 text-sm" style={invoiceDividerStyle}>
                  <div className="flex justify-between text-[#93a6bd]"><span>Subtotal</span><span className="text-white">{currency.format(subtotal)}</span></div>
                  <div className="flex justify-between text-[#93a6bd]"><span>SST estimate</span><span className="text-white">{currency.format(tax)}</span></div>
                  <div className="flex justify-between text-[#93a6bd]"><span>Handling</span><span className="text-white">{currency.format(handling)}</span></div>
                  <div className="flex justify-between items-center pt-3">
                    <span className="text-sm uppercase tracking-widest text-[#93a6bd]">Total</span>
                    <span className="text-2xl font-extrabold text-white">{currency.format(total)}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <Button
            variant="primary"
            fullWidth
            className="mt-6"
            disabled={cartItems.length === 0}
            onClick={clearCart}
          >
            Complete payment
          </Button>
          <Link href="/cart" className="mt-4 block">
            <Button variant="outline" fullWidth>
              Return to cart
            </Button>
          </Link>

          <div className="mt-5 flex items-center gap-2 text-xs text-[#8892a4]">
            <Radio size={15} className="text-cyan-400" />
            Live fraud detection is monitoring this session.
          </div>
        </aside>
      </section>
    </div>
  );
}

export default function Checkout() {
  return <RequireAuth><CheckoutContent /></RequireAuth>;
}
