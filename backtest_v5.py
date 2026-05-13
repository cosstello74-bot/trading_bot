"""
DAX 'Upgraded' ORB v5 — daily + 4H trend alignment, pullback-confirmation entry.

Mechanically encodes the rules described in the trader video:
1. Range: 09:00-09:15 CET (15-min opening range), wick-to-wick.
2. Direction bias: previous-day candle AND last-completed 4H candle (before
   today's 09:00 CET) must agree on direction. Both bullish => longs only;
   both bearish => shorts only; mismatch => skip the day.
3. Entry structure (5-min candles after 09:15):
   a. wait_breakout: at least one 5-min close beyond the range.
   b. wait_pullback: at least one bearish 5-min (longs) / bullish (shorts).
      The pullback's high (longs) / low (shorts) becomes the trigger level.
   c. wait_continuation: a 5-min candle whose CLOSE breaks the pullback's
      trigger level becomes the "qualifying candle".
4. Entry: a stop order at the qualifying candle's high (longs) / low (shorts).
   The order is filled by a subsequent 1-min bar breaking that level.
5. Stop loss: low of the qualifying candle (longs) / high (shorts).
6. Target: fixed 1:1 R-multiple (configurable via --target-r).
7. Optional break-even stop after 0.5R favourable (configurable / disabled).
8. Hard time stop: flat at 17:25 CET.

NOT encoded: the subjective "clean zones" / left-side-mess filter. Without a
proxy for it, the strategy will take some trades the trader would skip by eye.

Usage:
    python backtest_v5.py --data data\\dax_1m.csv
"""
import argparse
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytz

CET = pytz.timezone("Europe/Berlin")


@dataclass
class Config:
    range_start_min: int = 9 * 60
    range_end_min: int = 9 * 60 + 15
    entry_cutoff_min: int = 13 * 60       # latest time to FIND a qualifying setup
    session_end_min: int = 17 * 60 + 25
    min_range_pts: float = 8.0
    risk_pct: float = 0.04
    point_value_eur: float = 1.0
    starting_equity: float = 50000.0
    slippage_pts_rt: float = 3.0
    target_r: float = 1.0
    use_be_stop: bool = True
    be_trigger_r: float = 0.5


def load_1m(path):
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.set_index("timestamp").sort_index()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert(CET)
    return df[~df.index.duplicated(keep="first")]


def xetra_daily(df1m):
    m = df1m.index.hour * 60 + df1m.index.minute
    xetra = df1m[(m >= 9 * 60) & (m < 17 * 60 + 30)]
    daily = xetra.resample("1D").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    ).dropna()
    return daily


