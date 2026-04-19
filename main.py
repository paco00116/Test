"""CLI 入口：手動觸發各個流程，或啟動排程/Dashboard。"""
from __future__ import annotations
import click
from datetime import date, timedelta

from db import init_db
from fetchers import fetch_all
from backtest import run_full_search
from predict import predict_next_day
from tracker import settle_day, performance_summary
from scheduler import daily_job, run_forever


@click.group()
def cli():
    """台股當沖預測系統。"""


@cli.command()
def init():
    """初始化資料庫。"""
    init_db()
    click.echo("DB ready.")


@cli.command()
@click.option("--days", default=1, type=int, help="抓取最近幾天")
def fetch(days):
    """抓取盤後資料。"""
    res = fetch_all(days_back=days)
    for r in res:
        click.echo(r)


@cli.command()
@click.option("--combo", default="1,2", help="條件組合大小，逗號分隔")
def backtest(combo):
    """跑回測條件搜尋。"""
    sizes = tuple(int(x) for x in combo.split(","))
    df = run_full_search(combo_sizes=sizes)
    if df.empty:
        click.echo("No results.")
        return
    click.echo(df.head(20).to_string(index=False))


@cli.command()
@click.option("--min-winrate", default=0.55, type=float)
def predict(min_winrate):
    """產生明日當沖候選。"""
    df = predict_next_day(min_win_rate=min_winrate)
    if df.empty:
        click.echo("No picks today.")
    else:
        click.echo(df.to_string(index=False))


@cli.command()
def settle():
    """結算最近一個交易日的績效。"""
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    click.echo(settle_day(yesterday, today))


@cli.command()
def perf():
    """顯示每日累積績效。"""
    df = performance_summary()
    click.echo(df.tail(30).to_string(index=False) if not df.empty else "No data.")


@cli.command()
def run_once():
    """跑一次完整的每日流程。"""
    daily_job()


@cli.command()
def schedule_daemon():
    """啟動排程 daemon（每日 21:00 執行）。"""
    run_forever()


@cli.command()
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=5000, type=int)
def dashboard(host, port):
    """啟動 Web Dashboard。"""
    from dashboard.app import app
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    cli()
