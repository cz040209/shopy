"use client";

import Link from "next/link";
import { ArrowRight, Fingerprint, LockKeyhole, Mail, Shield } from "lucide-react";
import Button from "@/components/ui/Button";
import { useRouter } from "next/navigation";
import { useState } from "react";
import styles from "../auth.module.css";
import cardStyles from "../auth-card.module.css";

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("shopy.member@example.com");
  const [password, setPassword] = useState("mission-control");

  function handleSignIn(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      window.localStorage.setItem("shopy-session", "active");
      window.dispatchEvent(new Event("shopy-auth-change"));
    } catch {
      // Ignore localStorage write issues.
    }

    router.push("/profile");
  }

  return (
    <div className={styles.auth}>
      <section>
        <h1 className="max-w-3xl text-white">Welcome back</h1>
        <p className="mt-4 max-w-2xl text-base text-[#8892a4]">
          Sign in to keep your orders, saved details, and ShopyPay wallet in sync.
        </p>
      </section>

      <section className={`${cardStyles.card} relative overflow-hidden rounded-lg bg-white/[0.04] shadow-[0_30px_80px_rgba(0,0,0,0.35)]`}>
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_0%,rgba(0,212,255,0.18),transparent_32%),linear-gradient(145deg,rgba(255,255,255,0.07),transparent_38%)]" />
        <div className="relative">
          <div className="mb-8 flex items-center justify-between gap-4">
            <div>
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-cyan-400">Your Shopy account</p>
              <h2 className="mt-2 text-white">Sign in to continue</h2>
            </div>
            <span className="flex h-12 w-12 items-center justify-center rounded-lg bg-cyan-400/10 text-cyan-400">
              <Fingerprint size={25} />
            </span>
          </div>

          <form onSubmit={handleSignIn} className={cardStyles.form}>
            <div>
              <label htmlFor="email">Email</label>
              <div className="relative">
                <Mail
                  size={17}
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#5a6478]"
                />
                <input
                  id="email"
                  type="email"
                  placeholder="your@email.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input pl-10"
                />
              </div>
            </div>

            <div>
              <label htmlFor="password">Password</label>
              <div className="relative">
                <LockKeyhole
                  size={17}
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#5a6478]"
                />
                <input
                  id="password"
                  type="password"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input pl-10"
                />
              </div>
            </div>

            <Button type="submit" variant="primary" fullWidth>
              Sign in securely
              <ArrowRight size={15} />
            </Button>
          </form>

          <div className="security-note mt-5">
            <Shield size={18} className="mt-0.5 shrink-0 text-cyan-400" />
            Your account and payments are protected with secure checkout.
          </div>

          <p className="mt-6 text-center text-sm text-[#8892a4]">
            No account?{" "}
            <Link href="/signup" className="text-cyan-400 hover:underline">
              Create an account
            </Link>
          </p>
        </div>
      </section>
    </div>
  );
}
