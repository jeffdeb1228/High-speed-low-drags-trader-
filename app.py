import os
import math
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass, QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.enums import DataFeed

# SAFETY: this application is hard-wired to Alpaca PAPER trading.
# Do not change paper=True or add a live endpoint.
load_dotenv()

st.set_page_config(page_title="High Speed Low Drag Trader", page_icon="📈", layout="wide")
st.title("High Speed Low Drag Trader")
st.caption("Alpaca paper-trading prototype • Stocks & ETFs • No live-money connection")

# Streamlit Community Cloud secrets take priority; local .env is supported for desktop use.
def get_secret(name):
    try:
        value = st.secrets.get(name, "")
        if value:
            return str(value).strip()
    except Exception:
        pass
    return os.getenv(name, "").strip()

APP_PASSWORD = get_secret("APP_PASSWORD")
if not APP_PASSWORD:
    st.error("App password is not configured. Add APP_PASSWORD in Streamlit app Secrets before using this dashboard.")
    st.stop()

entered_password = st.text_input("Dashboard password", type="password")
if entered_password != APP_PASSWORD:
    st.info("Enter your dashboard password to continue.")
    st.stop()

API_KEY = get_secret("APCA_API_KEY_ID")
API_SECRET = get_secret("APCA_API_SECRET_KEY")

WATCHLIST = ["SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA"]
RISK_PER_TRADE = 5.00
DAILY_LOSS_LIMIT = 15.00
MAX_POSITIONS = 2
MAX_POSITION_VALUE_PCT = 0.10
STOP_PCT = 0.015
TARGET_PCT = 0.03

st.info(
    "Simulation only. The strategy is experimental and has not been shown to be profitable. "
    "Automatic orders are OFF until you explicitly enable them below."
)

if not API_KEY or not API_SECRET:
    st.error("API credentials are missing. Add your PAPER key and secret to the local .env file. Never paste them into chat.")
    st.code("APCA_API_KEY_ID=your_paper_key\nAPCA_API_SECRET_KEY=your_paper_secret", language="text")
    st.stop()

try:
    trading = TradingClient(API_KEY, API_SECRET, paper=True)
    market_data = StockHistoricalDataClient(API_KEY, API_SECRET)
    account = trading.get_account()
except Exception as e:
    st.error(f"Could not connect to Alpaca paper trading: {e}")
    st.stop()

def money(x):
    return f"${float(x):,.2f}"

def get_scan(symbol):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=5)
    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame(5, TimeFrameUnit.Minute),
        start=start,
        end=end,
        limit=100,
        feed=DataFeed.IEX,
    )
    df = market_data.get_stock_bars(req).df
    if df is None or df.empty:
        return None
    if isinstance(df.index, pd.MultiIndex):
        try:
            df = df.xs(symbol, level=0)
        except Exception:
            return None
    df = df.sort_index()
    if len(df) < 25:
        return None
    close = df["close"].astype(float)
    volume = df["volume"].astype(float)
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema20 = close.ewm(span=20, adjust=False).mean()
    avg_vol = volume.iloc[-21:-1].mean()
    latest_vol = volume.iloc[-1]
    price = float(close.iloc[-1])
    vol_ratio = float(latest_vol / avg_vol) if avg_vol and avg_vol > 0 else 0.0
    bullish = bool(ema9.iloc[-1] > ema20.iloc[-1] and close.iloc[-1] > ema20.iloc[-1])
    signal = "WATCH" if bullish and vol_ratio >= 1.5 else "NO SIGNAL"
    return {
        "Symbol": symbol,
        "Price": price,
        "EMA 9": float(ema9.iloc[-1]),
        "EMA 20": float(ema20.iloc[-1]),
        "Volume x Avg": vol_ratio,
        "Signal": signal,
    }

def place_paper_bracket(symbol, entry):
    # Only whole shares; max $5 planned risk and max 10% of account equity per position.
    stop = round(entry * (1 - STOP_PCT), 2)
    target = round(entry * (1 + TARGET_PCT), 2)
    risk_per_share = entry - stop
    if risk_per_share <= 0:
        return "Skipped: invalid stop distance."
    qty_by_risk = math.floor(RISK_PER_TRADE / risk_per_share)
    equity = float(account.equity)
    qty_by_cap = math.floor((equity * MAX_POSITION_VALUE_PCT) / entry)
    qty = min(qty_by_risk, qty_by_cap)
    if qty < 1:
        return "Skipped: position size too small under risk/capital limits."
    order = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.BRACKET,
        take_profit={"limit_price": target},
        stop_loss={"stop_price": stop},
    )
    submitted = trading.submit_order(order)
    return f"Submitted PAPER bracket order: {symbol} x {qty}; estimated entry ${entry:.2f}, stop ${stop:.2f}, target ${target:.2f}; order {submitted.id}"

