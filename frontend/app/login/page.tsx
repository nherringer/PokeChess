"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { login } from "@/lib/api/auth";
import { useAuthStore } from "@/lib/store/authStore";
import { Button } from "@/components/ui/Button";
import { PokeChessLogo } from "@/components/ui/PokeChessLogo";
import { StarfieldBg } from "@/components/ui/StarfieldBg";

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await login(email, password);
      setAuth(res.access_token, res.user_id);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen bg-bg-deep flex flex-col items-center justify-center px-6">
      <StarfieldBg showGlow particleCount={4} />

      <div className="relative z-10 w-full max-w-sm animate-page-enter">
        <div className="bg-bg-surface border border-white/10 rounded-2xl shadow-2xl px-8 py-10 flex flex-col items-center gap-6">
          <button onClick={() => router.push("/")} className="hover:opacity-80 transition-opacity">
            <PokeChessLogo size="sm" />
          </button>

          <p className="text-text-muted text-sm text-center -mt-2">
            Welcome back, Trainer.
          </p>

          {error && (
            <div className="w-full bg-red-team/20 border border-red-team/40 rounded-xl px-4 py-3 text-red-300 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="flex flex-col gap-4 w-full">
            <div>
              <label className="text-white/60 text-sm block mb-1.5">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full bg-bg-card border border-white/10 rounded-xl px-4 py-3 text-white placeholder-white/20 focus:outline-none focus:border-poke-blue transition-colors"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="text-white/60 text-sm block mb-1.5">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full bg-bg-card border border-white/10 rounded-xl px-4 py-3 text-white placeholder-white/20 focus:outline-none focus:border-poke-blue transition-colors"
                placeholder="••••••••"
              />
            </div>
            <Button type="submit" variant="primary" size="lg" fullWidth loading={loading}>
              Sign In
            </Button>
          </form>

          <p className="text-white/40 text-sm">
            New Trainer?{" "}
            <Link href="/register" className="text-poke-blue underline hover:text-poke-yellow transition-colors">
              Register here
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
