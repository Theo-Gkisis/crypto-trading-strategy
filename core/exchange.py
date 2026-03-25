import ccxt
import logging
from config.settings import (
    BINANCE_API_KEY,
    BINANCE_API_SECRET,
    USE_TESTNET
)

logger = logging.getLogger(__name__)


class Exchange:
    """
    Διαχειρίζεται όλη την επικοινωνία με τη Binance.
    Χρησιμοποιεί τη βιβλιοθήκη ccxt.
    """

    def __init__(self):
        self.client = ccxt.binance({
            "apiKey": BINANCE_API_KEY,
            "secret": BINANCE_API_SECRET,
            "enableRateLimit": True,   # Σέβεται τα limits της Binance
            "options": {
                "defaultType": "spot",  # Spot trading (όχι futures)
            }
        })

        # Testnet: δοκιμαστικό περιβάλλον με ψεύτικα χρήματα
        if USE_TESTNET:
            self.client.set_sandbox_mode(True)
            logger.info("🧪 Testnet mode ενεργό — χρησιμοποιούνται ψεύτικα χρήματα")
        else:
            logger.info("🚀 Live mode ενεργό — χρησιμοποιούνται ΑΛΗΘΙΝΑ χρήματα")

        self._load_markets()

    # ----------------------------------------------------------
    # ΑΡΧΙΚΟΠΟΙΗΣΗ
    # ----------------------------------------------------------

    def _load_markets(self):
        """Φορτώνει τα διαθέσιμα pairs από τη Binance."""
        try:
            self.client.load_markets()
            logger.info("✅ Σύνδεση με Binance επιτυχής")
        except Exception as e:
            logger.error(f"❌ Αποτυχία σύνδεσης με Binance: {e}")
            raise

    # ----------------------------------------------------------
    # ΥΠΟΛΟΙΠΟ
    # ----------------------------------------------------------

    def get_balance(self, currency: str = "USDT") -> float:
        """
        Επιστρέφει το διαθέσιμο υπόλοιπο σε USDT (ή άλλο νόμισμα).

        Παράδειγμα: get_balance("USDT") → 95.50
        """
        try:
            balance = self.client.fetch_balance()
            available = balance["free"].get(currency, 0.0)
            logger.debug(f"Υπόλοιπο {currency}: {available}")
            return float(available)
        except Exception as e:
            logger.error(f"❌ Σφάλμα ανάκτησης υπολοίπου: {e}")
            return 0.0

    def get_all_balances(self) -> dict:
        """Επιστρέφει όλα τα υπόλοιπα (μόνο αυτά > 0)."""
        try:
            balance = self.client.fetch_balance()
            return {
                currency: amount
                for currency, amount in balance["free"].items()
                if float(amount) > 0
            }
        except Exception as e:
            logger.error(f"❌ Σφάλμα ανάκτησης υπολοίπων: {e}")
            return {}

    # ----------------------------------------------------------
    # ΤΙΜΕΣ
    # ----------------------------------------------------------

    def get_price(self, symbol: str) -> float:
        """
        Επιστρέφει την τρέχουσα τιμή ενός pair.

        Παράδειγμα: get_price("BTC/USDT") → 83500.0
        """
        try:
            ticker = self.client.fetch_ticker(symbol)
            return float(ticker["last"])
        except Exception as e:
            logger.error(f"❌ Σφάλμα ανάκτησης τιμής {symbol}: {e}")
            return 0.0

    def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 200) -> list:
        """
        Επιστρέφει ιστορικά κεριά (OHLCV).

        OHLCV = Open, High, Low, Close, Volume
        Παράδειγμα: get_ohlcv("BTC/USDT", "1h", 200)
        → τελευταία 200 ωριαία κεριά του Bitcoin
        """
        try:
            ohlcv = self.client.fetch_ohlcv(symbol, timeframe, limit=limit)
            logger.debug(f"✅ {len(ohlcv)} κεριά για {symbol} ({timeframe})")
            return ohlcv
        except Exception as e:
            logger.error(f"❌ Σφάλμα ανάκτησης OHLCV {symbol}: {e}")
            return []

    # ----------------------------------------------------------
    # ORDERS
    # ----------------------------------------------------------

    def place_buy_order(self, symbol: str, amount_usdt: float) -> dict | None:
        """
        Κάνει αγορά (market order) αξίας amount_usdt USDT.

        Παράδειγμα: place_buy_order("BTC/USDT", 10)
        → Αγοράζει $10 αξίας Bitcoin στην τρέχουσα τιμή
        """
        try:
            price = self.get_price(symbol)
            if price == 0:
                return None

            # Υπολογισμός ποσότητας σε crypto
            quantity = amount_usdt / price
            quantity = self._round_quantity(symbol, quantity)

            order = self.client.create_market_buy_order(symbol, quantity)
            logger.info(f"✅ BUY {symbol}: ${amount_usdt} @ ${price:.2f}")
            return order

        except Exception as e:
            logger.error(f"❌ Σφάλμα buy order {symbol}: {e}")
            return None

    def place_sell_order(self, symbol: str, quantity: float) -> dict | None:
        """
        Πουλάει συγκεκριμένη ποσότητα crypto.

        Παράδειγμα: place_sell_order("BTC/USDT", 0.00012)
        → Πουλάει 0.00012 BTC
        """
        try:
            price = self.get_price(symbol)
            quantity = self._round_quantity(symbol, quantity)

            order = self.client.create_market_sell_order(symbol, quantity)
            logger.info(f"✅ SELL {symbol}: {quantity} @ ${price:.2f}")
            return order

        except Exception as e:
            logger.error(f"❌ Σφάλμα sell order {symbol}: {e}")
            return None

    def place_limit_buy_order(self, symbol: str, quantity: float, price: float) -> dict | None:
        """
        Βάζει limit buy order — αγοράζει ΜΟΝΟ αν η τιμή φτάσει στο price.
        Χρησιμοποιείται από το Grid Trading.
        """
        try:
            quantity = self._round_quantity(symbol, quantity)
            price    = self._round_price(symbol, price)

            order = self.client.create_limit_buy_order(symbol, quantity, price)
            logger.info(f"📋 LIMIT BUY {symbol}: {quantity} @ ${price:.2f}")
            return order

        except Exception as e:
            logger.error(f"❌ Σφάλμα limit buy {symbol}: {e}")
            return None

    def place_limit_sell_order(self, symbol: str, quantity: float, price: float) -> dict | None:
        """
        Βάζει limit sell order — πουλάει ΜΟΝΟ αν η τιμή φτάσει στο price.
        Χρησιμοποιείται από το Grid Trading.
        """
        try:
            quantity = self._round_quantity(symbol, quantity)
            price    = self._round_price(symbol, price)

            order = self.client.create_limit_sell_order(symbol, quantity, price)
            logger.info(f"📋 LIMIT SELL {symbol}: {quantity} @ ${price:.2f}")
            return order

        except Exception as e:
            logger.error(f"❌ Σφάλμα limit sell {symbol}: {e}")
            return None

    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Ακυρώνει ένα ανοιχτό order."""
        try:
            self.client.cancel_order(order_id, symbol)
            logger.info(f"🚫 Order {order_id} ακυρώθηκε")
            return True
        except Exception as e:
            logger.error(f"❌ Σφάλμα ακύρωσης order {order_id}: {e}")
            return False

    def get_open_orders(self, symbol: str) -> list:
        """Επιστρέφει όλα τα ανοιχτά orders για ένα pair."""
        try:
            return self.client.fetch_open_orders(symbol)
        except Exception as e:
            logger.error(f"❌ Σφάλμα ανάκτησης open orders {symbol}: {e}")
            return []

    def cancel_all_orders(self, symbol: str) -> int:
        """Ακυρώνει όλα τα ανοιχτά orders. Επιστρέφει πόσα ακυρώθηκαν."""
        orders = self.get_open_orders(symbol)
        cancelled = 0
        for order in orders:
            if self.cancel_order(order["id"], symbol):
                cancelled += 1
        logger.info(f"🚫 Ακυρώθηκαν {cancelled} orders για {symbol}")
        return cancelled

    # ----------------------------------------------------------
    # ΒΟΗΘΗΤΙΚΕΣ ΣΥΝΑΡΤΗΣΕΙΣ
    # ----------------------------------------------------------

    def _round_quantity(self, symbol: str, quantity: float) -> float:
        """
        Στρογγυλοποιεί την ποσότητα στα decimal places που δέχεται η Binance.
        Η Binance δεν δέχεται π.χ. 0.000123456789 BTC — έχει συγκεκριμένα limits.
        """
        try:
            market = self.client.market(symbol)
            precision = market["precision"]["amount"]
            return float(self.client.amount_to_precision(symbol, quantity))
        except Exception:
            return round(quantity, 6)

    def _round_price(self, symbol: str, price: float) -> float:
        """Στρογγυλοποιεί την τιμή στα decimal places που δέχεται η Binance."""
        try:
            return float(self.client.price_to_precision(symbol, price))
        except Exception:
            return round(price, 2)

    def is_connected(self) -> bool:
        """Ελέγχει αν η σύνδεση με τη Binance είναι ενεργή."""
        try:
            self.client.fetch_time()
            return True
        except Exception:
            return False