# Account summary
c1, c2, c3, c4 = st.columns(4)
c1.metric("Paper equity", money(account.equity))
c2.metric("Cash", money(account.cash))
c3.metric("Buying power", money(account.buying_power))
day_pl = float(account.equity) - float(account.last_equity)
c4.metric("Today's equity change", money(day_pl), delta=money(day_pl))

st.caption("Risk limits: $5 planned risk per trade • $15 daily equity-loss stop • 2 positions max • 10% equity cap per position.")

try:
    clock = trading.get_clock()
    st.write(f"**Market status:** {'OPEN' if clock.is_open else 'CLOSED'}")
except Exception:
    clock = None
    st.warning("Could not verify market clock. Orders will remain disabled.")

st.subheader("Market scanner")
st.write("Scans a small starter watchlist using 5-minute EMA momentum and a volume expansion filter.")
if st.button("Scan watchlist", type="primary"):
    rows = []
    with st.spinner("Fetching recent IEX bars..."):
        for sym in WATCHLIST:
            try:
                item = get_scan(sym)
                if item:
                    rows.append(item)
            except Exception as e:
                st.warning(f"{sym}: data unavailable ({e})")
    if rows:
        scan_df = pd.DataFrame(rows)
        st.session_state["scan_df"] = scan_df
    else:
        st.session_state["scan_df"] = pd.DataFrame()

scan_df = st.session_state.get("scan_df")
if scan_df is not None:
    if len(scan_df):
        st.dataframe(scan_df, use_container_width=True, hide_index=True)
    else:
        st.caption("No scan results yet. Press Scan watchlist.")

st.subheader("Paper execution controls")
auto_enabled = st.checkbox("Enable automatic PAPER orders for qualifying signals", value=False)
st.caption("When enabled, pressing the button below may submit paper orders. It never submits live orders.")
confirm = st.checkbox("I understand this is experimental and paper-only", value=False)

if st.button("Run one paper-trading cycle", disabled=not (auto_enabled and confirm)):
    if clock is None or not clock.is_open:
        st.error("No orders sent: market is closed or market status could not be verified.")
    elif day_pl <= -DAILY_LOSS_LIMIT:
        st.error("Daily loss limit reached. Trading is locked for today.")
    elif scan_df is None or scan_df.empty:
        st.error("Run the scanner first. No orders sent.")
    else:
        try:
            positions = trading.get_all_positions()
            open_orders = trading.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=500))
            held = {p.symbol for p in positions}
            pending = {o.symbol for o in open_orders}
            if len(positions) >= MAX_POSITIONS:
                st.warning("Position limit reached. No orders sent.")
            else:
                results = []
                candidates = scan_df[scan_df["Signal"] == "WATCH"].sort_values("Volume x Avg", ascending=False)
                for _, row in candidates.iterrows():
                    symbol = row["Symbol"]
                    if symbol in held or symbol in pending:
                        continue
                    if len(positions) >= MAX_POSITIONS:
                        break
                    result = place_paper_bracket(symbol, float(row["Price"]))
                    results.append(result)
                    # Reserve a slot immediately to prevent multiple orders in this cycle.
                    positions.append(symbol)
                if results:
                    for r in results:
                        st.write("• " + r)
                else:
                    st.info("No qualifying new signals or no available position slots. No orders sent.")
        except Exception as e:
            st.error(f"Paper cycle stopped safely: {e}")

st.subheader("Current positions")
try:
    positions = trading.get_all_positions()
    if positions:
        pos_rows = [{
            "Symbol": p.symbol,
            "Qty": p.qty,
            "Market value": money(p.market_value),
            "Unrealized P/L": money(p.unrealized_pl),
        } for p in positions]
        st.dataframe(pd.DataFrame(pos_rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No open positions.")
except Exception as e:
    st.warning(f"Could not load positions: {e}")

st.subheader("Open orders")
try:
    orders = trading.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=100))
    if orders:
        order_rows = [{"Symbol": o.symbol, "Side": str(o.side), "Qty": o.qty, "Type": str(o.type), "Status": str(o.status)} for o in orders]
        st.dataframe(pd.DataFrame(order_rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No open orders.")
except Exception as e:
    st.warning(f"Could not load orders: {e}")

st.divider()
st.caption(
    "Important: Paper fills are simulations and can differ from live execution. "
    "This prototype is not investment advice, does not guarantee profit, and should not be switched to live trading. "
    "Review signals and logs; test over many market conditions before considering any real-money system."
)
