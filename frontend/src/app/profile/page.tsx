"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  AUTH_CHANGE_EVENT,
  AuthUser,
  getCurrentUser,
  logoutAccount,
  resolveAvatarUrl,
} from "@/lib/auth";
import {
  ChevronRight,
  CreditCard,
  PackageCheck,
  Settings,
  ChartNoAxesCombined,
  UserRound,
} from "lucide-react";
import styles from "./profile.module.css";
import shortcutStyles from "./profile-shortcuts.module.css";
import orderStatusStyles from "./order-status.module.css";
import heroStyles from "./profile-hero.module.css";
import RequireAuth from "@/components/auth/RequireAuth";
import { API_URL, apiFetch } from "@/lib/api";

type AccountOrder = {
  id: string;
  order_number: string;
  status: string;
  payment_status: string;
  total_amount: string | number;
  created_at: string;
  items: Array<{ id: string; product_name: string; quantity: number }>;
};

const currency = new Intl.NumberFormat("en-MY", { style: "currency", currency: "MYR", maximumFractionDigits: 2 });

function accountSections(orderCount: number) {
  return [
  {
    title: "Order History",
    description: "Track active shipments and inspect previous purchases.",
    icon: PackageCheck, tone: "orders",
    href: "#order-history",
    metric: `${orderCount} order${orderCount === 1 ? "" : "s"}`,
  },
  {
    title: "Purchase dashboard",
    description: "See how often you shop and how your spending changes over time.",
    icon: ChartNoAxesCombined, tone: "dashboard",
    href: "/dashboard",
    metric: "Activity",
  },
  {
    title: "Payment Vault",
    description: "Manage cards, billing preferences, and checkout speed.",
    icon: CreditCard, tone: "payments",
    href: "/checkout",
    metric: "Secured",
  },
  {
    title: "Account Settings",
    description: "Update profile details, alerts, and privacy controls.",
    icon: Settings, tone: "settings",
    href: "/settings",
    metric: "Verified",
  },
  ];
}

const AVATAR_SIZE = 160;

function resizeAvatar(file: File) {
  return new Promise<string>((resolve, reject) => {
    const image = new window.Image();
    const reader = new FileReader();

    reader.onerror = () => reject(new Error("Could not read avatar file."));
    reader.onload = () => {
      if (typeof reader.result !== "string") {
        reject(new Error("Avatar file could not be converted."));
        return;
      }

      image.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = AVATAR_SIZE;
        canvas.height = AVATAR_SIZE;

        const context = canvas.getContext("2d");
        if (!context) {
          reject(new Error("Could not prepare avatar image."));
          return;
        }

        const sourceSize = Math.min(image.naturalWidth, image.naturalHeight);
        const sourceX = (image.naturalWidth - sourceSize) / 2;
        const sourceY = (image.naturalHeight - sourceSize) / 2;

        context.drawImage(
          image,
          sourceX,
          sourceY,
          sourceSize,
          sourceSize,
          0,
          0,
          AVATAR_SIZE,
          AVATAR_SIZE,
        );

        resolve(canvas.toDataURL("image/jpeg", 0.9));
      };
      image.onerror = () => reject(new Error("Could not load avatar image."));
      image.src = reader.result;
    };

    reader.readAsDataURL(file);
  });
}

