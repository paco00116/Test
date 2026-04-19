"""離線 demo：產生合成的台股價量資料寫入 DB，方便測試整條 pipeline。"""
from __future__ import annotations
import random
from datetime import date, timedelta

import numpy as np

from db import init_db, upsert_many

random.seed(42)
np.random.seed(42)

STOCKS = [
    ("2330", "台積電", 900),
    ("2317", "鴻海",   180),
    ("2454", "聯發科", 1200),
    ("2412", "中華電",  120),
    ("2881", "富邦金",   85),
    ("2303", "聯電",     55),
    ("3008", "大立光", 2500),
    ("2308", "台達電", 400),
    ("2603", "長榮",    150),
    ("2609", "陽明",     75),
    ("1301", "台塑",     75),
    ("1303", "南亞",     60),
    ("2002", "中鋼",     30),
    ("3711", "日月光",  150),
    ("2891", "中信金",   35),
]


def gen_series(start_price: float, n_days: int) -> list[dict]:
    """產生 n_days 天的 OHLCV，帶趨勢與雜訊。"""
    px = start_price
    rows = []
    d = date.today() - timedelta(days=n_days + 2)
    trend = np.random.choice([-1, 0, 1], p=[0.3, 0.4, 0.3])
    for i in range(n_days):
        d = d + timedelta(days=1)
        while d.weekday() >= 5:
            d = d + timedelta(days=1)
        # 偶爾切換趨勢
        if random.random() < 0.05:
            trend = np.random.choice([-1, 0, 1])
        drift = trend * 0.002
        shock = np.random.normal(0, 0.018)
        ret = drift + shock
        open_ = px * (1 + np.random.normal(0, 0.004))
        close = open_ * (1 + ret)
        high = max(open_, close) * (1 + abs(np.random.normal(0, 0.006)))
        low = min(open_, close) * (1 - abs(np.random.normal(0, 0.006)))
        vol = int(max(1_000_000, np.random.normal(5_000_000, 2_000_000)))
        rows.append({
            "date": d.isoformat(), "stock_id": None, "name": None,
            "open": round(open_, 2), "high": round(high, 2),
            "low": round(low, 2),   "close": round(close, 2),
            "volume": vol, "turnover": round(close * vol, 0),
            "trades": int(vol / 1000), "change": round(close - px, 2),
        })
        px = close
    return rows


def gen_inst(n_days: int) -> list[dict]:
    rows = []
    d0 = date.today() - timedelta(days=n_days + 2)
    d = d0
    trading_days = []
    for _ in range(n_days):
        d = d + timedelta(days=1)
        while d.weekday() >= 5:
            d = d + timedelta(days=1)
        trading_days.append(d)
    return trading_days


def seed(n_days: int = 240):
    init_db()
    all_prices = []
    inst_rows = []
    trading_days = gen_inst(n_days)
    for sid, name, p0 in STOCKS:
        series = gen_series(p0, n_days)
        for r in series:
            r["stock_id"] = sid
            r["name"] = name
        all_prices.extend(series)
        for d in trading_days:
            fnet = int(np.random.normal(0, 3_000_000))
            tnet = int(np.random.normal(0, 800_000))
            dnet = int(np.random.normal(0, 500_000))
            inst_rows.append({
                "date": d.isoformat(), "stock_id": sid,
                "foreign_buy": max(fnet, 0), "foreign_sell": max(-fnet, 0),
                "foreign_net": fnet,
                "trust_buy": max(tnet, 0), "trust_sell": max(-tnet, 0),
                "trust_net": tnet,
                "dealer_net": dnet,
                "total_net": fnet + tnet + dnet,
            })
    upsert_many("daily_price", all_prices)
    upsert_many("institutional", inst_rows)
    print(f"seeded {len(all_prices)} price rows, {len(inst_rows)} inst rows")
    print(f"stocks: {len(STOCKS)}, trading days: {n_days}")


if __name__ == "__main__":
    seed()
