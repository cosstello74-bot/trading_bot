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

## 6. Locked v1 spec (CFD, one-shot, flat 4%)

Decisions taken:

- Instrument: **DAX CFD** (broker-execution; e.g. IG / CMC DE40).
- Window: **Xetra leg only** (09:00–09:15 CET).
- Per-trade risk: **flat 4% of equity**.
- Trade frequency: **one shot per day**, first qualified breakout only, no re-entry.
- Data source: **Dukascopy DEU.IDX 1-min** (free, ~20yr history). Volume column
  is broker-quote volume and not used for RVOL in v1.

### Rules

- Range: 1-min bars from 09:00:00 inclusive to 09:15:00 exclusive (CET).
- Min range size: ≥ 12 pts. Skip if smaller.
- Range sanity: skip if range > 0.6 × ATR(14, daily).
- Trend filter: prev-day close > EMA20(daily) ⇒ longs only; below ⇒ shorts only.
- Gap filter: today's 09:00 open vs prev 17:30 close must agree with trade direction.
- Buffer above/below range: max(2 pts, 0.10 × range).
- Entry: first 1-min bar that **closes** beyond range ± buffer, between 09:15
  and session end. Take first valid side only.
- Stop: opposite side of range, capped at 0.25 × ATR(14, daily) as a 15-min
  ATR proxy in v1. To be replaced with true ATR(15-min) in v2.
- Targets: 50% off at +1R, runner trailed by 2 × 0.10 × ATR(14, daily) as a
  5-min ATR proxy in v1; move runner stop to break-even after first half hits.
- Hard time stop: flat at 17:25 CET.
- Slippage model: **3 pts round-trip** per trade (default; conservative for
  09:00 entries on most retail DAX CFD brokers).

### Daily-feature window

Daily EMA20, ATR14 and the gap-filter `prev_close` are computed from the
**Xetra cash session only (09:00-17:30 CET)**. Pre-Xetra and post-Xetra
prints present on FDAX-style feeds (e.g. Dukascopy DEUIDXEUR, which trades
~08:00-22:00 CET) are excluded so the gap signal is Xetra-to-Xetra, not
contaminated by overnight FDAX drift.

### Risk & sizing

- Equity-fraction sizing: contracts = (equity × 0.04) / (stop_dist × point_value).
- Point value defaults to €1/pt; user must set their broker's actual point
  value via CLI flag.

### Day-of-week / regime

- Friday block: configurable (default off; can be re-evaluated after backtest).
- Half-size after weekend gap > 0.7%: deferred to v2.

### Known v1 simplifications (to fix in v2)

- ATR(15-min) and ATR(5-min) approximated as fixed fractions of daily ATR
  (0.25 and 0.10 respectively).
- RVOL filter omitted (CFD volume unreliable).
- News-blackout filter omitted (no macro calendar wired up).
- Intra-bar stop/TP ambiguity resolved pessimistically: if both stop and TP1
  prices fall inside the same bar's range, stop is assumed hit first.

### Backtest data plan

- Period: rolling 5+ years (e.g. 2020-01-01 to today) for in-sample, then
  add 2015–2019 as out-of-sample once v1 stabilises.
- Walk-forward: annual OOS slices once initial baseline numbers exist.

### What we expect to see (rough sanity targets, not promises)

- Trades: ~100–180 per year (after filters).
- Win rate: 45–55%.
- Profit factor: 1.3–1.8.
- Max drawdown at 4% flat risk: 20–35% within any given year.
- Sharpe (per-trade): 1.0–1.8.
- Numbers materially outside these bands are a red flag — overfit or bug.

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
