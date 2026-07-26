import ccxt.async_support as ccxt
from dotenv import load_dotenv
import os
from db import add_transaction
from grid_logic import init_grid, monitor_grid
import asyncio
load_dotenv()

secret_key = os.getenv("SECRET_KEY")
api_key = os.getenv("API_KEY")


grid_config = {
    'symbol': 'BTC/USDC',
    'min_limit': 55000.0,
    'max_limit': 65000.0,
    'count_of_levels': 5,
    'quantity_per_grid': 0.001
}

async def sync_recent_trades(exchange,symbol):
    print(f"Connecting to Bybit exchange and downloading history for {symbol} ")
    try:
        closed_orders=await exchange.fetch_closed_orders(symbol,limit=10)

        if not closed_orders:
            print("Lack of closed orders for this pair")
            return
        print(f"Downloaded {len(closed_orders)} orders. I saving ..")
        for order in closed_orders:
            add_transaction(order)
    except Exception as e:
        print("Api Error ",e)

async def main():

    exchange = ccxt.bybiteu({
        'apiKey': api_key,
        'secret': secret_key,
        'enableRateLimit': True,

    })
    exchange.set_sandbox_mode(True)

    exchange.urls['api']['ws'] = {
        'public': 'wss://stream-testnet.bybit.eu/v5/public/spot',
        'private': 'wss://stream-testnet.bybit.eu/v5/private',
    }

    try:

        await sync_recent_trades(exchange,grid_config['symbol'])

        active_orders,price_step=await init_grid(exchange,grid_config)

        await monitor_grid(
            exchange,
            grid_config['symbol'],
            active_orders,
            price_step,
            grid_config['quantity_per_grid']
        )
    finally:
        await exchange.close()

asyncio.run(main())