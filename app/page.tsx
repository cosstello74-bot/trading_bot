import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 px-6 text-center">
      <h1 className="max-w-2xl text-4xl font-bold leading-tight sm:text-5xl">
        Find the perfect laptop in under 60 seconds
      </h1>
      <p className="max-w-md text-lg text-gray-400">
        Answer two quick questions and our decision engine ranks the best match
        for you.
      </p>
      <Link
        href="/quiz"
        className="rounded-full bg-emerald-500 px-8 py-4 text-lg font-semibold text-black transition hover:bg-emerald-400"
      >
        Start Quiz →
      </Link>
    </main>
  );
}