function ProfileContent() {
  const router = useRouter();
  const [avatar, setAvatar] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoadingUser, setIsLoadingUser] = useState(true);
  const [orders, setOrders] = useState<AccountOrder[]>([]);
  const [isLoadingOrders, setIsLoadingOrders] = useState(true);
  const [ordersError, setOrdersError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    const syncAuth = async () => {
      try {
        const currentUser = await getCurrentUser();
        if (!isMounted) return;
        setUser(currentUser);
        if (!currentUser) {
          setAvatar(null);
        } else {
          setAvatar(resolveAvatarUrl(currentUser.avatar_url));
        }
      } catch {
        if (isMounted) {
          setUser(null);
          setAvatar(null);
        }
      } finally {
        if (isMounted) setIsLoadingUser(false);
      }
    };

    void syncAuth();

    window.addEventListener(AUTH_CHANGE_EVENT, syncAuth);

    return () => {
      isMounted = false;
      window.removeEventListener(AUTH_CHANGE_EVENT, syncAuth);
    };
  }, []);

  useEffect(() => {
    let isMounted = true;
    const loadOrders = async () => {
      try {
        const result = await apiFetch("/api/v1/orders") as AccountOrder[];
        if (isMounted) { setOrders(result); setOrdersError(null); }
      } catch (error) {
        if (isMounted) { setOrders([]); setOrdersError(error instanceof Error ? error.message : "Unable to load order history."); }
      } finally {
        if (isMounted) setIsLoadingOrders(false);
      }
    };
    const requestId = window.setTimeout(() => void loadOrders(), 0);
    return () => { isMounted = false; window.clearTimeout(requestId); };
  }, []);

  async function signOut() {
    try {
      await logoutAccount();
    } catch {
      // Continue to the sign-in page even if the API is temporarily unavailable.
    }

    setUser(null);
    window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
    router.push("/login");
    router.refresh();
  }

  async function handleAvatarChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const resizedAvatar = await resizeAvatar(file);
      const formData = new FormData();
      formData.append("avatar", new File([await (await fetch(resizedAvatar)).blob()], "avatar.jpg", { type: "image/jpeg" }));
      const response = await fetch(`${API_URL}/api/v1/auth/avatar`, { method: "POST", body: formData, credentials: "include" });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail || "Could not upload your avatar.");
      }
      const updatedUser = await response.json() as AuthUser;
      setUser(updatedUser);
      setAvatar(resolveAvatarUrl(updatedUser.avatar_url));
      window.dispatchEvent(new Event("shopy-avatar-change"));
    } catch (error) {
      console.error(error);
    } finally {
      event.target.value = "";
    }
  }

  return (
    <main className={styles.page}>
      <section className={`${styles.hero} ${heroStyles.hero}`}>
        <div className={styles.heroCopy}>
          <div className={styles.kicker}>Member center</div>
          <div className={styles.title}>Your account</div>
          <div className={styles.subtitle}>Manage orders, payment preferences, and personalised shopping in one place.</div>
          <div className={styles.heroActions}><Link href="/shop" className={styles.primaryAction}>Explore products</Link><Link href="/cart" className={styles.secondaryAction}>View cart</Link></div>
        </div>
        <div className={`${styles.heroStats} ${heroStyles.stats}`}><div><strong>{isLoadingOrders ? "—" : orders.length}</strong><span>Orders</span></div><div><strong>24/7</strong><span>Wallet protection</span></div></div>
      </section>

      <section className={styles.accountGrid}>
        <div className={styles.profileCard}>
          {isLoadingUser ? (
            <div className={styles.profileContent} aria-live="polite">
              <div className={styles.avatar}><UserRound size={28} /></div>
              <div className={styles.profileText}><div className={styles.profileOverline}>Shopy member</div><div className={styles.profileName}>Checking your account…</div><div className={styles.profileEmail}>Securely restoring your session.</div></div>
            </div>
          ) : user ? (
            <div className={styles.profileContent}>
              <label className={styles.avatar}>
                {avatar ? <Image src={avatar} alt="User avatar" width={AVATAR_SIZE} height={AVATAR_SIZE} unoptimized /> : <UserRound size={28} />}
                <div className={styles.avatarUpload}>Change</div>
                <input type="file" accept="image/*" onChange={handleAvatarChange} />
              </label>
              <div className={styles.profileText}><div className={styles.profileOverline}>Signed in as</div><div className={styles.profileName}>{user.full_name}</div><div className={styles.profileEmail}>{user.email}</div><button type="button" onClick={signOut} className={styles.signOut}>Sign out</button></div>
            </div>
          ) : (
            <div className={styles.profileContent}>
              <div className={styles.avatar}><UserRound size={28} /></div>
              <div className={styles.profileText}><div className={styles.profileOverline}>Shopy member</div><div className={styles.profileName}>Welcome to Shopy</div><div className={styles.profileEmail}>Sign in to save your preferences, orders, and wallet settings.</div><div className={styles.authActions}><Link href="/login" className={styles.signIn}>Sign in</Link><Link href="/signup" className={styles.signUp}>Create account</Link></div></div>
            </div>
          )}
        </div>
      </section>

      <section className={styles.sectionHeader}><div><div className={styles.sectionKicker}>Your shortcuts</div><div className={styles.sectionTitle}>Everything you need, in one place</div></div><div className={styles.sectionNote}>Personalised for your account</div></section>
      <section className={styles.actionGrid}>
        {accountSections(orders.length).map((section) => {
          const Icon = section.icon;
          return <Link key={section.title} href={section.href} className={`${styles.actionCard} ${shortcutStyles[section.tone]}`}>
            <div className={styles.cardTop}><div className={`${styles.actionIcon} ${shortcutStyles.icon}`}><Icon size={21} /></div><div className={styles.metric}>{section.metric}</div></div>
            <div className={styles.cardBottom}><div><div className={styles.actionTitle}>{section.title}</div><div className={styles.actionDescription}>{section.description}</div></div><ChevronRight size={21} className={`${styles.chevron} ${shortcutStyles.arrow}`} /></div>
          </Link>;
        })}
      </section>
      <section id="order-history" className={styles.ordersSection} aria-labelledby="order-history-heading">
        <div className={styles.ordersHeader}><div><div className={styles.sectionKicker}>Order history</div><h2 id="order-history-heading" className={styles.sectionTitle}>Your recent orders</h2></div><span className={styles.sectionNote}>Synced with your Shopy account</span></div>
        {isLoadingOrders ? <div className={styles.ordersEmpty}>Loading your orders…</div> : ordersError ? <div className={styles.ordersEmpty}>{ordersError}</div> : orders.length === 0 ? <div className={styles.ordersEmpty}>You have not placed an order yet. Completed checkout orders will appear here.</div> : <div className={styles.orderList}>{orders.map((order) => { const statusTone = ["confirmed", "processing", "shipped", "delivered"].includes(order.status) ? "confirmed" : order.status === "pending" ? "pending" : "failed"; return <article key={order.id} className={styles.orderCard}><div className={styles.orderTop}><div><span className={styles.orderLabel}>Order</span><strong>{order.order_number}</strong></div><span className={`${styles.orderStatus} ${orderStatusStyles[statusTone]}`}>{order.status.replaceAll("_", " ")}</span></div><p className={styles.orderItems}>{order.items.map((item) => `${item.product_name} × ${item.quantity}`).join(", ")}</p><div className={styles.orderBottom}><span>{new Date(order.created_at).toLocaleDateString("en-MY", { dateStyle: "medium" })} · Payment {order.payment_status.replaceAll("_", " ")}</span><strong>{currency.format(Number(order.total_amount))}</strong></div></article>; })}</div>}
      </section>
    </main>
  );
}

export default function Profile() {
  return <RequireAuth><ProfileContent /></RequireAuth>;
}
