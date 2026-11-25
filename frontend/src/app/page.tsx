"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  Bot,
  Check,
  Globe,
  Lock,
  MessageSquare,
  Sparkles,
} from "@/components/ui/Icons";
import { API_URL } from "@/lib/api";
import { formatPriceCents } from "@/lib/utils";
import { Plan } from "@/types";

const FALLBACK_PLANS: Plan[] = [
  {
    id: 1,
    code: "free",
    name: "Free",
    monthly_price_cents: 0,
    monthly_message_limit: 100,
    document_limit: 5,
    chatbot_limit: 1,
    features: [
      "100 AI messages / month",
      "5 knowledge sources",
      "1 website chatbot",
      "Personal & Support AI playground",
    ],
  },
  {
    id: 2,
    code: "pro",
    name: "Pro",
    monthly_price_cents: 2900,
    monthly_message_limit: 2500,
    document_limit: 50,
    chatbot_limit: 5,
    features: [
      "2,500 AI messages / month",
      "50 knowledge sources",
      "5 website chatbots",
      "Website crawling & RAG citations",
    ],
  },
  {
    id: 3,
    code: "business",
    name: "Business",
    monthly_price_cents: 9900,
    monthly_message_limit: 15000,
    document_limit: 500,
    chatbot_limit: 25,
    features: [
      "15,000 AI messages / month",
      "500 knowledge sources",
      "25 website chatbots",
      "Team members & audit logs",
    ],
  },
];

