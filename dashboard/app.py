"""Flask 可視化 Dashboard。

頁面：
  /               總覽（今日預測、累積績效、勝率）
  /predictions    明日當沖候選清單
  /conditions     條件搜尋 top 勝率
  /performance    每日績效折線圖
  /stock/<id>     單檔 K 線 + 訊號
  /api/*          JSON API 給前端 Chart.js
"""
from __future__ import annotations
from datetime import date
import pandas as pd
from flask import Flask, render_template, jsonify, request

from db import connect

app = Flask(__name__, template_folder="templates", static_folder="static")


def _fetchall(sql: str, params: list | tuple = ()) -> list[dict]:
    with connect() as c:
        rows = c.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# ---------- Pages ----------

@app.route("/")
def index():
    today = date.today().isoformat()
    latest_pred_date = _fetchall("SELECT MAX(date) AS d FROM predictions")
    latest_pred_date = latest_pred_date[0]["d"] if latest_pred_date else None
    preds = _fetchall(
        "SELECT * FROM predictions WHERE date = ? ORDER BY confidence DESC",
        [latest_pred_date or today],
    )
    perf_rows = _fetchall("SELECT * FROM daily_performance ORDER BY date DESC LIMIT 30")
    stats = _fetchall(
        "SELECT COUNT(*) AS n, SUM(is_win) AS wins, SUM(net_return) AS pnl FROM trade_log WHERE mode='live'"
    )
    s = stats[0] if stats else {"n": 0, "wins": 0, "pnl": 0}
    overall_wr = (s["wins"] or 0) / s["n"] if s["n"] else 0
    return render_template(
        "index.html",
        predictions=preds,
        perf=perf_rows,
        latest_pred_date=latest_pred_date,
        overall_winrate=overall_wr,
        total_trades=s["n"] or 0,
        total_pnl=s["pnl"] or 0,
    )


@app.route("/predictions")
def predictions():
    d = request.args.get("date")
    if not d:
        r = _fetchall("SELECT MAX(date) AS d FROM predictions")
        d = r[0]["d"] if r else None
    rows = _fetchall(
        "SELECT p.*, c.expression FROM predictions p LEFT JOIN conditions c "
        "ON p.condition_id = c.id WHERE p.date = ? ORDER BY p.confidence DESC",
        [d or ""],
    )
    return render_template("predictions.html", predictions=rows, date=d)


@app.route("/conditions")
def conditions():
    rows = _fetchall(
        "SELECT * FROM conditions ORDER BY win_rate DESC, sample_size DESC LIMIT 100"
    )
    return render_template("conditions.html", conditions=rows)


@app.route("/performance")
def performance():
    return render_template("performance.html")


@app.route("/stock/<stock_id>")
def stock_detail(stock_id):
    return render_template("stock.html", stock_id=stock_id)


# ---------- JSON API ----------

@app.route("/api/performance")
def api_performance():
    rows = _fetchall("SELECT * FROM daily_performance ORDER BY date")
    return jsonify(rows)


@app.route("/api/stock/<stock_id>")
def api_stock(stock_id):
    rows = _fetchall(
        "SELECT date, open, high, low, close, volume FROM daily_price "
        "WHERE stock_id = ? ORDER BY date DESC LIMIT 180",
        [stock_id],
    )
    rows.reverse()
    return jsonify(rows)


@app.route("/api/trade_log")
def api_trade_log():
    limit = int(request.args.get("limit", 200))
    rows = _fetchall(
        "SELECT * FROM trade_log ORDER BY id DESC LIMIT ?", [limit]
    )
    return jsonify(rows)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
