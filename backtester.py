import sqlite3
import pandas as pd

from grid_strategy import calculate_grid_levels

INPUT_DB = 'btc_usdc_features.db'
INITIAL_CAPITAL = 1000.0
FEE = 0.001
COUNT_OF_GRID = 20
GRID_RANGE = 0.05
QUANTITY_PER_ORDER = 20.0


def run_backtest(df):
    capital_usdc = INITIAL_CAPITAL
    capital_btc = 0.0

    start_price = df.iloc[0]['close']

    upper_price = start_price * (1 + GRID_RANGE)
    lower_price = start_price * (1 - GRID_RANGE)

    grid_data = calculate_grid_levels(start_price, lower_price, upper_price, COUNT_OF_GRID)
    price_step = grid_data['price_step']

    active_orders = {}

    order_id_counter = 1

    for price in grid_data['buy_levels']:
        active_orders[order_id_counter] = {'price': price, 'side': "BUY"}
        order_id_counter += 1
    for price in grid_data['sell_levels']:
        active_orders[order_id_counter] = {'price': price, 'side': 'SELL'}
        order_id_counter += 1

    trades_count = 0
    sum_of_fees = 0.0

    for index, row in df.iterrows():
        low = row['low']
        high = row['high']

        current_order_ids = list(active_orders.keys())

        for order_id in current_order_ids:
            if order_id not in active_orders:
                continue

            order = active_orders[order_id]
            price = order['price']
            side = order['side']

            if side == "BUY" and low <= price:
                if capital_usdc >= QUANTITY_PER_ORDER:
                    btc_bought = QUANTITY_PER_ORDER / price
                    fee = btc_bought * FEE

                    capital_usdc -= QUANTITY_PER_ORDER
                    capital_btc += (btc_bought - fee)

                    trades_count += 1
                    sum_of_fees += (QUANTITY_PER_ORDER * FEE)

                    del active_orders[order_id]

                    new_sell_price = round(price + price_step, 2)
                    active_orders[order_id_counter] = {'price': new_sell_price, 'side': 'SELL'}
                    order_id_counter += 1
            elif side == 'SELL' and high >= price:
                btc_to_sell = QUANTITY_PER_ORDER / price
                if capital_btc >= btc_to_sell:
                    usdc_gained = btc_to_sell * price
                    fee = usdc_gained * FEE

                    capital_btc -= btc_to_sell
                    capital_usdc += (usdc_gained - fee)

                    trades_count += 1
                    sum_of_fees += fee

                    del active_orders[order_id]

                    new_buy_price = round(price - price_step, 2)
                    active_orders[order_id_counter] = {'price': new_buy_price, 'side': 'BUY'}
                    order_id_counter += 1

    final_price = df.iloc[-1]['close']
    final_capital = capital_usdc + (capital_btc * final_price)
    profit_percent = ((final_capital - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100

    print("=" * 30)
    print(f"Start Capital:    {INITIAL_CAPITAL} USDC")
    print(f"End capital      {final_capital:.2f} USDC")
    print(f"Profit/Loss {profit_percent:.2f} %")
    print(f"Count of transaction:     {trades_count}")
    print(f"Cost of fees:    {sum_of_fees} USDC")
    print("=" * 30)


def main():
    connection = None
    try:
        connection = sqlite3.connect(INPUT_DB)
        df = pd.read_sql("SELECT * FROM features", connection)

        if df.empty:
            print("Lack of data")
            return
        run_backtest(df)
    except Exception as e:
        print("error: ", e)
    finally:
        if connection:
            connection.close()


if __name__ == "__main__":
    main()
