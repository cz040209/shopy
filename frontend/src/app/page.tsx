"use client";

import Image from "next/image";
import Link from "next/link";
import { ArrowRight, ShieldCheck, Sparkles, Truck } from "lucide-react";
import { useEffect, useState } from "react";
import { AUTH_CHANGE_EVENT, type AuthUser, getCurrentUser } from "@/lib/auth";
import styles from "./home.module.css";

export default function Home() {
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    const syncUser = async () => {
      try {
        setUser(await getCurrentUser());
      } catch {
        setUser(null);
      }
    };

    void syncUser();
    window.addEventListener(AUTH_CHANGE_EVENT, syncUser);
    return () => window.removeEventListener(AUTH_CHANGE_EVENT, syncUser);
  }, []);

  const firstName = user?.full_name.trim().split(/\s+/, 1)[0];
  const isSignedIn = user !== null;

  return (
    <main className={styles.home}>
      <section className={styles.hero}>
        <div className={styles.copy}>
          <div className={styles.eyebrow}>{isSignedIn ? `Welcome back${firstName ? `, ${firstName}` : ""}` : "Welcome to Shopy"}</div>
          <h1>{isSignedIn ? "Ready for your next great find?" : "Make every purchase feel more personal."}</h1>
          <p>{isSignedIn ? "Explore products picked around your preferences, revisit your saved details, and keep every order in one place." : "Create an account to unlock your private wallet, saved delivery details, order history, and AI recommendations that improve with you."}</p>
          <div className={styles.actions}>
            <Link href={isSignedIn ? "/shop" : "/signup"} className={styles.primary}>{isSignedIn ? "Explore the shop" : "Create your account"} <ArrowRight size={18} /></Link>
            <Link href={isSignedIn ? "/profile" : "/login"} className={styles.secondary}>{isSignedIn ? "View your account" : "Sign in"}</Link>
          </div>
          <div className={styles.trust}><span><ShieldCheck size={16} />Protected account and payments</span><span><Truck size={16} />Fast delivery across Malaysia</span></div>
        </div>
        <div className={styles.visual}><Image src="/images/home/partnership-collaboration.png" alt="A seamless Shopy shopping experience" fill preload sizes="(max-width: 900px) 100vw, 48vw" /><div className={styles.caption}><Sparkles size={17} />Your account. Your preferences. Your pace.</div></div>
      </section>
      <section className={styles.statement}><div className={styles.eyebrow}>Designed around you</div><h2>One sign-in. A more thoughtful way to shop.</h2><p>Browse whenever you like, then sign in to securely save the details that make checkout, rewards, and recommendations feel effortless.</p></section>
      <section className={styles.values}><div><strong>Personal</strong><span>Saved preferences and order history</span></div><div><strong>Protected</strong><span>Secure wallet and checkout</span></div><div><strong>Effortless</strong><span>Smarter picks with every visit</span></div></section>
    </main>
  );
}
