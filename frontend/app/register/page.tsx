"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { register } from "@/lib/api/auth";
import { useAuthStore } from "@/lib/store/authStore";
import { Button } from "@/components/ui/Button";

export default function RegisterPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await register(username, email, password);
      setAuth(res.access_token, res.user_id);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg-deep flex flex-col items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <h1 className="font-display text-3xl font-bold text-white mb-2 text-center">
          ♟ POKECHESS
        </h1>
        <p className="text-white/40 text-sm text-center mb-8">Create your account</p>

        {error && (
          <div className="mb-4 bg-red-team/20 border border-red-team/40 rounded-xl px-4 py-3 text-red-300 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="text-white/60 text-sm block mb-1.5">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="w-full bg-bg-card border border-white/10 rounded-xl px-4 py-3 text-white placeholder-white/20 focus:outline-none focus:border-blue-team transition-colors"
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
              className="w-full bg-bg-card border border-white/10 rounded-xl px-4 py-3 text-white placeholder-white/20 focus:outline-none focus:border-blue-team transition-colors"
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
              minLength={6}
              className="w-full bg-bg-card border border-white/10 rounded-xl px-4 py-3 text-white placeholder-white/20 focus:outline-none focus:border-blue-team transition-colors"
              placeholder="••••••••"
            />
          </div>
          <Button type="submit" variant="secondary" size="lg" fullWidth loading={loading}>
            Create Account
          </Button>
        </form>

        <p className="text-center mt-6 text-white/40 text-sm">
          Already have an account?{" "}
          <Link href="/login" className="text-blue-team underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
