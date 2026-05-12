"""
DAX Xetra ORB v1 backtester — one shot per day, flat 4% risk.

Spec (full version: docs/orb_dax_research.md §6):
  - Range 09:00-09:15 CET, min size 12 pts, sanity ≤ 0.6 × ATR(14, daily).
  - Trend filter (EMA20 daily) + gap filter (vs prev 17:30 close).
  - Entry: first 1-min close beyond range ± max(2 pts, 0.10 × range).
  - Stop: opposite range side, capped at 0.25 × ATR(14, daily).
  - 50% off at +1R, runner trailed by 2 × 0.10 × ATR(14, daily), BE after TP1.
  - Hard flat at 17:25 CET.
  - Slippage: 2 pts round-trip.

Input CSV: timestamp,open,high,low,close,volume (timestamp UTC, index in CET
after load). Produced by fetch_dax_data.py.
"""
import argparse
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytz

CET = pytz.timezone("Europe/Berlin")


@dataclass
class Config:
    range_start_min: int = 9 * 60          # 09:00 CET in minutes-of-day
    range_end_min: int = 9 * 60 + 15       # 09:15
    entry_cutoff_min: int = 10 * 60 + 30   # 10:30 — no new entries after this
    session_end_min: int = 17 * 60 + 25    # 17:25
    min_range_pts: float = 12.0
    buffer_pts: float = 2.0
    buffer_pct: float = 0.10
    ema_period: int = 20
    atr_period: int = 14
    range_sanity_atr_mult: float = 0.6
    # Default cap raised from 0.25 to 1.0 × ATR_d so the cap rarely binds —
    # stop sits at the opposite range side, which is the strategy's theoretical
    # invalidation level. The old 0.25 cap was putting stops *inside* the range
    # and getting nibbled on routine post-breakout retraces.
    stop_atr_d_mult: float = 1.0
    trail_atr_d_mult: float = 0.20         # 5-min ATR proxy × 2
    scale_out: bool = True                 # 50% off at +1R, runner trails
    risk_pct: float = 0.04
    point_value_eur: float = 1.0
    starting_equity: float = 50000.0
    slippage_pts_rt: float = 3.0
    # Ablations showed the strict daily-trend filter hurt PF on 2023-24 DAX
    # (PF 0.72 with vs 0.87 without). Default it OFF; can be re-enabled.
    use_trend: bool = False
    use_gap: bool = True
    use_range_sanity: bool = True
    skip_friday: bool = False


def load_1m(path):
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.set_index("timestamp").sort_index()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert(CET)
    df = df[~df.index.duplicated(keep="first")]
    return df


