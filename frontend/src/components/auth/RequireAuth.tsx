"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getCurrentUser } from "@/lib/auth";

type RequireAuthProps = {
  children: ReactNode;
};

export default function RequireAuth({ children }: RequireAuthProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [authorisedPath, setAuthorisedPath] = useState<string | null>(null);

  useEffect(() => {
    let isCurrent = true;

    const verifySession = async () => {
      try {
        const user = await getCurrentUser();
        if (!isCurrent) return;

        if (user) {
          setAuthorisedPath(pathname);
          return;
        }
      } catch {
        // Treat an unavailable or invalid session as signed out.
      }

      if (!isCurrent) return;
      const returnTo = `${window.location.pathname}${window.location.search}`;
      router.replace(`/login?next=${encodeURIComponent(returnTo)}`);
    };

    void verifySession();

    return () => {
      isCurrent = false;
    };
  }, [pathname, router]);

  if (authorisedPath !== pathname) {
    return (
      <div className="flex min-h-[45vh] items-center justify-center" role="status" aria-live="polite">
        <div className="flex items-center gap-3 rounded-full border border-white/10 bg-white/[0.04] px-5 py-3 text-sm text-[#aab5c8]">
          <span className="h-2 w-2 animate-pulse rounded-full bg-cyan-400" />
          Securing your Shopy account…
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
