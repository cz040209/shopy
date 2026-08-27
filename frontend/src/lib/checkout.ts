const MIN_SHIPPING_FEE = 3;
const MAX_SHIPPING_FEE = 30;
const SHIPPING_FEE_STORAGE_PREFIX = "shopy-checkout-shipping-fee:";

/**
 * Returns one whole-ringgit shipping quote per cart for the current browser
 * session. The saved quote prevents totals from changing on a component rerender
 * or when a shopper moves between ShopyPay and Checkout.
 */
export function getSessionShippingFee(cartSignature: string): number {
  if (!cartSignature) return 0;
  if (typeof window === "undefined") return 0;

  const storageKey = `${SHIPPING_FEE_STORAGE_PREFIX}${cartSignature}`;
  const savedFee = Number(window.sessionStorage.getItem(storageKey));
  if (Number.isInteger(savedFee) && savedFee >= MIN_SHIPPING_FEE && savedFee <= MAX_SHIPPING_FEE) {
    return savedFee;
  }

  const fee = Math.floor(Math.random() * (MAX_SHIPPING_FEE - MIN_SHIPPING_FEE + 1)) + MIN_SHIPPING_FEE;
  window.sessionStorage.setItem(storageKey, String(fee));
  return fee;
}
