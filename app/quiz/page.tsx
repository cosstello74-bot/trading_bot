"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { Budget, Purpose } from "../../lib/engine";

const PURPOSES: Purpose[] = ["gaming", "work", "creative", "general"];
const BUDGETS: Budget[] = ["low", "mid", "high"];

export default function QuizPage() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2>(1);
  const [purpose, setPurpose] = useState<Purpose | null>(null);

  useEffect(() => {
    console.log("quiz_started");
  }, []);

  function selectPurpose(value: Purpose) {
    setPurpose(value);
    setStep(2);
  }

  function selectBudget(value: Budget) {
    if (!purpose) return;
    console.log("quiz_completed", { purpose, budget: value });
    router.push(`/results?purpose=${purpose}&budget=${value}`);
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-10 px-6">
      <p className="text-sm uppercase tracking-widest text-gray-500">
        Step {step} of 2
      </p>

      {step === 1 ? (
        <section className="flex flex-col items-center gap-6">
          <h2 className="text-3xl font-bold">What will you use it for?</h2>
          <div className="grid w-full max-w-md grid-cols-2 gap-4">
            {PURPOSES.map((p) => (
              <button
                key={p}
                onClick={() => selectPurpose(p)}
                className="rounded-xl border border-gray-700 px-6 py-5 text-lg font-medium capitalize transition hover:border-emerald-400 hover:bg-gray-900"
              >
                {p}
              </button>
            ))}
          </div>
        </section>
      ) : (
        <section className="flex flex-col items-center gap-6">
          <h2 className="text-3xl font-bold">What is your budget?</h2>
          <div className="grid w-full max-w-md grid-cols-3 gap-4">
            {BUDGETS.map((b) => (
              <button
                key={b}
                onClick={() => selectBudget(b)}
                className="rounded-xl border border-gray-700 px-6 py-5 text-lg font-medium capitalize transition hover:border-emerald-400 hover:bg-gray-900"
              >
                {b}
              </button>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
