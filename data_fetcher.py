import ccxt.async_support as ccxt
from datetime import datetime, timedelta
import asyncio
import pandas as pd
import sqlite3

SYMBOL = 'BTC/USDC'
TIMEFRAME = '15m'
COUNT_OF_DAYS = 365
OUTPUT_FILE = 'btc_usdc_history_15m.db'


async def fetch_historical_candles(symbol, timeframe, count_of_days):
    exchange = ccxt.bybiteu({'enableRateLimit': True})

    since_dt = datetime.now() - timedelta(days=count_of_days)
    since_ms = int(since_dt.timestamp() * 1000)

    all_candles = []

    try:
        while True:
            candles = await exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=since_ms,
                limit=1000
            )
            if not candles:
                break
            all_candles.extend(candles)
            last_time = candles[-1][0]
            since_ms = last_time + 1

            if last_time >= int(datetime.now().timestamp() * 1000) - 900000:
                break
            await asyncio.sleep(exchange.rateLimit / 1000)
    except Exception as e:
        print(f"Error with fetching historical candles")
    finally:
        await exchange.close()
    return all_candles


async def main():
    candles = await fetch_historical_candles(SYMBOL, TIMEFRAME, COUNT_OF_DAYS)

    if not candles:
        print("Lack of historical candles")
    df = pd.DataFrame(
        data=candles,
        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
    )
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[['datetime', 'timestamp', 'open', 'high', 'low', 'close', 'volume']]

    connection = sqlite3.connect(OUTPUT_FILE)

    df.to_sql(name="historical_candles", con=connection, if_exists='replace', index=False)

    print(f"Success, download {len(df)} candles to database {OUTPUT_FILE} ")

if __name__=="__main__":
    asyncio.run(main())