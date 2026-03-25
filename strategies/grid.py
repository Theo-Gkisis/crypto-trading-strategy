import logging
from core.exchange import Exchange
from core.risk import RiskManager
from database.models import Database
from config.settings import (
    GRID_LEVELS,
    GRID_SPREAD,
    GRID_ORDER_AMOUNT,
)

logger = logging.getLogger(__name__)


class GridStrategy:
    """
    Grid Trading Strategy.

    Λογική:
      Μοιράζει το κεφάλαιο σε πολλά μικρά buy/sell orders
      σε ένα εύρος τιμών (grid). Κερδίζει από κάθε κίνηση
      πάνω-κάτω της αγοράς.

    Παράδειγμα BTC @ $71,000, spread 1%, 5 επίπεδα:
      SELL $73,955  ← πουλάει εδώ (κέρδος)
      SELL $72,669
      SELL $71,393  ← τρέχουσα τιμή
      BUY  $70,679  ← αγοράζει εδώ
      BUY  $69,979
      BUY  $69,279
    """

    def __init__(self, exchange: Exchange, risk: RiskManager, db=None, telegram=None):
        self.exchange    = exchange
        self.risk        = risk
        self.db          = db
        self.telegram    = telegram
        self.active_grids = {}   # symbol → grid info

    # ----------------------------------------------------------
    # ΔΗΜΙΟΥΡΓΙΑ GRID
    # ----------------------------------------------------------

    def create_grid(self, symbol: str, current_price: float,
                    capital: float, atr: float) -> dict:
        """
        Υπολογίζει και δημιουργεί το grid για ένα pair.

        Βήματα:
          1. Υπολογίζει το spread βάσει ATR
          2. Δημιουργεί τα επίπεδα πάνω και κάτω
          3. Βάζει limit orders σε κάθε επίπεδο
        """
        # Δυναμικό spread βάσει ATR (πιο volatile = πιο φαρδύ grid)
        atr_pct = atr / current_price
        spread  = max(atr_pct * 0.5, GRID_SPREAD)  # Τουλάχιστον 1%
        spread  = min(spread, 0.03)                  # Μέγιστο 3%

        # Ποσό ανά order
        order_amount = self.risk.get_grid_order_amount(capital, GRID_LEVELS)

        # Υπολογισμός επιπέδων
        buy_levels  = []
        sell_levels = []

        for i in range(1, GRID_LEVELS + 1):
            buy_price  = current_price * (1 - spread * i)
            sell_price = current_price * (1 + spread * i)
            buy_levels.append(round(buy_price, 2))
            sell_levels.append(round(sell_price, 2))

        grid_info = {
            "symbol":        symbol,
            "center_price":  current_price,
            "spread":        spread,
            "order_amount":  order_amount,
            "buy_levels":    buy_levels,
            "sell_levels":   sell_levels,
            "buy_orders":    [],   # order IDs που δημιουργήθηκαν
            "sell_orders":   [],
            "total_invested": 0.0,
            "total_profit":   0.0,
            "trades_count":   0,
        }

        logger.info(
            f"Grid created: {symbol} @ ${current_price:,.2f} | "
            f"Spread: {spread:.1%} | Levels: {GRID_LEVELS} | "
            f"Per order: ${order_amount}"
        )
        self._log_grid(grid_info)

        return grid_info

    def place_grid_orders(self, grid_info: dict) -> dict:
        """
        Βάζει τα limit orders στη Binance για κάθε επίπεδο.
        """
        symbol       = grid_info["symbol"]
        order_amount = grid_info["order_amount"]
        price        = grid_info["center_price"]

        # BUY orders (κάτω από την τρέχουσα τιμή)
        for buy_price in grid_info["buy_levels"]:
            ok, msg = self.risk.can_trade(order_amount, f"Grid BUY {symbol} @ {buy_price}")
            if not ok:
                logger.warning(f"Grid BUY skipped: {msg}")
                continue

            quantity = order_amount / buy_price
            order = self.exchange.place_limit_buy_order(symbol, quantity, buy_price)

            if order:
                grid_info["buy_orders"].append({
                    "id":       order["id"],
                    "price":    buy_price,
                    "quantity": quantity,
                    "amount":   order_amount,
                })
                grid_info["total_invested"] += order_amount

        # SELL orders (πάνω από την τρέχουσα τιμή)
        # Για τα sell orders χρειαζόμαστε να έχουμε ήδη crypto
        # Τα βάζουμε μόνο αν έχουμε αρκετό balance
        balance = self.exchange.get_balance(symbol.split("/")[0])  # π.χ. "BTC"
        crypto_per_level = (order_amount / price) if price > 0 else 0

        if balance >= crypto_per_level * len(grid_info["sell_levels"]):
            for sell_price in grid_info["sell_levels"]:
                quantity = order_amount / sell_price
                order = self.exchange.place_limit_sell_order(symbol, quantity, sell_price)

                if order:
                    grid_info["sell_orders"].append({
                        "id":       order["id"],
                        "price":    sell_price,
                        "quantity": quantity,
                        "amount":   order_amount,
                    })
        else:
            logger.info(f"Δεν υπάρχει αρκετό {symbol.split('/')[0]} για sell orders — μόνο buy orders")

        self.active_grids[symbol] = grid_info

        logger.info(
            f"Grid orders placed: {symbol} | "
            f"BUY: {len(grid_info['buy_orders'])} | "
            f"SELL: {len(grid_info['sell_orders'])} | "
            f"Invested: ${grid_info['total_invested']:.2f}"
        )

        return grid_info

    # ----------------------------------------------------------
    # ΠΑΡΑΚΟΛΟΥΘΗΣΗ & ΑΝΑΝΕΩΣΗ
    # ----------------------------------------------------------

    def check_and_refresh(self, symbol: str, current_price: float,
                          capital: float, atr: float) -> dict:
        """
        Κύρια συνάρτηση που καλείται κάθε ώρα.

        Ελέγχει αν χρειάζεται να ανανεωθεί το grid:
          - Αν η τιμή βγήκε εκτός range → νέο grid
          - Αν εκτελέστηκε κάποιο order → βάλε νέο
        """
        if symbol not in self.active_grids:
            # Πρώτη φορά → δημιούργησε grid
            logger.info(f"Νέο grid για {symbol}")
            grid = self.create_grid(symbol, current_price, capital, atr)
            return self.place_grid_orders(grid)

        grid = self.active_grids[symbol]

        # Έλεγχος αν η τιμή βγήκε εκτός grid range
        lowest_buy   = min(grid["buy_levels"])
        highest_sell = max(grid["sell_levels"])

        if current_price < lowest_buy or current_price > highest_sell:
            logger.info(
                f"Τιμή ${current_price:,.2f} εκτός grid range "
                f"[${lowest_buy:,.2f} - ${highest_sell:,.2f}] → Ανανέωση grid"
            )
            # Ακύρωσε όλα τα παλιά orders
            self.cancel_grid(symbol)
            # Δημιούργησε νέο grid στην τρέχουσα τιμή
            grid = self.create_grid(symbol, current_price, capital, atr)
            return self.place_grid_orders(grid)

        # Έλεγχος εκτελεσμένων orders
        self._check_filled_orders(symbol, current_price)

        return grid

    def _check_filled_orders(self, symbol: str, current_price: float):
        """
        Ελέγχει αν εκτελέστηκε κάποιο order και βάζει νέο αντίθετο.

        Λογική grid:
          Αν εκτελέστηκε BUY @ $70,000 → βάλε SELL @ $70,700 (+1%)
          Αν εκτελέστηκε SELL @ $72,000 → βάλε BUY @ $71,280 (-1%)
        """
        grid = self.active_grids[symbol]
        open_orders = self.exchange.get_open_orders(symbol)
        open_ids    = {o["id"] for o in open_orders}

        # Έλεγχος buy orders
        filled_buys = [o for o in grid["buy_orders"] if o["id"] not in open_ids]
        for order in filled_buys:
            profit_price = order["price"] * (1 + grid["spread"])
            new_order    = self.exchange.place_limit_sell_order(
                symbol, order["quantity"], profit_price
            )
            if new_order:
                estimated_profit = order["quantity"] * (profit_price - order["price"])
                grid["sell_orders"].append({
                    "id":       new_order["id"],
                    "price":    profit_price,
                    "quantity": order["quantity"],
                    "amount":   order["amount"],
                })
                grid["trades_count"] += 1
                if self.db:
                    self.db.save_trade(
                        symbol=symbol, side="buy", strategy="grid",
                        price=order["price"], quantity=order["quantity"],
                        amount=order["amount"]
                    )
                if self.telegram:
                    self.telegram.trade_opened(symbol, "BUY", order["price"], order["amount"], "Grid")
                logger.info(
                    f"BUY filled @ ${order['price']:,.2f} → "
                    f"SELL set @ ${profit_price:,.2f} | "
                    f"Expected profit: ${estimated_profit:.3f}"
                )
            grid["buy_orders"].remove(order)

        # Έλεγχος sell orders
        filled_sells = [o for o in grid["sell_orders"] if o["id"] not in open_ids]
        for order in filled_sells:
            buy_back_price = order["price"] * (1 - grid["spread"])
            quantity       = order["amount"] / buy_back_price
            new_order      = self.exchange.place_limit_buy_order(
                symbol, quantity, buy_back_price
            )
            if new_order:
                profit = order["quantity"] * (order["price"] - buy_back_price)
                grid["total_profit"] += profit
                grid["buy_orders"].append({
                    "id":       new_order["id"],
                    "price":    buy_back_price,
                    "quantity": quantity,
                    "amount":   order["amount"],
                })
                grid["trades_count"] += 1
                self.risk.record_trade_result(profit)
                if self.db:
                    self.db.save_trade(
                        symbol=symbol, side="sell", strategy="grid",
                        price=order["price"], quantity=order["quantity"],
                        amount=order["amount"], pnl=profit
                    )
                if self.telegram:
                    self.telegram.trade_closed(symbol, order["price"] * (1 - grid["spread"]), order["price"], profit, "Grid")
                logger.info(
                    f"SELL filled @ ${order['price']:,.2f} | "
                    f"Profit: +${profit:.3f} | "
                    f"Total profit: +${grid['total_profit']:.3f}"
                )
            grid["sell_orders"].remove(order)

    # ----------------------------------------------------------
    # ΑΚΥΡΩΣΗ
    # ----------------------------------------------------------

    def cancel_grid(self, symbol: str):
        """Ακυρώνει όλα τα orders και καθαρίζει το grid."""
        cancelled = self.exchange.cancel_all_orders(symbol)
        if symbol in self.active_grids:
            del self.active_grids[symbol]
        logger.info(f"Grid cancelled: {symbol} | {cancelled} orders ακυρώθηκαν")

    def cancel_all_grids(self):
        """Emergency stop — ακυρώνει όλα τα grids."""
        for symbol in list(self.active_grids.keys()):
            self.cancel_grid(symbol)
        logger.warning("ALL GRIDS CANCELLED")

    # ----------------------------------------------------------
    # ΣΤΑΤΙΣΤΙΚΑ
    # ----------------------------------------------------------

    def get_stats(self, symbol: str) -> dict:
        """Επιστρέφει στατιστικά του grid για ένα pair."""
        if symbol not in self.active_grids:
            return {}

        grid = self.active_grids[symbol]
        return {
            "symbol":         symbol,
            "center_price":   grid["center_price"],
            "buy_orders":     len(grid["buy_orders"]),
            "sell_orders":    len(grid["sell_orders"]),
            "total_invested": round(grid["total_invested"], 2),
            "total_profit":   round(grid["total_profit"], 4),
            "trades_count":   grid["trades_count"],
        }

    def _log_grid(self, grid: dict):
        """Εκτυπώνει το grid για debugging."""
        logger.info(f"  Grid levels για {grid['symbol']}:")
        for price in reversed(grid["sell_levels"]):
            logger.info(f"    SELL @ ${price:,.2f}")
        logger.info(f"    --- τρέχουσα τιμή @ ${grid['center_price']:,.2f} ---")
        for price in grid["buy_levels"]:
            logger.info(f"    BUY  @ ${price:,.2f}")
