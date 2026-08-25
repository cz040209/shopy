"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { apiFetch } from "@/lib/api";
import type { ApiProduct, Product } from "@/features/products/types";
import { toProduct } from "@/features/products/types";

export type CartItem = Product & {
  cartItemId: string;
  quantity: number;
};

type CartContextValue = {
  cartItems: CartItem[];
  cartCount: number;
  subtotal: number;
  addToCart: (product: Product, quantity?: number) => Promise<void>;
  removeFromCart: (cartItemId: string) => Promise<void>;
  updateQuantity: (cartItemId: string, quantity: number) => Promise<void>;
  clearCart: () => Promise<void>;
  refreshCart: () => Promise<void>;
  isLoading: boolean;
};

const CartContext = createContext<CartContextValue | null>(null);

type ApiCart = {
  items: Array<{ id: string; product: ApiProduct; quantity: number }>;
};

function cartFromApi(data: ApiCart): CartItem[] {
  return data.items.map((item) => ({ ...toProduct(item.product), cartItemId: item.id, quantity: item.quantity }));
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [cartItems, setCartItems] = useState<CartItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const refreshCart = async () => {
    const data = await apiFetch("/api/v1/cart") as ApiCart;
    setCartItems(cartFromApi(data));
  };

  useEffect(() => {
    const requestId = window.setTimeout(() => {
      void refreshCart().catch(() => setCartItems([])).finally(() => setIsLoading(false));
    }, 0);
    return () => window.clearTimeout(requestId);
  }, []);

  const value = useMemo<CartContextValue>(() => {
    const cartCount = cartItems.reduce((sum, item) => sum + item.quantity, 0);
    const subtotal = cartItems.reduce(
      (sum, item) => sum + item.price * item.quantity,
      0,
    );

    return {
      cartItems,
      cartCount,
      subtotal,
      async addToCart(product, quantity = 1) {
        await apiFetch("/api/v1/cart/items", { method: "POST", body: JSON.stringify({ product_id: product.id, quantity }) });
        await refreshCart();
      },
      async removeFromCart(cartItemId) {
        await apiFetch(`/api/v1/cart/items/${cartItemId}`, { method: "DELETE" });
        await refreshCart();
      },
      async updateQuantity(cartItemId, quantity) {
        if (quantity < 1) {
          await apiFetch(`/api/v1/cart/items/${cartItemId}`, { method: "DELETE" });
          await refreshCart();
          return;
        }
        await apiFetch(`/api/v1/cart/items/${cartItemId}`, { method: "PATCH", body: JSON.stringify({ quantity }) });
        await refreshCart();
      },
      async clearCart() {
        await Promise.all(cartItems.map((item) => apiFetch(`/api/v1/cart/items/${item.id}`, { method: "DELETE" })));
        await refreshCart();
      },
      isLoading,
      refreshCart,
    };
  }, [cartItems, isLoading]);

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  const context = useContext(CartContext);

  if (!context) {
    throw new Error("useCart must be used inside CartProvider");
  }

  return context;
}
