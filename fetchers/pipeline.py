"""資料抓取主流程：整合上市/上櫃每日資料寫入 DB。"""
from __future__ import annotations
import logging
from datetime import date, timedelta

from db import upsert_many, init_db, connect
from .twse import fetch_twse_daily, fetch_twse_institutional
from .tpex import fetch_tpex_daily, fetch_tpex_institutional

log = logging.getLogger(__name__)


def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def fetch_one_day(d: date) -> dict:
    """抓取單日所有資料。回傳各資料表筆數。"""
    if _is_weekend(d):
        return {"skipped": "weekend"}

    prices = fetch_twse_daily(d) + fetch_tpex_daily(d)
    inst = fetch_twse_institutional(d) + fetch_tpex_institutional(d)

    upsert_many("daily_price", prices)
    upsert_many("institutional", inst)

    return {
        "date": d.isoformat(),
        "price_rows": len(prices),
        "inst_rows": len(inst),
    }


def fetch_all(days_back: int = 1) -> list[dict]:
    """抓取最近 N 天。預設抓今天。"""
    init_db()
    results = []
    today = date.today()
    for i in range(days_back):
        d = today - timedelta(days=i)
        try:
            res = fetch_one_day(d)
            results.append(res)
            log.info("fetched %s: %s", d, res)
        except Exception as e:
            log.exception("fetch failed on %s", d)
            results.append({"date": d.isoformat(), "error": str(e)})
    return results


def last_trading_day() -> date | None:
    with connect() as c:
        row = c.execute("SELECT MAX(date) AS d FROM daily_price").fetchone()
    return date.fromisoformat(row["d"]) if row and row["d"] else None
