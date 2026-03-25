import logging
from core.exchange import Exchange
from core.risk import RiskManager
from config.settings import EMA_FAST, EMA_SLOW

logger = logging.getLogger(__name__)


class TrendStrategy:
    """
    EMA Trend Following Strategy.

    Λογική:
      Όταν η αγορά ανεβαίνει δυνατά, δεν θέλουμε να κάνουμε grid
      (χάνουμε την άνοδο). Αντ' αυτού, μπαίνουμε στην τάση και
      κρατάμε τη θέση μέχρι να αντιστραφεί.

      EMA20 > EMA50 → Uptrend  → BUY και κράτα
      EMA20 < EMA50 → Downtrend → SELL και βγες

    Παράδειγμα:
      BTC ανεβαίνει από $71,000 → $85,000
      Grid θα έκανε: πολλά μικρά trades, χάνει την μεγάλη άνοδο
      Trend θα έκανε: αγορά στα $71,000, πώληση στα $85,000 = +19.7%
    """

    def __init__(self, exchange: Exchange, risk: RiskManager):
        self.exchange     = exchange
        self.risk         = risk
        self.positions    = {}   # symbol → position info

    # ----------------------------------------------------------
    # ΚΥΡΙΑ ΛΟΓΙΚΗ
    # ----------------------------------------------------------

    def run(self, symbol: str, state: dict, capital: float) -> str:
        """
        Κύρια συνάρτηση — καλείται κάθε ώρα.
        Επιστρέφει: "buy", "sell", "hold", ή "none"
        """
        price    = state["price"]
        ema_fast = state["ema_fast"]
        ema_slow = state["ema_slow"]
        rsi      = state["rsi"]

        in_position = symbol in self.positions

        # --- Σήμα αγοράς ---
        if self._is_buy_signal(ema_fast, ema_slow, rsi) and not in_position:
            return self._open_position(symbol, price, capital, state)

        # --- Σήμα πώλησης ---
        if in_position:
            position = self.positions[symbol]
            if self._is_sell_signal(ema_fast, ema_slow, rsi, price, position):
                return self._close_position(symbol, price)

        return "hold" if in_position else "none"

    # ----------------------------------------------------------
    # ΣΗΜΑΤΑ
    # ----------------------------------------------------------

    def _is_buy_signal(self, ema_fast: float, ema_slow: float, rsi: float) -> bool:
        """
        Σήμα αγοράς όταν:
          1. EMA20 μόλις πέρασε πάνω από EMA50 (golden cross)
          2. RSI δεν είναι overbought (< 70) — αποφυγή αγοράς στην κορυφή
        """
        ema_cross = ema_fast > ema_slow * 1.002   # EMA20 > EMA50 κατά 0.2%
        rsi_ok    = rsi < 70                        # Δεν είναι overbought

        if ema_cross and rsi_ok:
            logger.info(f"BUY signal: EMA{EMA_FAST}={ema_fast:.2f} > EMA{EMA_SLOW}={ema_slow:.2f} | RSI={rsi:.1f}")
            return True
        return False

    def _is_sell_signal(self, ema_fast: float, ema_slow: float,
                        rsi: float, current_price: float, position: dict) -> bool:
        """
        Σήμα πώλησης όταν:
          1. EMA20 έπεσε κάτω από EMA50 (death cross) → τάση αλλάζει
          2. RSI > 75 (overbought) → πιθανή κορυφή → lock in profits
          3. Stop loss: τιμή έπεσε >3% από την αγορά → περιόρισε ζημιά
        """
        entry_price = position["entry_price"]

        ema_death_cross = ema_fast < ema_slow * 0.998
        rsi_overbought  = rsi > 75
        stop_loss       = current_price < entry_price * 0.97   # -3%
        take_profit     = current_price > entry_price * 1.08   # +8%

        if ema_death_cross:
            logger.info(f"SELL signal (death cross): EMA{EMA_FAST} < EMA{EMA_SLOW}")
            return True
        if rsi_overbought:
            logger.info(f"SELL signal (overbought): RSI={rsi:.1f}")
            return True
        if stop_loss:
            pnl_pct = (current_price - entry_price) / entry_price * 100
            logger.warning(f"SELL signal (stop loss): {pnl_pct:.1f}%")
            return True
        if take_profit:
            pnl_pct = (current_price - entry_price) / entry_price * 100
            logger.info(f"SELL signal (take profit): +{pnl_pct:.1f}%")
            return True

        return False

    # ----------------------------------------------------------
    # ΕΚΤΕΛΕΣΗ TRADES
    # ----------------------------------------------------------

    def _open_position(self, symbol: str, price: float,
                       capital: float, state: dict) -> str:
        """Ανοίγει θέση — αγοράζει crypto."""
        atr    = state.get("atr", price * 0.01)
        amount = max(self.risk.get_position_size(capital, atr, price), 10.0)

        ok, msg = self.risk.can_trade(amount, f"Trend BUY {symbol}")
        if not ok:
            logger.warning(f"Trend BUY blocked: {msg}")
            return "none"

        order = self.exchange.place_buy_order(symbol, amount)
        if not order:
            return "none"

        quantity = amount / price

        self.positions[symbol] = {
            "entry_price":  price,
            "quantity":     quantity,
            "amount_usdt":  amount,
            "entry_time":   None,   # θα το βάλει η database
        }

        logger.info(
            f"TREND POSITION OPENED: {symbol} | "
            f"Entry: ${price:,.2f} | Amount: ${amount:.2f}"
        )
        return "buy"

    def _close_position(self, symbol: str, price: float) -> str:
        """Κλείνει θέση — πουλάει crypto."""
        if symbol not in self.positions:
            return "none"

        position   = self.positions[symbol]
        quantity   = position["quantity"]
        entry      = position["entry_price"]

        order = self.exchange.place_sell_order(symbol, quantity)
        if not order:
            return "none"

        pnl     = (price - entry) * quantity
        pnl_pct = (price - entry) / entry * 100

        self.risk.record_trade_result(pnl)
        del self.positions[symbol]

        logger.info(
            f"TREND POSITION CLOSED: {symbol} | "
            f"Entry: ${entry:,.2f} → Exit: ${price:,.2f} | "
            f"PnL: {'+'if pnl>=0 else ''}{pnl:.3f} ({pnl_pct:+.1f}%)"
        )
        return "sell"

    # ----------------------------------------------------------
    # ΣΤΑΤΙΣΤΙΚΑ
    # ----------------------------------------------------------

    def get_position(self, symbol: str) -> dict:
        """Επιστρέφει την ανοιχτή θέση για ένα pair (αν υπάρχει)."""
        if symbol not in self.positions:
            return {}

        position    = self.positions[symbol]
        entry       = position["entry_price"]
        current_pnl = None   # Θα υπολογιστεί με live τιμή

        return {
            "symbol":      symbol,
            "entry_price": entry,
            "quantity":    position["quantity"],
            "amount_usdt": position["amount_usdt"],
            "in_position": True,
        }

    def has_position(self, symbol: str) -> bool:
        return symbol in self.positions
