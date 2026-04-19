"""每日收盤後，依據歷史最高勝率條件預測明日當沖候選股。

輸出：每檔候選的方向、建議進場價、出場價、停損、信心度（歷史勝率）。
"""
from __future__ import annotations
import pandas as pd

from config import FEE_RATE, FEE_DISCOUNT, TAX_RATE_DAYTRADE
from db import connect, upsert_many
from features import build_features
from backtest import CONDITIONS, _base_filter


def _eval_expr(df: pd.DataFrame, condition_name: str) -> pd.Series:
    """依 conditions 表的 name 欄（例如 'long:rsi_oversold+vol_surge'）重建 mask。"""
    _, combo = condition_name.split(":", 1)
    keys = combo.split("+")
    mask = pd.Series(True, index=df.index)
    for k in keys:
        if k not in CONDITIONS:
            return pd.Series(False, index=df.index)
        mask &= CONDITIONS[k][1](df)
    return mask


def load_top_conditions(limit: int = 30) -> pd.DataFrame:
    with connect() as c:
        df = pd.read_sql(
            "SELECT * FROM conditions ORDER BY win_rate DESC, sample_size DESC LIMIT ?",
            c, params=[limit],
        )
    return df


def predict_next_day(min_win_rate: float = 0.55) -> pd.DataFrame:
    """取最新交易日資料，套用 top conditions，產生明日當沖候選。"""
    df = build_features()
    df = _base_filter(df)
    if df.empty:
        return df

    latest_date = df["date"].max()
    today_df = df[df["date"] == latest_date].copy()

    conds = load_top_conditions()
    if conds.empty:
        return pd.DataFrame()
    conds = conds[conds["win_rate"] >= min_win_rate]

    picks: list[dict] = []
    for _, c in conds.iterrows():
        mask = _eval_expr(today_df, c["name"])
        hits = today_df[mask]
        if hits.empty:
            continue
        for _, row in hits.iterrows():
            direction = c["direction"]
            entry = float(row["close"])  # 以收盤價估算隔日開盤
            expected_ret = float(c["avg_return"])
            if direction == "long":
                exit_price = entry * (1 + expected_ret + _roundtrip_cost())
                stop = entry * (1 - max(0.02, 2 * row.get("atr_14", 0) / entry))
            else:
                exit_price = entry * (1 - expected_ret - _roundtrip_cost())
                stop = entry * (1 + max(0.02, 2 * row.get("atr_14", 0) / entry))
            picks.append({
                "date": latest_date.date().isoformat() if hasattr(latest_date, "date") else str(latest_date),
                "stock_id": row["stock_id"],
                "direction": direction,
                "entry_price": round(entry, 2),
                "exit_price": round(exit_price, 2),
                "stop_loss": round(stop, 2),
                "confidence": float(c["win_rate"]),
                "condition_id": int(c["id"]),
                "expected_return": expected_ret,
            })

    if not picks:
        return pd.DataFrame()

    out = pd.DataFrame(picks)
    # 同股同方向取信心度最高者
    out = out.sort_values("confidence", ascending=False).drop_duplicates(["stock_id", "direction"])
    upsert_many("predictions", out.to_dict("records"))
    return out.reset_index(drop=True)


def _roundtrip_cost() -> float:
    return 2 * FEE_RATE * FEE_DISCOUNT + TAX_RATE_DAYTRADE
