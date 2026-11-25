"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  BookOpen,
  Bot,
  MessageSquare,
  Sparkles,
} from "@/components/ui/Icons";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { Card, StatusBadge } from "@/components/ui/Card";
import { apiFetch } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import { AnalyticsOverview, Conversation, SubscriptionInfo } from "@/types";

export default function DashboardOverviewPage() {
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [subscription, setSubscription] = useState<SubscriptionInfo | null>(
    null
  );
  const [recentConvs, setRecentConvs] = useState<Conversation[]>([]);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    setError("");
    try {
      const [anRes, subRes, convRes] = await Promise.all([
        apiFetch<AnalyticsOverview>("/analytics/overview?days=30"),
        apiFetch<SubscriptionInfo>("/billing/subscription"),
        apiFetch<{ conversations: Conversation[] }>(
          "/conversations?mode=all&status=all"
        ),
      ]);
      setAnalytics(anRes);
      setSubscription(subRes);
      setRecentConvs((convRes.conversations || []).slice(0, 5));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load dashboard data."
      );
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const [anRes, subRes, convRes] = await Promise.all([
          apiFetch<AnalyticsOverview>("/analytics/overview?days=30"),
          apiFetch<SubscriptionInfo>("/billing/subscription"),
          apiFetch<{ conversations: Conversation[] }>(
            "/conversations?mode=all&status=all"
          ),
        ]);
        if (cancelled) return;
        setAnalytics(anRes);
        setSubscription(subRes);
        setRecentConvs((convRes.conversations || []).slice(0, 5));
        setError("");
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load dashboard data."
          );
        }
      }
    }
    void init();
    return () => {
      cancelled = true;
    };
  }, []);

  const metrics = analytics?.metrics;

  return (
    <DashboardShell
      title="Workspace Overview"
      subtitle="Live metrics from your conversations, knowledge base, and chatbots"
      onWorkspaceChange={() => void loadData()}
    >
      {error && (
        <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          {
            label: "Total Conversations",
            value: metrics?.total_conversations ?? 0,
            icon: MessageSquare,
            href: "/dashboard/conversations",
          },
          {
            label: "Total Messages",
            value: metrics?.total_messages ?? 0,
            icon: Sparkles,
            href: "/dashboard/playground",
          },
          {
            label: "Active Chatbots",
            value: metrics?.active_chatbots ?? 0,
            icon: Bot,
            href: "/dashboard/chatbots",
          },
          {
            label: "Knowledge Sources",
            value: metrics?.knowledge_sources ?? 0,
            icon: BookOpen,
            href: "/dashboard/knowledge",
          },
        ].map((card) => {
          const Icon = card.icon;
          return (
            <Link key={card.label} href={card.href}>
              <Card className="p-5 transition hover:border-blue-500/40">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-400">
                    {card.label}
                  </span>
                  <Icon className="h-4 w-4 text-blue-400" />
                </div>
                <p className="mt-3 text-3xl font-bold text-white">
                  {card.value}
                </p>
              </Card>
            </Link>
          );
        })}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="p-6 lg:col-span-2">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-white">
                Recent Conversations
              </h2>
              <p className="text-xs text-slate-400">
                Latest personal, support, and widget sessions
              </p>
            </div>
            <Link
              href="/dashboard/conversations"
              className="flex items-center gap-1 text-xs font-medium text-blue-400 hover:text-blue-300"
            >
              View all
              <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          <div className="mt-4 divide-y divide-white/10">
            {recentConvs.length === 0 ? (
              <p className="py-8 text-center text-sm text-slate-400">
                No conversations yet. Start chatting in the AI Playground.
              </p>
            ) : (
              recentConvs.map((conv) => (
                <div
                  key={conv.id}
                  className="flex items-center justify-between gap-4 py-3"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-white">
                      {conv.title}
                    </p>
                    <p className="text-xs text-slate-400">
                      Updated {formatDateTime(conv.updated_at)}
                      {conv.customer_id ? ` · ${conv.customer_id}` : ""}
                    </p>
                  </div>
                  <StatusBadge
                    label={conv.mode}
                    tone={conv.mode === "support" ? "blue" : "neutral"}
                  />
                </div>
              ))
            )}
          </div>
        </Card>

        <Card className="p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-white">
              Plan &amp; Monthly Quota
            </h2>
            <StatusBadge
              label={subscription?.subscription.plan_name || "Free"}
              tone="blue"
            />
          </div>

          {subscription && (
            <div className="mt-5 space-y-4">
              {[
                {
                  label: "AI Messages",
                  used: subscription.usage.messages_used,
                  limit: subscription.subscription.monthly_message_limit,
                },
                {
                  label: "Knowledge Sources",
                  used: subscription.usage.documents_used,
                  limit: subscription.subscription.document_limit,
                },
                {
                  label: "Chatbots",
                  used: subscription.usage.chatbots_used,
                  limit: subscription.subscription.chatbot_limit,
                },
              ].map((quota) => {
                const pct = Math.min(
                  100,
                  Math.round((quota.used / Math.max(1, quota.limit)) * 100)
                );
                return (
                  <div key={quota.label}>
                    <div className="mb-1.5 flex justify-between text-xs">
                      <span className="text-slate-300">{quota.label}</span>
                      <span className="text-slate-400">
                        {quota.used} / {quota.limit}
                      </span>
                    </div>
                    <div className="h-2 rounded-full bg-white/10">
                      <div
                        className="h-2 rounded-full bg-blue-500 transition-all"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}

              <Link
                href="/dashboard/billing"
                className="mt-4 block rounded-xl border border-white/10 px-4 py-2.5 text-center text-xs font-semibold text-slate-200 transition hover:bg-white/5"
              >
                Manage plan &amp; limits
              </Link>
            </div>
          )}
        </Card>
      </div>
    </DashboardShell>
  );
}
