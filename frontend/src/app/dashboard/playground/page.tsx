"use client";

import React, { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  Check,
  Copy,
  Eraser,
  Plus,
  RefreshCw,
  Search,
  Send,
  Sparkles,
  Trash2,
} from "@/components/ui/Icons";
import { MarkdownContent } from "@/components/chat/MarkdownContent";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { apiFetch, API_URL } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import {
  Conversation,
  KnowledgeBase,
  Message,
  SourceCitation,
} from "@/types";

type Mode = "personal" | "support";

export default function PlaygroundPage() {
  const [mode, setMode] = useState<Mode>("personal");
  const [customerId, setCustomerId] = useState("demo-customer");
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedKbId, setSelectedKbId] = useState<number | "">("");

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [activeId, setActiveId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);

  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [apiConnected, setApiConnected] = useState<boolean | null>(null);
  const [error, setError] = useState("");

  const endRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const loadKnowledgeBases = useCallback(async () => {
    try {
      const res = await apiFetch<{ knowledge_bases: KnowledgeBase[] }>(
        "/knowledge/bases"
      );
      setKnowledgeBases(res.knowledge_bases || []);
    } catch {
      setKnowledgeBases([]);
    }
  }, []);

  const loadConversations = useCallback(async () => {
    try {
      const params = new URLSearchParams({ mode, status: "open" });
      if (mode === "support") {
        const trimmed = customerId.trim();
        if (!trimmed) {
          setConversations([]);
          return;
        }
        params.set("customer_id", trimmed);
      }
      if (searchTerm.trim()) {
        params.set("search", searchTerm.trim());
      }
      const res = await apiFetch<{ conversations: Conversation[] }>(
        `/conversations?${params.toString()}`
      );
      setConversations(res.conversations || []);
      setApiConnected(true);
    } catch {
      setConversations([]);
      setApiConnected(false);
    }
  }, [mode, customerId, searchTerm]);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const kbRes = await apiFetch<{ knowledge_bases: KnowledgeBase[] }>(
          "/knowledge/bases"
        );
        if (!cancelled) setKnowledgeBases(kbRes.knowledge_bases || []);
      } catch {
        if (!cancelled) setKnowledgeBases([]);
      }

      if (mode === "support" && !customerId.trim()) {
        return;
      }

      try {
        const params = new URLSearchParams({ mode, status: "open" });
        if (mode === "support") params.set("customer_id", customerId.trim());
        if (searchTerm.trim()) params.set("search", searchTerm.trim());
        const res = await apiFetch<{ conversations: Conversation[] }>(
          `/conversations?${params.toString()}`
        );
        if (!cancelled) {
          setConversations(res.conversations || []);
          setApiConnected(true);
        }
      } catch {
        if (!cancelled) {
          setConversations([]);
          setApiConnected(false);
        }
      }
    }
    void init();
    return () => {
      cancelled = true;
    };
  }, [mode, customerId, searchTerm]);

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((r) => setApiConnected(r.ok))
      .catch(() => setApiConnected(false));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function loadMessages(convId: number) {
    setLoadingHistory(true);
    setError("");
    try {
      const res = await apiFetch<{ messages: Message[] }>(
        `/conversations/${convId}/messages`
      );
      const parsed = (res.messages || []).map((m) => {
        let sources: SourceCitation[] | undefined;
        if (m.sources_json) {
          try {
            sources = JSON.parse(m.sources_json) as SourceCitation[];
          } catch {
            sources = undefined;
          }
        }
        return { ...m, sources };
      });
      setMessages(parsed);
      setActiveId(convId);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not load conversation."
      );
    } finally {
      setLoadingHistory(false);
    }
  }

  function startNewChat() {
    setActiveId(null);
    setMessages([]);
    setMessage("");
    setError("");
    textareaRef.current?.focus();
  }

  function handleModeSwitch(next: Mode) {
    setMode(next);
    setActiveId(null);
    setMessages([]);
    setError("");
  }

  async function handleSend(e: FormEvent) {
    e.preventDefault();
    const text = message.trim();
    if (!text || loading) return;

    if (mode === "support" && !customerId.trim()) {
      setError("Please enter a Customer ID before sending.");
      return;
    }

    setError("");
    setMessage("");
    setLoading(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: text, created_at: new Date().toISOString() },
    ]);

    try {
      const res = await apiFetch<{
        conversation_id: number;
        reply: string;
        sources?: SourceCitation[];
      }>("/chat", {
        method: "POST",
        body: JSON.stringify({
          message: text,
          mode,
          conversation_id: activeId ?? undefined,
          customer_id: mode === "support" ? customerId.trim() : undefined,
          knowledge_base_id: selectedKbId === "" ? undefined : selectedKbId,
        }),
      });
      setActiveId(res.conversation_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.reply,
          sources: res.sources,
          created_at: new Date().toISOString(),
        },
      ]);
      await loadConversations();
    } catch (err) {
      setMessages((prev) => prev.slice(0, -1));
      setMessage(text);
      setError(err instanceof Error ? err.message : "AI request failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRegenerate() {
    if (!activeId || loading) return;
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch<{
        reply: string;
        sources?: SourceCitation[];
      }>(`/conversations/${activeId}/regenerate`, {
        method: "POST",
        body: JSON.stringify({
          knowledge_base_id: selectedKbId === "" ? undefined : selectedKbId,
        }),
      });
      setMessages((prev) => {
        const next = [...prev];
        if (next.length > 0 && next[next.length - 1].role === "assistant") {
          next[next.length - 1] = {
            ...next[next.length - 1],
            content: res.reply,
            sources: res.sources,
            created_at: new Date().toISOString(),
          };
        } else {
          next.push({
            role: "assistant",
            content: res.reply,
            sources: res.sources,
            created_at: new Date().toISOString(),
          });
        }
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Regenerate failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleClearConversation() {
    if (!activeId) {
      startNewChat();
      return;
    }
    try {
      await apiFetch(`/conversations/${activeId}/clear`, { method: "POST" });
      setMessages([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Clear failed.");
    }
  }

  async function handleDeleteConversation(id: number) {
    try {
      await apiFetch(`/conversations/${id}`, { method: "DELETE" });
      if (activeId === id) {
        startNewChat();
      }
      await loadConversations();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed.");
    }
  }

  async function copyContent(text: string, idx: number) {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 1500);
    } catch {
      // Clipboard unavailable
    }
  }

  return (
    <DashboardShell
      title="AI Playground"
      subtitle="Personal AI assistant & grounded Customer Support workspace"
      onWorkspaceChange={() => {
        startNewChat();
        void loadKnowledgeBases();
        void loadConversations();
      }}
    >
      <div className="grid h-[calc(100vh-8.5rem)] min-h-[540px] gap-4 lg:grid-cols-[290px_1fr]">
        {/* LEFT CONVERSATION PANEL */}
        <div className="flex min-h-0 flex-col rounded-2xl border border-white/10 bg-[#0b1324] p-4">
          <button
            onClick={startNewChat}
            className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-3 py-2.5 text-xs font-semibold text-white transition hover:bg-blue-500"
          >
            <Plus className="h-4 w-4" />
            New conversation
          </button>

          <div className="mt-3 grid grid-cols-2 gap-2">
            <button
              onClick={() => handleModeSwitch("personal")}
              className={`rounded-xl px-2.5 py-2 text-xs font-medium transition ${
                mode === "personal"
                  ? "bg-blue-600/20 text-blue-300 border border-blue-500/40"
                  : "bg-white/5 text-slate-400 hover:text-white"
              }`}
            >
              Personal AI
            </button>
            <button
              onClick={() => handleModeSwitch("support")}
              className={`rounded-xl px-2.5 py-2 text-xs font-medium transition ${
                mode === "support"
                  ? "bg-blue-600/20 text-blue-300 border border-blue-500/40"
                  : "bg-white/5 text-slate-400 hover:text-white"
              }`}
            >
              Support AI
            </button>
          </div>

          {mode === "support" && (
            <div className="mt-3">
              <label className="mb-1 block text-[11px] text-slate-400">
                Customer ID
              </label>
              <input
                value={customerId}
                onChange={(e) => {
                  setCustomerId(e.target.value);
                  setActiveId(null);
                  setMessages([]);
                }}
                placeholder="customer-123"
                className="w-full rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white outline-none focus:border-blue-500"
              />
            </div>
          )}

          {knowledgeBases.length > 0 && (
            <div className="mt-3">
              <label className="mb-1 block text-[11px] text-slate-400">
                RAG Knowledge Base
              </label>
              <select
                value={selectedKbId}
                onChange={(e) =>
                  setSelectedKbId(
                    e.target.value ? Number(e.target.value) : ""
                  )
                }
                className="w-full rounded-xl border border-white/10 bg-[#060b16] px-2.5 py-2 text-xs text-white outline-none focus:border-blue-500"
              >
                <option value="">All workspace knowledge</option>
                {knowledgeBases.map((kb) => (
                  <option key={kb.id} value={kb.id}>
                    {kb.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="mt-3 flex items-center gap-2 rounded-xl border border-white/10 bg-[#060b16] px-2.5 py-1.5">
            <Search className="h-3.5 w-3.5 text-slate-500" />
            <input
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search conversations..."
              className="w-full bg-transparent text-xs text-white outline-none placeholder:text-slate-500"
            />
          </div>

          <div className="mt-3 min-h-0 flex-1 space-y-1 overflow-y-auto">
            {conversations.length === 0 ? (
              <p className="py-6 text-center text-xs text-slate-500">
                No conversations found.
              </p>
            ) : (
              conversations.map((conv) => (
                <div
                  key={conv.id}
                  className={`group flex items-center gap-1 rounded-xl px-2.5 py-2 text-xs transition ${
                    activeId === conv.id
                      ? "bg-blue-600/20 text-white"
                      : "text-slate-300 hover:bg-white/5"
                  }`}
                >
                  <button
                    onClick={() => void loadMessages(conv.id)}
                    className="min-w-0 flex-1 truncate text-left"
                    title={conv.title}
                  >
                    {conv.title}
                  </button>
                  <button
                    onClick={() => void handleDeleteConversation(conv.id)}
                    className="rounded p-1 text-slate-500 opacity-0 transition hover:text-red-400 group-hover:opacity-100"
                    aria-label="Delete conversation"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))
            )}
          </div>

          <div className="mt-3 flex items-center justify-between border-t border-white/10 pt-3 text-[11px] text-slate-400">
            <span className="flex items-center gap-1.5">
              <span
                className={`h-2 w-2 rounded-full ${
                  apiConnected === true
                    ? "bg-emerald-400"
                    : apiConnected === false
                      ? "bg-red-400"
                      : "bg-amber-400"
                }`}
              />
              API {apiConnected ? "Connected" : "Offline"}
            </span>
            <span>{conversations.length} chats</span>
          </div>
        </div>

        {/* CHAT WINDOW */}
        <div className="flex min-h-0 flex-col rounded-2xl border border-white/10 bg-[#0b1324]">
          <div className="flex items-center justify-between border-b border-white/10 px-5 py-3">
            <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
              <Sparkles className="h-4 w-4 text-blue-400" />
              {mode === "personal" ? "Personal AI" : `Support · ${customerId}`}
            </div>
            <div className="flex items-center gap-2">
              {activeId && messages.length > 0 && (
                <>
                  <button
                    onClick={() => void handleRegenerate()}
                    disabled={loading}
                    className="flex items-center gap-1.5 rounded-lg border border-white/10 px-2.5 py-1.5 text-xs text-slate-300 hover:bg-white/5 disabled:opacity-50"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                    Regenerate
                  </button>
                  <button
                    onClick={() => void handleClearConversation()}
                    disabled={loading}
                    className="flex items-center gap-1.5 rounded-lg border border-white/10 px-2.5 py-1.5 text-xs text-slate-300 hover:bg-white/5 disabled:opacity-50"
                  >
                    <Eraser className="h-3.5 w-3.5" />
                    Clear
                  </button>
                </>
              )}
            </div>
          </div>

          <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-5">
            {messages.length === 0 && !loadingHistory ? (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-600/15 text-blue-400">
                  <Sparkles className="h-6 w-6" />
                </div>
                <h2 className="mt-4 text-lg font-semibold text-white">
                  {mode === "personal"
                    ? "Ask your Personal AI"
                    : "Simulate a Customer Support session"}
                </h2>
                <p className="mt-1 max-w-md text-xs leading-5 text-slate-400">
                  Responses automatically incorporate your saved workspace
                  memories and indexed Knowledge Base documents with citations.
                </p>
              </div>
            ) : (
              messages.map((item, idx) => (
                <div
                  key={item.id ?? `${item.role}-${idx}`}
                  className={`flex gap-3 ${
                    item.role === "user" ? "flex-row-reverse" : ""
                  }`}
                >
                  <div
                    className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-xs font-bold ${
                      item.role === "user"
                        ? "bg-white/10 text-white"
                        : "bg-blue-600 text-white"
                    }`}
                  >
                    {item.role === "user" ? "You" : "AI"}
                  </div>
                  <div
                    className={`max-w-[82%] rounded-2xl px-4 py-3 ${
                      item.role === "user"
                        ? "bg-blue-600 text-white"
                        : "border border-white/10 bg-[#080f1e] text-slate-200"
                    }`}
                  >
                    {item.role === "user" ? (
                      <p className="whitespace-pre-wrap text-sm leading-relaxed">
                        {item.content}
                      </p>
                    ) : (
                      <MarkdownContent content={item.content} />
                    )}

                    {item.sources && item.sources.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1.5 border-t border-white/10 pt-2">
                        {item.sources.map((src) => (
                          <span
                            key={`${src.source_id}-${src.title}`}
                            className="rounded-md bg-blue-500/10 px-2 py-0.5 text-[11px] text-blue-300 border border-blue-500/20"
                          >
                            Source: {src.title}
                          </span>
                        ))}
                      </div>
                    )}

                    <div className="mt-2 flex items-center justify-between gap-3 text-[10px] opacity-70">
                      <span>{formatDateTime(item.created_at)}</span>
                      {item.role === "assistant" && (
                        <button
                          onClick={() => void copyContent(item.content, idx)}
                          className="inline-flex items-center gap-1 hover:text-white"
                        >
                          {copiedIdx === idx ? (
                            <>
                              <Check className="h-3 w-3" /> Copied
                            </>
                          ) : (
                            <>
                              <Copy className="h-3 w-3" /> Copy
                            </>
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}

            {loading && (
              <div className="text-xs text-slate-400">
                SupportAI is generating a grounded response...
              </div>
            )}
            <div ref={endRef} />
          </div>

          {error && (
            <div className="mx-5 mb-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-xs text-red-300">
              {error}
            </div>
          )}

          <form
            onSubmit={handleSend}
            className="border-t border-white/10 p-4"
          >
            <div className="flex items-end gap-2 rounded-2xl border border-white/10 bg-[#060b16] p-2 focus-within:border-blue-500">
              <textarea
                ref={textareaRef}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    e.currentTarget.form?.requestSubmit();
                  }
                }}
                rows={2}
                placeholder={
                  mode === "personal"
                    ? "Ask your personal AI assistant..."
                    : "Ask a customer support question..."
                }
                className="max-h-36 min-h-[44px] flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-white outline-none placeholder:text-slate-500"
              />
              <button
                type="submit"
                disabled={!message.trim() || loading}
                className="flex h-10 items-center gap-1.5 rounded-xl bg-blue-600 px-4 text-xs font-semibold text-white transition hover:bg-blue-500 disabled:opacity-40"
              >
                <Send className="h-3.5 w-3.5" />
                Send
              </button>
            </div>
          </form>
        </div>
      </div>
    </DashboardShell>
  );
}
