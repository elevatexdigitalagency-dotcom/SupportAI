"use client";

import React, { FormEvent, useCallback, useEffect, useState } from "react";
import { Building2, Plus, Trash2, Users } from "@/components/ui/Icons";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { Card, StatusBadge } from "@/components/ui/Card";
import { apiFetch } from "@/lib/api";
import { getActiveWorkspaceId, setActiveWorkspaceId } from "@/lib/auth";
import { Workspace } from "@/types";

type Member = {
  user_id: number;
  email: string;
  full_name: string;
  role: string;
  created_at: string;
};

export default function TeamPage() {
  const [members, setMembers] = useState<Member[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"member" | "admin">("member");
  const [newWsName, setNewWsName] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadMembers = useCallback(async () => {
    const wsId = getActiveWorkspaceId();
    if (!wsId) return;
    setError("");
    try {
      const res = await apiFetch<{ members: Member[] }>(
        `/workspaces/${wsId}/members`
      );
      setMembers(res.members || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load members.");
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      const wsId = getActiveWorkspaceId();
      if (!wsId) return;
      try {
        const res = await apiFetch<{ members: Member[] }>(
          `/workspaces/${wsId}/members`
        );
        if (!cancelled) {
          setMembers(res.members || []);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load members."
          );
        }
      }
    }
    void init();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleInvite(e: FormEvent) {
    e.preventDefault();
    const wsId = getActiveWorkspaceId();
    if (!wsId || !inviteEmail.trim()) return;
    setError("");
    setMessage("");
    try {
      await apiFetch(`/workspaces/${wsId}/members`, {
        method: "POST",
        body: JSON.stringify({
          email: inviteEmail.trim(),
          role: inviteRole,
        }),
      });
      setInviteEmail("");
      setMessage("Team member added to workspace.");
      await loadMembers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invite failed.");
    }
  }

  async function handleRemove(userId: number) {
    const wsId = getActiveWorkspaceId();
    if (!wsId) return;
    setError("");
    try {
      await apiFetch(`/workspaces/${wsId}/members/${userId}`, {
        method: "DELETE",
      });
      await loadMembers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Remove failed.");
    }
  }

  async function handleCreateWorkspace(e: FormEvent) {
    e.preventDefault();
    if (!newWsName.trim()) return;
    setError("");
    try {
      const res = await apiFetch<{ workspace: Workspace }>("/workspaces", {
        method: "POST",
        body: JSON.stringify({ name: newWsName.trim() }),
      });
      setActiveWorkspaceId(res.workspace.id);
      window.location.reload();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create workspace."
      );
    }
  }

  return (
    <DashboardShell
      title="Team & Workspaces"
      subtitle="Manage workspace members and create isolated team workspaces"
      onWorkspaceChange={() => void loadMembers()}
    >
      {error && (
        <div className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}
      {message && (
        <div className="mb-4 rounded-xl border border-blue-500/30 bg-blue-500/10 px-4 py-3 text-sm text-blue-200">
          {message}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-5">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-white">
            <Users className="h-4 w-4 text-blue-400" />
            Add Member to Current Workspace
          </h2>
          <p className="mt-1 text-xs text-slate-400">
            User must already have a registered SupportAI account.
          </p>
          <form onSubmit={handleInvite} className="mt-4 flex flex-wrap gap-2">
            <input
              type="email"
              required
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="teammate@company.com"
              className="flex-1 rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white"
            />
            <select
              value={inviteRole}
              onChange={(e) =>
                setInviteRole(e.target.value as "member" | "admin")
              }
              className="rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white"
            >
              <option value="member">Member</option>
              <option value="admin">Admin</option>
            </select>
            <button
              type="submit"
              className="inline-flex items-center gap-1 rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-500"
            >
              <Plus className="h-4 w-4" />
              Add
            </button>
          </form>
        </Card>

        <Card className="p-5">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-white">
            <Building2 className="h-4 w-4 text-blue-400" />
            Create New Workspace
          </h2>
          <p className="mt-1 text-xs text-slate-400">
            Each workspace has isolated conversations, knowledge bases, and
            quotas.
          </p>
          <form
            onSubmit={handleCreateWorkspace}
            className="mt-4 flex flex-wrap gap-2"
          >
            <input
              value={newWsName}
              onChange={(e) => setNewWsName(e.target.value)}
              required
              placeholder="Workspace name"
              className="flex-1 rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white"
            />
            <button
              type="submit"
              className="inline-flex items-center gap-1 rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-500"
            >
              <Plus className="h-4 w-4" />
              Create
            </button>
          </form>
        </Card>
      </div>

      <Card className="mt-6 divide-y divide-white/10">
        <div className="px-5 py-4">
          <h2 className="text-sm font-semibold text-white">
            Workspace Members ({members.length})
          </h2>
        </div>
        {members.map((m) => (
          <div
            key={m.user_id}
            className="flex items-center justify-between px-5 py-3.5 text-xs"
          >
            <div>
              <p className="font-semibold text-white">{m.full_name}</p>
              <p className="text-slate-400">{m.email}</p>
            </div>
            <div className="flex items-center gap-3">
              <StatusBadge
                label={m.role}
                tone={m.role === "owner" ? "blue" : "neutral"}
              />
              {m.role !== "owner" && (
                <button
                  onClick={() => void handleRemove(m.user_id)}
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-red-500/10 hover:text-red-400"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        ))}
      </Card>
    </DashboardShell>
  );
}
