"use client";

import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { PRODUCTS, type Product } from "@/features/products/data/products";

export type CartItem = Product & {
  quantity: number;
};

type CartContextValue = {
  cartItems: CartItem[];
  cartCount: number;
  subtotal: number;
  addToCart: (product: Product) => void;
  removeFromCart: (productId: number) => void;
  updateQuantity: (productId: number, quantity: number) => void;
  clearCart: () => void;
};

const CartContext = createContext<CartContextValue | null>(null);

const initialCart: CartItem[] = PRODUCTS.slice(0, 3).map((product) => ({
  ...product,
  quantity: product.id === 3 ? 1 : 2,
}));

export function CartProvider({ children }: { children: ReactNode }) {
  const [cartItems, setCartItems] = useState<CartItem[]>(initialCart);

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
      addToCart(product) {
        setCartItems((current) => {
          const existing = current.find((item) => item.id === product.id);

          if (existing) {
            return current.map((item) =>
              item.id === product.id
                ? { ...item, quantity: item.quantity + 1 }
                : item,
            );
          }

          return [...current, { ...product, quantity: 1 }];
        });
      },
      removeFromCart(productId) {
        setCartItems((current) =>
          current.filter((item) => item.id !== productId),
        );
      },
      updateQuantity(productId, quantity) {
        if (quantity < 1) {
          setCartItems((current) =>
            current.filter((item) => item.id !== productId),
          );
          return;
        }

        setCartItems((current) =>
          current.map((item) =>
            item.id === productId ? { ...item, quantity } : item,
          ),
        );
      },
      clearCart() {
        setCartItems([]);
      },
    };
  }, [cartItems]);

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  const context = useContext(CartContext);

  if (!context) {
    throw new Error("useCart must be used inside CartProvider");
  }

  return context;
}
