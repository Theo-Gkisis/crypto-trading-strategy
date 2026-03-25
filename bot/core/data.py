import pandas as pd
import numpy as np
import logging
from core.exchange import Exchange
from config.settings import (
    TIMEFRAME, RSI_PERIOD, EMA_FAST, EMA_SLOW
)

logger = logging.getLogger(__name__)


class DataManager:
    """
    Παίρνει ιστορικά κεριά από τη Binance και υπολογίζει
    τους τεχνικούς δείκτες (RSI, EMA) που χρειάζονται
    οι στρατηγικές για να πάρουν αποφάσεις.
    """

    def __init__(self, exchange: Exchange):
        self.exchange = exchange

    # ----------------------------------------------------------
    # ΒΑΣΙΚΑ ΔΕΔΟΜΕΝΑ
    # ----------------------------------------------------------

    def get_candles(self, symbol: str, timeframe: str = None, limit: int = 200) -> pd.DataFrame:
        """
        Επιστρέφει DataFrame με τα κεριά (OHLCV) ενός pair.

        Κάθε γραμμή = 1 κερί (π.χ. 1 ώρα)
        Στήλες: timestamp, open, high, low, close, volume
        """
        tf = timeframe or TIMEFRAME
        raw = self.exchange.get_ohlcv(symbol, tf, limit)

        if not raw:
            logger.warning(f"Δεν ελήφθησαν δεδομένα για {symbol}")
            return pd.DataFrame()

        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)

        # Μετατροπή σε αριθμούς
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col])

        logger.debug(f"Ελήφθησαν {len(df)} κεριά για {symbol} ({tf})")
        return df

    # ----------------------------------------------------------
    # ΤΕΧΝΙΚΟΙ ΔΕΙΚΤΕΣ
    # ----------------------------------------------------------

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Προσθέτει όλους τους δείκτες στο DataFrame.
        Καλείται πάντα πριν από τις στρατηγικές.
        """
        if df.empty:
            return df

        df = df.copy()
        df = self._add_rsi(df)
        df = self._add_ema(df)
        df = self._add_bollinger_bands(df)
        df = self._add_atr(df)
        return df

    def _add_rsi(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        RSI (Relative Strength Index) — δείκτης δύναμης αγοράς.

        Τιμές:
          > 70 → overbought (πολύ ακριβό, πιθανή πτώση)
          < 30 → oversold   (πολύ φθηνό, πιθανή άνοδος)
          < 25 → crash zone (ενεργοποίηση DCA)
        """
        period = RSI_PERIOD
        delta  = df["close"].diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

        rs         = avg_gain / avg_loss
        df["rsi"]  = 100 - (100 / (1 + rs))

        return df

    def _add_ema(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        EMA (Exponential Moving Average) — κινητός μέσος όρος.

        Χρήση:
          EMA20 > EMA50 → uptrend  (ανοδική τάση → Trend Following mode)
          EMA20 < EMA50 → downtrend (καθοδική τάση → Grid mode ή DCA)
        """
        df[f"ema_{EMA_FAST}"] = df["close"].ewm(span=EMA_FAST, adjust=False).mean()
        df[f"ema_{EMA_SLOW}"] = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()
        return df

    def _add_bollinger_bands(self, df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        """
        Bollinger Bands — δείχνουν αν η τιμή είναι εκτός του κανονικού εύρους.

        Χρήση:
          Τιμή < BB_lower → oversold  (κοντά στο κάτω όριο)
          Τιμή > BB_upper → overbought (κοντά στο πάνω όριο)
          BB_width → πόσο "volatile" είναι η αγορά
        """
        sma = df["close"].rolling(period).mean()
        std = df["close"].rolling(period).std()

        df["bb_upper"]  = sma + (2 * std)
        df["bb_middle"] = sma
        df["bb_lower"]  = sma - (2 * std)
        df["bb_width"]  = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]

        return df

    def _add_atr(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        ATR (Average True Range) — μετράει την volatility της αγοράς.

        Χρήση στο Grid Trading:
          Υψηλό ATR → μεγάλες κινήσεις → αυξάνουμε το grid spread
          Χαμηλό ATR → μικρές κινήσεις → μικρότερο grid spread
        """
        high_low   = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close  = (df["low"] - df["close"].shift()).abs()

        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"]  = true_range.ewm(span=period, adjust=False).mean()

        return df

    # ----------------------------------------------------------
    # ΑΝΑΛΥΣΗ ΑΓΟΡΑΣ
    # ----------------------------------------------------------

    def get_market_state(self, symbol: str) -> dict:
        """
        Αναλύει την τρέχουσα κατάσταση της αγοράς και επιστρέφει
        ένα dict με όλες τις πληροφορίες που χρειάζονται οι στρατηγικές.

        Επιστρέφει:
          {
            "symbol":     "BTC/USDT",
            "price":      83500.0,
            "rsi":        45.2,
            "ema_fast":   83200.0,
            "ema_slow":   82100.0,
            "trend":      "up" / "down" / "sideways",
            "mode":       "grid" / "trend" / "dca",
            "bb_upper":   85000.0,
            "bb_lower":   80000.0,
            "atr":        450.0,
            "candles":    DataFrame
          }
        """
        df = self.get_candles(symbol)
        if df.empty:
            return {}

        df = self.add_indicators(df)
        latest = df.iloc[-1]   # Τελευταίο (τρέχον) κερί

        price    = float(latest["close"])
        rsi      = float(latest["rsi"])
        ema_fast = float(latest[f"ema_{EMA_FAST}"])
        ema_slow = float(latest[f"ema_{EMA_SLOW}"])
        atr      = float(latest["atr"])

        # --- Καθορισμός τάσης ---
        ema_diff_pct = (ema_fast - ema_slow) / ema_slow * 100

        if ema_diff_pct > 0.5:
            trend = "up"
        elif ema_diff_pct < -0.5:
            trend = "down"
        else:
            trend = "sideways"

        # --- Καθορισμός mode ---
        if rsi < 25:
            mode = "dca"          # Crash → αγορά με DCA
        elif trend == "up":
            mode = "trend"        # Uptrend → Trend Following
        else:
            mode = "grid"         # Sideways/down → Grid Trading

        state = {
            "symbol":     symbol,
            "price":      price,
            "rsi":        round(rsi, 2),
            "ema_fast":   round(ema_fast, 2),
            "ema_slow":   round(ema_slow, 2),
            "ema_diff":   round(ema_diff_pct, 3),
            "trend":      trend,
            "mode":       mode,
            "bb_upper":   round(float(latest["bb_upper"]), 2),
            "bb_middle":  round(float(latest["bb_middle"]), 2),
            "bb_lower":   round(float(latest["bb_lower"]), 2),
            "bb_width":   round(float(latest["bb_width"]), 4),
            "atr":        round(atr, 2),
            "candles":    df,
        }

        logger.info(
            f"{symbol} | Price: ${price:,.2f} | RSI: {rsi:.1f} | "
            f"Trend: {trend} | Mode: {mode}"
        )

        return state