export default function LandingPage() {
  const [plans, setPlans] = useState<Plan[]>(FALLBACK_PLANS);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/billing/plans`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data?.plans?.length) {
          setPlans(data.plans);
        }
      })
      .catch(() => {
        // Keep default plan table when backend is offline
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-screen bg-[#060b16] text-slate-100">
      {/* HEADER */}
      <header className="sticky top-0 z-40 border-b border-white/10 bg-[#060b16]/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600 font-bold text-white">
              S
            </div>
            <span className="text-lg font-bold tracking-tight text-white">
              Support<span className="text-blue-400">AI</span>
            </span>
          </Link>

          <nav className="hidden items-center gap-7 text-sm text-slate-300 md:flex">
            <a href="#features" className="hover:text-white">
              Features
            </a>
            <a href="#how-it-works" className="hover:text-white">
              How it works
            </a>
            <a href="#use-cases" className="hover:text-white">
              Use cases
            </a>
            <a href="#pricing" className="hover:text-white">
              Pricing
            </a>
            <a href="#faq" className="hover:text-white">
              FAQ
            </a>
          </nav>

          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="rounded-xl px-3.5 py-2 text-xs font-semibold text-slate-200 transition hover:bg-white/5"
            >
              Sign in
            </Link>
            <Link
              href="/register"
              className="rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-blue-500"
            >
              Start free
            </Link>
          </div>
        </div>
      </header>

      {/* HERO */}
      <section className="mx-auto max-w-6xl px-4 pb-20 pt-16 sm:px-6 sm:pt-24">
        <div className="mx-auto max-w-3xl text-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-3.5 py-1 text-xs font-medium text-blue-300">
            <Sparkles className="h-3.5 w-3.5" />
            Powered by Google Gemini & ChromaDB RAG
          </span>
          <h1 className="mt-6 text-4xl font-bold tracking-tight text-white sm:text-6xl">
            Personal AI workspace &amp;{" "}
            <span className="text-blue-400">grounded customer support</span>
          </h1>
          <p className="mt-6 text-base leading-7 text-slate-300 sm:text-lg">
            Train AI chatbots directly on your PDFs, DOCX guides, and website
            pages. Embed a fast support widget on any site while using your
            private Gemini assistant inside one isolated workspace.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/register"
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-6 py-3.5 text-sm font-semibold text-white transition hover:bg-blue-500 sm:w-auto"
            >
              Create free workspace
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/login"
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/[0.03] px-6 py-3.5 text-sm font-semibold text-slate-200 transition hover:bg-white/[0.07] sm:w-auto"
            >
              Sign in to Dashboard
            </Link>
          </div>
        </div>
      </section>

      {/* PRODUCT INTRO / FEATURES */}
      <section
        id="features"
        className="border-t border-white/10 bg-[#080f1e] py-20"
      >
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-widest text-blue-400">
              Platform Capabilities
            </p>
            <h2 className="mt-2 text-3xl font-bold text-white">
              Everything you need to run AI support in production
            </h2>
          </div>

          <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {[
              {
                icon: Sparkles,
                title: "Dual-Mode AI Playground",
                desc: "Switch seamlessly between Personal AI productivity and Customer Support simulations with full markdown and conversation history.",
              },
              {
                icon: BookOpen,
                title: "Document & URL Knowledge Base",
                desc: "Upload PDF, DOCX, TXT, or crawl public website pages. Automatic chunking, Gemini embeddings, and ChromaDB indexing.",
              },
              {
                icon: Bot,
                title: "Custom Website Chatbot Builder",
                desc: "Customize brand color, logo, welcome copy, system instructions, fallback responses, and allowed domains.",
              },
              {
                icon: Globe,
                title: "One-Line Embeddable Widget",
                desc: "Drop a single lightweight script tag onto WordPress, Webflow, Shopify, or custom HTML sites.",
              },
              {
                icon: Lock,
                title: "Workspace Isolation & Security",
                desc: "Strict JWT authentication, workspace-scoped collections, upload validation, domain checks, and audit logs.",
              },
              {
                icon: BarChart3,
                title: "Real-Time Usage & Analytics",
                desc: "Track real conversation volume, message trends, active bots, and monthly plan quotas from SQLite.",
              },
            ].map((item) => {
              const Icon = item.icon;
              return (
                <div
                  key={item.title}
                  className="rounded-2xl border border-white/10 bg-[#0b1324] p-6"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600/15 text-blue-400">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="mt-4 text-base font-semibold text-white">
                    {item.title}
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-slate-400">
                    {item.desc}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section id="how-it-works" className="border-t border-white/10 py-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <div className="text-center">
            <p className="text-xs font-semibold uppercase tracking-widest text-blue-400">
              How It Works
            </p>
            <h2 className="mt-2 text-3xl font-bold text-white">
              From raw docs to live widget in three steps
            </h2>
          </div>

          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {[
              {
                step: "01",
                title: "Add your knowledge",
                desc: "Upload help docs (PDF, DOCX, TXT) or crawl your website URLs into an isolated workspace knowledge base.",
              },
              {
                step: "02",
                title: "Configure your chatbot",
                desc: "Set your brand color, welcome message, instructions, fallback rules, and allowed website domains.",
              },
              {
                step: "03",
                title: "Embed & monitor",
                desc: "Paste the widget snippet onto your site and review grounded conversations, citations, and analytics.",
              },
            ].map((item) => (
              <div
                key={item.step}
                className="rounded-2xl border border-white/10 bg-[#0b1324] p-6"
              >
                <span className="text-xs font-bold text-blue-400">
                  STEP {item.step}
                </span>
                <h3 className="mt-2 text-lg font-semibold text-white">
                  {item.title}
                </h3>
                <p className="mt-2 text-sm leading-6 text-slate-400">
                  {item.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* USE CASES */}
      <section
        id="use-cases"
        className="border-t border-white/10 bg-[#080f1e] py-20"
      >
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-widest text-blue-400">
              Use Cases
            </p>
            <h2 className="mt-2 text-3xl font-bold text-white">
              Built for solo builders and support teams
            </h2>
          </div>

          <div className="mt-10 grid gap-6 md:grid-cols-3">
            {[
              {
                title: "SaaS & Product Support",
                desc: "Answer pricing, onboarding, and troubleshooting questions directly from your product docs without hallucinating policies.",
              },
              {
                title: "E-Commerce & WordPress Sites",
                desc: "Embed a customizable floating assistant for shipping, returns, and FAQs with domain-level access protection.",
              },
              {
                title: "Personal AI Copilot",
                desc: "Organize research notes, project plans, and saved memories in a private workspace separated from public chatbots.",
              },
            ].map((uc) => (
              <div
                key={uc.title}
                className="rounded-2xl border border-white/10 bg-[#0b1324] p-6"
              >
                <MessageSquare className="h-5 w-5 text-blue-400" />
                <h3 className="mt-4 text-base font-semibold text-white">
                  {uc.title}
                </h3>
                <p className="mt-2 text-sm leading-6 text-slate-400">
                  {uc.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PRICING */}
      <section id="pricing" className="border-t border-white/10 py-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <div className="text-center">
            <p className="text-xs font-semibold uppercase tracking-widest text-blue-400">
              Pricing
            </p>
            <h2 className="mt-2 text-3xl font-bold text-white">
              Simple, transparent workspace plans
            </h2>
            <p className="mt-2 text-sm text-slate-400">
              Start free and scale quotas as your support volume grows.
            </p>
          </div>

          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {plans.map((plan) => {
              const highlighted = plan.code === "pro";
              return (
                <div
                  key={plan.code}
                  className={`flex flex-col rounded-2xl border p-6 ${
                    highlighted
                      ? "border-blue-500 bg-[#0e1a33]"
                      : "border-white/10 bg-[#0b1324]"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-white">
                      {plan.name}
                    </h3>
                    {highlighted && (
                      <span className="rounded-full bg-blue-600 px-2.5 py-0.5 text-[11px] font-semibold text-white">
                        Popular
                      </span>
                    )}
                  </div>
                  <div className="mt-4 flex items-baseline gap-1">
                    <span className="text-3xl font-bold text-white">
                      {formatPriceCents(plan.monthly_price_cents)}
                    </span>
                    <span className="text-xs text-slate-400">/ month</span>
                  </div>
                  <ul className="mt-6 flex-1 space-y-3 text-sm text-slate-300">
                    {plan.features.map((feat) => (
                      <li key={feat} className="flex items-start gap-2.5">
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-blue-400" />
                        <span>{feat}</span>
                      </li>
                    ))}
                  </ul>
                  <Link
                    href="/register"
                    className={`mt-6 block rounded-xl px-4 py-2.5 text-center text-sm font-semibold transition ${
                      highlighted
                        ? "bg-blue-600 text-white hover:bg-blue-500"
                        : "border border-white/15 text-slate-200 hover:bg-white/5"
                    }`}
                  >
                    Get started with {plan.name}
                  </Link>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="border-t border-white/10 bg-[#080f1e] py-20">
        <div className="mx-auto max-w-4xl px-4 sm:px-6">
          <h2 className="text-center text-3xl font-bold text-white">
            Frequently asked questions
          </h2>
          <div className="mt-10 space-y-4">
            {[
              {
                q: "How does SupportAI prevent the chatbot from inventing answers?",
                a: "Every knowledge-grounded response retrieves top matching chunks from your workspace's ChromaDB collection and instructs Gemini to answer strictly from retrieved context or use your configured fallback message.",
              },
              {
                q: "Can I embed the chatbot on WordPress or static HTML websites?",
                a: "Yes. Copy the <script> embed snippet from your Chatbot Builder page and paste it before </body>. You can restrict allowed domains to prevent unauthorized embedding.",
              },
              {
                q: "Is each workspace isolated?",
                a: "Yes. Users, conversations, memories, uploaded documents, vector collections, chatbots, and analytics are strictly isolated by authenticated workspace membership.",
              },
            ].map((item) => (
              <div
                key={item.q}
                className="rounded-2xl border border-white/10 bg-[#0b1324] p-5"
              >
                <h3 className="text-sm font-semibold text-white">{item.q}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-400">
                  {item.a}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-white/10 py-10">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 text-xs text-slate-400 sm:flex-row sm:px-6">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-white">SupportAI</span>
            <span>· Intelligent AI Workspace &amp; Support Platform</span>
          </div>
          <div className="flex items-center gap-6">
            <Link href="/login" className="hover:text-white">
              Sign in
            </Link>
            <Link href="/register" className="hover:text-white">
              Create account
            </Link>
            <Link href="/dashboard" className="hover:text-white">
              Dashboard
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
