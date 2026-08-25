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
import { apiFetch } from "@/lib/api";
import styles from "./checkout.module.css";
import invoiceStyles from "./invoice.module.css";

const currency = new Intl.NumberFormat("en-MY", {
  currency: "MYR",
  style: "currency",
  maximumFractionDigits: 0,
});

function CheckoutContent() {
  const invoiceRef = useRef<HTMLDivElement | null>(null);
  const [invoiceNumber, setInvoiceNumber] = useState("Pending");
  const [invoiceDate, setInvoiceDate] = useState("Pending");
  const [isExporting, setIsExporting] = useState(false);
  const { cartItems, subtotal, refreshCart } = useCart();
  const [isPlacingOrder, setIsPlacingOrder] = useState(false);
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
      const margin = 16;
      const contentWidth = pageWidth - margin * 2;
      const itemColumn = margin + 5;
      const unitPriceColumn = pageWidth - margin - 65;
      const quantityColumn = pageWidth - margin - 37;
      const amountColumn = pageWidth - margin - 5;
      const footerY = pageHeight - 11;
      let y = 0;

      const drawPageChrome = (isContinuation = false) => {
        pdf.setFillColor(10, 16, 33);
        pdf.rect(0, 0, pageWidth, pageHeight, "F");
        pdf.setFillColor(103, 79, 224);
        pdf.rect(0, 0, pageWidth, 42, "F");
        pdf.setFillColor(34, 211, 238);
        pdf.rect(0, 40, pageWidth, 2, "F");

        pdf.setFillColor(255, 255, 255);
        pdf.roundedRect(margin, 12, 11, 11, 2.5, 2.5, "F");
        pdf.setTextColor(93, 70, 213);
        pdf.setFont("helvetica", "bold");
        pdf.setFontSize(13);
        pdf.text("S", margin + 5.5, 19.7, { align: "center" });

        pdf.setTextColor(255, 255, 255);
        pdf.setFontSize(16);
        pdf.text("SHOPY", margin + 15, 18);
        pdf.setFont("helvetica", "normal");
        pdf.setFontSize(7.5);
        pdf.setTextColor(226, 232, 255);
        pdf.text(isContinuation ? "INVOICE - CONTINUED" : "SECURE COMMERCE INVOICE", margin + 15, 24);

        pdf.setFont("helvetica", "bold");
        pdf.setFontSize(8);
        pdf.setTextColor(226, 232, 255);
        pdf.text("INVOICE NUMBER", pageWidth - margin, 15, { align: "right" });
        pdf.setFontSize(11);
        pdf.setTextColor(255, 255, 255);
        pdf.text(`#${invoiceNumber}`, pageWidth - margin, 21, { align: "right" });
        pdf.setFont("helvetica", "normal");
        pdf.setFontSize(8);
        pdf.setTextColor(226, 232, 255);
        pdf.text(`Issued ${invoiceDate}`, pageWidth - margin, 27, { align: "right" });
      };

      const drawItemHeader = (top: number) => {
        pdf.setFillColor(28, 39, 67);
        pdf.roundedRect(margin, top, contentWidth, 10, 2, 2, "F");
        pdf.setFont("helvetica", "bold");
        pdf.setFontSize(7.5);
        pdf.setTextColor(173, 187, 224);
        pdf.text("ITEM", itemColumn, top + 6.3);
        pdf.text("UNIT PRICE", unitPriceColumn, top + 6.3, { align: "right" });
        pdf.text("QTY", quantityColumn, top + 6.3, { align: "right" });
        pdf.text("AMOUNT", amountColumn, top + 6.3, { align: "right" });
      };

      const startNewPage = () => {
        pdf.addPage();
        drawPageChrome(true);
        y = 55;
        drawItemHeader(y);
        y += 15;
      };

      drawPageChrome();
      y = 53;

      const cardGap = 6;
      const cardWidth = (contentWidth - cardGap) / 2;
      const rightCardX = margin + cardWidth + cardGap;
      pdf.setFillColor(20, 30, 54);
      pdf.roundedRect(margin, y, cardWidth, 34, 3, 3, "F");
      pdf.roundedRect(rightCardX, y, cardWidth, 34, 3, 3, "F");

      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(7.5);
      pdf.setTextColor(151, 166, 211);
      pdf.text("BILLED TO", margin + 5, y + 7);
      pdf.text("PAYMENT & DELIVERY", rightCardX + 5, y + 7);
      pdf.setFontSize(10.5);
      pdf.setTextColor(245, 247, 255);
      pdf.text("Jeffrey Tan", margin + 5, y + 14);
      pdf.text("Secure checkout", rightCardX + 5, y + 14);
      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(8.5);
      pdf.setTextColor(180, 193, 222);
      pdf.text("+60 12 345 6789", margin + 5, y + 20);
      pdf.text("Card payment - authorization pending", rightCardX + 5, y + 20);
      pdf.text("Kuala Lumpur City Centre", margin + 5, y + 26);
      pdf.text("Kuala Lumpur, Malaysia", rightCardX + 5, y + 26);

      y += 48;
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(13);
      pdf.setTextColor(245, 247, 255);
      pdf.text("Order details", margin, y);
      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(8.5);
      pdf.setTextColor(160, 175, 211);
      pdf.text(`${cartItems.length} item${cartItems.length === 1 ? "" : "s"} in this order`, margin, y + 5.5);
      y += 11;
      drawItemHeader(y);
      y += 15;

      for (const item of cartItems) {
        const nameLines = pdf.splitTextToSize(item.name, 75) as string[];
        const rowHeight = Math.max(18, nameLines.length * 4.3 + 10);

        if (y + rowHeight > footerY - 45) {
          startNewPage();
        }

        pdf.setFillColor(19, 28, 50);
        pdf.roundedRect(margin, y, contentWidth, rowHeight, 2.5, 2.5, "F");
        pdf.setFont("helvetica", "bold");
        pdf.setFontSize(9.5);
        pdf.setTextColor(245, 247, 255);
        pdf.text(nameLines, itemColumn, y + 7);
        pdf.setFont("helvetica", "normal");
        pdf.setFontSize(7.5);
        pdf.setTextColor(151, 166, 211);
        pdf.text(`SKU ${item.id.slice(-8).toUpperCase()}`, itemColumn, y + 7 + nameLines.length * 4.3 + 2.5);
        pdf.setFontSize(8.5);
        pdf.setTextColor(218, 226, 249);
        pdf.text(currency.format(item.price), unitPriceColumn, y + 9, { align: "right" });
        pdf.text(String(item.quantity), quantityColumn, y + 9, { align: "right" });
        pdf.setFont("helvetica", "bold");
        pdf.setTextColor(255, 255, 255);
        pdf.text(currency.format(item.price * item.quantity), amountColumn, y + 9, { align: "right" });
        y += rowHeight + 4;
      }

      const totalsHeight = 50;
      if (y + totalsHeight > footerY) {
        startNewPage();
      }

      const totalsWidth = 82;
      const totalsX = pageWidth - margin - totalsWidth;
      pdf.setFillColor(28, 39, 67);
      pdf.roundedRect(totalsX, y, totalsWidth, totalsHeight, 3, 3, "F");
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(8);
      pdf.setTextColor(151, 166, 211);
      pdf.text("PAYMENT SUMMARY", totalsX + 6, y + 8);

      const totals = [
        ["Subtotal", currency.format(subtotal)],
        ["SST estimate", currency.format(tax)],
        ["Handling", currency.format(handling)],
      ];
      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(8.5);
      for (const [index, [label, value]] of totals.entries()) {
        const lineY = y + 16 + index * 6;
        pdf.setTextColor(180, 193, 222);
        pdf.text(label, totalsX + 6, lineY);
        pdf.setTextColor(245, 247, 255);
        pdf.text(value, totalsX + totalsWidth - 6, lineY, { align: "right" });
      }
      pdf.setDrawColor(74, 88, 128);
      pdf.line(totalsX + 6, y + 35, totalsX + totalsWidth - 6, y + 35);
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(11);
      pdf.setTextColor(255, 255, 255);
      pdf.text("TOTAL", totalsX + 6, y + 44);
      pdf.setTextColor(111, 235, 255);
      pdf.text(currency.format(total), totalsX + totalsWidth - 6, y + 44, { align: "right" });

      pdf.setDrawColor(39, 53, 87);
      pdf.line(margin, footerY - 5, pageWidth - margin, footerY - 5);
      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(7.5);
      pdf.setTextColor(134, 149, 185);
      pdf.text("Generated by Shopy - secure checkout reference.", margin, footerY);
      pdf.text("Thank you for shopping with us.", pageWidth - margin, footerY, { align: "right" });

      pdf.save(`shopy-invoice-${invoiceNumber}.pdf`);
    } catch (error) {
      console.error("Invoice export failed", error);
    } finally {
      setIsExporting(false);
    }
  };

  const completeCheckout = async () => {
    try {
      setIsPlacingOrder(true);
      const order = await apiFetch("/api/v1/orders/checkout", {
        method: "POST",
        body: JSON.stringify({
          shipping_address: {
            recipient_name: "Jeffrey Tan", phone: "+60 12 345 6789",
            line1: "Kuala Lumpur City Centre", city: "Kuala Lumpur", state: "Kuala Lumpur",
            postal_code: "50088", country_code: "MY",
          },
          payment_method: "card",
        }),
      }) as { order_number: string; placed_at: string };
      setInvoiceNumber(order.order_number);
      setInvoiceDate(new Date(order.placed_at).toLocaleDateString());
      await refreshCart();
    } catch (error) {
      console.error("Checkout failed", error);
    } finally {
      setIsPlacingOrder(false);
    }
  };

  return (
    <div className={styles.checkout}>
      <section className={styles.checkoutHeader}>
        <div>
          <h1 className="max-w-3xl text-white title-fancy">Order Summary</h1>
          <p className="mt-4 max-w-2xl text-base text-[#8892a4] subtitle-fancy">
            Confirm your delivery vector, payment method, and final amount
            before the order enters fulfillment.
          </p>
        </div>

        <div className={styles.paymentShield}>
          <div className={styles.paymentShieldIcon}>
              <ShieldCheck size={20} />
          </div>
          <div><p>Payment shield online</p><strong>AI risk scoring runs before authorization.</strong><span>Protected checkout monitoring is active</span></div>
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

        <aside className={styles.invoiceSidebar}>
          <div className={styles.invoiceHeader}>
            <div>
              <h3 className="text-lg font-semibold text-white">Shopy Invoice</h3>
              <p className="text-xs text-[#93a6bd]">Order summary & receipt</p>
            </div>
            <div>
              <button
                type="button"
                onClick={exportInvoicePdf}
                disabled={isExporting || cartItems.length === 0}
                className={styles.downloadButton}
              >
                {isExporting ? "Preparing PDF..." : "Download PDF"}
              </button>
            </div>
          </div>

          <div className={`${styles.invoicePrintArea} invoice-print-area`} ref={invoiceRef}>
            <div className={styles.invoicePanel}>
                <div className={styles.invoiceMeta}>
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

                <div className={styles.invoiceTotals}>
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

          <Button
            variant="primary"
            fullWidth
            className={styles.createOrderButton}
            onClick={completeCheckout}
            disabled={cartItems.length === 0 || isPlacingOrder}
          >
            {isPlacingOrder ? "Creating order…" : "Create order"}
          </Button>
          <Link href="/cart" className={styles.returnToCart}>
            <Button variant="outline" fullWidth>
              Return to cart
            </Button>
          </Link>

          <div className={styles.invoiceSecurity}>
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
