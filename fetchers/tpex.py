"""櫃買中心（上櫃）盤後資料抓取。"""
from __future__ import annotations
import time
import requests
from datetime import date

from config import TPEX_DAILY_URL, TPEX_INST_URL

HEADERS = {"User-Agent": "Mozilla/5.0 (daytrade-bot)"}


def _to_int(s) -> int:
    if s is None:
        return 0
    s = str(s).replace(",", "").strip()
    if s in ("", "--", "X"):
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


def _to_float(s) -> float:
    if s is None:
        return 0.0
    s = str(s).replace(",", "").strip()
    if s in ("", "--", "X"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _roc(d: date) -> str:
    """西元年轉民國年 yyy/mm/dd。"""
    return f"{d.year - 1911}/{d.month:02d}/{d.day:02d}"


def fetch_tpex_daily(d: date) -> list[dict]:
    params = {"l": "zh-tw", "d": _roc(d), "o": "json"}
    try:
        resp = requests.get(TPEX_DAILY_URL, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        j = resp.json()
    except Exception:
        return []
    rows = []
    for row in j.get("aaData", []):
        try:
            stock_id = row[0].strip()
            if not (stock_id.isdigit() and len(stock_id) == 4):
                continue
            rows.append({
                "date": d.isoformat(),
                "stock_id": stock_id,
                "name": row[1].strip(),
                "close": _to_float(row[2]),
                "change": _to_float(row[3]),
                "open": _to_float(row[4]),
                "high": _to_float(row[5]),
                "low": _to_float(row[6]),
                "volume": _to_int(row[7]) * 1000,  # 櫃買以張為單位
                "turnover": _to_float(row[8]) * 1000,
                "trades": _to_int(row[9]),
            })
        except (IndexError, ValueError):
            continue
    time.sleep(1)
    return rows


def fetch_tpex_institutional(d: date) -> list[dict]:
    params = {"l": "zh-tw", "t": "D", "d": _roc(d), "o": "json", "se": "EW"}
    try:
        resp = requests.get(TPEX_INST_URL, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        j = resp.json()
    except Exception:
        return []
    rows = []
    for row in j.get("aaData", []):
        try:
            stock_id = row[0].strip()
            if not (stock_id.isdigit() and len(stock_id) == 4):
                continue
            rows.append({
                "date": d.isoformat(),
                "stock_id": stock_id,
                "foreign_buy": _to_int(row[2]),
                "foreign_sell": _to_int(row[3]),
                "foreign_net": _to_int(row[4]),
                "trust_buy": _to_int(row[8]),
                "trust_sell": _to_int(row[9]),
                "trust_net": _to_int(row[10]),
                "dealer_net": _to_int(row[14]),
                "total_net": _to_int(row[-1]),
            })
        except (IndexError, ValueError):
            continue
    time.sleep(1)
    return rows
