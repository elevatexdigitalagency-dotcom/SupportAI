"use client";

import React, { useCallback, useEffect, useState } from "react";
import { BarChart3, BookOpen, Bot, MessageSquare, Sparkles } from "@/components/ui/Icons";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { Card } from "@/components/ui/Card";
import { apiFetch } from "@/lib/api";
import { AnalyticsOverview } from "@/types";

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [error, setError] = useState("");

  const loadAnalytics = useCallback(async () => {
    setError("");
    try {
      const res = await apiFetch<AnalyticsOverview>(
        `/analytics/overview?days=${days}`
      );
      setData(res);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load analytics."
      );
    }
  }, [days]);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const res = await apiFetch<AnalyticsOverview>(
          `/analytics/overview?days=${days}`
        );
        if (!cancelled) {
          setData(res);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load analytics."
          );
        }
      }
    }
    void init();
    return () => {
      cancelled = true;
    };
  }, [days]);

  const maxMessages = Math.max(
    1,
    ...(data?.daily_messages.map((d) => d.count) || [1])
  );
  const maxConvs = Math.max(
    1,
    ...(data?.daily_conversations.map((d) => d.count) || [1])
  );

  return (
    <DashboardShell
      title="Analytics & Usage"
      subtitle="Real-time metrics queried directly from your workspace database"
      onWorkspaceChange={() => void loadAnalytics()}
    >
      {error && (
        <div className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="mb-6 flex items-center justify-between">
        <p className="text-xs text-slate-400">
          Showing activity for the last {days} days
        </p>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="rounded-xl border border-white/10 bg-[#0b1324] px-3 py-2 text-xs text-white"
        >
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {[
          {
            label: "Conversations",
            value: data?.metrics.total_conversations ?? 0,
            icon: MessageSquare,
          },
          {
            label: "Total Messages",
            value: data?.metrics.total_messages ?? 0,
            icon: BarChart3,
          },
          {
            label: "Active Chatbots",
            value: data?.metrics.active_chatbots ?? 0,
            icon: Bot,
          },
          {
            label: "Knowledge Sources",
            value: data?.metrics.knowledge_sources ?? 0,
            icon: BookOpen,
          },
          {
            label: "Monthly AI Replies",
            value: data?.metrics.monthly_ai_usage ?? 0,
            icon: Sparkles,
          },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <Card key={item.label} className="p-5">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">{item.label}</span>
                <Icon className="h-4 w-4 text-blue-400" />
              </div>
              <p className="mt-3 text-2xl font-bold text-white">{item.value}</p>
            </Card>
          );
        })}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <h2 className="text-sm font-semibold text-white">
            Daily Conversations
          </h2>
          <div className="mt-4 space-y-2.5">
            {!data || data.daily_conversations.length === 0 ? (
              <p className="py-6 text-center text-xs text-slate-500">
                No conversation activity recorded in this window.
              </p>
            ) : (
              data.daily_conversations.map((item) => (
                <div key={item.day} className="flex items-center gap-3 text-xs">
                  <span className="w-24 shrink-0 text-slate-400">
                    {item.day}
                  </span>
                  <div className="h-3 flex-1 rounded-full bg-white/10">
                    <div
                      className="h-3 rounded-full bg-blue-500"
                      style={{
                        width: `${Math.round((item.count / maxConvs) * 100)}%`,
                      }}
                    />
                  </div>
                  <span className="w-8 text-right font-semibold text-white">
                    {item.count}
                  </span>
                </div>
              ))
            )}
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="text-sm font-semibold text-white">Daily Messages</h2>
          <div className="mt-4 space-y-2.5">
            {!data || data.daily_messages.length === 0 ? (
              <p className="py-6 text-center text-xs text-slate-500">
                No message activity recorded in this window.
              </p>
            ) : (
              data.daily_messages.map((item) => (
                <div key={item.day} className="flex items-center gap-3 text-xs">
                  <span className="w-24 shrink-0 text-slate-400">
                    {item.day}
                  </span>
                  <div className="h-3 flex-1 rounded-full bg-white/10">
                    <div
                      className="h-3 rounded-full bg-emerald-500"
                      style={{
                        width: `${Math.round((item.count / maxMessages) * 100)}%`,
                      }}
                    />
                  </div>
                  <span className="w-8 text-right font-semibold text-white">
                    {item.count}
                  </span>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>
    </DashboardShell>
  );
}
