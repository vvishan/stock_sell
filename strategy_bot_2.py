import os
import time
import pytz
import yfinance as yf
import numpy as np
from datetime import datetime
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# ========= CONFIG =========
SYMBOLS = ["ICON", "PLDN", "IOTR"]
QTY_PER_STOCK = 5
RSI_THRESHOLD = 35
TARGET_PCT = 0.01
STOP_LOSS_PCT = 0.005
CHECK_INTERVAL = 30
TIMEZONE = pytz.timezone("US/Eastern")
FORCE_EXIT_HOUR = 15
FORCE_EXIT_MIN = 55
# ==========================

client = TradingClient(
    api_key=os.getenv("ALPACA_API_KEY"),
    secret_key=os.getenv("ALPACA_SECRET_KEY"),
    paper=True
)

# Track per-stock state
state = {
    symbol: {
        "bought": False,
        "entry_price": None
    } for symbol in SYMBOLS
}

# ---------- HELPERS ----------

def market_time_ok():
    now = datetime.now(TIMEZONE)
    return 10 <= now.hour < 16

def should_force_exit():
    now = datetime.now(TIMEZONE)
    return now.hour == FORCE_EXIT_HOUR and now.minute >= FORCE_EXIT_MIN

def get_intraday_data(symbol):
    return yf.Ticker(symbol).history(period="1d", interval="1m")

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    rs = gain.ewm(alpha=1/period, min_periods=period).mean() / \
         loss.ewm(alpha=1/period, min_periods=period).mean()
    return 100 - (100 / (1 + rs.iloc[-1]))
    # rs = gain.rolling(period).mean() / loss.rolling(period).mean()
    # return 100 - (100 / (1 + rs)).iloc[-1]

def buy(symbol, price):
    order = LimitOrderRequest(
        symbol=symbol,
        qty=QTY_PER_STOCK,
        limit_price=round(price, 2),
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY
    )
    client.submit_order(order)
    print(f"✅ BUY {symbol} @ {price:.2f}")

def sell(symbol, reason):
    order = MarketOrderRequest(
        symbol=symbol,
        qty=QTY_PER_STOCK,
        side=OrderSide.SELL,
        time_in_force=TimeInForce.DAY
    )
    client.submit_order(order)
    print(f"✅ SELL {symbol} ({reason})")

# ---------- MAIN LOOP ----------

print("🚀 Multi-Stock Intraday Bot Started")

while True:
    try:
        if not market_time_ok():
            print("⏳ Waiting for market hours...")
            time.sleep(300)
            continue

        for symbol in SYMBOLS:
            df = get_intraday_data(symbol)
            price = df["Close"].iloc[-1]
            day_low = df["Low"].min()
            vwap = (df["Close"] * df["Volume"]).sum() / df["Volume"].sum()
            rsi = calculate_rsi(df["Close"])

            print(f"{symbol} | Price={price:.2f} VWAP={vwap:.2f} RSI={rsi:.2f}")


            # ===== BUY =====
            if not state[symbol]["bought"]:
                if price >= vwap * 1.002 and rsi <= RSI_THRESHOLD:
                    entry = round(max(day_low, vwap) + 0.02, 2)
                    buy(symbol, entry)
                    state[symbol].update({"bought": True, "entry_price": entry})

            # ===== SELL =====
            else:
                entry = state[symbol]["entry_price"]
                target = entry * (1 + TARGET_PCT)
                stop = entry * (1 - STOP_LOSS_PCT)

                reason = (
                    "TARGET HIT" if price >= target else
                    "STOP LOSS HIT" if price <= stop else
                    "TIME EXIT" if should_force_exit() else
                    None
                )

                if reason:
                    sell(symbol, reason)
                    state[symbol]["bought"] = False            
            # # ---------- BUY ----------
            # if not state[symbol]["bought"]:
            #     if price <= vwap * 1.002 and rsi <= RSI_THRESHOLD:
            #         entry = round(max(day_low, vwap) + 0.02, 2)
            #         buy(symbol, entry)
            #         state[symbol]["bought"] = True
            #         state[symbol]["entry_price"] = entry

            # # ---------- SELL ----------
            # if state[symbol]["bought"]:
            #     entry = state[symbol]["entry_price"]
            #     target = entry * (1 + TARGET_PCT)
            #     stop = entry * (1 - STOP_LOSS_PCT)

            #     if price >= target:
            #         sell(symbol, "TARGET HIT")
            #         state[symbol]["bought"] = False

            #     elif price <= stop:
            #         sell(symbol, "STOP LOSS HIT")
            #         state[symbol]["bought"] = False

            #     elif should_force_exit():
            #         sell(symbol, "TIME EXIT")
            #         state[symbol]["bought"] = False

        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        print("⚠️ Error:", e)
        time.sleep(CHECK_INTERVAL)
