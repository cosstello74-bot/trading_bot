# DEN v1 — Decision Engine Network

A deterministic, rule-based affiliate decision engine built with Next.js 14
(App Router). It converts user intent into ranked product recommendations and
affiliate click-throughs. No backend, no database, no external APIs — all logic
runs client-side against a static JSON file.

## Flow

```
/          landing page    → "Find the perfect laptop in under 60 seconds"
/quiz      2-step quiz      → purpose, then budget
/results   ranked products  → Best Match / Value Option / Upgrade Option
```

## Engine

`lib/engine.ts` is the deterministic core:

- Always prioritises an exact rule match (`purpose` + `budget`).
- Falls back to the top 3 products when no rule matches.
- Always returns at most 3 ranked products.
- Passes affiliate URLs through exactly as stored in `data/logic.json`.

Recommendation rules and products live in `data/logic.json`.

## Tracking

Console-only events (no analytics integration): `quiz_started`,
`quiz_completed`, `results_viewed`, `affiliate_clicked`.

## Commands

```bash
npm install
npm run dev     # local development
npm run build   # production build
npm run start   # serve production build
npm test        # run engine unit tests (vitest)
```

Deployable to Vercel without modification.
