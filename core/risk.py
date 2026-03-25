import logging
from config.settings import (
    TOTAL_CAPITAL,
    MAX_TRADE_PERCENT,
    MAX_DAILY_LOSS_PERCENT,
    GRID_ORDER_AMOUNT,
)

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Προστατεύει το κεφάλαιο.

    Πριν από κάθε trade, ο bot ρωτάει τον RiskManager:
    "Μπορώ να κάνω αυτό το trade;"
    Αν ο κίνδυνος είναι μεγάλος, λέει ΟΧΙ.
    """

    def __init__(self, db=None):
        self.total_capital    = TOTAL_CAPITAL
        self.daily_loss       = 0.0      # Απώλεια σημερινής ημέρας σε $
        self.daily_loss_limit = TOTAL_CAPITAL * MAX_DAILY_LOSS_PERCENT
        self.db               = db       # Σύνδεση με database (αργότερα)

    # ----------------------------------------------------------
    # ΚΥΡΙΑ ΣΥΝΑΡΤΗΣΗ ΕΛΕΓΧΟΥ
    # ----------------------------------------------------------

    def can_trade(self, amount_usdt: float, reason: str = "") -> tuple[bool, str]:
        """
        Ελέγχει αν επιτρέπεται το trade.
        Επιστρέφει (True, "") αν ΟΚ, ή (False, "λόγος") αν ΟΧΙ.

        Παράδειγμα:
          ok, msg = risk.can_trade(10)
          if ok:
              exchange.buy(...)
          else:
              print(f"Trade απορρίφθηκε: {msg}")
        """
        checks = [
            self._check_min_amount(amount_usdt),
            self._check_max_amount(amount_usdt),
            self._check_daily_loss(),
        ]

        for passed, message in checks:
            if not passed:
                logger.warning(f"Risk check FAIL: {message} | {reason}")
                return False, message

        logger.debug(f"Risk check OK: ${amount_usdt} | {reason}")
        return True, ""

    # ----------------------------------------------------------
    # ΕΛΕΓΧΟΙ
    # ----------------------------------------------------------

    def _check_min_amount(self, amount: float) -> tuple[bool, str]:
        """Ελάχιστο ποσό trade στη Binance = $10."""
        if amount < 10:
            return False, f"Ποσό ${amount} κάτω από το ελάχιστο ($10)"
        return True, ""

    def _check_max_amount(self, amount: float) -> tuple[bool, str]:
        """Μέγιστο ποσό ανά trade = 10% του κεφαλαίου."""
        max_amount = self.total_capital * MAX_TRADE_PERCENT
        if amount > max_amount:
            return False, f"Ποσό ${amount} πάνω από το μέγιστο (${max_amount:.1f})"
        return True, ""

    def _check_daily_loss(self) -> tuple[bool, str]:
        """Αν χαθεί >5% σε μία μέρα, σταματάμε όλα."""
        if self.daily_loss >= self.daily_loss_limit:
            return False, f"Daily loss limit: -${self.daily_loss:.2f} (όριο: ${self.daily_loss_limit:.2f})"
        return True, ""

    # ----------------------------------------------------------
    # POSITION SIZING
    # ----------------------------------------------------------

    def get_position_size(self, capital: float, atr: float, price: float) -> float:
        """
        Υπολογίζει το βέλτιστο μέγεθος θέσης βάσει της volatility.

        Λογική:
          Όταν η αγορά είναι volatile (υψηλό ATR) → μικρότερα trades
          Όταν η αγορά είναι ήρεμη (χαμηλό ATR)   → μεγαλύτερα trades

        Παράδειγμα με BTC @ $71,000, ATR=$900:
          risk_per_trade = $100 * 1% = $1
          atr_pct        = $900 / $71,000 = 1.27%
          size           = $1 / 1.27% = $78.7 → capped στο max ($10)
        """
        risk_per_trade = capital * 0.01       # Ρισκάρουμε 1% ανά trade
        atr_pct        = atr / price           # ATR ως % της τιμής
        atr_pct        = max(atr_pct, 0.001)   # Αποφυγή διαίρεσης με μηδέν

        size     = risk_per_trade / atr_pct
        max_size = capital * MAX_TRADE_PERCENT  # Max 10% του κεφαλαίου

        final_size = min(size, max_size)
        final_size = max(final_size, 5.0)       # Τουλάχιστον $5 (Binance min)

        logger.debug(f"Position size: ${final_size:.2f} (ATR: {atr_pct:.2%})")
        return round(final_size, 2)

    def get_grid_order_amount(self, capital: float, grid_levels: int) -> float:
        """
        Υπολογίζει πόσα $ να βάλει σε κάθε grid order.

        Λογική: Μοιράζει το κεφάλαιο ισόποσα στα επίπεδα,
        αλλά κρατάει πάντα 30% ως απόθεμα ασφαλείας.
        """
        usable_capital = capital * 0.70    # Χρησιμοποιούμε max 70% του κεφαλαίου
        amount_per_level = usable_capital / grid_levels
        amount_per_level = max(amount_per_level, 5.0)   # Min $5
        amount_per_level = min(amount_per_level, GRID_ORDER_AMOUNT)  # Max από settings

        return round(amount_per_level, 2)

    # ----------------------------------------------------------
    # ΠΑΡΑΚΟΛΟΥΘΗΣΗ ΑΠΟΤΕΛΕΣΜΑΤΩΝ
    # ----------------------------------------------------------

    def record_trade_result(self, pnl: float):
        """
        Καταγράφει το αποτέλεσμα ενός trade.
        pnl > 0 = κέρδος, pnl < 0 = απώλεια
        """
        if pnl < 0:
            self.daily_loss += abs(pnl)
            logger.info(f"Trade loss: -${abs(pnl):.2f} | Daily loss: ${self.daily_loss:.2f}/{self.daily_loss_limit:.2f}")

            if self.daily_loss >= self.daily_loss_limit:
                logger.warning("⛔ DAILY LOSS LIMIT REACHED — Ο bot σταματάει trades για σήμερα!")

    def reset_daily_loss(self):
        """Καλείται κάθε μέρα στις 00:00 για να μηδενίσει τον μετρητή."""
        logger.info(f"Daily reset | Χθες: -${self.daily_loss:.2f}")
        self.daily_loss = 0.0

    def get_status(self) -> dict:
        """Επιστρέφει την τρέχουσα κατάσταση του risk manager."""
        return {
            "daily_loss":       round(self.daily_loss, 2),
            "daily_loss_limit": round(self.daily_loss_limit, 2),
            "daily_loss_pct":   round(self.daily_loss / self.daily_loss_limit * 100, 1) if self.daily_loss_limit > 0 else 0,
            "trading_allowed":  self.daily_loss < self.daily_loss_limit,
        }
