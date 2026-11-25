"use client";

import React, { FormEvent, useCallback, useEffect, useState } from "react";
import {
  BookOpen,
  FileText,
  Globe,
  Plus,
  Search,
  Trash2,
  Upload,
} from "@/components/ui/Icons";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { Card, StatusBadge } from "@/components/ui/Card";
import { apiFetch } from "@/lib/api";
import { formatBytes, formatDateTime } from "@/lib/utils";
import { KnowledgeBase, KnowledgeSource, SourceCitation } from "@/types";

export default function KnowledgePage() {
  const [bases, setBases] = useState<KnowledgeBase[]>([]);
  const [selectedKbId, setSelectedKbId] = useState<number | "">("");
  const [sources, setSources] = useState<KnowledgeSource[]>([]);

  const [newKbName, setNewKbName] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [maxPages, setMaxPages] = useState(3);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResult, setSearchResult] = useState<{
    context: string;
    sources: SourceCitation[];
  } | null>(null);

  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadAll = useCallback(async () => {
    try {
      const [kbRes, srcRes] = await Promise.all([
        apiFetch<{ knowledge_bases: KnowledgeBase[] }>("/knowledge/bases"),
        apiFetch<{ sources: KnowledgeSource[] }>(
          selectedKbId !== ""
            ? `/knowledge/sources?knowledge_base_id=${selectedKbId}`
            : "/knowledge/sources"
        ),
      ]);
      setBases(kbRes.knowledge_bases || []);
      setSources(srcRes.sources || []);
      if (selectedKbId === "" && kbRes.knowledge_bases?.length > 0) {
        setSelectedKbId(kbRes.knowledge_bases[0].id);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load knowledge base."
      );
    }
  }, [selectedKbId]);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const [kbRes, srcRes] = await Promise.all([
          apiFetch<{ knowledge_bases: KnowledgeBase[] }>("/knowledge/bases"),
          apiFetch<{ sources: KnowledgeSource[] }>(
            selectedKbId !== ""
              ? `/knowledge/sources?knowledge_base_id=${selectedKbId}`
              : "/knowledge/sources"
          ),
        ]);
        if (cancelled) return;
        setBases(kbRes.knowledge_bases || []);
        setSources(srcRes.sources || []);
        if (selectedKbId === "" && kbRes.knowledge_bases?.length > 0) {
          setSelectedKbId(kbRes.knowledge_bases[0].id);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load knowledge base."
          );
        }
      }
    }
    void init();
    return () => {
      cancelled = true;
    };
  }, [selectedKbId]);

  async function handleCreateKb(e: FormEvent) {
    e.preventDefault();
    if (!newKbName.trim()) return;
    setError("");
    setMessage("");
    setBusy(true);
    try {
      const res = await apiFetch<{ knowledge_base: KnowledgeBase }>(
        "/knowledge/bases",
        {
          method: "POST",
          body: JSON.stringify({ name: newKbName.trim() }),
        }
      );
      setNewKbName("");
      setSelectedKbId(res.knowledge_base.id);
      setMessage(`Created knowledge base "${res.knowledge_base.name}".`);
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");
    setMessage("");
    setBusy(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      if (selectedKbId !== "") {
        formData.append("knowledge_base_id", String(selectedKbId));
      }
      const res = await apiFetch<{ source: KnowledgeSource }>(
        "/knowledge/upload",
        {
          method: "POST",
          body: formData,
        }
      );
      setMessage(
        `Indexed "${res.source.title}" (${res.source.chunk_count} chunks).`
      );
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  async function handleCrawl(e: FormEvent) {
    e.preventDefault();
    if (!urlInput.trim()) return;
    setError("");
    setMessage("");
    setBusy(true);
    try {
      const res = await apiFetch<{ source: KnowledgeSource }>(
        "/knowledge/crawl",
        {
          method: "POST",
          body: JSON.stringify({
            url: urlInput.trim(),
            max_pages: maxPages,
            knowledge_base_id: selectedKbId === "" ? undefined : selectedKbId,
          }),
        }
      );
      setUrlInput("");
      setMessage(
        `Crawled & indexed "${res.source.title}" (${res.source.chunk_count} chunks).`
      );
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Website crawl failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteSource(id: number) {
    setError("");
    try {
      await apiFetch(`/knowledge/sources/${id}`, { method: "DELETE" });
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed.");
    }
  }

  async function handleSearch(e: FormEvent) {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setError("");
    try {
      const res = await apiFetch<{
        context: string;
        sources: SourceCitation[];
      }>("/knowledge/search", {
        method: "POST",
        body: JSON.stringify({
          query: searchQuery.trim(),
          knowledge_base_id: selectedKbId === "" ? undefined : selectedKbId,
          top_k: 4,
        }),
      });
      setSearchResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed.");
    }
  }

  return (
    <DashboardShell
      title="Knowledge Base & RAG"
      subtitle="Upload PDF, DOCX, TXT files or crawl websites into workspace-isolated ChromaDB"
      onWorkspaceChange={() => {
        setSelectedKbId("");
        void loadAll();
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

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="p-5">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-white">
            <BookOpen className="h-4 w-4 text-blue-400" />
            Knowledge Bases
          </h2>
          <div className="mt-3">
            <select
              value={selectedKbId}
              onChange={(e) =>
                setSelectedKbId(e.target.value ? Number(e.target.value) : "")
              }
              className="w-full rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white outline-none focus:border-blue-500"
            >
              {bases.map((kb) => (
                <option key={kb.id} value={kb.id}>
                  {kb.name} ({kb.source_count ?? 0} sources)
                </option>
              ))}
            </select>
          </div>
          <form onSubmit={handleCreateKb} className="mt-3 flex gap-2">
            <input
              value={newKbName}
              onChange={(e) => setNewKbName(e.target.value)}
              placeholder="New knowledge base name"
              className="flex-1 rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white outline-none focus:border-blue-500"
            />
            <button
              type="submit"
              disabled={busy}
              className="rounded-xl bg-blue-600 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-500 disabled:opacity-50"
            >
              <Plus className="h-4 w-4" />
            </button>
          </form>
        </Card>

        <Card className="p-5">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-white">
            <Upload className="h-4 w-4 text-blue-400" />
            Upload Document
          </h2>
          <p className="mt-1 text-xs text-slate-400">
            Supports PDF, DOCX, TXT, and MD up to 10 MB.
          </p>
          <label className="mt-4 flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-blue-500/40 bg-blue-500/5 px-4 py-6 text-xs font-medium text-blue-300 transition hover:bg-blue-500/10">
            <Upload className="h-4 w-4" />
            <span>{busy ? "Processing..." : "Choose file to upload"}</span>
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md"
              disabled={busy}
              onChange={(e) => void handleFileUpload(e)}
              className="hidden"
            />
          </label>
        </Card>

        <Card className="p-5">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-white">
            <Globe className="h-4 w-4 text-blue-400" />
            Crawl Website URL
          </h2>
          <form onSubmit={handleCrawl} className="mt-3 space-y-2.5">
            <input
              type="url"
              required
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="https://docs.example.com"
              className="w-full rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white outline-none focus:border-blue-500"
            />
            <div className="flex items-center gap-2">
              <label className="text-xs text-slate-400">Max pages:</label>
              <select
                value={maxPages}
                onChange={(e) => setMaxPages(Number(e.target.value))}
                className="rounded-lg border border-white/10 bg-[#060b16] px-2 py-1 text-xs text-white"
              >
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
              <button
                type="submit"
                disabled={busy}
                className="ml-auto rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-500 disabled:opacity-50"
              >
                {busy ? "Crawling..." : "Crawl & Index"}
              </button>
            </div>
          </form>
        </Card>
      </div>

      {/* SEMANTIC SEARCH TESTER */}
      <Card className="mt-6 p-5">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-white">
          <Search className="h-4 w-4 text-blue-400" />
          Test Semantic Retrieval
        </h2>
        <form onSubmit={handleSearch} className="mt-3 flex gap-2">
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Ask a test question to inspect retrieved ChromaDB chunks..."
            className="flex-1 rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white outline-none focus:border-blue-500"
          />
          <button
            type="submit"
            className="rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-500"
          >
            Search
          </button>
        </form>
        {searchResult && (
          <div className="mt-4 space-y-2 rounded-xl border border-white/10 bg-[#060b16] p-4 text-xs text-slate-300">
            {searchResult.context ? (
              <pre className="whitespace-pre-wrap font-sans leading-relaxed">
                {searchResult.context}
              </pre>
            ) : (
              <p className="text-slate-500">No matching chunks found.</p>
            )}
          </div>
        )}
      </Card>

      {/* SOURCES TABLE */}
      <Card className="mt-6 overflow-hidden">
        <div className="border-b border-white/10 px-5 py-4">
          <h2 className="text-sm font-semibold text-white">
            Indexed Knowledge Sources ({sources.length})
          </h2>
        </div>
        <div className="divide-y divide-white/10">
          {sources.length === 0 ? (
            <p className="p-8 text-center text-sm text-slate-400">
              No documents or website URLs indexed yet.
            </p>
          ) : (
            sources.map((src) => (
              <div
                key={src.id}
                className="flex flex-wrap items-center justify-between gap-4 px-5 py-3.5 text-xs"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <FileText className="h-4 w-4 shrink-0 text-blue-400" />
                  <div className="min-w-0">
                    <p className="truncate font-medium text-white">
                      {src.title}
                    </p>
                    <p className="text-slate-400">
                      {src.source_type.toUpperCase()} · {src.chunk_count} chunks ·{" "}
                      {formatBytes(src.file_size_bytes)} ·{" "}
                      {formatDateTime(src.created_at)}
                    </p>
                    {src.error_message && (
                      <p className="mt-1 text-red-400">{src.error_message}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <StatusBadge
                    label={src.status}
                    tone={
                      src.status === "indexed"
                        ? "green"
                        : src.status === "failed"
                          ? "red"
                          : "amber"
                    }
                  />
                  <button
                    onClick={() => void handleDeleteSource(src.id)}
                    className="rounded-lg p-1.5 text-slate-400 hover:bg-red-500/10 hover:text-red-400"
                    aria-label="Delete source"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>
    </DashboardShell>
  );
}
