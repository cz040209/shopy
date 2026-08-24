"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useCart } from "@/features/cart/cart-context";
import { Search, ShoppingBag, UserRound } from "lucide-react";
import styles from "./Navbar.module.css";
import menuStyles from "./NavMenu.module.css";
import fixStyles from "./NavbarFix.module.css";
import logoStyles from "./NavbarLogoV2.module.css";

const TOP_LINKS = [
  { href: "/", label: "Home" },
  { href: "/shop", label: "Shop" },
  { href: "/shopy-pay", label: "ShopyPay" },
];

const PROFILE_MENU_ITEMS = [
  { href: "/profile", label: "Account" },
  { href: "/shopy-pay", label: "ShopyPay" },
  { href: "/login", label: "Login" },
  { href: "/signup", label: "Sign Up" },
];

const SESSION_STORAGE_KEY = "shopy-session";

export default function Navbar() {
  const headerRef = useRef<HTMLElement | null>(null);
  const pathname = usePathname();
  const router = useRouter();
  const { cartCount } = useCart();
  const [scrolled, setScrolled] = useState(false);
  const [navbarHeight, setNavbarHeight] = useState(188);
  const [shopQuery, setShopQuery] = useState(() => {
    if (typeof window === "undefined") {
      return "";
    }

    return pathname === "/shop"
      ? new URLSearchParams(window.location.search).get("q") ?? ""
      : "";
  });
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  function to_sync_avatar() {
    const syncAvatar = () => {
      try {
        const stored = window.localStorage.getItem("shopy-avatar");
        setAvatarUrl(stored);
      } catch {
        // Ignore localStorage access issues.
      }
    };

    const id = window.setTimeout(syncAvatar, 0);
    window.addEventListener("shopy-avatar-change", syncAvatar);

    return () => {
      window.clearTimeout(id);
      window.removeEventListener("shopy-avatar-change", syncAvatar);
    };
  }

  function to_sync_auth() {
    const syncAuth = () => {
      try {
        setIsLoggedIn(window.localStorage.getItem(SESSION_STORAGE_KEY) === "active");
      } catch {
        setIsLoggedIn(false);
      }
    };

    syncAuth();
    window.addEventListener("shopy-auth-change", syncAuth);

    return () => window.removeEventListener("shopy-auth-change", syncAuth);
  }

  function set_scroll_listener() {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }

  function sync_navbar_height_observer() {
    const header = headerRef.current;
    if (!header) return;
    let frame = 0;

    const syncNavbarHeight = () => {
      const nextHeight = Math.ceil(header.getBoundingClientRect().height);
      document.documentElement.style.setProperty(
        "--navbar-height",
        `${nextHeight}px`,
      );
      setNavbarHeight((currentHeight) =>
        currentHeight === nextHeight ? currentHeight : nextHeight,
      );
    };

    frame = window.requestAnimationFrame(syncNavbarHeight);
    const observer = new ResizeObserver(syncNavbarHeight);
    observer.observe(header);
    window.addEventListener("resize", syncNavbarHeight);

    return () => {
      window.cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("resize", syncNavbarHeight);
    };
  }

  useEffect(() => to_sync_avatar(), []);
  useEffect(() => to_sync_auth(), []);
  useEffect(() => set_scroll_listener(), []);
  useEffect(() => sync_navbar_height_observer(), []);

  function signOut() {
    try {
      window.localStorage.removeItem(SESSION_STORAGE_KEY);
      window.dispatchEvent(new Event("shopy-auth-change"));
    } catch {
      // Ignore localStorage write issues.
    }

    router.push("/login");
  }

  function handleSearchSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const query = String(formData.get("q") ?? "").trim();
    setShopQuery(query);
    router.push(query ? `/shop?q=${encodeURIComponent(query)}` : "/shop");
  }

  const linkClass = (active: boolean) =>
    [
      "inline-flex items-center justify-center rounded-full px-5 py-2.5 text-[0.8rem] font-semibold uppercase tracking-[0.12em]",
      "transition-all duration-300 ease-out", // Apply transition-all for transform and colors
      active
        ? "bg-cyan-400/10 text-cyan-400"
        : "bg-white/10 text-white hover:bg-white/15 hover:text-cyan-400",
      // Add hover effects for transform (translate/scale)
      "hover:-translate-y-0.5 hover:scale-[1.03]",
    ].join(" ");

  const profileLinkClass = () =>
    [
      "inline-flex items-center gap-2 rounded-full px-4 py-2 text-[0.8rem] font-semibold uppercase tracking-[0.12em] no-underline",
      "transition-all duration-300 ease-out", // Apply transition-all for transform and colors
      "bg-white/10 text-white hover:bg-white/15 hover:text-cyan-400",
      // Add hover effects for transform (translate/scale)
      "hover:-translate-y-0.5 hover:scale-[1.03]",
    ].join(" ");
    
  const profileMenuItemClass = (isButton?: boolean) =>
    [
      "rounded-xl px-3 py-2 text-left text-[0.72rem] font-semibold uppercase tracking-[0.12em]",
      "transition-colors duration-200 ease-out", // For color transitions
      isButton ? "text-red-400 hover:bg-white/10 hover:text-red-300" : "text-[#dfe5f0] hover:bg-white/10 hover:text-cyan-400"
    ].join(" ");

  return (
    <>
      <header
        ref={headerRef}
        className={[
          styles.header,
          "fixed left-0 right-0 top-0 z-50 transition-all duration-300",
          scrolled
            ? "bg-[color:var(--bg)]/95 shadow-[0_12px_40px_rgba(0,0,0,0.28)] backdrop-blur-2xl"
            : "bg-[color:var(--bg)]/90 backdrop-blur-xl",
        ].join(" ")}
      >
        <div className="bg-[linear-gradient(90deg,rgba(255,255,255,0.02),rgba(255,255,255,0.01))] w-screen max-w-full">
          <div className="flex w-screen max-w-full flex-wrap items-center justify-between gap-8 px-8 py-4 sm:px-10 lg:px-12">
            <div   className="flex flex-wrap items-center"
                    style={{
                      columnGap: "10px",
                      rowGap: "10px",
                    }}>
              {TOP_LINKS.map(({ href, label }) => (
                <Link
                  key={href}
                  href={href}
                  className={`${linkClass(pathname === href)} no-underline`}
                >
                  {label}
                </Link>
              ))}
            </div>

            <div className="flex flex-wrap items-center gap-4 sm:gap-6">
              <div className="group relative">
                <Link
                  href="/profile"
                  className={profileLinkClass()} // Use the new class generator
                >
                  <span className="relative flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-full bg-cyan-400/10 text-cyan-400">
                    {avatarUrl ? (
                      <Image
                        src={avatarUrl}
                        alt=""
                        width={28}
                        height={28}
                        unoptimized
                        className="h-7 w-7 rounded-full object-cover"
                      />
                    ) : (
                      <UserRound size={15} />
                    )}
                  </span>
                  Profile
                </Link>

                <div className={`${menuStyles.profileMenu} pointer-events-none absolute left-0 top-full mt-2 flex min-w-[9rem] flex-col opacity-0 transition duration-200 group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:opacity-100`}>
                  {PROFILE_MENU_ITEMS.filter(
                    (item) => !isLoggedIn || (item.label !== "Login" && item.label !== "Sign Up"),
                  ).map(({ href, label }) => (
                    <Link
                      key={href}
                      href={href}
                      className={`${profileMenuItemClass()} ${menuStyles.menuItem}`}
                    >
                      {label}
                    </Link>
                  ))}
                  {isLoggedIn ? (
                    <button
                      type="button"
                      onClick={signOut}
                      className={`${profileMenuItemClass(true)} ${menuStyles.menuItem} ${menuStyles.signOutItem}`}
                    >
                      Sign Out
                    </button>
                  ) : null}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-black w-screen max-w-full">
          <div className="flex w-screen max-w-full items-center justify-between gap-8 px-8 py-5 sm:px-10 lg:px-12">
            <Link
              href="/"
              className={`group flex shrink-0 items-center ${fixStyles.logoFrame} ${logoStyles.frame}`}
            >
              <Image
                src="/images/brand/shopy-logo-v2.png"
                alt="Shopy"
                width={240}
                height={96}
                priority
                className={`h-16 w-auto object-contain ${fixStyles.logoImage} ${logoStyles.image}`}
              />
            </Link>

            <div className="flex min-w-0 flex-1 items-center justify-center gap-10">
              <form onSubmit={handleSearchSubmit} className="flex min-w-0 flex-1 max-w-[600px]">
                <div className={`relative flex w-full items-center gap-3 rounded-full border border-white/20 pl-7 pr-12 py-4 transition duration-300 sm:pl-8 sm:pr-12 sm:py-4 ${fixStyles.searchShell}`}>
                  <Search
                    className="pointer-events-none absolute left-8 top-1/2 -translate-y-1/2 text-cyan-400 sm:left-10"
                    size={22}
                  />
                  <input
                    name="q"
                    key={`${pathname}-${shopQuery}`}
                    defaultValue={shopQuery}
                    placeholder="Search products, brands, categories"
                    className="w-full rounded-full border-0 bg-transparent pl-14 pr-6 text-sm text-white outline-none placeholder:text-white/50 sm:pl-16 sm:pr-7"
                    style={{ height: 40 }}
                  />
                  <button
                    type="submit"
                    className={`mr-2 inline-flex items-center justify-center px-6 text-sm font-semibold uppercase text-white transition duration-200 sm:px-7 ${fixStyles.searchButton}`}
                  >
                    Search
                  </button>
                </div>
              </form>

              <Link
                href="/cart"
                className="relative ml-10 flex h-16 w-16 items-center justify-center rounded-full bg-white/10 text-white transition duration-200 hover:-translate-y-0.5 hover:scale-[1.05] hover:bg-white/15 hover:text-cyan-400"
                aria-label="Cart"
              >
                <ShoppingBag size={25} strokeWidth={2.1} />
                {cartCount > 0 && (
                  <span className="absolute -right-2 -top-2 flex h-7 min-w-7 items-center justify-center rounded-full bg-cyan-400 px-2 text-[0.9rem] font-extrabold leading-none text-[#000000] shadow-[0_0_12px_rgba(0,212,255,0.35)]">
                    {cartCount > 99 ? "99+" : cartCount}
                  </span>
                )}
              </Link>
            </div>
          </div>
        </div>
      </header>
      <div
        aria-hidden="true"
        className="shrink-0"
        style={{ height: `calc(${navbarHeight}px + 1.5rem)` }}
      />
    </>
  );
}
