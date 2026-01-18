import os
import time
import pytz
import yfinance as yf
import pandas as pd
from datetime import datetime
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# ========= CONFIG =========
SYMBOL = "TME"
QTY = 10
RSI_THRESHOLD = 35
CHECK_INTERVAL = 15   # seconds
TIMEZONE = pytz.timezone("US/Eastern")
# ==========================

client = TradingClient(
    api_key=os.getenv("ALPACA_API_KEY"),
    secret_key=os.getenv("ALPACA_SECRET_KEY"),
    paper=True
)

def market_time_ok():
    now = datetime.now(TIMEZONE)
    return now.hour >= 10  # trade only after 10 AM ET

def get_intraday_data(symbol):
    df = yf.Ticker(symbol).history(period="1d", interval="1m")
    return df

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def place_limit_buy(price):
    order = LimitOrderRequest(
        symbol=SYMBOL,
        qty=QTY,
        limit_price=round(price, 2),
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY
    )
    client.submit_order(order)
    print(f"✅ LIMIT BUY PLACED at {price:.2f}")

print("🚀 Intraday BUY strategy started")

while True:
    try:
        if not market_time_ok():
            print("⏳ Waiting for 10:00 AM ET...")
            time.sleep(300)
            continue

        df = get_intraday_data(SYMBOL)
        price = df["Close"].iloc[-1]
        day_low = df["Low"].min()
        vwap = (df["Close"] * df["Volume"]).sum() / df["Volume"].sum()
        rsi = calculate_rsi(df["Close"])

        print(f"Price={price:.2f} | DayLow={day_low:.2f} | VWAP={vwap:.2f} | RSI={rsi:.2f}")

        # BUY CONDITIONS
        if price <= vwap * 1.002 and rsi <= RSI_THRESHOLD:
            buy_price = max(day_low, vwap) + 0.02
            place_limit_buy(buy_price)
            break

        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        print("⚠️ Error:", e)
        time.sleep(CHECK_INTERVAL)

print("🛑 BUY logic finished")