def daily_features(df1m, ema_p, atr_p):
    # Restrict to Xetra cash session (09:00-17:30 CET) so the daily close
    # used for the gap filter and EMA20 is the Xetra close, not a 22:00
    # extended-hours print on FDAX-style feeds (e.g. Dukascopy DEU.IDX).
    m = df1m.index.hour * 60 + df1m.index.minute
    xetra = df1m[(m >= 9 * 60) & (m < 17 * 60 + 30)]
    daily = xetra.resample("1D").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    ).dropna()
    daily["ema"] = daily["close"].ewm(span=ema_p, adjust=False).mean()
    tr = pd.concat(
        [
            daily["high"] - daily["low"],
            (daily["high"] - daily["close"].shift()).abs(),
            (daily["low"] - daily["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    daily["atr"] = tr.rolling(atr_p).mean()
    return daily


def run_backtest(df1m, cfg):
    daily = daily_features(df1m, cfg.ema_period, cfg.atr_period)
    daily_by_date = {ts.date(): row for ts, row in daily.iterrows()}

    minute_of_day = df1m.index.hour * 60 + df1m.index.minute
    df1m = df1m.assign(mod=minute_of_day.values, date=df1m.index.date)

    trades = []
    equity = cfg.starting_equity
    half_slip = cfg.slippage_pts_rt / 2

    days = sorted(set(df1m["date"]))
    prev_daily_date = None

    for i, date in enumerate(days):
        if cfg.skip_friday and date.weekday() == 4:
            continue

        # Most recent prior daily bar with valid features
        prev = None
        for d in reversed(days[:i]):
            r = daily_by_date.get(d)
            if r is not None and not pd.isna(r["ema"]) and not pd.isna(r["atr"]):
                prev = r
                break
        if prev is None:
            continue
        prev_close = prev["close"]
        prev_ema = prev["ema"]
        prev_atr = prev["atr"]

        day = df1m[df1m["date"] == date]
        in_range = day[(day["mod"] >= cfg.range_start_min) & (day["mod"] < cfg.range_end_min)]
        if len(in_range) < 10:
            continue

        rh = in_range["high"].max()
        rl = in_range["low"].min()
        rng = rh - rl
        if rng < cfg.min_range_pts:
            continue
        if cfg.use_range_sanity and rng > cfg.range_sanity_atr_mult * prev_atr:
            continue

        open_px = in_range["open"].iloc[0]
        gap = open_px - prev_close

        long_ok = True
        short_ok = True
        if cfg.use_trend:
            long_ok = long_ok and prev_close > prev_ema
            short_ok = short_ok and prev_close < prev_ema
        if cfg.use_gap:
            long_ok = long_ok and gap >= 0
            short_ok = short_ok and gap <= 0
        if not (long_ok or short_ok):
            continue

        buf = max(cfg.buffer_pts, cfg.buffer_pct * rng)
        long_trig = rh + buf
        short_trig = rl - buf

        post = day[(day["mod"] >= cfg.range_end_min) & (day["mod"] < cfg.entry_cutoff_min)]
        if post.empty:
            continue

        # Find first valid breakout
        entry_px = None
        entry_time = None
        side = None
        for ts, bar in post.iterrows():
            if long_ok and bar["close"] > long_trig:
                entry_px = bar["close"] + half_slip
                entry_time = ts
                side = "long"
                break
            if short_ok and bar["close"] < short_trig:
                entry_px = bar["close"] - half_slip
                entry_time = ts
                side = "short"
                break
        if entry_px is None:
            continue

        # Stop placement
        if side == "long":
            range_stop_dist = entry_px - rl
        else:
            range_stop_dist = rh - entry_px
        stop_dist = min(range_stop_dist, cfg.stop_atr_d_mult * prev_atr)
        if stop_dist <= 0:
            continue
        tp1_dist = stop_dist
        trail_offset = cfg.trail_atr_d_mult * prev_atr

        # Position size
        risk_eur = equity * cfg.risk_pct
        size = risk_eur / (stop_dist * cfg.point_value_eur)

        if side == "long":
            stop_px = entry_px - stop_dist
            tp1_px = entry_px + tp1_dist
        else:
            stop_px = entry_px + stop_dist
            tp1_px = entry_px - tp1_dist

        # Walk forward through the day. runner_stop is always defined and
        # starts at the initial stop. If --scale-out, the trail only kicks in
        # after the half-close at TP1; otherwise the full position trails from
        # the very first bar.
        sim = day[(day.index > entry_time) & (day["mod"] < cfg.session_end_min)]
        half_done = False
        runner_stop = stop_px
        exit_legs = []
        stopped_out = False
        for ts, bar in sim.iterrows():
            if side == "long":
                if bar["low"] <= runner_stop:
                    frac = 0.5 if (cfg.scale_out and half_done) else 1.0
                    exit_legs.append((runner_stop, frac))
                    stopped_out = True
                    break
                if cfg.scale_out and not half_done and bar["high"] >= tp1_px:
                    exit_legs.append((tp1_px, 0.5))
                    half_done = True
                    runner_stop = entry_px
                if (not cfg.scale_out) or half_done:
                    new_trail = bar["high"] - trail_offset
                    if new_trail > runner_stop:
                        runner_stop = new_trail
            else:
                if bar["high"] >= runner_stop:
                    frac = 0.5 if (cfg.scale_out and half_done) else 1.0
                    exit_legs.append((runner_stop, frac))
                    stopped_out = True
                    break
                if cfg.scale_out and not half_done and bar["low"] <= tp1_px:
                    exit_legs.append((tp1_px, 0.5))
                    half_done = True
                    runner_stop = entry_px
                if (not cfg.scale_out) or half_done:
                    new_trail = bar["low"] + trail_offset
                    if new_trail < runner_stop:
                        runner_stop = new_trail

        if not stopped_out:
            if len(sim) == 0:
                continue
            last_close = sim.iloc[-1]["close"]
            frac = 0.5 if (cfg.scale_out and half_done) else 1.0
            exit_legs.append((last_close, frac))

        # PnL with exit slippage
        pnl_pts = 0.0
        for exit_px, frac in exit_legs:
            if side == "long":
                leg = (exit_px - half_slip) - entry_px
            else:
                leg = entry_px - (exit_px + half_slip)
            pnl_pts += leg * frac
        pnl_eur = pnl_pts * size * cfg.point_value_eur
        equity += pnl_eur

        trades.append(
            {
                "date": date,
                "side": side,
                "entry_time": entry_time,
                "entry_px": round(entry_px, 2),
                "stop_dist": round(stop_dist, 2),
                "size": round(size, 2),
                "range": round(rng, 2),
                "half_done": half_done,
                "stopped_out": stopped_out,
                "pnl_pts": round(pnl_pts, 2),
                "pnl_eur": round(pnl_eur, 2),
                "equity_after": round(equity, 2),
            }
        )

    return pd.DataFrame(trades)


def metrics(trades, start_eq):
    if trades.empty:
        return {"trades": 0}
    eq = np.concatenate([[start_eq], trades["equity_after"].to_numpy()])
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak
    days = (trades["date"].iloc[-1] - trades["date"].iloc[0]).days
    years = max(days / 365.25, 1 / 365.25)
    cagr = (eq[-1] / start_eq) ** (1 / years) - 1
    wins = trades[trades["pnl_eur"] > 0]
    losses = trades[trades["pnl_eur"] <= 0]
    win_rate = len(wins) / len(trades)
    gross_w = wins["pnl_eur"].sum()
    gross_l = -losses["pnl_eur"].sum()
    pf = gross_w / gross_l if gross_l > 0 else float("inf")
    rets = trades["pnl_eur"] / start_eq
    sharpe = rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else 0.0
    return {
        "trades": int(len(trades)),
        "win_rate": round(win_rate, 4),
        "profit_factor": round(pf, 3),
        "avg_win_eur": round(wins["pnl_eur"].mean() if len(wins) else 0, 2),
        "avg_loss_eur": round(losses["pnl_eur"].mean() if len(losses) else 0, 2),
        "total_pnl_eur": round(trades["pnl_eur"].sum(), 2),
        "final_equity": round(eq[-1], 2),
        "cagr": round(cagr, 4),
        "max_dd": round(dd.min(), 4),
        "sharpe_trade_annualised": round(sharpe, 3),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--equity", type=float, default=50000.0)
    ap.add_argument("--risk", type=float, default=0.04)
    ap.add_argument("--point-value", type=float, default=1.0,
                    help="Broker EUR-per-point per 1 contract/lot.")
    ap.add_argument("--slippage", type=float, default=3.0,
                    help="Round-trip slippage in points.")
    ap.add_argument("--trend", action="store_true",
                    help="Enable the daily-trend filter (off by default).")
    ap.add_argument("--no-gap", action="store_true")
    ap.add_argument("--no-range-sanity", action="store_true")
    ap.add_argument("--skip-friday", action="store_true")
    ap.add_argument("--entry-cutoff", default="10:30",
                    help="Latest entry time HH:MM CET. Default 10:30.")
    ap.add_argument("--no-scale-out", action="store_true",
                    help="Disable 50% at +1R; trail full position from entry.")
    ap.add_argument("--stop-cap", type=float, default=1.0,
                    help="Cap stop distance at this × ATR_daily. Default 1.0 "
                         "(effectively no cap; opposite range side is used).")
    ap.add_argument("--out-trades", default="trades.csv")
    args = ap.parse_args()

    h, m = args.entry_cutoff.split(":")
    cutoff = int(h) * 60 + int(m)

    cfg = Config(
        risk_pct=args.risk,
        starting_equity=args.equity,
        point_value_eur=args.point_value,
        slippage_pts_rt=args.slippage,
        use_trend=args.trend,
        use_gap=not args.no_gap,
        use_range_sanity=not args.no_range_sanity,
        skip_friday=args.skip_friday,
        entry_cutoff_min=cutoff,
        scale_out=not args.no_scale_out,
        stop_atr_d_mult=args.stop_cap,
    )

    df = load_1m(args.data)
    trades = run_backtest(df, cfg)
    m = metrics(trades, cfg.starting_equity)

    print("=== Xetra ORB v1 backtest ===")
    for k, v in m.items():
        print(f"  {k:>25}: {v}")

    trades.to_csv(args.out_trades, index=False)
    print(f"\nTrade log: {args.out_trades}")


if __name__ == "__main__":
    main()
