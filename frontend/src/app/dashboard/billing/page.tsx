"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Check, CreditCard } from "@/components/ui/Icons";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { Card, StatusBadge } from "@/components/ui/Card";
import { apiFetch } from "@/lib/api";
import { formatPriceCents } from "@/lib/utils";
import { Plan, SubscriptionInfo } from "@/types";

export default function BillingPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [sub, setSub] = useState<SubscriptionInfo | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [plansRes, subRes] = await Promise.all([
        apiFetch<{ plans: Plan[] }>("/billing/plans"),
        apiFetch<SubscriptionInfo>("/billing/subscription"),
      ]);
      setPlans(plansRes.plans || []);
      setSub(subRes);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load billing details."
      );
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const [plansRes, subRes] = await Promise.all([
          apiFetch<{ plans: Plan[] }>("/billing/plans"),
          apiFetch<SubscriptionInfo>("/billing/subscription"),
        ]);
        if (!cancelled) {
          setPlans(plansRes.plans || []);
          setSub(subRes);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load billing details."
          );
        }
      }
    }
    void init();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handlePlanChange(planCode: string) {
    setError("");
    setMessage("");
    try {
      const res = await apiFetch<SubscriptionInfo>("/billing/change-plan", {
        method: "POST",
        body: JSON.stringify({ plan_code: planCode }),
      });
      setSub(res);
      setMessage(`Workspace plan switched to ${res.subscription.plan_name}.`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not update subscription."
      );
    }
  }

  return (
    <DashboardShell
      title="Subscription & Usage"
      subtitle="Monitor monthly quotas and switch workspace subscription tiers"
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

      {sub && (
        <Card className="mb-6 p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <CreditCard className="h-5 w-5 text-blue-400" />
              <div>
                <h2 className="text-base font-semibold text-white">
                  Current Plan: {sub.subscription.plan_name}
                </h2>
                <p className="text-xs text-slate-400">
                  Billing period {sub.usage.period_month} ·{" "}
                  {sub.payment_provider_connected
                    ? "Payment gateway active"
                    : "Plan quota management active (payment gateway not yet connected)"}
                </p>
              </div>
            </div>
            <StatusBadge label={sub.subscription.status} tone="green" />
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            {[
              {
                label: "Monthly AI Messages",
                used: sub.usage.messages_used,
                limit: sub.subscription.monthly_message_limit,
              },
              {
                label: "Knowledge Sources",
                used: sub.usage.documents_used,
                limit: sub.subscription.document_limit,
              },
              {
                label: "Chatbots",
                used: sub.usage.chatbots_used,
                limit: sub.subscription.chatbot_limit,
              },
            ].map((item) => (
              <div
                key={item.label}
                className="rounded-xl border border-white/10 bg-[#060b16] p-4"
              >
                <p className="text-xs text-slate-400">{item.label}</p>
                <p className="mt-2 text-xl font-bold text-white">
                  {item.used}{" "}
                  <span className="text-xs font-normal text-slate-400">
                    / {item.limit}
                  </span>
                </p>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="grid gap-6 md:grid-cols-3">
        {plans.map((plan) => {
          const isCurrent = sub?.subscription.plan_code === plan.code;
          return (
            <Card
              key={plan.code}
              className={`flex flex-col p-6 ${
                isCurrent ? "border-blue-500 bg-[#0d1830]" : ""
              }`}
            >
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-white">
                  {plan.name}
                </h3>
                {isCurrent && <StatusBadge label="Current" tone="blue" />}
              </div>
              <div className="mt-3 flex items-baseline gap-1">
                <span className="text-3xl font-bold text-white">
                  {formatPriceCents(plan.monthly_price_cents)}
                </span>
                <span className="text-xs text-slate-400">/ month</span>
              </div>
              <ul className="mt-5 flex-1 space-y-2.5 text-xs text-slate-300">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-center gap-2">
                    <Check className="h-3.5 w-3.5 text-blue-400" />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              <button
                disabled={isCurrent}
                onClick={() => void handlePlanChange(plan.code)}
                className={`mt-6 rounded-xl px-4 py-2.5 text-xs font-semibold transition ${
                  isCurrent
                    ? "cursor-default bg-white/10 text-slate-400"
                    : "bg-blue-600 text-white hover:bg-blue-500"
                }`}
              >
                {isCurrent ? "Active Plan" : `Switch to ${plan.name}`}
              </button>
            </Card>
          );
        })}
      </div>
    </DashboardShell>
  );
}
