"""全域設定：手續費、交易稅、資料來源、排程時間。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "market.db"
DATA_DIR.mkdir(exist_ok=True)

# 交易成本
FEE_RATE = 0.001425        # 券商手續費（單邊）
FEE_DISCOUNT = 1.0         # 手續費折扣（例如 0.28 = 28 折）
TAX_RATE_DAYTRADE = 0.0015 # 當沖證交稅（賣出單邊，減半）
MIN_FEE = 20               # 最低手續費（元）

# 資料來源
TWSE_DAILY_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
TWSE_INST_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
TPEX_DAILY_URL = "https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php"
TPEX_INST_URL = "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php"

# 排程
DAILY_RUN_HOUR = 21
DAILY_RUN_MINUTE = 0

# 回測預設
DEFAULT_LOOKBACK_DAYS = 180
MIN_VOLUME = 1_000_000       # 當沖候選最低成交量（股）
MIN_PRICE = 10               # 最低股價
MAX_PRICE = 500              # 最高股價
