"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { register } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { useAuthStore } from "@/lib/store/authStore";
import { Button } from "@/components/ui/Button";
import { PokeChessLogo } from "@/components/ui/PokeChessLogo";
import { StarfieldBg } from "@/components/ui/StarfieldBg";

export default function RegisterPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setConfirmError("Passwords do not match");
      return;
    }
    setConfirmError(null);
    setLoading(true);
    setError(null);
    try {
      const res = await register(username, email, password);
      setAuth(res.access_token, res.user_id);
      router.push("/");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("An account with that username or email already exists. Try signing in instead.");
      } else {
        setError(err instanceof Error ? err.message : "Registration failed");
      }
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
            Create your account, Trainer.
          </p>

          {error && (
            <div className="w-full bg-red-team/20 border border-red-team/40 rounded-xl px-4 py-3 text-red-300 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="flex flex-col gap-4 w-full">
            <div>
              <label className="text-white/60 text-sm block mb-1.5">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="w-full bg-bg-card border border-white/10 rounded-xl px-4 py-3 text-white placeholder-white/20 focus:outline-none focus:border-poke-blue transition-colors"
                placeholder="TrainerAsh"
              />
            </div>
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
                minLength={8}
                className="w-full bg-bg-card border border-white/10 rounded-xl px-4 py-3 text-white placeholder-white/20 focus:outline-none focus:border-poke-blue transition-colors"
                placeholder="••••••••"
              />
            </div>
            <div>
              <label className="text-white/60 text-sm block mb-1.5">Confirm Password</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => {
                  setConfirmPassword(e.target.value);
                  setConfirmError(null);
                }}
                required
                className={`w-full bg-bg-card border rounded-xl px-4 py-3 text-white placeholder-white/20 focus:outline-none transition-colors ${
                  confirmError
                    ? "border-red-team focus:border-red-team"
                    : "border-white/10 focus:border-poke-blue"
                }`}
                placeholder="••••••••"
              />
              {confirmError && (
                <p className="mt-1 text-xs text-red-team">{confirmError}</p>
              )}
            </div>
            <Button type="submit" variant="primary" size="lg" fullWidth loading={loading}>
              Begin My Journey
            </Button>
          </form>

          <p className="text-white/40 text-sm text-center">
            Already have an account?{" "}
            <Link href="/login" className="text-poke-blue underline hover:text-poke-yellow transition-colors">
              Sign In
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
