"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  BookOpen,
  Bot,
  CreditCard,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  Plug,
  Settings,
  Shield,
  Sparkles,
  Users,
  X,
} from "@/components/ui/Icons";
import { apiFetch } from "@/lib/api";
import {
  clearSession,
  getAccessToken,
  getActiveWorkspaceId,
  getRefreshToken,
  getStoredUser,
  getStoredWorkspaces,
  saveStoredUser,
  setActiveWorkspaceId,
} from "@/lib/auth";
import { User, Workspace } from "@/types";

type NavItem = {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
};

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/playground", label: "AI Playground", icon: Sparkles },
  { href: "/dashboard/knowledge", label: "Knowledge Base", icon: BookOpen },
  { href: "/dashboard/conversations", label: "Conversations", icon: MessageSquare },
  { href: "/dashboard/chatbots", label: "Chatbots", icon: Bot },
  { href: "/dashboard/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/dashboard/integrations", label: "Integrations", icon: Plug },
  { href: "/dashboard/team", label: "Team", icon: Users },
  { href: "/dashboard/billing", label: "Billing", icon: CreditCard },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

export function DashboardShell({
  title,
  subtitle,
  children,
  onWorkspaceChange,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  onWorkspaceChange?: (workspaceId: number) => void;
}) {
  const pathname = usePathname();
  const router = useRouter();

  const [ready, setReady] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [user, setUser] = useState<User | null>(() => getStoredUser());
  const [workspaces, setWorkspaces] = useState<Workspace[]>(() =>
    getStoredWorkspaces()
  );
  const [activeWsId, setActiveWsId] = useState<number | null>(() =>
    getActiveWorkspaceId()
  );

  useEffect(() => {
    let cancelled = false;
    async function verifyAuth() {
      const token = getAccessToken();
      if (!token) {
        router.replace("/login");
        return;
      }
      try {
        const data = await apiFetch<{ user: User; workspaces: Workspace[] }>(
          "/auth/me"
        );
        if (cancelled) return;
        setUser(data.user);
        setWorkspaces(data.workspaces || []);
        saveStoredUser(data.user, data.workspaces || []);
        const current = getActiveWorkspaceId();
        const valid = data.workspaces?.some((w) => w.id === current);
        if (!valid && data.workspaces?.length > 0) {
          setActiveWorkspaceId(data.workspaces[0].id);
          setActiveWsId(data.workspaces[0].id);
        } else if (current) {
          setActiveWsId(current);
        }
        setReady(true);
      } catch {
        if (!cancelled) {
          clearSession();
          router.replace("/login");
        }
      }
    }
    void verifyAuth();
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function handleLogout() {
    try {
      await apiFetch("/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: getRefreshToken() }),
      });
    } catch {
      // Proceed with client logout even if token already expired
    }
    clearSession();
    router.push("/login");
  }

  function handleWorkspaceSelect(nextId: number) {
    setActiveWorkspaceId(nextId);
    setActiveWsId(nextId);
    if (onWorkspaceChange) {
      onWorkspaceChange(nextId);
    } else {
      window.location.reload();
    }
  }

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#060b16] text-slate-300">
        <div className="flex items-center gap-3 rounded-xl border border-white/10 bg-[#0b1324] px-5 py-3 text-sm">
          <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-blue-500" />
          Loading SupportAI workspace...
        </div>
      </div>
    );
  }

  const navContent = (
    <div className="flex h-full flex-col bg-[#080f1e] text-slate-200">
      <div className="flex h-16 items-center justify-between border-b border-white/10 px-5">
        <Link href="/dashboard" className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600 font-bold text-white shadow-sm">
            S
          </div>
          <div>
            <span className="text-base font-bold tracking-tight text-white">
              Support<span className="text-blue-400">AI</span>
            </span>
            <p className="text-[11px] text-slate-400">AI SaaS Platform</p>
          </div>
        </Link>
        <button
          onClick={() => setMobileOpen(false)}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-white/5 hover:text-white lg:hidden"
          aria-label="Close navigation"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {workspaces.length > 0 && (
        <div className="border-b border-white/10 p-4">
          <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Active Workspace
          </label>
          <select
            value={activeWsId ?? workspaces[0]?.id ?? ""}
            onChange={(e) => handleWorkspaceSelect(Number(e.target.value))}
            className="w-full rounded-xl border border-white/10 bg-[#0d172c] px-3 py-2 text-xs font-medium text-white outline-none focus:border-blue-500"
          >
            {workspaces.map((ws) => (
              <option key={ws.id} value={ws.id}>
                {ws.name} ({ws.role})
              </option>
            ))}
          </select>
        </div>
      )}

      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active =
            item.href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMobileOpen(false)}
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                active
                  ? "border border-blue-500/30 bg-blue-600/15 text-blue-300"
                  : "text-slate-400 hover:bg-white/5 hover:text-white"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span>{item.label}</span>
            </Link>
          );
        })}

        {user?.role === "admin" && (
          <Link
            href="/admin"
            onClick={() => setMobileOpen(false)}
            className={`mt-3 flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
              pathname.startsWith("/admin")
                ? "border border-blue-500/30 bg-blue-600/15 text-blue-300"
                : "text-amber-300/90 hover:bg-white/5 hover:text-amber-200"
            }`}
          >
            <Shield className="h-4 w-4 shrink-0" />
            <span>Admin Console</span>
          </Link>
        )}
      </nav>

      <div className="border-t border-white/10 p-4">
        <div className="mb-3 flex items-center gap-3 rounded-xl bg-white/[0.03] p-2.5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-600/20 text-xs font-bold text-blue-300">
            {user?.full_name?.slice(0, 2).toUpperCase() || "SA"}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-white">
              {user?.full_name}
            </p>
            <p className="truncate text-[11px] text-slate-400">{user?.email}</p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/10 px-3 py-2 text-xs font-medium text-slate-300 transition hover:border-red-500/40 hover:bg-red-500/10 hover:text-red-300"
        >
          <LogOut className="h-3.5 w-3.5" />
          Sign out
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen bg-[#060b16] text-slate-100">
      <aside className="hidden w-64 shrink-0 border-r border-white/10 lg:block">
        <div className="sticky top-0 h-screen">{navContent}</div>
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div
            className="fixed inset-0 bg-black/60"
            onClick={() => setMobileOpen(false)}
          />
          <div className="relative z-10 w-72 border-r border-white/10">
            {navContent}
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-white/10 bg-[#080f1e]/90 px-4 backdrop-blur sm:px-8">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileOpen(true)}
              className="rounded-lg border border-white/10 p-2 text-slate-300 hover:bg-white/5 lg:hidden"
              aria-label="Open navigation"
            >
              <Menu className="h-4 w-4" />
            </button>
            <div>
              <h1 className="text-base font-semibold text-white sm:text-lg">
                {title}
              </h1>
              {subtitle && (
                <p className="hidden text-xs text-slate-400 sm:block">
                  {subtitle}
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/dashboard/playground"
              className="rounded-xl bg-blue-600 px-3.5 py-2 text-xs font-semibold text-white transition hover:bg-blue-500"
            >
              Open Playground
            </Link>
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-8">{children}</main>
      </div>
    </div>
  );
}
