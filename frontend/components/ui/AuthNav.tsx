"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useAuthStore } from "@/lib/store/authStore";
import { PokeChessLogo } from "@/components/ui/PokeChessLogo";

const NAV_LINKS = [
  { label: "My Pokémon", href: "/my-pokemon" },
  { label: "My Games", href: "/my-games" },
  { label: "Play vs Bot", href: "/play" },
  { label: "Friends", href: "/friends" },
];

export function AuthNav() {
  const router = useRouter();
  const pathname = usePathname();
  const accessToken = useAuthStore((s) => s.accessToken);
  const clearAuth = useAuthStore((s) => s.clearAuth);

  if (!accessToken) return null;

  const handleLogout = () => {
    clearAuth();
    router.push("/");
  };

  return (
    <nav className="sticky top-0 z-50 bg-bg-surface border-b border-white/10">
      <div className="max-w-5xl mx-auto px-4 h-14 flex items-center gap-4">
        {/* Home button */}
        <button
          onClick={() => router.push("/my-pokemon")}
          aria-label="Home"
          className="shrink-0 hover:opacity-80 transition-opacity"
        >
          <PokeChessLogo size="sm" />
        </button>

        {/* Nav links */}
        <div className="flex items-center gap-1 overflow-x-auto flex-1 scrollbar-none">
          {NAV_LINKS.map(({ label, href }) => {
            const isActive = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`px-3 py-1.5 rounded-lg text-sm whitespace-nowrap transition-colors ${
                  isActive
                    ? "bg-white/10 text-white font-semibold"
                    : "text-text-muted hover:text-white hover:bg-white/5"
                }`}
              >
                {label}
              </Link>
            );
          })}
        </div>

        {/* Log out */}
        <button
          onClick={handleLogout}
          className="shrink-0 text-xs font-bold text-white px-3 py-1.5 rounded-lg bg-red-team hover:brightness-110 active:scale-95 transition-all"
        >
          Log out
        </button>
      </div>
    </nav>
  );
}
