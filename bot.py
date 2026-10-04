import ccxt.async_support as ccxt
from dotenv import load_dotenv
import os
from db import add_transaction
from grid_logic import init_grid, monitor_grid
from dynamic_grid import get_dynamic_grid_params
from retrainer import retrain_models_task, RETRAIN_INTERVAL_SECONDS
import asyncio

load_dotenv()

secret_key = os.getenv("SECRET_KEY")
api_key = os.getenv("API_KEY")


grid_config = {
    'symbol': 'BTC/USDC'
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
    
    # Start the background retraining task
    asyncio.create_task(retrain_models_task())

    try:

        await sync_recent_trades(exchange,grid_config['symbol'])

        while True:
            print(f"\n--- Initializing Grid for {grid_config['symbol']} ---")
            
            # 1. Calculate dynamic params based on current market and ML model
            params = await get_dynamic_grid_params(exchange, grid_config['symbol'])
            
            if params is None:
                print("Failed to calculate grid parameters. Retrying in 60 seconds...")
                await asyncio.sleep(60)
                continue
                
            # 2. Cooldown logic based on market conditions
            if params['rsi'] > 70 or params['rsi'] < 30:
                print(f"RSI is extreme ({params['rsi']:.2f}). Waiting 5 minutes for cooldown...")
                await asyncio.sleep(300)
                continue
                
            if params['ema_trend'] <= 0:
                print(f"EMA Trend is negative ({params['ema_trend']:.4f}). Waiting 5 minutes for recovery...")
                await asyncio.sleep(300)
                continue

            # 3. Setup grid
            active_orders, ratio = await init_grid(
                exchange,
                grid_config['symbol'],
                params['lower_price'],
                params['upper_price'],
                params['count_of_levels'],
                0.95
            )
            
            if not active_orders:
                print("Failed to initialize grid orders. Retrying in 60 seconds...")
                await asyncio.sleep(60)
                continue

            # 4. Monitor grid
            reason = await monitor_grid(
                exchange,
                grid_config['symbol'],
                active_orders,
                ratio,
                params['lower_price'],
                params['upper_price']
            )
            
            print(f"\nGrid broken due to: {reason}. Liquidated to USDC. Re-evaluating market in 60 seconds...")
            await asyncio.sleep(60)

    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())