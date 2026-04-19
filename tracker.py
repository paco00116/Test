"""績效追蹤：比對昨日預測 vs 今日真實開高低收，計算勝率與淨損益。"""
from __future__ import annotations
import pandas as pd
from datetime import date

from config import FEE_RATE, FEE_DISCOUNT, TAX_RATE_DAYTRADE
from db import connect


COST = 2 * FEE_RATE * FEE_DISCOUNT + TAX_RATE_DAYTRADE


def _load_predictions_for(d: str) -> pd.DataFrame:
    with connect() as c:
        return pd.read_sql("SELECT * FROM predictions WHERE date = ?", c, params=[d])


def _load_actual(stock_ids: list[str], d: str) -> pd.DataFrame:
    if not stock_ids:
        return pd.DataFrame()
    placeholders = ",".join("?" for _ in stock_ids)
    with connect() as c:
        return pd.read_sql(
            f"SELECT date, stock_id, open, high, low, close FROM daily_price "
            f"WHERE date = ? AND stock_id IN ({placeholders})",
            c, params=[d, *stock_ids],
        )


def settle_day(pred_date: str, actual_date: str) -> dict:
    """用 pred_date 產生的預測，結算 actual_date（隔一交易日）真實績效。"""
    preds = _load_predictions_for(pred_date)
    if preds.empty:
        return {"actual_date": actual_date, "n_trades": 0}

    actual = _load_actual(preds["stock_id"].tolist(), actual_date)
    if actual.empty:
        return {"actual_date": actual_date, "n_trades": 0}

    merged = preds.merge(actual, on="stock_id", suffixes=("_pred", ""))
    if merged.empty:
        return {"actual_date": actual_date, "n_trades": 0}

    # 以隔日 open 進場、close 出場
    long_mask = merged["direction"] == "long"
    merged["gross_return"] = 0.0
    merged.loc[long_mask, "gross_return"] = (merged["close"] - merged["open"]) / merged["open"]
    merged.loc[~long_mask, "gross_return"] = (merged["open"] - merged["close"]) / merged["open"]
    merged["net_return"] = merged["gross_return"] - COST
    merged["is_win"] = (merged["net_return"] > 0).astype(int)

    logs = [{
        "date": actual_date,
        "stock_id": r["stock_id"],
        "direction": r["direction"],
        "entry": float(r["open"]),
        "exit": float(r["close"]),
        "gross_return": float(r["gross_return"]),
        "net_return": float(r["net_return"]),
        "condition_id": int(r["condition_id"]) if pd.notna(r["condition_id"]) else None,
        "is_win": int(r["is_win"]),
        "mode": "live",
    } for _, r in merged.iterrows()]

    with connect() as c:
        c.executemany(
            """INSERT INTO trade_log
               (date, stock_id, direction, entry, exit, gross_return, net_return,
                condition_id, is_win, mode)
               VALUES (:date,:stock_id,:direction,:entry,:exit,:gross_return,:net_return,
                       :condition_id,:is_win,:mode)""",
            logs,
        )

    n = len(merged)
    wins = int(merged["is_win"].sum())
    gross = float(merged["gross_return"].sum())
    net = float(merged["net_return"].sum())

    with connect() as c:
        prev = c.execute(
            "SELECT cumulative_pnl FROM daily_performance ORDER BY date DESC LIMIT 1"
        ).fetchone()
        prev_cum = prev["cumulative_pnl"] if prev else 0.0
        c.execute(
            """INSERT OR REPLACE INTO daily_performance
               (date, n_trades, wins, win_rate, gross_pnl, net_pnl, cumulative_pnl)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (actual_date, n, wins, wins / n if n else 0.0, gross, net, prev_cum + net),
        )

    return {
        "actual_date": actual_date,
        "n_trades": n,
        "wins": wins,
        "win_rate": wins / n if n else 0.0,
        "gross_pnl": gross,
        "net_pnl": net,
    }


def performance_summary() -> pd.DataFrame:
    with connect() as c:
        return pd.read_sql(
            "SELECT * FROM daily_performance ORDER BY date", c, parse_dates=["date"]
        )
