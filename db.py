"""SQLite schema 與基本 CRUD。

資料表：
  daily_price   每日盤後 OHLCV
  institutional 三大法人買賣超
  fundamentals  財報快照（EPS、毛利率、ROE 等）
  predictions   每日預測結果
  trade_log     回測/實盤交易紀錄
  conditions    條件搜尋結果（特徵組合 + 勝率）
"""
import sqlite3
from contextlib import contextmanager
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_price (
    date TEXT, stock_id TEXT, name TEXT,
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER, turnover REAL, trades INTEGER,
    change REAL,
    PRIMARY KEY (date, stock_id)
);
CREATE INDEX IF NOT EXISTS idx_price_stock ON daily_price(stock_id, date);

CREATE TABLE IF NOT EXISTS institutional (
    date TEXT, stock_id TEXT,
    foreign_buy INTEGER, foreign_sell INTEGER, foreign_net INTEGER,
    trust_buy INTEGER, trust_sell INTEGER, trust_net INTEGER,
    dealer_net INTEGER, total_net INTEGER,
    PRIMARY KEY (date, stock_id)
);

CREATE TABLE IF NOT EXISTS fundamentals (
    stock_id TEXT, period TEXT,
    eps REAL, revenue REAL, gross_margin REAL,
    op_margin REAL, net_margin REAL, roe REAL, roa REAL,
    PRIMARY KEY (stock_id, period)
);

CREATE TABLE IF NOT EXISTS predictions (
    date TEXT, stock_id TEXT,
    direction TEXT,          -- 'long' or 'short'
    entry_price REAL,        -- 建議進場
    exit_price REAL,         -- 建議出場
    stop_loss REAL,
    confidence REAL,         -- 該條件歷史勝率
    condition_id INTEGER,
    expected_return REAL,
    PRIMARY KEY (date, stock_id, direction)
);

CREATE TABLE IF NOT EXISTS trade_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT, stock_id TEXT,
    direction TEXT, entry REAL, exit REAL,
    gross_return REAL, net_return REAL,
    condition_id INTEGER, is_win INTEGER,
    mode TEXT               -- 'backtest' | 'live'
);

CREATE TABLE IF NOT EXISTS conditions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    expression TEXT,          -- 人類可讀的條件表達式
    direction TEXT,
    sample_size INTEGER,
    wins INTEGER,
    win_rate REAL,
    avg_return REAL,
    sharpe REAL,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS daily_performance (
    date TEXT PRIMARY KEY,
    n_trades INTEGER,
    wins INTEGER,
    win_rate REAL,
    gross_pnl REAL,
    net_pnl REAL,
    cumulative_pnl REAL
);
"""


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connect() as c:
        c.executescript(SCHEMA)


def upsert_many(table: str, rows: list[dict]):
    if not rows:
        return
    cols = list(rows[0].keys())
    placeholders = ",".join("?" for _ in cols)
    collist = ",".join(cols)
    sql = f"INSERT OR REPLACE INTO {table} ({collist}) VALUES ({placeholders})"
    with connect() as c:
        c.executemany(sql, [tuple(r[col] for col in cols) for r in rows])


if __name__ == "__main__":
    init_db()
    print(f"DB initialised at {DB_PATH}")
