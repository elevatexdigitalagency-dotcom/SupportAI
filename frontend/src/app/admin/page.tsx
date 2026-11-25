"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Shield } from "@/components/ui/Icons";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { Card, StatusBadge } from "@/components/ui/Card";
import { apiFetch } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";

type AdminStats = {
  stats: Record<string, number>;
  system: { database_exists: boolean; status: string };
};

type AdminUser = {
  id: number;
  email: string;
  full_name: string;
  role: "user" | "admin";
  is_active: number;
  created_at: string;
};

type AdminWorkspace = {
  id: number;
  name: string;
  owner_email: string;
  plan_name: string | null;
  member_count: number;
  chatbot_count: number;
};

type AuditLog = {
  id: number;
  action: string;
  resource_type: string;
  resource_id: string | null;
  actor_email: string | null;
  created_at: string;
};

export default function AdminPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [workspaces, setWorkspaces] = useState<AdminWorkspace[]>([]);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [sRes, uRes, wRes, lRes] = await Promise.all([
        apiFetch<AdminStats>("/admin/stats"),
        apiFetch<{ users: AdminUser[] }>("/admin/users"),
        apiFetch<{ workspaces: AdminWorkspace[] }>("/admin/workspaces"),
        apiFetch<{ audit_logs: AuditLog[] }>("/admin/audit-logs"),
      ]);
      setStats(sRes);
      setUsers(uRes.users || []);
      setWorkspaces(wRes.workspaces || []);
      setLogs(lRes.audit_logs || []);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Administrator authorization required."
      );
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const [sRes, uRes, wRes, lRes] = await Promise.all([
          apiFetch<AdminStats>("/admin/stats"),
          apiFetch<{ users: AdminUser[] }>("/admin/users"),
          apiFetch<{ workspaces: AdminWorkspace[] }>("/admin/workspaces"),
          apiFetch<{ audit_logs: AuditLog[] }>("/admin/audit-logs"),
        ]);
        if (cancelled) return;
        setStats(sRes);
        setUsers(uRes.users || []);
        setWorkspaces(wRes.workspaces || []);
        setLogs(lRes.audit_logs || []);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Administrator authorization required."
          );
        }
      }
    }
    void init();
    return () => {
      cancelled = true;
    };
  }, []);

  async function toggleUserActive(u: AdminUser) {
    try {
      await apiFetch(`/admin/users/${u.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !u.is_active }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed.");
    }
  }

  return (
    <DashboardShell
      title="Platform Administration"
      subtitle="System health, users, workspaces, and security audit trail"
    >
      {error ? (
        <Card className="border-red-500/30 bg-red-500/10 p-6 text-sm text-red-300">
          <div className="flex items-center gap-2 font-semibold">
            <Shield className="h-4 w-4" />
            Access Restricted
          </div>
          <p className="mt-2">{error}</p>
        </Card>
      ) : (
        <>
          {stats && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(stats.stats).map(([key, val]) => (
                <Card key={key} className="p-5">
                  <p className="text-xs uppercase tracking-wider text-slate-400">
                    {key.replaceAll("_", " ")}
                  </p>
                  <p className="mt-2 text-2xl font-bold text-white">{val}</p>
                </Card>
              ))}
            </div>
          )}

          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <Card className="overflow-hidden">
              <div className="border-b border-white/10 px-5 py-4">
                <h2 className="text-sm font-semibold text-white">
                  Users ({users.length})
                </h2>
              </div>
              <div className="divide-y divide-white/10">
                {users.map((u) => (
                  <div
                    key={u.id}
                    className="flex items-center justify-between gap-3 px-5 py-3 text-xs"
                  >
                    <div>
                      <p className="font-semibold text-white">{u.full_name}</p>
                      <p className="text-slate-400">{u.email}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <StatusBadge
                        label={u.role}
                        tone={u.role === "admin" ? "amber" : "neutral"}
                      />
                      <button
                        onClick={() => void toggleUserActive(u)}
                        className="rounded-lg border border-white/10 px-2.5 py-1 text-slate-200 hover:bg-white/5"
                      >
                        {u.is_active ? "Disable" : "Enable"}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="overflow-hidden">
              <div className="border-b border-white/10 px-5 py-4">
                <h2 className="text-sm font-semibold text-white">
                  Workspaces ({workspaces.length})
                </h2>
              </div>
              <div className="divide-y divide-white/10">
                {workspaces.map((w) => (
                  <div
                    key={w.id}
                    className="flex items-center justify-between gap-3 px-5 py-3 text-xs"
                  >
                    <div>
                      <p className="font-semibold text-white">{w.name}</p>
                      <p className="text-slate-400">Owner: {w.owner_email}</p>
                    </div>
                    <div className="text-right text-slate-300">
                      <StatusBadge label={w.plan_name || "Free"} tone="blue" />
                      <p className="mt-1 text-[11px] text-slate-400">
                        {w.member_count} members · {w.chatbot_count} bots
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          <Card className="mt-6 overflow-hidden">
            <div className="border-b border-white/10 px-5 py-4">
              <h2 className="text-sm font-semibold text-white">
                Recent Audit Logs
              </h2>
            </div>
            <div className="divide-y divide-white/10">
              {logs.map((log) => (
                <div
                  key={log.id}
                  className="flex flex-wrap items-center justify-between gap-2 px-5 py-3 text-xs"
                >
                  <div>
                    <span className="font-semibold text-blue-300">
                      {log.action}
                    </span>{" "}
                    <span className="text-slate-400">
                      ({log.resource_type} {log.resource_id || ""})
                    </span>
                  </div>
                  <div className="text-slate-400">
                    {log.actor_email || "system"} ·{" "}
                    {formatDateTime(log.created_at)}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </>
      )}
    </DashboardShell>
  );
}
