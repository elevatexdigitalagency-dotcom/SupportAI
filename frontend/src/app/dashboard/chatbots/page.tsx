"use client";

import React, { FormEvent, useCallback, useEffect, useState } from "react";
import { Bot, Check, Copy, Plus, Send, Trash2 } from "@/components/ui/Icons";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { Card, StatusBadge } from "@/components/ui/Card";
import { apiFetch, API_URL } from "@/lib/api";
import { Chatbot, KnowledgeBase } from "@/types";

export default function ChatbotsPage() {
  const [chatbots, setChatbots] = useState<Chatbot[]>([]);
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [selected, setSelected] = useState<Chatbot | null>(null);

  // Create form
  const [newName, setNewName] = useState("");
  const [newKbId, setNewKbId] = useState<number | "">("");

  // Preview state
  const [previewMsgs, setPreviewMsgs] = useState<
    { role: "user" | "assistant"; content: string }[]
  >([]);
  const [previewInput, setPreviewInput] = useState("");
  const [previewConvId, setPreviewConvId] = useState<number | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const [copiedCode, setCopiedCode] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    try {
      const [botRes, kbRes] = await Promise.all([
        apiFetch<{ chatbots: Chatbot[] }>("/chatbots"),
        apiFetch<{ knowledge_bases: KnowledgeBase[] }>("/knowledge/bases"),
      ]);
      const list = botRes.chatbots || [];
      setChatbots(list);
      setKbs(kbRes.knowledge_bases || []);
      if (list.length > 0 && !selected) {
        setSelected(list[0]);
        setPreviewMsgs([
          { role: "assistant", content: list[0].welcome_message },
        ]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load chatbots.");
    }
  }, [selected]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setError("");
    setMessage("");
    try {
      const res = await apiFetch<{ chatbot: Chatbot }>("/chatbots", {
        method: "POST",
        body: JSON.stringify({
          name: newName.trim(),
          knowledge_base_id: newKbId === "" ? undefined : newKbId,
        }),
      });
      setNewName("");
      setSelected(res.chatbot);
      setPreviewConvId(null);
      setPreviewMsgs([
        { role: "assistant", content: res.chatbot.welcome_message },
      ]);
      setMessage(`Created chatbot "${res.chatbot.name}".`);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create chatbot.");
    }
  }

  async function handleSaveConfig(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setError("");
    setMessage("");
    try {
      const res = await apiFetch<{ chatbot: Chatbot }>(
        `/chatbots/${selected.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            name: selected.name,
            knowledge_base_id: selected.knowledge_base_id,
            is_enabled: Boolean(selected.is_enabled),
            allowed_domains: selected.allowed_domains,
            primary_color: selected.primary_color,
            welcome_message: selected.welcome_message,
            system_instructions: selected.system_instructions,
            fallback_message: selected.fallback_message,
          }),
        }
      );
      setSelected(res.chatbot);
      setMessage("Chatbot settings saved.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed.");
    }
  }

  async function handleLogoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !selected) return;
    setError("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await apiFetch<{ chatbot: Chatbot }>(
        `/chatbots/${selected.id}/logo`,
        { method: "POST", body: fd }
      );
      setSelected(res.chatbot);
      setMessage("Brand logo uploaded.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Logo upload failed.");
    } finally {
      e.target.value = "";
    }
  }

  async function handleDelete(id: number) {
    await apiFetch(`/chatbots/${id}`, { method: "DELETE" });
    setSelected(null);
    await loadData();
  }

  async function handlePreviewSend(e: FormEvent) {
    e.preventDefault();
    if (!selected || !previewInput.trim() || previewLoading) return;
    const text = previewInput.trim();
    setPreviewInput("");
    setPreviewMsgs((prev) => [...prev, { role: "user", content: text }]);
    setPreviewLoading(true);
    try {
      const res = await fetch(`${API_URL}/widget/${selected.public_id}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          session_id: "dashboard-preview",
          conversation_id: previewConvId,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Preview failed");
      setPreviewConvId(data.conversation_id);
      setPreviewMsgs((prev) => [
        ...prev,
        { role: "assistant", content: data.reply },
      ]);
    } catch (err) {
      setPreviewMsgs((prev) => [
        ...prev,
        {
          role: "assistant",
          content: err instanceof Error ? err.message : "Error",
        },
      ]);
    } finally {
      setPreviewLoading(false);
    }
  }

  const embedSnippet = selected
    ? `<script\n  src="${API_URL}/widget.js"\n  data-chatbot-id="${selected.public_id}"\n  async\n></script>`
    : "";

  async function copyEmbed() {
    if (!embedSnippet) return;
    await navigator.clipboard.writeText(embedSnippet);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 1500);
  }

  return (
    <DashboardShell
      title="Website Chatbot Builder"
      subtitle="Configure brand styling, RAG knowledge base, allowed domains, and embeddable script"
      onWorkspaceChange={() => {
        setSelected(null);
        void loadData();
      }}
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

      <Card className="mb-6 p-4">
        <form onSubmit={handleCreate} className="flex flex-wrap gap-3">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="New chatbot name (e.g. Store Support Bot)"
            className="min-w-[220px] flex-1 rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white outline-none focus:border-blue-500"
          />
          <select
            value={newKbId}
            onChange={(e) =>
              setNewKbId(e.target.value ? Number(e.target.value) : "")
            }
            className="rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white"
          >
            <option value="">Default Knowledge Base</option>
            {kbs.map((kb) => (
              <option key={kb.id} value={kb.id}>
                {kb.name}
              </option>
            ))}
          </select>
          <button
            type="submit"
            className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-500"
          >
            <Plus className="h-4 w-4" />
            Create Chatbot
          </button>
        </form>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[240px_1fr_360px]">
        {/* BOT LIST */}
        <Card className="p-3 space-y-1.5">
          {chatbots.length === 0 ? (
            <p className="p-4 text-center text-xs text-slate-400">
              Create your first chatbot above.
            </p>
          ) : (
            chatbots.map((bot) => (
              <button
                key={bot.id}
                onClick={() => {
                  setSelected(bot);
                  setPreviewConvId(null);
                  setPreviewMsgs([
                    { role: "assistant", content: bot.welcome_message },
                  ]);
                }}
                className={`flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-xs transition ${
                  selected?.id === bot.id
                    ? "bg-blue-600/20 text-white"
                    : "text-slate-300 hover:bg-white/5"
                }`}
              >
                <span className="flex items-center gap-2 truncate">
                  <Bot className="h-4 w-4 shrink-0 text-blue-400" />
                  <span className="truncate">{bot.name}</span>
                </span>
                <StatusBadge
                  label={bot.is_enabled ? "On" : "Off"}
                  tone={bot.is_enabled ? "green" : "neutral"}
                />
              </button>
            ))
          )}
        </Card>

        {/* CONFIG FORM + EMBED */}
        {selected ? (
          <Card className="p-5">
            <form onSubmit={handleSaveConfig} className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-white">
                  Chatbot Settings ({selected.public_id})
                </h2>
                <button
                  type="button"
                  onClick={() => void handleDelete(selected.id)}
                  className="inline-flex items-center gap-1 rounded-lg border border-red-500/30 px-2.5 py-1 text-xs text-red-300 hover:bg-red-500/10"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete
                </button>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Chatbot Name
                  </label>
                  <input
                    value={selected.name}
                    onChange={(e) =>
                      setSelected({ ...selected, name: e.target.value })
                    }
                    className="w-full rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Knowledge Base
                  </label>
                  <select
                    value={selected.knowledge_base_id ?? ""}
                    onChange={(e) =>
                      setSelected({
                        ...selected,
                        knowledge_base_id: e.target.value
                          ? Number(e.target.value)
                          : null,
                      })
                    }
                    className="w-full rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white"
                  >
                    <option value="">None</option>
                    {kbs.map((kb) => (
                      <option key={kb.id} value={kb.id}>
                        {kb.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Primary Color
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      type="color"
                      value={selected.primary_color}
                      onChange={(e) =>
                        setSelected({
                          ...selected,
                          primary_color: e.target.value,
                        })
                      }
                      className="h-9 w-12 rounded border border-white/10 bg-transparent"
                    />
                    <input
                      value={selected.primary_color}
                      onChange={(e) =>
                        setSelected({
                          ...selected,
                          primary_color: e.target.value,
                        })
                      }
                      className="flex-1 rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white"
                    />
                  </div>
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-400">
                    Allowed Domains (comma-separated or *)
                  </label>
                  <input
                    value={selected.allowed_domains}
                    onChange={(e) =>
                      setSelected({
                        ...selected,
                        allowed_domains: e.target.value,
                      })
                    }
                    className="w-full rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs text-slate-400">
                  Welcome Message
                </label>
                <input
                  value={selected.welcome_message}
                  onChange={(e) =>
                    setSelected({
                      ...selected,
                      welcome_message: e.target.value,
                    })
                  }
                  className="w-full rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs text-slate-400">
                  System Instructions
                </label>
                <textarea
                  rows={3}
                  value={selected.system_instructions}
                  onChange={(e) =>
                    setSelected({
                      ...selected,
                      system_instructions: e.target.value,
                    })
                  }
                  className="w-full rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs text-slate-400">
                  Fallback Message
                </label>
                <input
                  value={selected.fallback_message}
                  onChange={(e) =>
                    setSelected({
                      ...selected,
                      fallback_message: e.target.value,
                    })
                  }
                  className="w-full rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white"
                />
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3">
                <label className="flex items-center gap-2 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    checked={Boolean(selected.is_enabled)}
                    onChange={(e) =>
                      setSelected({
                        ...selected,
                        is_enabled: e.target.checked,
                      })
                    }
                  />
                  Chatbot enabled
                </label>

                <label className="cursor-pointer rounded-xl border border-white/10 px-3 py-2 text-xs text-slate-300 hover:bg-white/5">
                  Upload Brand Logo
                  <input
                    type="file"
                    accept=".png,.jpg,.jpeg,.webp"
                    onChange={(e) => void handleLogoUpload(e)}
                    className="hidden"
                  />
                </label>

                <button
                  type="submit"
                  className="rounded-xl bg-blue-600 px-5 py-2 text-xs font-semibold text-white hover:bg-blue-500"
                >
                  Save Changes
                </button>
              </div>
            </form>

            <div className="mt-6 border-t border-white/10 pt-5">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-white">
                  Website Installation Snippet (WordPress / HTML)
                </h3>
                <button
                  onClick={() => void copyEmbed()}
                  className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
                >
                  {copiedCode ? (
                    <>
                      <Check className="h-3.5 w-3.5" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="h-3.5 w-3.5" /> Copy code
                    </>
                  )}
                </button>
              </div>
              <pre className="mt-2 overflow-x-auto rounded-xl border border-white/10 bg-[#060b16] p-3 font-mono text-xs text-blue-200">
                <code>{embedSnippet}</code>
              </pre>
            </div>
          </Card>
        ) : (
          <Card className="flex items-center justify-center p-10 text-sm text-slate-400">
            Select or create a chatbot to configure it.
          </Card>
        )}

        {/* LIVE WIDGET PREVIEW */}
        <Card className="flex h-[520px] flex-col overflow-hidden">
          <div
            className="px-4 py-3 text-sm font-semibold text-white"
            style={{ backgroundColor: selected?.primary_color || "#2563eb" }}
          >
            {selected?.name || "Widget Preview"}
          </div>
          <div className="flex-1 space-y-3 overflow-y-auto bg-[#060b16] p-4">
            {previewMsgs.map((m, i) => (
              <div
                key={i}
                className={`max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed ${
                  m.role === "user"
                    ? "ml-auto bg-blue-600 text-white"
                    : "border border-white/10 bg-[#0b1324] text-slate-200"
                }`}
              >
                {m.content}
              </div>
            ))}
            {previewLoading && (
              <div className="text-xs text-slate-400">Thinking...</div>
            )}
          </div>
          <form
            onSubmit={handlePreviewSend}
            className="flex gap-2 border-t border-white/10 bg-[#0b1324] p-3"
          >
            <input
              value={previewInput}
              onChange={(e) => setPreviewInput(e.target.value)}
              disabled={!selected}
              placeholder="Test widget chat..."
              className="flex-1 rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white outline-none"
            />
            <button
              type="submit"
              disabled={!selected || previewLoading}
              className="rounded-xl px-3 py-2 text-xs font-semibold text-white disabled:opacity-40"
              style={{ backgroundColor: selected?.primary_color || "#2563eb" }}
            >
              <Send className="h-3.5 w-3.5" />
            </button>
          </form>
        </Card>
      </div>
    </DashboardShell>
  );
}
