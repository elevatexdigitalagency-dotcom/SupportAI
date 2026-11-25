"use client";

import React, { FormEvent, useCallback, useEffect, useState } from "react";
import { Plus, Trash2 } from "@/components/ui/Icons";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { Card } from "@/components/ui/Card";
import { apiFetch } from "@/lib/api";
import { getActiveWorkspaceId, saveStoredUser } from "@/lib/auth";
import { User } from "@/types";

type MemoryItem = {
  id: number;
  category: string;
  content: string;
  scope: string;
  created_at: string;
};

export default function SettingsPage() {
  const [user, setUser] = useState<User | null>(null);
  const [fullName, setFullName] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");

  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [memCategory, setMemCategory] = useState("preference");
  const [memContent, setMemContent] = useState("");

  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [meRes, memRes] = await Promise.all([
        apiFetch<{ user: User }>("/users/me"),
        apiFetch<{ memories: MemoryItem[] }>("/memories?scope=personal"),
      ]);
      setUser(meRes.user);
      setFullName(meRes.user.full_name);
      setMemories(memRes.memories || []);

      const wsId = getActiveWorkspaceId();
      if (wsId) {
        const wsRes = await apiFetch<{ workspace: { name: string } }>(
          `/workspaces/${wsId}`
        );
        setWorkspaceName(wsRes.workspace.name);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load settings.");
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const [meRes, memRes] = await Promise.all([
          apiFetch<{ user: User }>("/users/me"),
          apiFetch<{ memories: MemoryItem[] }>("/memories?scope=personal"),
        ]);
        if (cancelled) return;
        setUser(meRes.user);
        setFullName(meRes.user.full_name);
        setMemories(memRes.memories || []);

        const wsId = getActiveWorkspaceId();
        if (wsId) {
          const wsRes = await apiFetch<{ workspace: { name: string } }>(
            `/workspaces/${wsId}`
          );
          if (!cancelled) setWorkspaceName(wsRes.workspace.name);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load settings."
          );
        }
      }
    }
    void init();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleProfileSave(e: FormEvent) {
    e.preventDefault();
    setError("");
    setMessage("");
    try {
      const res = await apiFetch<{ user: User }>("/users/me", {
        method: "PATCH",
        body: JSON.stringify({ full_name: fullName }),
      });
      setUser(res.user);
      saveStoredUser(res.user);
      setMessage("Profile updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Profile update failed.");
    }
  }

  async function handleWorkspaceRename(e: FormEvent) {
    e.preventDefault();
    const wsId = getActiveWorkspaceId();
    if (!wsId) return;
    setError("");
    setMessage("");
    try {
      await apiFetch(`/workspaces/${wsId}`, {
        method: "PATCH",
        body: JSON.stringify({ name: workspaceName }),
      });
      setMessage("Workspace name updated.");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Workspace update failed."
      );
    }
  }

  async function handleChangePassword(e: FormEvent) {
    e.preventDefault();
    setError("");
    setMessage("");
    try {
      await apiFetch("/users/me/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      setCurrentPassword("");
      setNewPassword("");
      setMessage("Password changed successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Password change failed.");
    }
  }

  async function handleAddMemory(e: FormEvent) {
    e.preventDefault();
    if (!memContent.trim()) return;
    setError("");
    try {
      await apiFetch("/memories", {
        method: "POST",
        body: JSON.stringify({
          category: memCategory.trim() || "preference",
          content: memContent.trim(),
          scope: "personal",
        }),
      });
      setMemContent("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save memory.");
    }
  }

  async function handleDeleteMemory(id: number) {
    await apiFetch(`/memories/${id}`, { method: "DELETE" });
    await load();
  }

  return (
    <DashboardShell
      title="Settings & Profile"
      subtitle="Account profile, security, workspace settings, and saved AI memories"
      onWorkspaceChange={() => void load()}
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
        <Card className="p-6">
          <h2 className="text-sm font-semibold text-white">User Profile</h2>
          <form onSubmit={handleProfileSave} className="mt-4 space-y-3">
            <div>
              <label className="mb-1 block text-xs text-slate-400">Email</label>
              <input
                disabled
                value={user?.email || ""}
                className="w-full rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-slate-400"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Full Name
              </label>
              <input
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
                className="w-full rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white"
              />
            </div>
            <button
              type="submit"
              className="rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-500"
            >
              Save Profile
            </button>
          </form>

          <form
            onSubmit={handleWorkspaceRename}
            className="mt-6 space-y-3 border-t border-white/10 pt-5"
          >
            <h3 className="text-sm font-semibold text-white">
              Active Workspace Name
            </h3>
            <div className="flex gap-2">
              <input
                value={workspaceName}
                onChange={(e) => setWorkspaceName(e.target.value)}
                className="flex-1 rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white"
              />
              <button
                type="submit"
                className="rounded-xl border border-white/15 px-4 py-2 text-xs font-semibold text-white hover:bg-white/5"
              >
                Rename
              </button>
            </div>
          </form>
        </Card>

        <Card className="p-6">
          <h2 className="text-sm font-semibold text-white">Change Password</h2>
          <form onSubmit={handleChangePassword} className="mt-4 space-y-3">
            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Current Password
              </label>
              <input
                type="password"
                required
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="w-full rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">
                New Password (min 8 characters)
              </label>
              <input
                type="password"
                required
                minLength={8}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white"
              />
            </div>
            <button
              type="submit"
              className="rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-500"
            >
              Update Password
            </button>
          </form>
        </Card>
      </div>

      <Card className="mt-6 p-6">
        <h2 className="text-sm font-semibold text-white">
          Personal AI Saved Memories
        </h2>
        <form onSubmit={handleAddMemory} className="mt-3 flex flex-wrap gap-2">
          <input
            value={memCategory}
            onChange={(e) => setMemCategory(e.target.value)}
            placeholder="Category (e.g. preference)"
            className="w-40 rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white"
          />
          <input
            value={memContent}
            onChange={(e) => setMemContent(e.target.value)}
            placeholder="Remember that I prefer concise TypeScript examples..."
            className="flex-1 rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white"
          />
          <button
            type="submit"
            className="inline-flex items-center gap-1 rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-500"
          >
            <Plus className="h-4 w-4" />
            Save Memory
          </button>
        </form>

        <div className="mt-4 divide-y divide-white/10">
          {memories.length === 0 ? (
            <p className="py-4 text-xs text-slate-500">
              No saved personal memories yet.
            </p>
          ) : (
            memories.map((m) => (
              <div
                key={m.id}
                className="flex items-center justify-between gap-4 py-2.5 text-xs"
              >
                <div>
                  <span className="mr-2 rounded bg-blue-500/15 px-2 py-0.5 text-[11px] text-blue-300">
                    {m.category}
                  </span>
                  <span className="text-slate-200">{m.content}</span>
                </div>
                <button
                  onClick={() => void handleDeleteMemory(m.id)}
                  className="rounded p-1 text-slate-400 hover:text-red-400"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))
          )}
        </div>
      </Card>
    </DashboardShell>
  );
}
