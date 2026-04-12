"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/store/authStore";

const PUBLIC_PATHS = ["/", "/login", "/register"];

export function AuthInitializer({ children }: { children: React.ReactNode }) {
  const hydrate = useAuthStore((s) => s.hydrate);
  const accessToken = useAuthStore((s) => s.accessToken);
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (!accessToken && !PUBLIC_PATHS.includes(pathname)) {
      router.push("/login");
    }
  }, [accessToken, pathname, router]);

  return <>{children}</>;
}
