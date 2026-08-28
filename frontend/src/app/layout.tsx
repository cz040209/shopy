import "./globals.css";
import "./home-spacing.css";
import { Inter, Manrope } from "next/font/google";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import AIAssistant from "@/features/assistant/components/AIAssistant";
import { CartProvider } from "@/features/cart/cart-context";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans",
});

const manrope = Manrope({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-display",
});

export const metadata = {
  title: "Shopy | AI Commerce",
  description:
    "A modern AI-commerce storefront with curated products, secure checkout, and intelligent recommendations.",
  icons: {
    icon: "/images/brand/shopy-logo.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${manrope.variable}`}>
      <body className="min-h-screen text-white antialiased">
        <CartProvider>
          <Navbar />
          <main className="container py-0">
            {children}
          </main>
          <Footer />
        </CartProvider>
        <AIAssistant />
      </body>
    </html>
  );
}
