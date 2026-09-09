"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { getCurrentUser, getSafeReturnPath } from "@/lib/auth";

type RedirectIfAuthenticatedProps = {
  children: ReactNode;
};

function destination(next: string | null): string {
  const safePath = getSafeReturnPath(next);
  return safePath === "/login" || safePath === "/signup" ? "/profile" : safePath;
}

export default function RedirectIfAuthenticated({ children }: RedirectIfAuthenticatedProps) {
  const router = useRouter();
  const [sessionChecked, setSessionChecked] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    let active = true;

    const verifyGuestAccess = async () => {
      try {
        const user = await getCurrentUser();
        if (!active) return;
        if (user) {
          setIsAuthenticated(true);
          const next = new URLSearchParams(window.location.search).get("next");
          router.replace(destination(next));
          return;
        }
      } catch {
        // A failed session check must not prevent a guest from signing in.
      }

      if (active) setSessionChecked(true);
    };

    void verifyGuestAccess();
    return () => { active = false; };
  }, [router]);

  if (!sessionChecked) {
    return (
      <div className="flex min-h-[45vh] items-center justify-center" role="status" aria-live="polite">
        <div className="flex items-center gap-3 rounded-full border border-white/10 bg-white/[0.04] px-5 py-3 text-sm text-[#aab5c8]">
          <span className="h-2 w-2 animate-pulse rounded-full bg-indigo-500" />
          {isAuthenticated ? "Opening your Shopy account…" : "Checking your Shopy account…"}
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
