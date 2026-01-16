import os
import time
import yfinance as yf
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from marketopen import is_market_open

# ========= CONFIG =========
SYMBOL = "GBX"
QTY = 5
ENTRY_PRICE = 49.30
TARGET_PRICE = 49.40
TRAILING_STOP_PCT = 0.02    # 5%
MAX_LOSS_PCT = 0.05         # 10%
CHECK_INTERVAL = 15         # seconds
# ==========================

client = TradingClient(
    api_key = os.getenv("ALPACA_API_KEY"),
    secret_key = os.getenv("ALPACA_SECRET_KEY"),
    paper=True
)

highest_price = ENTRY_PRICE
sold = False

def get_current_price(symbol):
    data = yf.Ticker(symbol).history(period="1d", interval="1m")
    return data["Close"].iloc[-1]

def should_sell(price, highest_price):
    trailing_stop = highest_price * (1 - TRAILING_STOP_PCT)
    max_loss_price = ENTRY_PRICE * (1 - MAX_LOSS_PCT)

    if price >= TARGET_PRICE:
        return True, "TARGET HIT"
    if price <= trailing_stop:
        return True, "TRAILING STOP HIT"
    if price <= max_loss_price:
        return True, "MAX LOSS HIT"

    return False, "HOLD"

def sell_stock():
    order = MarketOrderRequest(
        symbol=SYMBOL,
        qty=QTY,
        side=OrderSide.SELL,
        time_in_force=TimeInForce.GTC
    )
    client.submit_order(order)
    print("✅ SELL ORDER PLACED")

print("🚀 Strategy started... monitoring price")
MAX_RETRIES = 5
retries = 0
while not sold:
    try:
        if not is_market_open():
            print("⏸️ Market closed. Waiting...")
            time.sleep(20)  # check again in 5 minutes
            continue
        price = get_current_price(SYMBOL)
        highest_price = max(highest_price, price)

        sell, reason = should_sell(price, highest_price)

        print(f"Price: {price:.2f} | High: {highest_price:.2f} | Status: {reason}")

        if sell:
            print(f"🔔 SELL SIGNAL: {reason}")
            sell_stock()
            sold = True
            break
        retries = 0
        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        print("⚠️ Error:", e)
        retries += 1
        if retries >= MAX_RETRIES:
            print("❌ Too many errors. Exiting bot.")
            break
        time.sleep(CHECK_INTERVAL)

print("🛑 Strategy finished. Exiting.")
