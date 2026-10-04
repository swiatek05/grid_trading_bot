import sqlite3
import joblib
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from grid_strategy import calculate_grid_levels

INPUT_DB = 'btc_usdc_features_15m.db'
REGIME_MODEL_FILE = 'regime_kmeans.joblib'

INITIAL_CAPITAL = 1000.0
FEE = 0.0004


def run_backtest(df, regime_data, title="Backtest"):
    kmeans_model = regime_data['model']
    scaler = regime_data['scaler']
    mapping_label = regime_data['mapping']

    capital_usdc = INITIAL_CAPITAL
    capital_btc = 0.0
    equity_history = []

    active_orders = {}
    order_id_counter = 1

    upper_price = float('inf')
    lower_price = 0.0
    current_ratio = 1.0

    cooldown_mode = "none"

    trades_count = 0
    sum_of_fees = 0.0
    stop_losses_hit = 0

    for index, row in df.iterrows():
        low = row['low']
        high = row['high']
        close = row['close']
        rsi = row['rsi']
        current_atr = row['atr']

        ema_trend = row.get('ema_trend', 1)

        if active_orders:
            if close > upper_price:
                if capital_btc > 0:
                    usdc_gained = capital_btc * close
                    fee = usdc_gained * FEE
                    capital_usdc += (usdc_gained - fee)
                    capital_btc = 0.0
                    sum_of_fees += fee
                    trades_count += 1
                active_orders.clear()
                cooldown_mode = "pump"

            elif close < (lower_price * 0.998):
                if capital_btc > 0:
                    usdc_gained = capital_btc * close
                    fee = usdc_gained * FEE
                    capital_usdc += (usdc_gained - fee)
                    capital_btc = 0.0
                    sum_of_fees += fee
                    trades_count += 1
                    stop_losses_hit += 1
                active_orders.clear()
                cooldown_mode = "dump"

        if not active_orders:
            if cooldown_mode == "pump" and rsi > 70:
                continue
            elif cooldown_mode == "dump" and rsi < 30:
                continue

            cooldown_mode = "none"

            if ema_trend <= 0:
                continue

            atr_percent = (current_atr / close) * 100
            log_atr_percent = np.log1p(atr_percent)
            bb_width = row['bb_width']

            features_for_regime = pd.DataFrame([[log_atr_percent, bb_width]], columns=['log_atr_percent', 'bb_width'])
            scaled_features = scaler.transform(features_for_regime)
            raw_cluster = kmeans_model.predict(scaled_features)[0]
            current_regime = mapping_label[raw_cluster]

            if current_regime == 2 and rsi < 40:
                continue

            current_atr_decimal = current_atr / close

            if current_regime == 0:
                grid_range = current_atr_decimal * 8.0
            elif current_regime == 1:
                grid_range = current_atr_decimal * 15.0
            else:
                grid_range = current_atr_decimal * 25.0

            grid_range = max(grid_range, 0.035)

            min_step_pct = 5.5 * FEE
            price_step = max(current_atr_decimal * 1.2, min_step_pct)

            count_of_levels = int((2 * grid_range) / price_step)
            count_of_levels = max(10, min(count_of_levels, 40))

            upper_price = close * (1 + grid_range)
            lower_price = close * (1 - grid_range)

            grid_data = calculate_grid_levels(close, lower_price, upper_price, count_of_levels)
            current_ratio = grid_data.get('ratio', grid_data.get('price_ratio', 1.0))

            buy_levels = sorted(grid_data['buy_levels'], reverse=True)
            sell_levels = sorted(grid_data['sell_levels'])
            total_lines = len(buy_levels) + len(sell_levels)

            if total_lines > 0:
                usdc_per_line = (capital_usdc * 0.95) / total_lines
                usdc_needed_for_sells = usdc_per_line * len(sell_levels)

                if usdc_needed_for_sells > 0 and capital_usdc >= usdc_needed_for_sells:
                    btc_bought = usdc_needed_for_sells / close
                    fee = btc_bought * FEE
                    net_btc = btc_bought - fee

                    capital_usdc -= usdc_needed_for_sells
                    capital_btc += net_btc
                    trades_count += 1
                    sum_of_fees += (usdc_needed_for_sells * FEE)

                    btc_per_sell_line = net_btc / len(sell_levels)
                else:
                    btc_per_sell_line = 0

                for price in buy_levels:
                    active_orders[order_id_counter] = {'price': price, 'side': "BUY", 'usdc_size': usdc_per_line}
                    order_id_counter += 1

                for price in sell_levels:
                    active_orders[order_id_counter] = {'price': price, 'side': 'SELL', 'btc_size': btc_per_sell_line,
                                                       'original_usdc_size': usdc_per_line}
                    order_id_counter += 1

        current_order_ids = list(active_orders.keys())

        for order_id in current_order_ids:
            if order_id not in active_orders:
                continue

            order = active_orders[order_id]
            price = order['price']
            side = order['side']

            if side == "BUY" and low <= price:
                usdc_to_spend = min(order['usdc_size'], capital_usdc)
                if capital_usdc >= usdc_to_spend * 0.999:
                    btc_bought = usdc_to_spend / price
                    fee = btc_bought * FEE
                    net_btc = btc_bought - fee

                    capital_usdc -= usdc_to_spend
                    capital_btc += net_btc
                    trades_count += 1
                    sum_of_fees += (usdc_to_spend * FEE)
                    del active_orders[order_id]

                    new_sell_price = round(price * current_ratio, 2)
                    active_orders[order_id_counter] = {'price': new_sell_price, 'side': 'SELL', 'btc_size': net_btc,
                                                       'original_usdc_size': usdc_to_spend}
                    order_id_counter += 1

            elif side == 'SELL' and high >= price:
                btc_to_sell = order.get('btc_size', 0)
                if btc_to_sell > 0 and capital_btc >= btc_to_sell * 0.999:
                    btc_to_sell = min(btc_to_sell, capital_btc)
                    usdc_gained = btc_to_sell * price
                    fee = usdc_gained * FEE

                    capital_btc -= btc_to_sell
                    capital_usdc += (usdc_gained - fee)
                    trades_count += 1
                    sum_of_fees += fee
                    del active_orders[order_id]

                    new_buy_price = round(price / current_ratio, 2)
                    active_orders[order_id_counter] = {'price': new_buy_price, 'side': 'BUY',
                                                       'usdc_size': order.get('original_usdc_size', 0)}
                    order_id_counter += 1

        total_equity = capital_usdc + (capital_btc * close)
        equity_history.append(total_equity)

    final_price = df.iloc[-1]['close']
    if capital_btc > 0:
        usdc_gained = capital_btc * final_price
        fee = usdc_gained * FEE
        capital_usdc += (usdc_gained - fee)
        capital_btc = 0.0

    final_capital = capital_usdc
    profit_percent = ((final_capital - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100

    print("=" * 30)
    print(f"--- RESULTS FOR: {title} ---")
    print("=" * 30)
    print(f"Start Capital:    {INITIAL_CAPITAL} USDC")
    print(f"End capital:      {final_capital:.2f} USDC")
    print(f"Profit/Loss:      {profit_percent:.2f} %")
    print(f"Count of trades:  {trades_count}")
    print(f"Stop Losses hit:  {stop_losses_hit}")
    print(f"Cost of fees:     {sum_of_fees:.2f} USDC")
    print("=" * 30 + "\n")
    
    return equity_history


def main():
    connection = None
    try:
        regime_data = joblib.load(REGIME_MODEL_FILE)

        connection = sqlite3.connect(INPUT_DB)
        df = pd.read_sql("SELECT * FROM features", connection)

        if df.empty:
            print("Lack of data")
            return

        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df.dropna(inplace=True)

        split_index = int(len(df) * 0.8)

        test_df = df.iloc[split_index:].reset_index(drop=True)

        print(f"Running backtests for {len(df)} records...\n")

        run_backtest(df, regime_data, title=f"FULL DATA - 100% ({len(df)} rows)")
        test_equity = run_backtest(test_df, regime_data, title=f"UNSEEN DATA - 20% ({len(test_df)} rows)")

        plt.figure(figsize=(10, 5))
        plt.plot(test_equity, label='Equity (USDC)')
        plt.title('Equity Curve (Unseen Data)')
        plt.xlabel('Time step (15m)')
        plt.ylabel('USDC')
        plt.grid(True)
        plt.legend()
        plt.savefig('backtest_chart.png')
        print("Chart saved to backtest_chart.png")

    except Exception as e:
        print("error: ", e)
    finally:
        if connection:
            connection.close()


if __name__ == "__main__":
    main()