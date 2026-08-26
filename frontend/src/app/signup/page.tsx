"use client";

import Link from "next/link";
import { ArrowRight, LockKeyhole, Mail, Shield, UserRound } from "lucide-react";
import Button from "@/components/ui/Button";
import { getSafeReturnPath, notifyAuthChanged, registerAccount } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useState } from "react";
import styles from "../auth.module.css";
import cardStyles from "../auth-card.module.css";

export default function SignUp() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleCreateAccount(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setIsSubmitting(true);
    try {
      await registerAccount({ full_name: name, email, password });
      notifyAuthChanged();
      const returnTo = getSafeReturnPath(
        new URLSearchParams(window.location.search).get("next"),
      );
      router.replace(returnTo);
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not create your account.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className={styles.auth}>
      <section>
        <h1 className="max-w-3xl text-white">Shop smarter</h1>
        <p className="mt-4 max-w-2xl text-base text-[#8892a4]">
          Create your Shopy account for faster checkout and saved delivery details.
        </p>
      </section>

      <section className={`${cardStyles.card} relative overflow-hidden rounded-lg bg-white/[0.04] shadow-[0_30px_80px_rgba(0,0,0,0.35)]`}>
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_0%,rgba(0,212,255,0.18),transparent_32%),linear-gradient(145deg,rgba(255,255,255,0.07),transparent_38%)]" />
        <div className="relative">
          <div className="mb-6 flex items-center justify-between gap-4">
            <div>
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-cyan-400">New to Shopy?</p>
              <h2 className="mt-2 text-white">Create your account</h2>
            </div>
            <span className="flex h-12 w-12 items-center justify-center rounded-lg bg-cyan-400/10 text-cyan-400">
              <UserRound size={24} />
            </span>
          </div>

          <form onSubmit={handleCreateAccount} className={cardStyles.form}>
            <div>
              <label htmlFor="signup-name">Full name</label>
              <div className="relative">
                <UserRound
                  size={17}
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#5a6478]"
                />
                <input
                  id="signup-name"
                  name="full_name"
                  autoComplete="name"
                  placeholder="Your full name"
                  required
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
                  name="email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@example.com"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="input pl-10"
                />
              </div>
            </div>

            <div>
              <label htmlFor="signup-password">Password</label>
              <div className="relative">
                <LockKeyhole
                  size={17}
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#5a6478]"
                />
                <input
                  id="signup-password"
                  name="password"
                  type="password"
                  autoComplete="new-password"
                  placeholder="At least 8 characters"
                  minLength={8}
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="input pl-10"
                />
              </div>
            </div>

            <div>
              <label htmlFor="signup-confirm-password">Confirm password</label>
              <div className="relative">
                <LockKeyhole
                  size={17}
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#5a6478]"
                />
                <input
                  id="signup-confirm-password"
                  name="confirm_password"
                  type="password"
                  autoComplete="new-password"
                  placeholder="Enter your password again"
                  minLength={8}
                  required
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  className="input pl-10"
                />
              </div>
            </div>

            {error ? (
              <p role="alert" className="text-sm leading-5 text-red-300">
                {error}
              </p>
            ) : null}

            <Button type="submit" variant="primary" fullWidth disabled={isSubmitting}>
              {isSubmitting ? "Creating account…" : "Create account"}
              {!isSubmitting ? <ArrowRight size={15} /> : null}
            </Button>
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
