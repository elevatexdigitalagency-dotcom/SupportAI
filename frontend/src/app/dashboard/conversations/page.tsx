"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Archive, Download, Search, Trash2 } from "@/components/ui/Icons";
import { MarkdownContent } from "@/components/chat/MarkdownContent";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { Card, StatusBadge } from "@/components/ui/Card";
import { apiFetch } from "@/lib/api";
import { getActiveWorkspaceId } from "@/lib/auth";
import { formatDateTime } from "@/lib/utils";
import { Conversation, Message } from "@/types";

type Member = {
  user_id: number;
  email: string;
  full_name: string;
  role: string;
};

export default function ConversationsPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [members, setMembers] = useState<Member[]>([]);

  const [modeFilter, setModeFilter] = useState<"all" | "personal" | "support">(
    "all"
  );
  const [statusFilter, setStatusFilter] = useState<"open" | "archived" | "all">(
    "all"
  );
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");

  const loadList = useCallback(async () => {
    setError("");
    try {
      const params = new URLSearchParams({
        mode: modeFilter,
        status: statusFilter,
      });
      if (search.trim()) params.set("search", search.trim());
      const res = await apiFetch<{ conversations: Conversation[] }>(
        `/conversations?${params.toString()}`
      );
      setConversations(res.conversations || []);

      const wsId = getActiveWorkspaceId();
      if (wsId) {
        const memRes = await apiFetch<{ members: Member[] }>(
          `/workspaces/${wsId}/members`
        );
        setMembers(memRes.members || []);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load conversations."
      );
    }
  }, [modeFilter, statusFilter, search]);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const params = new URLSearchParams({
          mode: modeFilter,
          status: statusFilter,
        });
        if (search.trim()) params.set("search", search.trim());
        const res = await apiFetch<{ conversations: Conversation[] }>(
          `/conversations?${params.toString()}`
        );
        if (cancelled) return;
        setConversations(res.conversations || []);
        setError("");

        const wsId = getActiveWorkspaceId();
        if (wsId) {
          const memRes = await apiFetch<{ members: Member[] }>(
            `/workspaces/${wsId}/members`
          );
          if (!cancelled) setMembers(memRes.members || []);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load conversations."
          );
        }
      }
    }
    void init();
    return () => {
      cancelled = true;
    };
  }, [modeFilter, statusFilter, search]);

  async function selectConversation(conv: Conversation) {
    setSelected(conv);
    try {
      const res = await apiFetch<{
        conversation: Conversation;
        messages: Message[];
      }>(`/conversations/${conv.id}/messages`);
      setSelected(res.conversation);
      setMessages(res.messages || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load messages.");
    }
  }

  async function toggleArchive(conv: Conversation) {
    const nextStatus = conv.status === "archived" ? "open" : "archived";
    await apiFetch(`/conversations/${conv.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status: nextStatus }),
    });
    if (selected?.id === conv.id) {
      setSelected({ ...conv, status: nextStatus });
    }
    await loadList();
  }

  async function assignConversation(convId: number, userId: number) {
    const res = await apiFetch<{ conversation: Conversation }>(
      `/conversations/${convId}`,
      {
        method: "PATCH",
        body: JSON.stringify({ assigned_to_user_id: userId }),
      }
    );
    setSelected(res.conversation);
    await loadList();
  }

  async function handleExport(convId: number) {
    const data = await apiFetch<{
      conversation: Conversation;
      messages: Message[];
    }>(`/conversations/${convId}/export`);
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `conversation-${convId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleDelete(convId: number) {
    await apiFetch(`/conversations/${convId}`, { method: "DELETE" });
    if (selected?.id === convId) {
      setSelected(null);
      setMessages([]);
    }
    await loadList();
  }

  return (
    <DashboardShell
      title="Conversation Management"
      subtitle="Search, filter, assign, archive, and export workspace conversations"
      onWorkspaceChange={() => {
        setSelected(null);
        setMessages([]);
        void loadList();
      }}
    >
      {error && (
        <div className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex min-w-[220px] flex-1 items-center gap-2 rounded-xl border border-white/10 bg-[#0b1324] px-3 py-2">
          <Search className="h-4 w-4 text-slate-500" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by conversation title..."
            className="w-full bg-transparent text-xs text-white outline-none"
          />
        </div>
        <select
          value={modeFilter}
          onChange={(e) =>
            setModeFilter(e.target.value as "all" | "personal" | "support")
          }
          className="rounded-xl border border-white/10 bg-[#0b1324] px-3 py-2 text-xs text-white"
        >
          <option value="all">All modes</option>
          <option value="personal">Personal AI</option>
          <option value="support">Customer Support</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e) =>
            setStatusFilter(e.target.value as "open" | "archived" | "all")
          }
          className="rounded-xl border border-white/10 bg-[#0b1324] px-3 py-2 text-xs text-white"
        >
          <option value="all">All statuses</option>
          <option value="open">Open</option>
          <option value="archived">Archived</option>
        </select>
      </div>

      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        <Card className="max-h-[640px] overflow-y-auto divide-y divide-white/10">
          {conversations.length === 0 ? (
            <p className="p-8 text-center text-xs text-slate-400">
              No matching conversations.
            </p>
          ) : (
            conversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => void selectConversation(conv)}
                className={`block w-full p-4 text-left transition ${
                  selected?.id === conv.id
                    ? "bg-blue-600/15"
                    : "hover:bg-white/[0.03]"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-xs font-semibold text-white">
                    {conv.title}
                  </span>
                  <StatusBadge
                    label={conv.status || "open"}
                    tone={conv.status === "archived" ? "amber" : "green"}
                  />
                </div>
                <p className="mt-1 text-[11px] text-slate-400">
                  {conv.mode}
                  {conv.customer_id ? ` · ${conv.customer_id}` : ""} ·{" "}
                  {formatDateTime(conv.updated_at)}
                </p>
              </button>
            ))
          )}
        </Card>

        <Card className="flex min-h-[420px] flex-col p-5">
          {!selected ? (
            <div className="flex flex-1 items-center justify-center text-sm text-slate-400">
              Select a conversation to view details, assign, archive, or export.
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
                <div>
                  <h2 className="text-base font-semibold text-white">
                    {selected.title}
                  </h2>
                  <p className="text-xs text-slate-400">
                    ID #{selected.id} · {selected.mode}
                    {selected.customer_id
                      ? ` · Customer: ${selected.customer_id}`
                      : ""}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {members.length > 0 && (
                    <select
                      value={selected.assigned_to_user_id ?? ""}
                      onChange={(e) => {
                        if (e.target.value) {
                          void assignConversation(
                            selected.id,
                            Number(e.target.value)
                          );
                        }
                      }}
                      className="rounded-lg border border-white/10 bg-[#060b16] px-2.5 py-1.5 text-xs text-white"
                    >
                      <option value="">Unassigned</option>
                      {members.map((m) => (
                        <option key={m.user_id} value={m.user_id}>
                          {m.full_name}
                        </option>
                      ))}
                    </select>
                  )}

                  <button
                    onClick={() => void toggleArchive(selected)}
                    className="inline-flex items-center gap-1 rounded-lg border border-white/10 px-2.5 py-1.5 text-xs text-slate-200 hover:bg-white/5"
                  >
                    <Archive className="h-3.5 w-3.5" />
                    {selected.status === "archived" ? "Reopen" : "Archive"}
                  </button>
                  <button
                    onClick={() => void handleExport(selected.id)}
                    className="inline-flex items-center gap-1 rounded-lg border border-white/10 px-2.5 py-1.5 text-xs text-slate-200 hover:bg-white/5"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Export
                  </button>
                  <button
                    onClick={() => void handleDelete(selected.id)}
                    className="inline-flex items-center gap-1 rounded-lg border border-red-500/30 px-2.5 py-1.5 text-xs text-red-300 hover:bg-red-500/10"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Delete
                  </button>
                </div>
              </div>

              <div className="mt-4 flex-1 space-y-4 overflow-y-auto">
                {messages.map((m) => (
                  <div
                    key={m.id}
                    className={`rounded-xl p-3.5 ${
                      m.role === "user"
                        ? "bg-blue-600/15 border border-blue-500/20"
                        : "bg-[#060b16] border border-white/10"
                    }`}
                  >
                    <div className="mb-1 flex justify-between text-[11px] text-slate-400">
                      <span className="font-semibold uppercase text-slate-200">
                        {m.role}
                      </span>
                      <span>{formatDateTime(m.created_at)}</span>
                    </div>
                    {m.role === "assistant" ? (
                      <MarkdownContent content={m.content} />
                    ) : (
                      <p className="text-sm text-slate-100 whitespace-pre-wrap">
                        {m.content}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>
      </div>
    </DashboardShell>
  );
}
