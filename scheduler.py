"""每日 21:00 排程：抓資料 → 回測更新條件 → 產生明日預測 → 結算今日績效。"""
from __future__ import annotations
import logging
import time
from datetime import date, timedelta

import schedule

from config import DAILY_RUN_HOUR, DAILY_RUN_MINUTE
from db import init_db, connect
from fetchers import fetch_all
from backtest import run_full_search
from predict import predict_next_day
from tracker import settle_day

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def _prev_trading_day(d: date) -> date:
    with connect() as c:
        row = c.execute(
            "SELECT MAX(date) AS d FROM daily_price WHERE date < ?",
            [d.isoformat()],
        ).fetchone()
    return date.fromisoformat(row["d"]) if row and row["d"] else d - timedelta(days=1)


def daily_job():
    log.info("=== Daily job start ===")
    init_db()

    log.info("Step 1/4: fetching market data...")
    fetch_all(days_back=1)

    today = date.today()
    prev = _prev_trading_day(today)
    log.info("Step 2/4: settling %s predictions with %s close...", prev, today)
    try:
        result = settle_day(prev.isoformat(), today.isoformat())
        log.info("Settle: %s", result)
    except Exception:
        log.exception("settle failed")

    log.info("Step 3/4: running condition search backtest...")
    try:
        res = run_full_search(combo_sizes=(1, 2))
        log.info("Top 5 conditions: %s", res.head(5)[["name", "win_rate", "sample_size"]].to_dict("records"))
    except Exception:
        log.exception("backtest failed")

    log.info("Step 4/4: predicting next day...")
    try:
        picks = predict_next_day()
        log.info("Picks: %d candidates", len(picks))
    except Exception:
        log.exception("predict failed")

    log.info("=== Daily job done ===")


def run_forever():
    t = f"{DAILY_RUN_HOUR:02d}:{DAILY_RUN_MINUTE:02d}"
    schedule.every().day.at(t).do(daily_job)
    log.info("scheduler armed; next run at %s daily", t)
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    run_forever()
