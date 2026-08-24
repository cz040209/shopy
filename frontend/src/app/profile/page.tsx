"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Bell,
  CheckCircle2,
  ChevronRight,
  CreditCard,
  PackageCheck,
  Settings,
  Sparkles,
  UserRound,
} from "lucide-react";
import styles from "./profile.module.css";

const SESSION_STORAGE_KEY = "shopy-session";

const sections = [
  {
    title: "Order History",
    description: "Track active shipments and inspect previous purchases.",
    icon: PackageCheck,
    href: "/cart",
    metric: "12 orders",
  },
  {
    title: "AI Insights",
    description: "Review recommendations tuned to your shopping patterns.",
    icon: Sparkles,
    href: "/shop",
    metric: "94% match",
  },
  {
    title: "Payment Vault",
    description: "Manage cards, billing preferences, and checkout speed.",
    icon: CreditCard,
    href: "/checkout",
    metric: "Secured",
  },
  {
    title: "Account Settings",
    description: "Update profile details, alerts, and privacy controls.",
    icon: Settings,
    href: "/login",
    metric: "Verified",
  },
];

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

export default function Profile() {
  const router = useRouter();
  const [avatar, setAvatar] = useState<string | null>(null);
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    const syncAuth = () => {
      try {
        const active = window.localStorage.getItem(SESSION_STORAGE_KEY) === "active";
        setIsLoggedIn(active);
        if (!active) {
          setAvatar(null);
        }
      } catch {
        setIsLoggedIn(false);
        setAvatar(null);
      }
    };

    const id = window.setTimeout(() => {
      try {
        const stored = window.localStorage.getItem("shopy-avatar");
        if (stored) {
          setAvatar(stored);
        }
      } catch {
        // Ignore localStorage access issues.
      }
      syncAuth();
    }, 0);

    window.addEventListener("shopy-auth-change", syncAuth);

    return () => {
      window.clearTimeout(id);
      window.removeEventListener("shopy-auth-change", syncAuth);
    };
  }, []);

  function signOut() {
    try {
      window.localStorage.removeItem(SESSION_STORAGE_KEY);
    } catch {
      // Ignore localStorage write issues.
    }

    window.dispatchEvent(new Event("shopy-auth-change"));
    router.push("/login");
  }

  async function handleAvatarChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const resizedAvatar = await resizeAvatar(file);
      setAvatar(resizedAvatar);
      window.localStorage.setItem("shopy-avatar", resizedAvatar);
      window.dispatchEvent(new Event("shopy-avatar-change"));
    } catch (error) {
      console.error(error);
    } finally {
      event.target.value = "";
    }
  }

  return (
    <main className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.heroCopy}>
          <div className={styles.kicker}>Member center</div>
          <div className={styles.title}>Your account</div>
          <div className={styles.subtitle}>Manage orders, payment preferences, and personalised shopping in one place.</div>
          <div className={styles.heroActions}><Link href="/shop" className={styles.primaryAction}>Explore products</Link><Link href="/cart" className={styles.secondaryAction}>View cart</Link></div>
        </div>
        <div className={styles.heroStats}><div><strong>12</strong><span>Orders</span></div><div><strong>94%</strong><span>Match score</span></div><div><strong>24/7</strong><span>Wallet protection</span></div></div>
      </section>

      <section className={styles.accountGrid}>
        <div className={styles.profileCard}>
          {isLoggedIn ? (
            <div className={styles.profileContent}>
              <label className={styles.avatar}>
                {avatar ? <Image src={avatar} alt="User avatar" width={AVATAR_SIZE} height={AVATAR_SIZE} unoptimized /> : <UserRound size={28} />}
                <div className={styles.avatarUpload}>Change</div>
                <input type="file" accept="image/*" onChange={handleAvatarChange} />
              </label>
              <div className={styles.profileText}><div className={styles.profileOverline}>Signed in as</div><div className={styles.profileName}>Jeffrey Tan</div><div className={styles.profileEmail}>shopy.member@example.com</div><button type="button" onClick={signOut} className={styles.signOut}>Sign out</button></div>
            </div>
          ) : (
            <div className={styles.profileContent}>
              <div className={styles.avatar}><UserRound size={28} /></div>
              <div className={styles.profileText}><div className={styles.profileOverline}>Shopy member</div><div className={styles.profileName}>Welcome to Shopy</div><div className={styles.profileEmail}>Sign in to save your preferences, orders, and wallet settings.</div><div className={styles.authActions}><Link href="/login" className={styles.signIn}>Sign in</Link><Link href="/signup" className={styles.signUp}>Create account</Link></div></div>
            </div>
          )}
        </div>
        <div className={styles.alertCard}><div className={styles.alertIcon}><Bell size={20} /></div><div><div className={styles.alertTitle}>Stay in the loop</div><div className={styles.alertCopy}>Smart alerts are enabled for delivery milestones, price drops, and wallet activity.</div></div><CheckCircle2 size={20} className={styles.alertCheck} /></div>
      </section>

      <section className={styles.sectionHeader}><div><div className={styles.sectionKicker}>Your shortcuts</div><div className={styles.sectionTitle}>Everything you need, in one place</div></div><div className={styles.sectionNote}>Personalised for your account</div></section>
      <section className={styles.actionGrid}>
        {sections.map((section) => {
          const Icon = section.icon;
          return <Link key={section.title} href={section.href} className={styles.actionCard}>
            <div className={styles.cardTop}><div className={styles.actionIcon}><Icon size={21} /></div><div className={styles.metric}>{section.metric}</div></div>
            <div className={styles.cardBottom}><div><div className={styles.actionTitle}>{section.title}</div><div className={styles.actionDescription}>{section.description}</div></div><ChevronRight size={21} className={styles.chevron} /></div>
          </Link>;
        })}
      </section>
    </main>
  );
}
