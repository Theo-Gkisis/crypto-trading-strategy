import logging
from datetime import datetime
from core.exchange import Exchange
from core.risk import RiskManager
from config.settings import (
    RSI_OVERSOLD, RSI_CRASH,
    DCA_AMOUNT, DCA_INTERVAL_H,
)

logger = logging.getLogger(__name__)


class DCAStrategy:
    """
    DCA (Dollar Cost Averaging) + RSI Filter Strategy.

    Λογική:
      Όταν η αγορά πέφτει δυνατά (crash), αντί να πανικοβάλλεσαι,
      αγοράζεις σιγά-σιγά σε τακτά διαστήματα.
      Έτσι ο μέσος όρος τιμής αγοράς γίνεται χαμηλότερος,
      και κερδίζεις περισσότερο όταν η αγορά ανακάμψει.

    Παράδειγμα:
      BTC πέφτει: $71,000 → $65,000 → $60,000
      DCA αγοράζει: $5 @ $71,000 + $5 @ $65,000 + $5 @ $60,000
      Μέση τιμή αγοράς: $65,333  (καλύτερα από $71,000)
      Όταν BTC → $70,000: κέρδος +7.1%

    RSI Filter:
      RSI < 25 → Crash mode  → DCA ενεργό
      RSI < 30 → Oversold    → αγορά μία φορά
      RSI > 50 → Ανάκαμψη   → σταμάτα DCA
    """

    def __init__(self, exchange: Exchange, risk: RiskManager):
        self.exchange      = exchange
        self.risk          = risk
        self.dca_positions = {}   # symbol → λίστα αγορών
        self.last_dca_time = {}   # symbol → τελευταία ώρα DCA

    # ----------------------------------------------------------
    # ΚΥΡΙΑ ΛΟΓΙΚΗ
    # ----------------------------------------------------------

    def run(self, symbol: str, state: dict) -> str:
        """
        Καλείται κάθε ώρα.
        Επιστρέφει: "dca_buy", "stop_dca", ή "none"
        """
        rsi   = state["rsi"]
        price = state["price"]

        # Crash mode: RSI < 25
        if rsi < RSI_CRASH:
            return self._handle_crash(symbol, price, rsi)

        # Oversold: RSI < 30 → μία αγορά
        if rsi < RSI_OVERSOLD:
            return self._handle_oversold(symbol, price, rsi)

        # Ανάκαμψη: RSI > 50 → σταμάτα DCA
        if rsi > 50 and symbol in self.dca_positions:
            return self._stop_dca(symbol, price)

        return "none"

    # ----------------------------------------------------------
    # CRASH MODE
    # ----------------------------------------------------------

    def _handle_crash(self, symbol: str, price: float, rsi: float) -> str:
        """
        Αγοράζει κάθε DCA_INTERVAL_H ώρες κατά τη διάρκεια crash.
        """
        if not self._can_dca_now(symbol):
            return "none"

        ok, msg = self.risk.can_trade(DCA_AMOUNT, f"DCA crash {symbol} RSI={rsi:.1f}")
        if not ok:
            logger.warning(f"DCA blocked: {msg}")
            return "none"

        order = self.exchange.place_buy_order(symbol, DCA_AMOUNT)
        if not order:
            return "none"

        self._record_dca(symbol, price, DCA_AMOUNT)
        self.last_dca_time[symbol] = datetime.now()

        logger.warning(
            f"🚨 CRASH DCA: {symbol} @ ${price:,.2f} | "
            f"RSI={rsi:.1f} | Amount=${DCA_AMOUNT}"
        )
        return "dca_buy"

    def _handle_oversold(self, symbol: str, price: float, rsi: float) -> str:
        """
        Μία αγορά όταν το RSI είναι oversold (< 30).
        """
        # Αν έχουμε ήδη κάνει DCA πρόσφατα, παράλειψε
        if not self._can_dca_now(symbol):
            return "none"

        ok, msg = self.risk.can_trade(DCA_AMOUNT, f"DCA oversold {symbol} RSI={rsi:.1f}")
        if not ok:
            return "none"

        order = self.exchange.place_buy_order(symbol, DCA_AMOUNT)
        if not order:
            return "none"

        self._record_dca(symbol, price, DCA_AMOUNT)
        self.last_dca_time[symbol] = datetime.now()

        logger.info(
            f"📉 OVERSOLD DCA: {symbol} @ ${price:,.2f} | RSI={rsi:.1f}"
        )
        return "dca_buy"

    def _stop_dca(self, symbol: str, price: float) -> str:
        """
        Σταματάει το DCA mode όταν η αγορά ανακάμψει.
        Δεν πουλάει — απλά σταματάει νέες αγορές.
        """
        if symbol in self.dca_positions:
            avg_price = self._get_avg_price(symbol)
            total_qty = sum(p["quantity"] for p in self.dca_positions[symbol])
            pnl_pct   = (price - avg_price) / avg_price * 100

            logger.info(
                f"✅ DCA STOP: {symbol} ανάκαμψη | "
                f"Avg entry: ${avg_price:,.2f} | "
                f"Current: ${price:,.2f} | "
                f"PnL: {pnl_pct:+.1f}%"
            )
            del self.dca_positions[symbol]

        return "stop_dca"

    # ----------------------------------------------------------
    # ΒΟΗΘΗΤΙΚΕΣ
    # ----------------------------------------------------------

    def _can_dca_now(self, symbol: str) -> bool:
        """Ελέγχει αν έχουν περάσει αρκετές ώρες από το τελευταίο DCA."""
        if symbol not in self.last_dca_time:
            return True

        hours_passed = (datetime.now() - self.last_dca_time[symbol]).seconds / 3600
        return hours_passed >= DCA_INTERVAL_H

    def _record_dca(self, symbol: str, price: float, amount: float):
        """Καταγράφει την αγορά στο ιστορικό DCA."""
        if symbol not in self.dca_positions:
            self.dca_positions[symbol] = []

        self.dca_positions[symbol].append({
            "price":    price,
            "quantity": amount / price,
            "amount":   amount,
            "time":     datetime.now(),
        })

    def _get_avg_price(self, symbol: str) -> float:
        """Υπολογίζει τη μέση τιμή αγοράς για όλες τις DCA αγορές."""
        if symbol not in self.dca_positions or not self.dca_positions[symbol]:
            return 0.0

        total_cost = sum(p["amount"] for p in self.dca_positions[symbol])
        total_qty  = sum(p["quantity"] for p in self.dca_positions[symbol])

        return total_cost / total_qty if total_qty > 0 else 0.0

    def get_stats(self, symbol: str) -> dict:
        """Επιστρέφει στατιστικά DCA για ένα pair."""
        if symbol not in self.dca_positions:
            return {"active": False}

        positions  = self.dca_positions[symbol]
        avg_price  = self._get_avg_price(symbol)
        total_cost = sum(p["amount"] for p in positions)

        return {
            "active":      True,
            "symbol":      symbol,
            "buys":        len(positions),
            "avg_price":   round(avg_price, 2),
            "total_cost":  round(total_cost, 2),
        }
