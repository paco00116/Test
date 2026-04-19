"""特徵工程：技術指標 + 當沖相關特徵。

輸出一個 DataFrame，每列對應某日某股票，欄位為各種訊號。
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from db import connect


def load_prices(stock_id: str | None = None, days: int = 365) -> pd.DataFrame:
    q = "SELECT * FROM daily_price"
    params: list = []
    if stock_id:
        q += " WHERE stock_id = ?"
        params.append(stock_id)
    q += " ORDER BY stock_id, date"
    with connect() as c:
        df = pd.read_sql(q, c, params=params, parse_dates=["date"])
    return df


def load_institutional() -> pd.DataFrame:
    with connect() as c:
        df = pd.read_sql("SELECT * FROM institutional", c, parse_dates=["date"])
    return df


# ----- 技術指標 -----

def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(n).mean()
    loss = (-delta.clip(upper=0)).rolling(n).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_f = close.ewm(span=fast, adjust=False).mean()
    ema_s = close.ewm(span=slow, adjust=False).mean()
    m = ema_f - ema_s
    s = m.ewm(span=signal, adjust=False).mean()
    return m, s, m - s


def kd(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 9):
    lowest = low.rolling(n).min()
    highest = high.rolling(n).max()
    rsv = (close - lowest) / (highest - lowest).replace(0, np.nan) * 100
    k = rsv.ewm(alpha=1/3, adjust=False).mean()
    d = k.ewm(alpha=1/3, adjust=False).mean()
    return k, d


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0):
    ma = close.rolling(n).mean()
    sd = close.rolling(n).std()
    return ma, ma + k * sd, ma - k * sd


def atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    prev_c = close.shift(1)
    tr = pd.concat([high - low, (high - prev_c).abs(), (low - prev_c).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


# ----- 當沖特徵組合 -----

def build_features(stock_id: str | None = None) -> pd.DataFrame:
    prices = load_prices(stock_id)
    if prices.empty:
        return prices

    inst = load_institutional()
    df = prices.merge(inst, on=["date", "stock_id"], how="left")
    df = df.sort_values(["stock_id", "date"]).reset_index(drop=True)

    out_frames = []
    for sid, g in df.groupby("stock_id", sort=False):
        g = g.copy()
        g["ret_1d"] = g["close"].pct_change()
        g["ret_5d"] = g["close"].pct_change(5)
        g["vol_ma5"] = g["volume"].rolling(5).mean()
        g["vol_ma20"] = g["volume"].rolling(20).mean()
        g["vol_ratio"] = g["volume"] / g["vol_ma5"]
        g["price_ma5"] = g["close"].rolling(5).mean()
        g["price_ma20"] = g["close"].rolling(20).mean()
        g["price_ma60"] = g["close"].rolling(60).mean()
        g["above_ma5"] = (g["close"] > g["price_ma5"]).astype(int)
        g["above_ma20"] = (g["close"] > g["price_ma20"]).astype(int)
        g["rsi_14"] = rsi(g["close"], 14)
        m, s, h = macd(g["close"])
        g["macd"], g["macd_sig"], g["macd_hist"] = m, s, h
        k, d = kd(g["high"], g["low"], g["close"])
        g["kd_k"], g["kd_d"] = k, d
        ma, up, lo = bollinger(g["close"])
        g["bb_upper"], g["bb_lower"] = up, lo
        g["bb_pos"] = (g["close"] - lo) / (up - lo).replace(0, np.nan)
        g["atr_14"] = atr(g["high"], g["low"], g["close"], 14)

        # 當沖關鍵：隔日開高走低 / 開低走高 的潛力
        g["gap"] = g["open"] / g["close"].shift(1) - 1
        g["intraday_range"] = (g["high"] - g["low"]) / g["open"]
        g["upper_shadow"] = (g["high"] - g[["open", "close"]].max(axis=1)) / g["open"]
        g["lower_shadow"] = (g[["open", "close"]].min(axis=1) - g["low"]) / g["open"]
        g["body"] = (g["close"] - g["open"]) / g["open"]

        # 法人籌碼
        g["foreign_net_5d"] = g["foreign_net"].rolling(5).sum()
        g["trust_net_5d"] = g["trust_net"].rolling(5).sum()

        # 隔日當沖目標：隔日 (high - open)/open 與 (open - low)/open
        g["next_open"] = g["open"].shift(-1)
        g["next_high"] = g["high"].shift(-1)
        g["next_low"] = g["low"].shift(-1)
        g["next_close"] = g["close"].shift(-1)
        g["next_long_max"] = (g["next_high"] - g["next_open"]) / g["next_open"]
        g["next_short_max"] = (g["next_open"] - g["next_low"]) / g["next_open"]

        out_frames.append(g)

    return pd.concat(out_frames, ignore_index=True)
