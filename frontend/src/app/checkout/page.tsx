"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { jsPDF } from "jspdf";
import { CheckCircle2, LoaderCircle, MapPin, ArrowRight, WalletCards } from "lucide-react";
import Button from "@/components/ui/Button";
import RequireAuth from "@/components/auth/RequireAuth";
import { useCart } from "@/features/cart/cart-context";
import ProductImage from "@/features/products/components/ProductImage";
import { apiFetch } from "@/lib/api";
import { getSessionShippingFee } from "@/lib/checkout";
import styles from "./checkout.module.css";
import summaryStyles from "./checkout-summary.module.css";

const currency = new Intl.NumberFormat("en-MY", {
  currency: "MYR",
  style: "currency",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const SST_RATE = 0.06;

function roundUpToFiveSen(value: number) {
  return Math.ceil((value - Number.EPSILON) * 20) / 20;
}
type WalletApiResponse = {
  balance: string;
};

function CheckoutContent() {
  const router = useRouter();
  const invoiceRef = useRef<HTMLDivElement | null>(null);
  const successRedirectTimer = useRef<number | null>(null);
  const [invoiceNumber, setInvoiceNumber] = useState("Pending");
  const [invoiceDate, setInvoiceDate] = useState("Pending");
  const [isExporting, setIsExporting] = useState(false);
  const { cartItems, subtotal, refreshCart } = useCart();
  const [isPlacingOrder, setIsPlacingOrder] = useState(false);
  const [paymentStage, setPaymentStage] = useState<"idle" | "processing" | "success">("idle");
  const [receiptEmailQueued, setReceiptEmailQueued] = useState(false);
  const [shopyPayBalance, setShopyPayBalance] = useState(0);
  const [walletIsReady, setWalletIsReady] = useState(false);
  const cartSignature = cartItems
    .map((item) => `${item.id}:${item.quantity}`)
    .sort()
    .join("|");
  const shippingFee = useMemo(() => getSessionShippingFee(cartSignature), [cartSignature]);
  const merchandiseSubtotal = subtotal;
  const shippingSst = roundUpToFiveSen(shippingFee * SST_RATE);
  const shippingSubtotal = shippingFee + shippingSst;
  const total = merchandiseSubtotal + shippingSubtotal;
  const balanceAfterOrder = shopyPayBalance - total;
  const requiredTopUp = Math.max(total - shopyPayBalance, 0);
  const hasSufficientBalance = shopyPayBalance >= total;
  useEffect(() => {
    let active = true;
    void apiFetch("/api/v1/wallet")
      .then((wallet) => {
        if (!active) return;
        setShopyPayBalance(Number((wallet as WalletApiResponse).balance));
        setWalletIsReady(true);
      })
      .catch(() => {
        if (active) setWalletIsReady(true);
      });
    return () => { active = false; };
  }, []);

  useEffect(() => () => {
    if (successRedirectTimer.current !== null) {
      window.clearTimeout(successRedirectTimer.current);
    }
  }, []);

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
      pdf.text("ShopyPay wallet - authorization pending", rightCardX + 5, y + 20);
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

      const totalsHeight = 60;
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
        ["Merchandise subtotal", currency.format(merchandiseSubtotal)],
        ["Shipping subtotal", currency.format(shippingSubtotal)],
        ["  Shipping fee", currency.format(shippingFee)],
        [`  SST (${SST_RATE * 100}%)`, currency.format(shippingSst)],
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
      pdf.line(totalsX + 6, y + 42, totalsX + totalsWidth - 6, y + 42);
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(11);
      pdf.setTextColor(255, 255, 255);
      pdf.text("TOTAL", totalsX + 6, y + 52);
      pdf.setTextColor(111, 235, 255);
      pdf.text(currency.format(total), totalsX + totalsWidth - 6, y + 52, { align: "right" });

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
    if (!walletIsReady || !hasSufficientBalance || cartItems.length === 0) return;

    const paymentStartedAt = performance.now();
    try {
      setIsPlacingOrder(true);
      setPaymentStage("processing");

      const order = await apiFetch("/api/v1/orders/checkout", {
        method: "POST",
        body: JSON.stringify({
          shipping_address: {
            recipient_name: "Jeffrey Tan", phone: "+60 12 345 6789",
            line1: "Kuala Lumpur City Centre", city: "Kuala Lumpur", state: "Kuala Lumpur",
            postal_code: "50088", country_code: "MY",
          },
          payment_method: "shopy_pay",
          shipping_fee: shippingFee.toFixed(2),
        }),
      }) as { order_number: string; placed_at: string; receipt_email_queued: boolean };
      setInvoiceNumber(order.order_number);
      setInvoiceDate(new Date(order.placed_at).toLocaleDateString());
      setReceiptEmailQueued(order.receipt_email_queued);
      await refreshCart();
      const wallet = await apiFetch("/api/v1/wallet") as WalletApiResponse;
      setShopyPayBalance(Number(wallet.balance));
      const remainingProcessingTime = Math.max(0, 3000 - (performance.now() - paymentStartedAt));
      if (remainingProcessingTime > 0) {
        await new Promise<void>((resolve) => window.setTimeout(resolve, remainingProcessingTime));
      }
      setPaymentStage("success");
      successRedirectTimer.current = window.setTimeout(() => router.replace("/"), 2400);
    } catch (error) {
      console.error("Checkout failed", error);
      setPaymentStage("idle");
    } finally {
      setIsPlacingOrder(false);
    }
  };

  return (
    <div className={styles.checkout}>
      {paymentStage !== "idle" && (
        <div className={styles.paymentOverlay} role="status" aria-live="assertive" aria-label={paymentStage === "success" ? "Payment successful" : "Processing payment"}>
          <div className={styles.paymentDialog}>
            {paymentStage === "processing" ? (
              <>
                <span className={styles.paymentIcon}><LoaderCircle size={31} /></span>
                <p className={styles.paymentEyebrow}>ShopyPay secure checkout</p>
                <h2>Processing your payment</h2>
                <p>We’re confirming your order and updating your wallet. This will only take a moment.</p>
                <span className={styles.paymentProgress}><i /> Please keep this page open</span>
              </>
            ) : (
              <>
                <span className={`${styles.paymentIcon} ${styles.paymentSuccessIcon}`}><CheckCircle2 size={34} /></span>
                <p className={styles.paymentEyebrow}>Payment confirmed</p>
                <h2>Thank you for shopping with Shopy.</h2>
                <p>Your order <strong>#{invoiceNumber}</strong> is confirmed and we’re getting it ready for you.{receiptEmailQueued ? " A paid PDF receipt is on its way to your email." : ""}</p>
                <span className={styles.redirectNote}>Taking you back to Shopy…</span>
              </>
            )}
          </div>
        </div>
      )}
      <div className={summaryStyles.checkoutIntro}>
        <div>
          <h1>Order Summary</h1>
          <p>
            Confirm your delivery details, ShopyPay balance, and final amount
            before the order enters fulfillment.
          </p>
        </div>
      </div>

      <section className="grid gap-6 lg:grid-cols-[1fr_380px]">
        <div className="space-y-6">
          <div className={`${styles.detailCard} ${styles.deliveryCard}`}>
            <div className={styles.sectionHeading}>
              <MapPin className="text-indigo-400" size={21} />
              <div><span>01 · DELIVERY</span><h2>Where should we send it?</h2><p>Your saved details are ready. Make a quick edit if needed.</p></div>
            </div>
            <div className={styles.deliveryFields}>
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

          <div className={`${styles.detailCard} ${styles.walletCard}`}>
            <div className={styles.sectionHeading}>
              <WalletCards className="text-indigo-400" size={21} />
              <div><span>02 · PAYMENT</span><h2>Pay with ShopyPay</h2><p>Use your available wallet balance. No card details needed.</p></div>
            </div>
            <div className={styles.walletBalance}>
              <div><span>Available balance</span><strong>{currency.format(shopyPayBalance)}</strong></div>
              <WalletCards size={25} />
            </div>
            <div className={styles.walletBreakdown}>
              <div><span>This order</span><strong>{currency.format(total)}</strong></div>
              <div><span>After checkout</span><strong className={balanceAfterOrder >= 0 ? styles.balancePositive : styles.balanceNegative}>{currency.format(balanceAfterOrder)}</strong></div>
            </div>
            {balanceAfterOrder < 0 && <p className={styles.balanceWarning}>Add {currency.format(requiredTopUp)} to continue with this order.</p>}
            <Link href={hasSufficientBalance ? "/shopy-pay" : `/shopy-pay?top_up=${requiredTopUp}`} className={styles.walletLink}>{hasSufficientBalance ? "View ShopyPay wallet" : `Top up ${currency.format(requiredTopUp)}`} <ArrowRight size={15} /></Link>
          </div>
        </div>

        <aside className={styles.invoiceSidebar}>
          <div className={styles.invoiceHeader}>
            <div>
              <h3 className="text-lg font-semibold text-white">Payment Details</h3>
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

                <div className={summaryStyles.lineItems}>
                  <div className={summaryStyles.itemLabel}><span>Items</span><span>{cartItems.length} selected</span></div>
                  {cartItems.map((item) => (
                    <article className={summaryStyles.lineItem} key={item.id}>
                      <div className={summaryStyles.itemImage}>
                        <ProductImage
                          src={item.image}
                          alt={item.name}
                          width={112}
                          height={112}
                          sizes="64px"
                          fallback={<span role="img" aria-label={item.name}>{item.emoji}</span>}
                        />
                      </div>
                      <div className={summaryStyles.itemCopy}>
                        <span>{item.brand || item.category}</span>
                        <strong>{item.name}</strong>
                        <small>Qty {item.quantity} · {currency.format(item.price)} each</small>
                      </div>
                      <div className={summaryStyles.itemAmount}>
                        <span>Item total</span>
                        <strong>{currency.format(item.price * item.quantity)}</strong>
                      </div>
                    </article>
                  ))}
                </div>

                <div className={summaryStyles.totals}>
                  <div><span>Merchandise Subtotal</span><span>{currency.format(merchandiseSubtotal)}</span></div>
                  <div className={summaryStyles.shippingSubtotal}><span>Shipping Subtotal</span><span>{currency.format(shippingSubtotal)}</span></div>
                  <div className={summaryStyles.shippingBreakdown}><span>Shipping fee</span><span>{currency.format(shippingFee)}</span></div>
                  <div className={summaryStyles.shippingBreakdown}><span>SST ({SST_RATE * 100}%)</span><span>{currency.format(shippingSst)}</span></div>
                  <div className={summaryStyles.grandTotal}>
                    <span>Total</span>
                    <strong>{currency.format(total)}</strong>
                  </div>
                </div>
            </div>
          </div>

          {hasSufficientBalance ? (
            <Button
              variant="primary"
              fullWidth
              className={summaryStyles.createOrderAction}
              onClick={completeCheckout}
              disabled={cartItems.length === 0 || isPlacingOrder || !walletIsReady || paymentStage !== "idle"}
            >
              {isPlacingOrder ? "Processing payment…" : walletIsReady ? "Pay with ShopyPay" : "Checking ShopyPay…"}{isPlacingOrder ? <LoaderCircle className={styles.buttonSpinner} size={17} /> : <ArrowRight size={17} />}
            </Button>
          ) : (
            <Link href={`/shopy-pay?top_up=${requiredTopUp}`} className={summaryStyles.topUpAction}>
              Top up {currency.format(requiredTopUp)} to continue <ArrowRight size={17} />
            </Link>
          )}
          <Link href="/cart" className={styles.returnToCart}>
            <Button variant="outline" fullWidth className={summaryStyles.returnAction}>
              Return to cart
            </Button>
          </Link>
        </aside>
      </section>
    </div>
  );
}

export default function Checkout() {
  return <RequireAuth><CheckoutContent /></RequireAuth>;
}