def resample_5m(df1m):
    return df1m.resample("5min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    ).dropna()


def resample_4h(df1m):
    return df1m.resample("4h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    ).dropna()


def run_backtest(df1m, cfg):
    daily = xetra_daily(df1m)
    f5 = resample_5m(df1m)
    f4 = resample_4h(df1m)

    daily_dir = (daily["close"] > daily["open"])
    daily_by_date = {ts.date(): bool(b) for ts, b in daily_dir.items()}

    f4_dir = (f4["close"] > f4["open"])

    f5 = f5.assign(
        mod=f5.index.hour * 60 + f5.index.minute,
        date=f5.index.date,
    )
    df1m_idx = df1m.assign(
        mod=df1m.index.hour * 60 + df1m.index.minute,
        date=df1m.index.date,
    )

    days = sorted(set(df1m_idx["date"]))
    trades = []
    equity = cfg.starting_equity
    half_slip = cfg.slippage_pts_rt / 2

    for i, date in enumerate(days):
        prev_date = None
        for d in reversed(days[:i]):
            if d in daily_by_date:
                prev_date = d
                break
        if prev_date is None:
            continue
        daily_bullish = daily_by_date[prev_date]

        today_0900 = pd.Timestamp(str(date)).tz_localize(CET) + pd.Timedelta(hours=9)
        completed_4h = f4_dir[f4_dir.index + pd.Timedelta(hours=4) <= today_0900]
        if len(completed_4h) == 0:
            continue
        h4_bullish = bool(completed_4h.iloc[-1])

        if daily_bullish and h4_bullish:
            bias = "long"
        elif (not daily_bullish) and (not h4_bullish):
            bias = "short"
        else:
            continue

        day1m = df1m_idx[df1m_idx["date"] == date]
        day5m = f5[f5["date"] == date]
        if day1m.empty or day5m.empty:
            continue

        in_range = day1m[(day1m["mod"] >= cfg.range_start_min) & (day1m["mod"] < cfg.range_end_min)]
        if len(in_range) < 10:
            continue
        rh = in_range["high"].max()
        rl = in_range["low"].min()
        rng = rh - rl
        if rng < cfg.min_range_pts:
            continue

        # State machine on 5-min bars after the range closes.
        post5m = day5m[(day5m["mod"] >= cfg.range_end_min) & (day5m["mod"] < cfg.entry_cutoff_min)]
        if post5m.empty:
            continue

        state = "wait_breakout"
        pullback_level = None  # high for longs, low for shorts
        qualifying = None

        for ts, bar in post5m.iterrows():
            bullish_bar = bar["close"] > bar["open"]
            bearish_bar = bar["close"] < bar["open"]

            if bias == "long":
                if state == "wait_breakout":
                    if bar["close"] > rh:
                        state = "wait_pullback"
                elif state == "wait_pullback":
                    if bearish_bar:
                        pullback_level = bar["high"]
                        state = "wait_continuation"
                elif state == "wait_continuation":
                    if bearish_bar:
                        pullback_level = max(pullback_level, bar["high"])
                    elif bullish_bar and bar["close"] > pullback_level:
                        qualifying = (ts, bar)
                        break
            else:
                if state == "wait_breakout":
                    if bar["close"] < rl:
                        state = "wait_pullback"
                elif state == "wait_pullback":
                    if bullish_bar:
                        pullback_level = bar["low"]
                        state = "wait_continuation"
                elif state == "wait_continuation":
                    if bullish_bar:
                        pullback_level = min(pullback_level, bar["low"])
                    elif bearish_bar and bar["close"] < pullback_level:
                        qualifying = (ts, bar)
                        break

        if qualifying is None:
            continue

        q_ts, q_bar = qualifying
        if bias == "long":
            entry_stop = q_bar["high"]
            stop_loss_level = q_bar["low"]
        else:
            entry_stop = q_bar["low"]
            stop_loss_level = q_bar["high"]

        # Entry trigger: 1-min bar break of entry_stop, starting AFTER the
        # qualifying 5-min bar has closed.
        q_close_time = q_ts + pd.Timedelta(minutes=5)
        post1m = day1m[(day1m.index >= q_close_time) & (day1m["mod"] < cfg.session_end_min)]
        if post1m.empty:
            continue

        entry_px = None
        entry_time = None
        for ts, bar in post1m.iterrows():
            if bias == "long" and bar["high"] >= entry_stop:
                entry_px = entry_stop + half_slip
                entry_time = ts
                break
            elif bias == "short" and bar["low"] <= entry_stop:
                entry_px = entry_stop - half_slip
                entry_time = ts
                break
        if entry_px is None:
            continue

        if bias == "long":
            stop_dist = entry_px - stop_loss_level
            stop_px = stop_loss_level
            target_px = entry_px + cfg.target_r * stop_dist
        else:
            stop_dist = stop_loss_level - entry_px
            stop_px = stop_loss_level
            target_px = entry_px - cfg.target_r * stop_dist
        if stop_dist <= 0:
            continue

        risk_eur = equity * cfg.risk_pct
        size = risk_eur / (stop_dist * cfg.point_value_eur)

        sim = day1m[(day1m.index > entry_time) & (day1m["mod"] < cfg.session_end_min)]
        moved_to_be = False
        exit_px = None
        exit_reason = "eod"

        for ts, bar in sim.iterrows():
            if bias == "long":
                if bar["low"] <= stop_px:
                    exit_px = stop_px
                    exit_reason = "be" if moved_to_be else "stop"
                    break
                if bar["high"] >= target_px:
                    exit_px = target_px
                    exit_reason = "target"
                    break
                if cfg.use_be_stop and not moved_to_be:
                    if bar["high"] >= entry_px + cfg.be_trigger_r * stop_dist:
                        stop_px = entry_px
                        moved_to_be = True
            else:
                if bar["high"] >= stop_px:
                    exit_px = stop_px
                    exit_reason = "be" if moved_to_be else "stop"
                    break
                if bar["low"] <= target_px:
                    exit_px = target_px
                    exit_reason = "target"
                    break
                if cfg.use_be_stop and not moved_to_be:
                    if bar["low"] <= entry_px - cfg.be_trigger_r * stop_dist:
                        stop_px = entry_px
                        moved_to_be = True

        if exit_px is None:
            if len(sim) == 0:
                continue
            exit_px = sim.iloc[-1]["close"]
            exit_reason = "eod"

        if bias == "long":
            pnl_pts = (exit_px - half_slip) - entry_px
        else:
            pnl_pts = entry_px - (exit_px + half_slip)
        pnl_eur = pnl_pts * size * cfg.point_value_eur
        equity += pnl_eur

        trades.append({
            "date": date,
            "side": bias,
            "entry_time": entry_time,
            "entry_px": round(entry_px, 2),
            "stop_dist": round(stop_dist, 2),
            "size": round(size, 2),
            "range": round(rng, 2),
            "exit_reason": exit_reason,
            "pnl_pts": round(pnl_pts, 2),
            "pnl_eur": round(pnl_eur, 2),
            "equity_after": round(equity, 2),
        })

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
    gw = wins["pnl_eur"].sum()
    gl = -losses["pnl_eur"].sum()
    pf = gw / gl if gl > 0 else float("inf")
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
    ap.add_argument("--point-value", type=float, default=1.0)
    ap.add_argument("--slippage", type=float, default=3.0)
    ap.add_argument("--target-r", type=float, default=1.0)
    ap.add_argument("--no-be-stop", action="store_true",
                    help="Disable break-even stop move after 0.5R favourable.")
    ap.add_argument("--be-trigger-r", type=float, default=0.5)
    ap.add_argument("--entry-cutoff", default="13:00")
    ap.add_argument("--min-range", type=float, default=8.0)
    ap.add_argument("--out-trades", default="trades_v5.csv")
    args = ap.parse_args()

    def hhmm(s):
        h, m = s.split(":")
        return int(h) * 60 + int(m)

    cfg = Config(
        risk_pct=args.risk,
        starting_equity=args.equity,
        point_value_eur=args.point_value,
        slippage_pts_rt=args.slippage,
        target_r=args.target_r,
        use_be_stop=not args.no_be_stop,
        be_trigger_r=args.be_trigger_r,
        entry_cutoff_min=hhmm(args.entry_cutoff),
        min_range_pts=args.min_range,
    )

    df = load_1m(args.data)
    trades = run_backtest(df, cfg)
    m = metrics(trades, cfg.starting_equity)

    print("=== Xetra ORB v5 (upgraded) backtest ===")
    for k, v in m.items():
        print(f"  {k:>25}: {v}")

    trades.to_csv(args.out_trades, index=False)
    print(f"\nTrade log: {args.out_trades}")


if __name__ == "__main__":
    main()
