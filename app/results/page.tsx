"use client";

import { Suspense, useEffect, useMemo } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  getRecommendation,
  type Budget,
  type Purpose,
  type RankedProduct,
} from "../../lib/engine";

const PURPOSES: Purpose[] = ["gaming", "work", "creative", "general"];
const BUDGETS: Budget[] = ["low", "mid", "high"];

const SLOT_LABELS = ["Best Match", "Value Option", "Upgrade Option"];
const SLOT_REASONS = [
  "Top-ranked match for your purpose and budget.",
  "A dependable choice that balances price and performance.",
  "Step up for extra power and headroom.",
];

function isPurpose(value: string | null): value is Purpose {
  return value !== null && PURPOSES.includes(value as Purpose);
}

function isBudget(value: string | null): value is Budget {
  return value !== null && BUDGETS.includes(value as Budget);
}

function ResultsContent() {
  const searchParams = useSearchParams();

  const purpose = searchParams.get("purpose");
  const budget = searchParams.get("budget");

  const results: RankedProduct[] = useMemo(() => {
    const safePurpose: Purpose = isPurpose(purpose) ? purpose : "general";
    const safeBudget: Budget = isBudget(budget) ? budget : "mid";
    return getRecommendation({ purpose: safePurpose, budget: safeBudget });
  }, [purpose, budget]);

  useEffect(() => {
    console.log("results_viewed", { purpose, budget });
  }, [purpose, budget]);

  function handleAffiliateClick(product: RankedProduct) {
    console.log("affiliate_clicked", { id: product.id, name: product.name });
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-8 px-6 py-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold">Your ranked recommendations</h1>
        <p className="text-gray-400">
          Based on your answers, here are the top picks.
        </p>
      </header>

      <ul className="flex flex-col gap-6">
        {results.map((product, index) => {
          const isBest = index === 0;
          return (
            <li
              key={product.id}
              className={
                isBest
                  ? "rounded-2xl border-2 border-emerald-400 bg-gray-900 p-8"
                  : "rounded-2xl border border-gray-700 bg-gray-900/50 p-6"
              }
            >
              <p className="text-xs font-semibold uppercase tracking-widest text-emerald-400">
                {SLOT_LABELS[index] ?? `Option ${product.rank}`}
              </p>
              <h2
                className={
                  isBest
                    ? "mt-2 text-2xl font-bold"
                    : "mt-2 text-xl font-semibold"
                }
              >
                {product.name}
              </h2>
              <p className="mt-2 text-gray-400">
                {SLOT_REASONS[index] ?? "A solid recommendation for you."}
              </p>
              <a
                href={product.affiliate_url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => handleAffiliateClick(product)}
                className={
                  isBest
                    ? "mt-5 inline-block rounded-full bg-emerald-500 px-7 py-3 font-semibold text-black transition hover:bg-emerald-400"
                    : "mt-4 inline-block rounded-full border border-emerald-400 px-6 py-2.5 font-semibold text-emerald-300 transition hover:bg-emerald-400 hover:text-black"
                }
              >
                View Deal →
              </a>
            </li>
          );
        })}
      </ul>

      <Link href="/quiz" className="text-sm text-gray-500 underline">
        ← Retake quiz
      </Link>
    </main>
  );
}

export default function ResultsPage() {
  return (
    <Suspense fallback={<main className="p-16">Loading…</main>}>
      <ResultsContent />
    </Suspense>
  );
}
