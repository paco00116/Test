"""證交所（上市）盤後資料抓取。"""
from __future__ import annotations
import time
import requests
from datetime import date, datetime

from config import TWSE_DAILY_URL, TWSE_INST_URL

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


def _ymd(d: date) -> str:
    return d.strftime("%Y%m%d")


def fetch_twse_daily(d: date) -> list[dict]:
    """抓取某日上市所有股票的 OHLCV。"""
    params = {"response": "json", "date": _ymd(d), "type": "ALLBUT0999"}
    resp = requests.get(TWSE_DAILY_URL, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    j = resp.json()
    if j.get("stat") != "OK":
        return []

    # 找出第一個 fields 含「證券代號」的表
    rows = []
    tables = j.get("tables", []) or []
    for t in tables:
        fields = t.get("fields", [])
        if "證券代號" not in fields:
            continue
        idx = {f: i for i, f in enumerate(fields)}
        for row in t.get("data", []):
            try:
                stock_id = row[idx["證券代號"]].strip()
                # 只取 4 位數字股票代號（個股）
                if not (stock_id.isdigit() and len(stock_id) == 4):
                    continue
                rows.append({
                    "date": d.isoformat(),
                    "stock_id": stock_id,
                    "name": row[idx["證券名稱"]].strip(),
                    "volume": _to_int(row[idx.get("成交股數", 2)]),
                    "trades": _to_int(row[idx.get("成交筆數", 3)]),
                    "turnover": _to_float(row[idx.get("成交金額", 4)]),
                    "open": _to_float(row[idx.get("開盤價", 5)]),
                    "high": _to_float(row[idx.get("最高價", 6)]),
                    "low": _to_float(row[idx.get("最低價", 7)]),
                    "close": _to_float(row[idx.get("收盤價", 8)]),
                    "change": _to_float(row[idx.get("漲跌價差", 10)]),
                })
            except (KeyError, IndexError, ValueError):
                continue
        break
    return rows


def fetch_twse_institutional(d: date) -> list[dict]:
    """抓取某日上市三大法人買賣超。"""
    params = {"response": "json", "date": _ymd(d), "selectType": "ALLBUT0999"}
    resp = requests.get(TWSE_INST_URL, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    j = resp.json()
    if j.get("stat") != "OK":
        return []

    fields = j.get("fields", [])
    data = j.get("data", [])
    if not fields or not data:
        return []
    idx = {f: i for i, f in enumerate(fields)}
    rows = []
    for row in data:
        try:
            stock_id = row[idx["證券代號"]].strip()
            if not (stock_id.isdigit() and len(stock_id) == 4):
                continue
            rows.append({
                "date": d.isoformat(),
                "stock_id": stock_id,
                "foreign_buy": _to_int(row[idx.get("外陸資買進股數(不含外資自營商)", 2)]),
                "foreign_sell": _to_int(row[idx.get("外陸資賣出股數(不含外資自營商)", 3)]),
                "foreign_net": _to_int(row[idx.get("外陸資買賣超股數(不含外資自營商)", 4)]),
                "trust_buy": _to_int(row[idx.get("投信買進股數", 8)]),
                "trust_sell": _to_int(row[idx.get("投信賣出股數", 9)]),
                "trust_net": _to_int(row[idx.get("投信買賣超股數", 10)]),
                "dealer_net": _to_int(row[idx.get("自營商買賣超股數", 11)]),
                "total_net": _to_int(row[idx.get("三大法人買賣超股數", -1)]),
            })
        except (KeyError, IndexError, ValueError):
            continue
    time.sleep(1)
    return rows
