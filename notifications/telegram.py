import logging
import asyncio
import requests
from datetime import datetime
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Στέλνει μηνύματα στο Telegram σου για κάθε σημαντικό event.

    Events:
      - Bot ξεκίνησε/σταμάτησε
      - Trade εκτελέστηκε (buy/sell)
      - Κέρδος/ζημιά
      - Crash alert
      - Daily summary
      - Errors
    """

    def __init__(self):
        self.token   = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.enabled = bool(self.token and self.chat_id
                            and self.token != "your_telegram_bot_token_here")

        if not self.enabled:
            logger.warning("Telegram δεν έχει ρυθμιστεί — notifications απενεργοποιημένα")

    # ----------------------------------------------------------
    # ΒΑΣΙΚΗ ΑΠΟΣΤΟΛΗ
    # ----------------------------------------------------------

    def send(self, message: str) -> bool:
        """Στέλνει μήνυμα στο Telegram."""
        if not self.enabled:
            logger.debug(f"[Telegram disabled] {message}")
            return False

        try:
            url  = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {
                "chat_id":    self.chat_id,
                "text":       message,
                "parse_mode": "HTML",
            }
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            return True

        except Exception as e:
            logger.error(f"Telegram error: {e}")
            return False

    # ----------------------------------------------------------
    # ΕΙΔΙΚΑ ΜΗΝΥΜΑΤΑ
    # ----------------------------------------------------------

    def bot_started(self, mode: str, pairs: list, capital: float):
        self.send(
            f"🤖 <b>Trading Bot Ξεκίνησε!</b>\n\n"
            f"Mode    : <code>{mode.upper()}</code>\n"
            f"Pairs   : <code>{', '.join(pairs)}</code>\n"
            f"Capital : <code>${capital:.2f}</code>\n"
            f"Time    : <code>{datetime.now().strftime('%H:%M:%S')}</code>"
        )

    def bot_stopped(self, reason: str = "Manual stop"):
        self.send(
            f"🛑 <b>Trading Bot Σταμάτησε</b>\n\n"
            f"Λόγος: <code>{reason}</code>\n"
            f"Time : <code>{datetime.now().strftime('%H:%M:%S')}</code>"
        )

    def trade_opened(self, symbol: str, side: str, price: float,
                     amount: float, strategy: str):
        emoji = "🟢" if side == "BUY" else "🔴"
        self.send(
            f"{emoji} <b>{side} — {symbol}</b>\n\n"
            f"Στρατηγική : <code>{strategy}</code>\n"
            f"Τιμή       : <code>${price:,.2f}</code>\n"
            f"Ποσό       : <code>${amount:.2f}</code>\n"
            f"Ώρα        : <code>{datetime.now().strftime('%H:%M:%S')}</code>"
        )

    def trade_closed(self, symbol: str, entry: float, exit_price: float,
                     pnl: float, strategy: str):
        emoji   = "✅" if pnl >= 0 else "❌"
        pnl_pct = (exit_price - entry) / entry * 100
        self.send(
            f"{emoji} <b>CLOSE — {symbol}</b>\n\n"
            f"Στρατηγική : <code>{strategy}</code>\n"
            f"Entry      : <code>${entry:,.2f}</code>\n"
            f"Exit       : <code>${exit_price:,.2f}</code>\n"
            f"PnL        : <code>{'+'if pnl>=0 else ''}{pnl:.3f}$ ({pnl_pct:+.1f}%)</code>\n"
            f"Ώρα        : <code>{datetime.now().strftime('%H:%M:%S')}</code>"
        )

    def grid_refreshed(self, symbol: str, price: float,
                       buy_levels: list, sell_levels: list):
        self.send(
            f"🔄 <b>Grid ανανεώθηκε — {symbol}</b>\n\n"
            f"Τιμή       : <code>${price:,.2f}</code>\n"
            f"BUY orders : <code>{len(buy_levels)}</code>\n"
            f"SELL orders: <code>{len(sell_levels)}</code>\n"
            f"Range      : <code>${min(buy_levels):,.2f} — ${max(sell_levels):,.2f}</code>"
        )

    def crash_alert(self, symbol: str, price: float, rsi: float):
        self.send(
            f"🚨 <b>CRASH ALERT — {symbol}</b>\n\n"
            f"Τιμή : <code>${price:,.2f}</code>\n"
            f"RSI  : <code>{rsi:.1f}</code> ⚠️ Πολύ χαμηλό!\n"
            f"Action: DCA mode ενεργοποιήθηκε"
        )

    def daily_summary(self, stats: dict):
        pnl    = stats.get("daily_pnl", 0)
        trades = stats.get("daily_trades", 0)
        emoji  = "📈" if pnl >= 0 else "📉"

        lines = [
            f"{emoji} <b>Daily Summary</b>",
            f"",
            f"Trades    : <code>{trades}</code>",
            f"Daily PnL : <code>{'+'if pnl>=0 else ''}{pnl:.3f}$</code>",
        ]

        for symbol, data in stats.get("pairs", {}).items():
            lines.append(f"\n<b>{symbol}</b>")
            lines.append(f"  Mode  : <code>{data.get('mode', '-')}</code>")
            lines.append(f"  Price : <code>${data.get('price', 0):,.2f}</code>")
            lines.append(f"  RSI   : <code>{data.get('rsi', 0):.1f}</code>")

        self.send("\n".join(lines))

    def error_alert(self, error: str):
        self.send(
            f"⚠️ <b>Bot Error</b>\n\n"
            f"<code>{error[:300]}</code>"
        )

    def daily_loss_limit(self, loss: float, limit: float):
        self.send(
            f"🛑 <b>Daily Loss Limit!</b>\n\n"
            f"Σήμερα χάθηκαν: <code>${loss:.2f}</code>\n"
            f"Όριο           : <code>${limit:.2f}</code>\n\n"
            f"Ο bot σταμάτησε trades για σήμερα."
        )
