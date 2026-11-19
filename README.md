# High Speed Low Drag Trader — paper-only prototype

This is a starter dashboard for Alpaca paper trading. It is intentionally hard-wired to `paper=True`; it does not include a live-trading mode.

## What it does
- Reads your Alpaca paper account balance, positions, and open orders.
- Scans a small watchlist (SPY, QQQ, IWM, AAPL, MSFT, NVDA, AMZN, META, TSLA).
- Uses a simple 5-minute EMA momentum + relative-volume condition to flag WATCH signals.
- Can submit a simulated bracket order only after you enable the paper-order checkbox, confirm the warning, and press the cycle button.
- Uses conservative prototype limits: $5 planned risk per trade, $15 daily equity-loss lockout, max 2 positions, and 10% equity cap per position.

## Important limitations
This is an experimental prototype, not a proven profitable strategy. The signals are not validated by a rigorous backtest. Paper trading does not perfectly reproduce real fills, slippage, market impact, queue position, or all fees. Do not use it with live credentials or real money.

Alpaca paper trading endpoint is used by the official SDK when `TradingClient(..., paper=True)` is selected. This app hard-codes that setting.

## Run it on a computer
1. Install Python 3.10 or newer.
2. Unzip this folder.
3. Open a terminal in this folder.
4. Install packages:
   `pip install -r requirements.txt`
5. Copy `.env.example` to `.env`.
6. Put your **paper** API key and secret in `.env` (never share them in chat or upload `.env` to GitHub):
   `APCA_API_KEY_ID=...`
   `APCA_API_SECRET_KEY=...`
7. Start:
   `streamlit run app.py`
8. Open the local address Streamlit prints, usually `http://localhost:8501`.

## Security
- Use only API keys created for the paper account.
- Keep `.env` private. Do not commit or upload it.
- If a key is exposed, revoke/regenerate it in Alpaca immediately.
- Never paste API keys or secrets into ChatGPT.

## Strategy details
A symbol is flagged WATCH when the latest 5-minute close is above its 20-period EMA and EMA 9 is above EMA 20, while the latest bar's volume is at least 1.5x the mean volume of the preceding 20 bars. This is a simple screening rule, not a buy recommendation.

The prototype uses whole-share quantities and bracket orders with a 1.5% stop and 3% target. Actual realized risk can exceed the planned amount because stop orders can fill below the stop price, and market orders can slip.


## Deploy from an iPad with Streamlit Community Cloud
1. Extract the ZIP in the iPad Files app.
2. Create a **public** GitHub repository for the app source. Upload `app.py`, `requirements.txt`, and optionally `README.md` and `.gitignore`. Do NOT upload `.env`, real API keys, or `STREAMLIT_SECRETS_TEMPLATE.toml`.
3. Open https://share.streamlit.io and sign in with GitHub.
4. Create an app using the repository, branch `main`, and main file path `app.py`.
5. In Advanced settings / Secrets, enter TOML values for `APP_PASSWORD`, `APCA_API_KEY_ID`, and `APCA_API_SECRET_KEY`, using your paper credentials only.
6. Deploy. Open the app URL and enter your dashboard password.

The repository source will be public on the free Community Cloud path, but secrets must remain in Streamlit's Secrets settings. The app includes a password gate; use a unique password and do not share it. The app remains paper-only.
