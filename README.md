# 台股當沖預測系統 (Taiwan Day-Trade Lab)

每天晚上 21:00 自動抓取上市上櫃盤後資料，以大量條件回測搜尋歷史最高勝率組合，
產生隔日當沖候選（多 / 空 + 進場 / 出場 / 停損），並追蹤每日績效。
內建 Flask Web Dashboard 可視化預測、條件勝率、累積績效。

## 功能

1. **資料抓取**：TWSE（上市）+ TPEx（上櫃）每日盤後 OHLCV、三大法人買賣超。
2. **特徵工程**：RSI / MACD / KD / 布林 / ATR / 量比 / 法人籌碼 / 跳空 / K 線結構。
3. **條件搜尋回測**：單條件與雙條件笛卡兒乘積搜尋，保留勝率最高的 Top N。
4. **明日預測**：依 Top 條件掃描最新交易日，輸出方向、進場、出場、停損、信心度。
5. **績效追蹤**：每日結算實際 open→close 當沖報酬，計算累積淨損益與勝率。
6. **成本模型**：手續費 0.1425%（雙邊）× 折扣 + 當沖證交稅 0.15%（賣出單邊）。
7. **排程**：每日 21:00 自動跑完 抓資料 → 結算 → 回測 → 預測。
8. **Web Dashboard**：Flask + Chart.js，總覽 / 預測 / 條件 / 績效 / 個股走勢。

## 目錄結構

```
.
├── config.py          # 常數：手續費、資料來源、排程時間
├── db.py              # SQLite schema
├── fetchers/          # 證交所 / 櫃買盤後 + 三大法人
├── features.py        # 技術指標 + 當沖特徵
├── backtest.py        # 條件搜尋與評估
├── predict.py         # 明日當沖候選
├── tracker.py         # 每日結算
├── scheduler.py       # 21:00 排程 daemon
├── dashboard/         # Flask web UI
│   ├── app.py
│   ├── templates/
│   └── static/
└── main.py            # CLI 入口
```

## 使用

```bash
pip install -r requirements.txt

# 1. 初始化 DB
python main.py init

# 2. 抓取最近 60 天資料（第一次使用）
python main.py fetch --days 60

# 3. 跑條件搜尋回測
python main.py backtest --combo 1,2

# 4. 產生明日預測
python main.py predict --min-winrate 0.55

# 5. 結算昨日預測 vs 今日真實結果
python main.py settle

# 6. 查看累積績效
python main.py perf

# 一鍵跑完整個流程
python main.py run-once

# 啟動 21:00 排程 daemon
python main.py schedule-daemon

# 啟動 Web Dashboard
python main.py dashboard --host 0.0.0.0 --port 5000
```

Dashboard 開啟 http://localhost:5000。

## 免責聲明

本系統為量化研究與回測工具，不構成任何投資建議。實盤交易風險由使用者自負。
