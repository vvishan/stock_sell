import os
import time
import pytz
import yfinance as yf
from datetime import datetime
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# ========= CONFIG =========
SYMBOLS = ["ASM", "NVAX"]
QTY = 10

RSI_SHORT = 65
TARGET_PCT = 0.01
STOP_LOSS_PCT = 0.005

CHECK_INTERVAL = 15
REENTRY_COOLDOWN = 180  # seconds

TIMEZONE = pytz.timezone("US/Eastern")
FORCE_EXIT_HOUR = 15
FORCE_EXIT_MIN = 55
# ==========================

client = TradingClient(
    api_key=os.getenv("ALPACA_API_KEY"),
    secret_key=os.getenv("ALPACA_SECRET_KEY"),
    paper=True
)

# Track state per symbol
state = {
    s: {
        "in_position": False,
        "entry_price": None,
        "last_exit_time": 0
    } for s in SYMBOLS
}

# Track daily summary
summary = {
    s: {
        "trades": 0,
        "total_pnl": 0.0
    } for s in SYMBOLS
}

# ---------- HELPERS ----------

def market_time_ok():
    now = datetime.now(TIMEZONE)
    return (now.hour > 9 or (now.hour == 9 and now.minute >= 45)) and now.hour < 15

def should_force_exit():
    now = datetime.now(TIMEZONE)
    return now.hour == FORCE_EXIT_HOUR and now.minute >= FORCE_EXIT_MIN

def get_data(symbol):
    return yf.Ticker(symbol).history(period="1d", interval="1m")

def calculate_rsi(series, period=14):
    delta = series.diff().dropna()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()

    if avg_loss.iloc[-1] == 0:
        return 100.0

    rs = avg_gain.iloc[-1] / avg_loss.iloc[-1]
    return 100 - (100 / (1 + rs))

def print_pnl(symbol, entry, exit_price, qty, reason):
    pnl = (entry - exit_price) * qty  # SHORT formula
    status = "🟢 PROFIT" if pnl > 0 else "🔴 LOSS"
    print(
        f"{status} | {symbol} | "
        f"Entry={entry:.2f} Exit={exit_price:.2f} "
        f"Qty={qty} P/L={pnl:.2f} USD | {reason}"
    )
    # Update daily summary
    summary[symbol]["trades"] += 1
    summary[symbol]["total_pnl"] += pnl

def print_daily_summary():
    print("\n📊 DAILY SUMMARY")
    net_total = 0
    for symbol in SYMBOLS:
        trades = summary[symbol]["trades"]
        total_pnl = summary[symbol]["total_pnl"]
        net_total += total_pnl
        print(f"{symbol}: Trades={trades} | Total P/L={total_pnl:.2f} USD")
    print(f"💰 NET TOTAL P/L = {net_total:.2f} USD\n")

# ---------- ORDERS ----------

def open_short(symbol, price):
    client.submit_order(
        LimitOrderRequest(
            symbol=symbol,
            qty=QTY,
            limit_price=round(price, 2),
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )
    )
    print(f"🔴 SHORT {symbol} @ {price:.2f}")

def close_short(symbol, exit_price, reason):
    entry_price = state[symbol]["entry_price"]

    client.submit_order(
        MarketOrderRequest(
            symbol=symbol,
            qty=QTY,
            side=OrderSide.BUY,  # BUY to cover SHORT
            time_in_force=TimeInForce.DAY
        )
    )

    # Print P/L and update summary
    print_pnl(symbol, entry_price, exit_price, QTY, reason)

    # Reset state
    state[symbol]["in_position"] = False
    state[symbol]["entry_price"] = None
    state[symbol]["last_exit_time"] = time.time()

# ---------- MAIN LOOP ----------

print("🚀 SHORT-ONLY Multi-Trade Bot Started")

while True:
    try:
        if not market_time_ok():
            print("⏳ Waiting for market hours...")
            time.sleep(300)
            continue

        now_ts = time.time()

        for symbol in SYMBOLS:
            df = get_data(symbol)
            if df.empty or df["Volume"].sum() == 0:
                continue

            price = df["Close"].iloc[-1]
            vwap = (df["Close"] * df["Volume"]).sum() / df["Volume"].sum()
            rsi = calculate_rsi(df["Close"])

            print(f"{symbol} | Price={price:.2f} VWAP={vwap:.2f} RSI={rsi:.2f}")

            # ---------- ENTRY ----------
            if not state[symbol]["in_position"]:
                if now_ts - state[symbol]["last_exit_time"] < REENTRY_COOLDOWN:
                    continue

                if price <= vwap * 0.998 and rsi >= RSI_SHORT:
                    open_short(symbol, price)
                    state[symbol]["in_position"] = True
                    state[symbol]["entry_price"] = price

            # ---------- EXIT ----------
            else:
                entry = state[symbol]["entry_price"]
                target = entry * (1 - TARGET_PCT)
                stop = entry * (1 + STOP_LOSS_PCT)

                reason = None
                if price <= target:
                    reason = "TARGET HIT"
                elif price >= stop:
                    reason = "STOP LOSS HIT"
                elif should_force_exit():
                    reason = "TIME EXIT"

                if reason:
                    close_short(symbol, exit_price=price, reason=reason)

        # ---------- PRINT DAILY SUMMARY AT MARKET CLOSE ----------
        if should_force_exit():
            print_daily_summary()
            time.sleep(3600)  # sleep 1 hour after market close
        else:
            time.sleep(CHECK_INTERVAL)

    except Exception as e:
        print("⚠️ Error:", e)
        time.sleep(CHECK_INTERVAL)
