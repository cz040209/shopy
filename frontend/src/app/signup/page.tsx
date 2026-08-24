"use client";

import Link from "next/link";
import { ArrowRight, Mail, Shield, Sparkles, UserRound } from "lucide-react";
import Button from "@/components/ui/Button";
import { useState } from "react";
import styles from "../auth.module.css";
import cardStyles from "../auth-card.module.css";

export default function SignUp() {
  const [name, setName] = useState("Jeffrey Tan");
  const [email, setEmail] = useState("shopy.member@example.com");

  return (
    <div className={styles.auth}>
      <section>
        <h1 className="max-w-3xl text-white title-fancy">Start with Shopy.</h1>
        <p className="mt-4 max-w-2xl text-base text-[#8892a4] subtitle-fancy">
          Create your account for faster checkout and saved delivery details.
        </p>
      </section>

      <section className={`${cardStyles.card} relative overflow-hidden rounded-lg bg-white/[0.04] shadow-[0_30px_80px_rgba(0,0,0,0.35)]`}>
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_0%,rgba(0,212,255,0.18),transparent_32%),linear-gradient(145deg,rgba(255,255,255,0.07),transparent_38%)]" />
        <div className="relative">
          <div className="mb-6 flex items-center justify-between gap-4">
            <div>
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-cyan-400">Create account</p>
              <h2 className="mt-2 text-white subtitle-fancy">Start shopping</h2>
            </div>
            <span className="flex h-12 w-12 items-center justify-center rounded-lg bg-cyan-400/10 text-cyan-400">
              <Sparkles size={24} />
            </span>
          </div>

          <form className="space-y-5">
            <div>
              <label htmlFor="signup-name">Full name</label>
              <div className="relative">
                <UserRound
                  size={17}
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#5a6478]"
                />
                <input
                  id="signup-name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  className="input pl-10"
                />
              </div>
            </div>

            <div>
              <label htmlFor="signup-email">Email</label>
              <div className="relative">
                <Mail
                  size={17}
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#5a6478]"
                />
                <input
                  id="signup-email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="input pl-10"
                />
              </div>
            </div>

            <Link href="/profile" className="block">
              <Button variant="primary" fullWidth>
                Create account
                <ArrowRight size={15} />
              </Button>
            </Link>
          </form>

          <div className="security-note mt-5">
            <Shield size={18} className="mt-0.5 shrink-0 text-cyan-400" />
            Your account is ready for secure checkout from day one.
          </div>

          <p className="mt-6 text-center text-sm text-[#8892a4]">
            Already have an account?{" "}
            <Link href="/login" className="text-cyan-400 hover:underline">
              Login
            </Link>
          </p>
        </div>
      </section>
    </div>
  );
}
