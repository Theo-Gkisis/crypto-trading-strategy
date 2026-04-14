import os
import logging
import requests
import hmac
import hashlib
import time
from dotenv import load_dotenv
from binance.client import Client

logging.basicConfig(level=logging.DEBUG)
load_dotenv("../.env")

KEY    = os.getenv("BINANCE_API_KEY")
SECRET = os.getenv("BINANCE_API_SECRET")
MODE   = os.getenv("TRADING_MODE")

print(f"=== BINANCE DEBUG TEST ===")
print(f"Trading Mode : {MODE}")
print(f"API Key      : {KEY}")
print(f"Secret (first 10): {SECRET[:10]}...")

# Test 1: Public endpoint (no auth)
print("\n--- Test 1: Public ping ---")
r = requests.get("https://api.binance.com/api/v3/ping")
print(f"Status: {r.status_code} | Response: {r.text}")

# Test 2: Server time vs local time
print("\n--- Test 2: Time sync ---")
r = requests.get("https://api.binance.com/api/v3/time")
server_time = r.json()["serverTime"]
local_time  = int(time.time() * 1000)
print(f"Server time : {server_time}")
print(f"Local time  : {local_time}")
print(f"Difference  : {server_time - local_time} ms")

# Test 3: Raw authenticated request
print("\n--- Test 3: Raw /api/v3/account ---")
ts     = server_time
query  = f"timestamp={ts}&recvWindow=60000"
sig    = hmac.new(SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
url    = f"https://api.binance.com/api/v3/account?{query}&signature={sig}"
r = requests.get(url, headers={"X-MBX-APIKEY": KEY})
print(f"Status: {r.status_code}")
print(f"Response: {r.text[:500]}")

# Test 4: python-binance Client (binance.com)
print("\n--- Test 4: binance.com ---")
try:
    client = Client(KEY, SECRET)
    account = client.get_account()
    balances = {b["asset"]: b["free"] for b in account["balances"] if float(b["free"]) > 0}
    print(f"✅ Balances: {balances}")
except Exception as e:
    print(f"❌ ERROR: {e}")

# Test 5: python-binance Client (binance.us)
print("\n--- Test 5: binance.US ---")
try:
    client_us = Client(KEY, SECRET, tld="us")
    account = client_us.get_account()
    balances = {b["asset"]: b["free"] for b in account["balances"] if float(b["free"]) > 0}
    print(f"✅ Balances: {balances}")
except Exception as e:
    print(f"❌ ERROR: {e}")