"use client";

import React, { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Building2, Lock, Mail, User as UserIcon } from "@/components/ui/Icons";
import { apiFetch } from "@/lib/api";
import { saveSession } from "@/lib/auth";
import { AuthSession } from "@/types";

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const session = await apiFetch<AuthSession>("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          full_name: fullName,
          email,
          password,
          workspace_name: workspaceName.trim() || undefined,
        }),
      });
      saveSession(session);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#060b16] px-4 py-12">
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-[#0b1324] p-8 shadow-xl">
        <Link href="/" className="mb-6 flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600 font-bold text-white">
            S
          </div>
          <span className="text-xl font-bold text-white">
            Support<span className="text-blue-400">AI</span>
          </span>
        </Link>

        <h1 className="text-2xl font-bold text-white">Create your workspace</h1>
        <p className="mt-1 text-sm text-slate-400">
          Start free with 100 monthly AI messages and RAG knowledge base.
        </p>

        {error && (
          <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-300">
              Full name
            </label>
            <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-[#060b16] px-3 py-2.5 focus-within:border-blue-500">
              <UserIcon className="h-4 w-4 text-slate-500" />
              <input
                type="text"
                required
                minLength={2}
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Jane Doe"
                className="w-full bg-transparent text-sm text-white outline-none placeholder:text-slate-500"
              />
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-300">
              Work email
            </label>
            <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-[#060b16] px-3 py-2.5 focus-within:border-blue-500">
              <Mail className="h-4 w-4 text-slate-500" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="jane@company.com"
                className="w-full bg-transparent text-sm text-white outline-none placeholder:text-slate-500"
              />
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-300">
              Workspace name (optional)
            </label>
            <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-[#060b16] px-3 py-2.5 focus-within:border-blue-500">
              <Building2 className="h-4 w-4 text-slate-500" />
              <input
                type="text"
                value={workspaceName}
                onChange={(e) => setWorkspaceName(e.target.value)}
                placeholder="Acme Support"
                className="w-full bg-transparent text-sm text-white outline-none placeholder:text-slate-500"
              />
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-300">
              Password (minimum 8 characters)
            </label>
            <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-[#060b16] px-3 py-2.5 focus-within:border-blue-500">
              <Lock className="h-4 w-4 text-slate-500" />
              <input
                type="password"
                required
                minLength={8}
                maxLength={72}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Create a strong password"
                className="w-full bg-transparent text-sm text-white outline-none placeholder:text-slate-500"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:opacity-50"
          >
            {loading ? "Creating workspace..." : "Create account"}
            <ArrowRight className="h-4 w-4" />
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-slate-400">
          Already have an account?{" "}
          <Link
            href="/login"
            className="font-semibold text-blue-400 hover:text-blue-300"
          >
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
