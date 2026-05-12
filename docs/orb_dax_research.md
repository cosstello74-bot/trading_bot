# DAX Opening Range Breakout — Deep Research & Strategy Brief

> Working document. Branch: `claude/orb-dax-trading-research-3QTCi`.
> Goal: identify the most profitable ORB variant on DAX for automation, and a
> backtest/implementation plan.

## 1. DAX market microstructure relevant to ORB

- **Xetra cash session**: 09:00–17:30 CET (closing auction 17:30–17:35).
- **FDAX futures (Eurex)**: 01:10–22:00 CET. Liquidity meaningful from ~07:00 CET.
- **Two daily liquidity peaks**: 09:00 Xetra open and 15:30 CET US cash open.
- **Lunch lull**: ~12:00–13:30 CET — statistically chop, false-breakout zone.
- **Typical daily range**: 150–250 FDAX points. Most directional travel sets in
  the first 60–90 min and again 15:30–17:00 CET.
- **Tick economics**: FDAX = €25/pt, FDXM (mini) = €5/pt.

## 2. Documented ORB variants on DAX

| Variant            | Range window (CET) | Notes |
|--------------------|--------------------|-------|
| Pre-Xetra ORB      | 08:00–09:00        | Captures overnight + pre-market; entry on Xetra-open break |
| Klatt 15-min ORB   | 09:00–09:15        | Aggressive, many signals |
| Crabel 5-min ORB   | 09:00–09:05        | Zarattini/Aziz-style with RVOL filter is the modern form |
| 30-min ORB         | 09:00–09:30        | Conservative, fewer false breaks |
| First-Hour ORB     | 09:00–10:00        | Wider stop → smaller R-multiple |
| US-Open ORB        | 15:30–15:45        | "Golden hour" — fresh liquidity, less crowded |

**Pattern across sources**: naive breakout edge has eroded. Adding at least one
filter (RVOL, VWAP, daily trend) restores expectancy. Pure ORB win rate ~40%;
filtered ~50–55% with R-multiple ≥ 1.5.

## 3. Hypothesis: most profitable DAX ORB variant

A **dual-session, filter-heavy hybrid** — the Xetra-open leg as primary, the
US-open leg as a second uncorrelated bet on the same day.

### 3.1 Primary — Xetra ORB

- Range: **09:00–09:15 CET** (15-min).
- Entry: 1-min close beyond range + buffer = max(1 tick, 0.1 × range).
- Filters (all required):
  - RVOL: cumulative range-window volume > 1.2× 20-day average for the same window.
  - Trend: daily close > 20-EMA → longs only; below → shorts only.
  - Gap agreement: Xetra open vs prior 17:30 close; mismatch → skip.
  - Range sanity: skip if 15-min range > 0.6 × ATR(14, daily).
  - News blackout: no entry within ±30 min of ECB, German Ifo, CPI, NFP, FOMC.
- Stop: opposite side of range, capped at 1.0 × ATR(15-min).
- Targets: scale 50% at 1R, trail remainder with 2 × ATR(5-min) or chandelier.
- Time stop: flat at 17:25 CET.

### 3.2 Secondary — US-Open ORB

- Range: **15:30–15:35 CET** (5-min, Zarattini-style).
- Filter: ES/NQ direction at 15:30 must agree with the breakout side.
- Same risk envelope. One concurrent trade; primary stop-out releases for secondary.

### 3.3 Regime overlays

- No trades Friday afternoon (post-13:00).
- Half-size Mondays after weekend gaps > 0.7%.
- Skip first session of a new quarter / after Eurex maintenance gaps.

## 4. Enhancement ideas (backtest queue)

1. Adaptive range length keyed to Asian-session range.
2. Two-leg failure fade — opposite-side breakout after the first one retraces.
3. ES/NQ overnight slope filter (03:00→09:00 CET).
4. Bund / EURUSD divergence guard.
5. FDAX L2 cumulative-delta confirmation.
6. VSTOXX/HV regime gate (30–70th percentile).
7. Prior-day H/L proximity skip rule.
8. Volume-node entry (breakout bar > 1.5× prior 5-bar avg volume).
9. RVOL-scaled adaptive stop (tighter when RVOL high).
10. One half-R re-entry per side per session.
11. Calendar overlay: post-release fresh range on ECB/NFP days.
12. MDAX/SDAX leadership factor for long bias.

## 5. Bot implementation plan

- **Data**: 1-min FDAX (or DAX CFD) + daily; tick/L2 for advanced filters.
- **Calendar**: investpy / Trading Economics / FF API for blackouts.
- **Indicators**: session VWAP, ATR(14 daily) + ATR(14 5-min), 20-EMA daily,
  20-day RVOL by minute-of-day, prior-day H/L/C, gap %.
- **Engine**: event-driven backtester (vectorbt / backtrader / custom); walk-forward over ≥5 years, annual OOS.
- **Risk**: 0.25–0.5% per trade, daily loss cap 1.5%, 1 concurrent trade,
  3-loss-day kill-switch.
- **Robustness**: parameter sensitivity grid, Monte Carlo trade-order shuffle.

## 6. Open questions

- Data source: FDAX/FDXM intraday vs DAX CFD?
- Risk capital and per-trade R appetite?
- Always-in two-windows-per-day, or one-shot-per-day philosophy?
- Prototype primary leg first, then bolt on US-open leg?

## 7. Sources

- QuantifiedStrategies — ORB backtest overview.
- TradersMastermind — ORB rules & settings (2026).
- Trade That Swing — ORB strategy with strict rules.
- Open-Range-Breakout EA — DAX-specific commercial implementation.
- Forex Factory — Open Range Break Out DAX thread.
- Unger Academy — DAX First Hour Strategy; DAX Futures breakout systems 2025.
- WHSelfinvest — Jens Klatt DAX-ORB.
- FTMO — ORB and 15:30 US session ORB.
- Trader Tom — DAX/Dow open breakout.
- Zarattini, Barbon, Aziz — "A Profitable Day Trading Strategy For The U.S. Equity Market", SSRN 4729284.
- Sahm Capital / Benzinga — DAX ORB code & optimizations (Jan 2025).
- Deutsche Börse — Xetra hours and iXLM.
- MDPI — Price gaps and volatility, weekend gap closure.
