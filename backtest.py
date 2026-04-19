"""回測引擎：大量條件搜尋、找出最高勝率組合。

當沖策略：
  - 多方：當日 open 進場，當日 close 出場（或觸發停損/停利）
  - 空方：當日 open 放空，當日 close 回補
  - 成本：買賣手續費 0.1425% + 賣出證交稅 0.15%（當沖減半）

條件搜尋：
  使用預先定義的單一條件集合，做笛卡兒乘積（最多 K 個條件組合），
  回測每組合的勝率與平均報酬，保留樣本數 >= MIN_SAMPLES 的結果。
"""
from __future__ import annotations
import itertools
import json
from datetime import datetime

import numpy as np
import pandas as pd

from config import FEE_RATE, FEE_DISCOUNT, TAX_RATE_DAYTRADE, MIN_VOLUME, MIN_PRICE, MAX_PRICE
from db import connect, upsert_many
from features import build_features


MIN_SAMPLES = 30
TOP_N = 50


# ---------- 交易成本 ----------

def daytrade_net_return(entry: float, exit_: float, direction: str = "long") -> float:
    """回傳當沖淨報酬率（已扣手續費與交易稅）。"""
    fee = FEE_RATE * FEE_DISCOUNT
    if direction == "long":
        gross = (exit_ - entry) / entry
    else:
        gross = (entry - exit_) / entry
    # 買賣雙邊手續費 + 賣方課證交稅（當沖減半）
    cost = 2 * fee + TAX_RATE_DAYTRADE
    return gross - cost


# ---------- 條件集合 ----------

CONDITIONS = {
    # name: (expression string, mask function)
    "rsi_oversold":      ("rsi_14 < 30",         lambda df: df["rsi_14"] < 30),
    "rsi_overbought":    ("rsi_14 > 70",         lambda df: df["rsi_14"] > 70),
    "macd_golden":       ("macd_hist > 0",       lambda df: df["macd_hist"] > 0),
    "macd_dead":         ("macd_hist < 0",       lambda df: df["macd_hist"] < 0),
    "kd_golden":         ("kd_k > kd_d",         lambda df: df["kd_k"] > df["kd_d"]),
    "kd_dead":           ("kd_k < kd_d",         lambda df: df["kd_k"] < df["kd_d"]),
    "above_ma20":        ("close > price_ma20", lambda df: df["above_ma20"] == 1),
    "below_ma20":        ("close < price_ma20", lambda df: df["above_ma20"] == 0),
    "vol_surge":         ("vol_ratio > 2",       lambda df: df["vol_ratio"] > 2),
    "vol_dry":           ("vol_ratio < 0.5",     lambda df: df["vol_ratio"] < 0.5),
    "strong_up":         ("ret_1d > 0.03",       lambda df: df["ret_1d"] > 0.03),
    "strong_down":       ("ret_1d < -0.03",      lambda df: df["ret_1d"] < -0.03),
    "bb_near_upper":     ("bb_pos > 0.9",        lambda df: df["bb_pos"] > 0.9),
    "bb_near_lower":     ("bb_pos < 0.1",        lambda df: df["bb_pos"] < 0.1),
    "foreign_buy_5d":    ("foreign_net_5d > 0",  lambda df: df["foreign_net_5d"] > 0),
    "foreign_sell_5d":   ("foreign_net_5d < 0",  lambda df: df["foreign_net_5d"] < 0),
    "trust_buy_5d":      ("trust_net_5d > 0",    lambda df: df["trust_net_5d"] > 0),
    "long_body":         ("body > 0.02",         lambda df: df["body"] > 0.02),
    "short_body":        ("body < -0.02",        lambda df: df["body"] < -0.02),
    "gap_up":            ("gap > 0.01",          lambda df: df["gap"] > 0.01),
    "gap_down":          ("gap < -0.01",         lambda df: df["gap"] < -0.01),
}


def _base_filter(df: pd.DataFrame) -> pd.DataFrame:
    return df[
        (df["close"].between(MIN_PRICE, MAX_PRICE))
        & (df["volume"] >= MIN_VOLUME)
        & df["next_open"].notna()
    ].copy()


def _trade_return(df: pd.DataFrame, direction: str) -> pd.Series:
    """以隔日 open 進場、隔日 close 出場的當沖淨報酬。"""
    entry = df["next_open"]
    exit_ = df["next_close"]
    fee = FEE_RATE * FEE_DISCOUNT
    cost = 2 * fee + TAX_RATE_DAYTRADE
    if direction == "long":
        gross = (exit_ - entry) / entry
    else:
        gross = (entry - exit_) / entry
    return gross - cost


def evaluate_condition(df: pd.DataFrame, mask: pd.Series, direction: str):
    sub = df[mask]
    if len(sub) < MIN_SAMPLES:
        return None
    rets = _trade_return(sub, direction).dropna()
    if rets.empty:
        return None
    wins = (rets > 0).sum()
    return {
        "sample_size": int(len(rets)),
        "wins": int(wins),
        "win_rate": float(wins / len(rets)),
        "avg_return": float(rets.mean()),
        "sharpe": float(rets.mean() / rets.std()) if rets.std() > 0 else 0.0,
    }


def search_conditions(combo_size: int = 2) -> pd.DataFrame:
    """笛卡兒乘積 combo_size 個條件，跑多空兩方向。"""
    df = build_features()
    df = _base_filter(df)
    if df.empty:
        return pd.DataFrame()

    keys = list(CONDITIONS.keys())
    results = []
    for combo in itertools.combinations(keys, combo_size):
        mask = pd.Series(True, index=df.index)
        for k in combo:
            mask &= CONDITIONS[k][1](df)
        if mask.sum() < MIN_SAMPLES:
            continue
        for direction in ("long", "short"):
            r = evaluate_condition(df, mask, direction)
            if r is None:
                continue
            results.append({
                "name": f"{direction}:{'+'.join(combo)}",
                "expression": " AND ".join(CONDITIONS[k][0] for k in combo),
                "direction": direction,
                **r,
            })
    res_df = pd.DataFrame(results)
    if res_df.empty:
        return res_df
    res_df = res_df.sort_values(["win_rate", "avg_return"], ascending=False).reset_index(drop=True)
    return res_df


def save_top_conditions(res_df: pd.DataFrame, top_n: int = TOP_N):
    if res_df.empty:
        return 0
    top = res_df.head(top_n).copy()
    top["updated_at"] = datetime.now().isoformat(timespec="seconds")
    rows = top.to_dict("records")
    # 用 INSERT OR REPLACE，需要先清掉既有 id
    with connect() as c:
        c.execute("DELETE FROM conditions")
        c.executemany(
            """INSERT INTO conditions
               (name, expression, direction, sample_size, wins, win_rate, avg_return, sharpe, updated_at)
               VALUES (:name,:expression,:direction,:sample_size,:wins,:win_rate,:avg_return,:sharpe,:updated_at)""",
            rows,
        )
    return len(rows)


def run_full_search(combo_sizes=(1, 2)) -> pd.DataFrame:
    all_res = []
    for k in combo_sizes:
        r = search_conditions(k)
        if not r.empty:
            all_res.append(r)
    if not all_res:
        return pd.DataFrame()
    combined = pd.concat(all_res, ignore_index=True)
    combined = combined.sort_values(["win_rate", "sample_size"], ascending=False).reset_index(drop=True)
    save_top_conditions(combined)
    return combined
