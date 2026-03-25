import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# EXCHANGE
# ============================================================
TRADING_MODE = os.getenv("TRADING_MODE", "testnet")  # "testnet" ή "live"
USE_TESTNET  = TRADING_MODE == "testnet"

# Αυτόματη επιλογή keys ανάλογα με το mode
if USE_TESTNET:
    BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY_TESTNET", "")
    BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET_TESTNET", "")
else:
    BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# ============================================================
# ΚΕΦΑΛΑΙΟ
# ============================================================
TOTAL_CAPITAL = float(os.getenv("TOTAL_CAPITAL", 100))

# Μέγιστο % του κεφαλαίου ανά trade
MAX_TRADE_PERCENT = 0.10   # 10% → max $10 ανά trade

# Μέγιστο % απώλειας για να σταματήσει το bot (stop-loss ασφαλείας)
MAX_DAILY_LOSS_PERCENT = 0.05  # 5% → αν χαθούν $5 σε μία μέρα, σταμάτα

# ============================================================
# PAIRS & TIMEFRAME
# ============================================================
TRADING_PAIRS = ["BTC/USDT", "ETH/USDT"]
TIMEFRAME     = "1h"   # 1 ώρα

# ============================================================
# GRID TRADING
# ============================================================
GRID_LEVELS       = 3      # Αριθμός επιπέδων πάνω και κάτω
GRID_SPREAD       = 0.01   # 1% απόσταση μεταξύ επιπέδων
GRID_ORDER_AMOUNT = 10     # $10 ανά grid order

# ============================================================
# INDICATORS
# ============================================================
RSI_PERIOD       = 14
RSI_OVERSOLD     = 30   # Κάτω από 30 → oversold (πολύ φθηνό)
RSI_OVERBOUGHT   = 70   # Πάνω από 70 → overbought (πολύ ακριβό)
RSI_CRASH        = 25   # Κάτω από 25 → crash, ενεργοποίησε DCA

EMA_FAST         = 20   # Γρήγορος EMA
EMA_SLOW         = 50   # Αργός EMA

# ============================================================
# DCA (Dollar Cost Averaging)
# ============================================================
DCA_AMOUNT       = 10   # $10 ανά DCA αγορά (Binance min notional)
DCA_INTERVAL_H   = 4    # Κάθε 4 ώρες αγοράζει αν είμαστε σε crash mode

# ============================================================
# TELEGRAM
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

# ============================================================
# DATABASE
# ============================================================
DATABASE_URL = "sqlite:///database/trading_bot.db"

# ============================================================
# LOGGING
# ============================================================
LOG_LEVEL = "INFO"
LOG_FILE  = "logs/bot.log"
