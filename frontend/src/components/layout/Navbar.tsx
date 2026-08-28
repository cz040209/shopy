"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useCart } from "@/features/cart/cart-context";
import {
  AUTH_CHANGE_EVENT,
  getCurrentUser,
  logoutAccount,
} from "@/lib/auth";
import { ShoppingBag, UserRound } from "lucide-react";
import styles from "./Navbar.module.css";
import menuStyles from "./NavMenu.module.css";
import fixStyles from "./NavbarFix.module.css";
import logoStyles from "./NavbarLogoV2.module.css";

const PUBLIC_TOP_LINKS = [
  { href: "/", label: "Home" },
  { href: "/shop", label: "Shop" },
];

const MEMBER_TOP_LINKS = [
  ...PUBLIC_TOP_LINKS,
  { href: "/shopy-pay", label: "ShopyPay" },
];

const MEMBER_MENU_ITEMS = [
  { href: "/profile", label: "Account" },
  { href: "/shopy-pay", label: "ShopyPay" },
];

const GUEST_MENU_ITEMS = [
  { href: "/login", label: "Login" },
  { href: "/signup", label: "Sign Up" },
];

export default function Navbar() {
  const headerRef = useRef<HTMLElement | null>(null);
  const pathname = usePathname();
  const router = useRouter();
  const { cartCount } = useCart();
  const [scrolled, setScrolled] = useState(false);
  const [navbarHeight, setNavbarHeight] = useState(74);
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
    const syncAuth = async () => {
      try {
        setIsLoggedIn((await getCurrentUser()) !== null);
      } catch {
        setIsLoggedIn(false);
      }
    };

    void syncAuth();
    window.addEventListener(AUTH_CHANGE_EVENT, syncAuth);

    return () => window.removeEventListener(AUTH_CHANGE_EVENT, syncAuth);
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

  async function signOut() {
    try {
      await logoutAccount();
    } catch {
      // The menu should still return to a safe signed-out screen.
    }

    window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
    router.push("/login");
    router.refresh();
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

  const topLinks = isLoggedIn ? MEMBER_TOP_LINKS : PUBLIC_TOP_LINKS;
  const profileMenuItems = isLoggedIn ? MEMBER_MENU_ITEMS : GUEST_MENU_ITEMS;

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
          <div className="flex w-screen max-w-full flex-wrap items-center gap-7 px-8 py-4 sm:px-10 lg:px-12">
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
                className={`h-14 w-auto object-contain ${fixStyles.logoImage} ${logoStyles.image}`}
                style={{ width: "auto" }}
              />
            </Link>

            <div   className="flex flex-1 flex-wrap items-center"
                    style={{
                      columnGap: "10px",
                      rowGap: "10px",
                    }}>
              {topLinks.map(({ href, label }) => (
                <Link
                  key={href}
                  href={href}
                  className={`${linkClass(pathname === href)} no-underline`}
                >
                  {label}
                </Link>
              ))}
            </div>

            <div className="ml-auto flex flex-wrap items-center gap-3 sm:gap-5">
              <Link
                href={isLoggedIn ? "/cart" : "/login?next=%2Fcart"}
                className="relative flex h-11 w-11 items-center justify-center rounded-xl border border-white/10 bg-white/[0.06] text-white transition duration-200 hover:-translate-y-0.5 hover:border-cyan-300/40 hover:bg-white/10 hover:text-cyan-300"
                aria-label="Cart"
              >
                <ShoppingBag size={21} strokeWidth={2.1} />
                {cartCount > 0 && (
                  <span className="absolute -right-2 -top-2 flex h-5 min-w-5 items-center justify-center rounded-full bg-cyan-400 px-1 text-[0.68rem] font-extrabold leading-none text-[#000000] shadow-[0_0_12px_rgba(0,212,255,0.35)]">
                    {cartCount > 99 ? "99+" : cartCount}
                  </span>
                )}
              </Link>
              <div className="group relative">
                <Link
                  href={isLoggedIn ? "/profile" : "/login"}
                  className={profileLinkClass()}
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
                  {isLoggedIn ? "Profile" : "Sign in"}
                </Link>

                <div className={`${menuStyles.profileMenu} pointer-events-none absolute left-0 top-full mt-2 flex min-w-[9rem] flex-col opacity-0 transition duration-200 group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:opacity-100`}>
                  {profileMenuItems.map(({ href, label }) => (
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

      </header>
      <div
        aria-hidden="true"
        className="shrink-0"
        style={{ height: `calc(${navbarHeight}px + 1.5rem)` }}
      />
    </>
  );
}
