import ccxt
from dotenv import load_dotenv
import os
from db import add_transaction


load_dotenv()

secret_key = os.getenv("SECRET_KEY")
api_key = os.getenv("API_KEY")

exchange=ccxt.bybit({
    'apiKey': api_key,
    'secret': secret_key,
    'enableRateLimit': True
})

def sync_recent_trades(symbol):
    print(f"Connecting to Bybit exchange and downloading history for {symbol} ")
    try:
        closed_orders=exchange.fetch_closed_orders(symbol,limit=10)

        if not closed_orders:
            print("Lack of closed orders for this pair")
            return
        print(f"Downloaded {len(closed_orders)} orders. I saving ..")
        for order in closed_orders:
            add_transaction(order)
    except Exception as e:
        print("Api Error ",e)
sync_recent_trades('BTC/USDT')