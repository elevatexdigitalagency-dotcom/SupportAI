"use client";

import React, { FormEvent, useCallback, useEffect, useState } from "react";
import { Plug, Plus, Trash2 } from "@/components/ui/Icons";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { Card, StatusBadge } from "@/components/ui/Card";
import { apiFetch } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";

type Integration = {
  id: number;
  provider: string;
  name: string;
  config_json: string;
  is_enabled: number;
  created_at: string;
};

export default function IntegrationsPage() {
  const [items, setItems] = useState<Integration[]>([]);
  const [provider, setProvider] = useState("wordpress");
  const [name, setName] = useState("");
  const [endpointUrl, setEndpointUrl] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await apiFetch<{ integrations: Integration[] }>(
        "/integrations"
      );
      setItems(res.integrations || []);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load integrations."
      );
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const res = await apiFetch<{ integrations: Integration[] }>(
          "/integrations"
        );
        if (!cancelled) setItems(res.integrations || []);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load integrations."
          );
        }
      }
    }
    void init();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleAdd(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setError("");
    try {
      await apiFetch("/integrations", {
        method: "POST",
        body: JSON.stringify({
          provider,
          name: name.trim(),
          config: endpointUrl.trim() ? { url: endpointUrl.trim() } : {},
        }),
      });
      setName("");
      setEndpointUrl("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add integration.");
    }
  }

  async function handleDelete(id: number) {
    await apiFetch(`/integrations/${id}`, { method: "DELETE" });
    await load();
  }

  return (
    <DashboardShell
      title="Integrations"
      subtitle="Connect WordPress sites, webhooks, and external channels"
      onWorkspaceChange={() => void load()}
    >
      {error && (
        <div className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <Card className="mb-6 p-5">
        <h2 className="text-sm font-semibold text-white">Add Integration</h2>
        <form onSubmit={handleAdd} className="mt-4 grid gap-3 sm:grid-cols-4">
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className="rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white"
          >
            <option value="wordpress">WordPress Site</option>
            <option value="webhook">Webhook Endpoint</option>
            <option value="html">Custom HTML Website</option>
          </select>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            placeholder="Integration label"
            className="rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white"
          />
          <input
            value={endpointUrl}
            onChange={(e) => setEndpointUrl(e.target.value)}
            placeholder="Site or webhook URL (optional)"
            className="rounded-xl border border-white/10 bg-[#060b16] px-3 py-2 text-xs text-white"
          />
          <button
            type="submit"
            className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-500"
          >
            <Plus className="h-4 w-4" />
            Connect
          </button>
        </form>
      </Card>

      <Card className="divide-y divide-white/10">
        {items.length === 0 ? (
          <p className="p-8 text-center text-sm text-slate-400">
            No integrations configured yet.
          </p>
        ) : (
          items.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between gap-4 px-5 py-4 text-xs"
            >
              <div className="flex items-center gap-3">
                <Plug className="h-4 w-4 text-blue-400" />
                <div>
                  <p className="font-semibold text-white">{item.name}</p>
                  <p className="text-slate-400">
                    {item.provider} · Added {formatDateTime(item.created_at)}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <StatusBadge
                  label={item.is_enabled ? "Active" : "Disabled"}
                  tone="green"
                />
                <button
                  onClick={() => void handleDelete(item.id)}
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-red-500/10 hover:text-red-400"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))
        )}
      </Card>
    </DashboardShell>
  );
}
