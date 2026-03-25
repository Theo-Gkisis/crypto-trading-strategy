"""
AI Trading Bot — Main Entry Point

Χρήση:
  py -X utf8 main.py          → Εκκίνηση bot
  py -X utf8 main.py --stats  → Εμφάνιση στατιστικών
  py -X utf8 main.py --stop   → Graceful stop
"""
import sys
import time
import signal
import logging
import schedule
import colorlog
from datetime import datetime

from config.settings import (
    TRADING_MODE, TRADING_PAIRS, TIMEFRAME,
    TOTAL_CAPITAL, USE_TESTNET,
)
from core.exchange import Exchange
from core.data import DataManager
from core.risk import RiskManager
from strategies.grid import GridStrategy
from strategies.trend import TrendStrategy
from strategies.dca import DCAStrategy
from notifications.telegram import TelegramNotifier
from database.models import Database
from database.backup import S3Backup


# ----------------------------------------------------------
# LOGGING SETUP
# ----------------------------------------------------------

def setup_logging():
    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        log_colors={
            "DEBUG":    "cyan",
            "INFO":     "green",
            "WARNING":  "yellow",
            "ERROR":    "red",
            "CRITICAL": "red,bg_white",
        }
    ))

    file_handler = logging.FileHandler("logs/bot.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))

    logging.basicConfig(level=logging.INFO, handlers=[handler, file_handler])


# ----------------------------------------------------------
# BOT
# ----------------------------------------------------------

class TradingBot:
    """
    Κεντρικός συντονιστής — ενώνει όλα τα modules.

    Κάθε ώρα:
      1. Παίρνει market state για κάθε pair
      2. Αποφασίζει ποια στρατηγική να τρέξει
      3. Εκτελεί trades
      4. Στέλνει notifications
      5. Αποθηκεύει αποτελέσματα
    """

    def __init__(self):
        self.logger   = logging.getLogger(__name__)
        self.running  = False

        self.logger.info("Αρχικοποίηση bot...")

        # Modules
        self.exchange = Exchange()
        self.data     = DataManager(self.exchange)
        self.risk     = RiskManager()
        self.db       = Database()
        self.backup   = S3Backup()
        self.telegram = TelegramNotifier()

        # Strategies
        self.grid  = GridStrategy(self.exchange, self.risk, self.db, self.telegram)
        self.trend = TrendStrategy(self.exchange, self.risk)
        self.dca   = DCAStrategy(self.exchange, self.risk)

        self.logger.info("Bot αρχικοποιήθηκε επιτυχώς")

    # ----------------------------------------------------------
    # ΚΥΡΙΟΣ ΚΥΚΛΟΣ
    # ----------------------------------------------------------

    def run_cycle(self):
        """
        Ένας κύκλος ανάλυσης & trading.
        Εκτελείται κάθε ώρα για κάθε pair.
        """
        self.logger.info(f"{'='*50}")
        self.logger.info(f"Νέος κύκλος — {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        balance = self.exchange.get_balance("USDT")
        capital = min(balance, TOTAL_CAPITAL)

        if capital < 5:
            self.logger.warning(f"Ανεπαρκές υπόλοιπο: ${balance:.2f}")
            return

        for symbol in TRADING_PAIRS:
            try:
                self._process_symbol(symbol, capital / len(TRADING_PAIRS))
            except Exception as e:
                self.logger.error(f"Σφάλμα για {symbol}: {e}")
                self.telegram.error_alert(f"{symbol}: {str(e)}")

    def _process_symbol(self, symbol: str, capital: float):
        """Αναλύει και κάνει trading για ένα pair."""
        self.logger.info(f"Ανάλυση {symbol}...")

        # 1. Ανάλυση αγοράς
        state = self.data.get_market_state(symbol)
        if not state:
            return

        price = state["price"]
        rsi   = state["rsi"]
        mode  = state["mode"]
        atr   = state["atr"]

        self.logger.info(
            f"{symbol} | ${price:,.2f} | RSI={rsi:.1f} | "
            f"Mode={mode.upper()} | Trend={state['trend']}"
        )

        # 2. Επιλογή στρατηγικής βάσει mode
        if mode == "dca":
            # CRASH — RSI < 25
            self.logger.warning(f"🚨 {symbol}: CRASH MODE (RSI={rsi:.1f})")
            self.telegram.crash_alert(symbol, price, rsi)
            self.grid.cancel_grid(symbol)       # Ακύρωσε grid
            self.trend.positions.pop(symbol, None)  # Ακύρωσε θέση
            result = self.dca.run(symbol, state)

            if result == "dca_buy":
                self.db.save_trade(
                    symbol=symbol, side="buy", strategy="dca",
                    price=price, quantity=5/price, amount=5.0
                )
                self.telegram.trade_opened(symbol, "BUY", price, 5.0, "DCA")

        elif mode == "trend":
            # UPTREND — EMA20 > EMA50
            self.logger.info(f"📈 {symbol}: TREND MODE")
            result = self.trend.run(symbol, state, capital)

            if result == "buy":
                amount = self.risk.get_position_size(capital, atr, price)
                self.db.save_trade(
                    symbol=symbol, side="buy", strategy="trend",
                    price=price, quantity=amount/price, amount=amount
                )
                self.telegram.trade_opened(symbol, "BUY", price, amount, "Trend EMA")

            elif result == "sell":
                self.db.save_trade(
                    symbol=symbol, side="sell", strategy="trend",
                    price=price, quantity=0, amount=0
                )

        else:
            # GRID MODE — Sideways / Downtrend
            self.logger.info(f"⚡ {symbol}: GRID MODE")
            self.grid.check_and_refresh(symbol, price, capital, atr)

        # 3. Stop DCA αν ανάκαμψε
        if mode != "dca":
            dca_result = self.dca.run(symbol, state)
            if dca_result == "stop_dca":
                self.logger.info(f"✅ {symbol}: DCA mode τερματίστηκε (ανάκαμψη)")

    # ----------------------------------------------------------
    # ΕΚΚΙΝΗΣΗ / ΤΕΡΜΑΤΙΣΜΟΣ
    # ----------------------------------------------------------

    def start(self):
        """Εκκινεί τον bot."""
        self.running = True
        self.logger.info(f"🚀 Trading Bot ξεκίνησε | Mode: {TRADING_MODE.upper()}")
        self.logger.info(f"Pairs: {TRADING_PAIRS} | Capital: ${TOTAL_CAPITAL}")

        self.telegram.bot_started(TRADING_MODE, TRADING_PAIRS, TOTAL_CAPITAL)

        # Πρώτος κύκλος αμέσως
        self.run_cycle()

        # Scheduling — κάθε 1 ώρα
        schedule.every(1).hours.do(self.run_cycle)
        schedule.every(1).hours.do(self.backup.backup)

        # Daily summary κάθε μέρα στις 23:55
        schedule.every().day.at("23:55").do(self._daily_summary)

        # Daily reset κάθε μέρα στις 00:01
        schedule.every().day.at("00:01").do(self.risk.reset_daily_loss)

        self.logger.info("Ο bot τρέχει. Πατήστε Ctrl+C για να σταματήσει.")

        while self.running:
            schedule.run_pending()
            time.sleep(60)

    def stop(self, reason: str = "Manual stop"):
        """Graceful shutdown — ακυρώνει όλα τα orders πριν σταματήσει."""
        self.logger.warning(f"Bot σταματάει: {reason}")
        self.running = False

        # Ακύρωσε όλα τα grid orders
        self.grid.cancel_all_grids()

        # Daily summary
        self._daily_summary()

        self.telegram.bot_stopped(reason)
        self.logger.info("Bot σταμάτησε καθαρά.")

    def _daily_summary(self):
        """Στέλνει ημερήσια σύνοψη και αποθηκεύει στη βάση."""
        stats = self.db.get_stats()
        pairs_data = {}

        for symbol in TRADING_PAIRS:
            state = self.data.get_market_state(symbol)
            if state:
                pairs_data[symbol] = {
                    "mode":  state.get("mode", "-"),
                    "price": state.get("price", 0),
                    "rsi":   state.get("rsi", 0),
                }

        stats["pairs"] = pairs_data
        self.telegram.daily_summary(stats)
        self.db.save_daily_summary()

        self.logger.info(
            f"Daily Summary | Trades: {stats['total_trades']} | "
            f"PnL: ${stats['daily_pnl']:.3f} | "
            f"Win Rate: {stats['win_rate']}%"
        )


# ----------------------------------------------------------
# ENTRY POINT
# ----------------------------------------------------------

def main():
    setup_logging()
    logger = logging.getLogger(__name__)

    # Stats mode
    if "--stats" in sys.argv:
        db = Database()
        stats = db.get_stats()
        print("\n=== TRADING BOT STATISTICS ===")
        print(f"Total Trades : {stats['total_trades']}")
        print(f"Total PnL    : ${stats['total_pnl']:.4f}")
        print(f"Daily PnL    : ${stats['daily_pnl']:.4f}")
        print(f"Win Rate     : {stats['win_rate']}%")
        print(f"Best Trade   : ${stats['best_trade']:.4f}")
        print(f"Worst Trade  : ${stats['worst_trade']:.4f}")
        return

    bot = TradingBot()

    # Graceful shutdown με Ctrl+C
    def signal_handler(sig, frame):
        bot.stop("Ctrl+C")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    bot.start()


if __name__ == "__main__":
    main()
