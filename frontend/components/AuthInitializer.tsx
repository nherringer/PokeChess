"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/store/authStore";

const PUBLIC_PATHS = ["/", "/login", "/register"];

export function AuthInitializer({ children }: { children: React.ReactNode }) {
  const hydrate = useAuthStore((s) => s.hydrate);
  const accessToken = useAuthStore((s) => s.accessToken);
  const hydrated = useAuthStore((s) => s.hydrated);
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    // Don't redirect until we've read localStorage — otherwise we
    // get a spurious push to /login on every page load for logged-in
    // users, which corrupts the browser history stack.
    if (!hydrated) return;
    if (!accessToken && !PUBLIC_PATHS.includes(pathname)) {
      router.replace("/login");
    }
  }, [hydrated, accessToken, pathname, router]);

  // Don't render protected content until auth state is known — prevents UI flash.
  if (!hydrated && !PUBLIC_PATHS.includes(pathname)) return null;

  return <>{children}</>;
}
