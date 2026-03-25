"""
Γρήγορο test για να επαληθεύσουμε ότι όλες οι βιβλιοθήκες
και τα modules φορτώνουν σωστά.
Δεν χρειάζεται σύνδεση με Binance.
"""
import sys

print("=" * 50)
print("  TRADING BOT - TEST SETUP")
print("=" * 50)

# Test 1: Βιβλιοθήκες
print("\n[1] Έλεγχος βιβλιοθηκών...")
try:
    import ccxt
    print(f"  ✅ ccxt {ccxt.__version__}")
except ImportError as e:
    print(f"  ❌ ccxt: {e}")

try:
    import pandas as pd
    print(f"  ✅ pandas {pd.__version__}")
except ImportError as e:
    print(f"  ❌ pandas: {e}")

try:
    import numpy as np
    print(f"  ✅ numpy {np.__version__}")
except ImportError as e:
    print(f"  ❌ numpy: {e}")

try:
    import ta
    print(f"  ✅ ta (technical indicators)")
except ImportError as e:
    print(f"  ❌ ta: {e}")

try:
    import sqlalchemy
    print(f"  ✅ SQLAlchemy {sqlalchemy.__version__}")
except ImportError as e:
    print(f"  ❌ SQLAlchemy: {e}")

try:
    import telegram
    print(f"  ✅ python-telegram-bot {telegram.__version__}")
except ImportError as e:
    print(f"  ❌ python-telegram-bot: {e}")

try:
    import dotenv
    print(f"  ✅ python-dotenv")
except ImportError as e:
    print(f"  ❌ python-dotenv: {e}")

# Test 2: Config
print("\n[2] Έλεγχος config...")
try:
    from config.settings import (
        TOTAL_CAPITAL, TRADING_PAIRS, TIMEFRAME,
        GRID_LEVELS, RSI_PERIOD, EMA_FAST, EMA_SLOW
    )
    print(f"  ✅ Config φορτώθηκε")
    print(f"     Κεφάλαιο : ${TOTAL_CAPITAL}")
    print(f"     Pairs    : {TRADING_PAIRS}")
    print(f"     Timeframe: {TIMEFRAME}")
    print(f"     Grid     : {GRID_LEVELS} επίπεδα")
    print(f"     EMA      : {EMA_FAST}/{EMA_SLOW}")
    print(f"     RSI      : {RSI_PERIOD} περίοδοι")
except Exception as e:
    print(f"  ❌ Config: {e}")

# Test 3: ccxt Binance (χωρίς API keys)
print("\n[3] Έλεγχος Binance connection...")
try:
    exchange = ccxt.binance()
    markets = exchange.load_markets()
    btc_price = exchange.fetch_ticker("BTC/USDT")["last"]
    eth_price = exchange.fetch_ticker("ETH/USDT")["last"]
    print(f"  ✅ Binance συνδέθηκε (public API)")
    print(f"     BTC/USDT: ${btc_price:,.2f}")
    print(f"     ETH/USDT: ${eth_price:,.2f}")
except Exception as e:
    print(f"  ❌ Binance: {e}")

print("\n" + "=" * 50)
print("  Test ολοκληρώθηκε!")
print("=" * 50)
