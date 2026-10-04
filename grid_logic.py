import asyncio
from db import add_transaction
from grid_strategy import calculate_grid_levels


async def init_grid(exchange, symbol, lower_price, upper_price, count_of_levels, safe_capital_ratio=0.95):
    print(f"Initializing grid for symbol: {symbol}")

    ticker = await exchange.fetch_ticker(symbol)
    actual_price = ticker['last']

    grid_data = calculate_grid_levels(actual_price, lower_price, upper_price, count_of_levels)
    ratio = grid_data.get('ratio', grid_data.get('price_ratio', 1.0))

    buy_levels = sorted(grid_data['buy_levels'], reverse=True)
    sell_levels = sorted(grid_data['sell_levels'])
    total_lines = len(buy_levels) + len(sell_levels)

    if total_lines == 0:
        print("No grid levels generated.")
        return {}, ratio

    balance = await exchange.fetch_balance()
    available_usdc = balance['free'].get('USDC', 0.0)

    if available_usdc <= 10.0:
        print(f"Insufficient USDC balance: {available_usdc}")
        return {}, ratio

    usdc_per_line = (available_usdc * safe_capital_ratio) / total_lines
    req_usdc_for_sells = usdc_per_line * len(sell_levels)

    active_orders = {}

    if req_usdc_for_sells > 0 and len(sell_levels) > 0:
        market_btc_qty = req_usdc_for_sells / actual_price
        market_btc_qty = float(exchange.amount_to_precision(symbol, market_btc_qty))

        print(f"Buying base inventory: {market_btc_qty} BTC (~{req_usdc_for_sells:.2f} USDC)")
        try:
            market_order = await exchange.create_market_buy_order(symbol, market_btc_qty)
            await asyncio.sleep(0.5)
            try:
                fetched_order = await exchange.fetch_order(market_order['id'], symbol, params={'acknowledged': True})
                add_transaction(fetched_order)
            except Exception as e:
                print(f"Error fetching market order details: {e}")
                add_transaction(market_order)

            await asyncio.sleep(0.5)
            bal_after = await exchange.fetch_balance()
            actual_free_btc = bal_after['free'].get('BTC', 0.0)

            btc_per_sell = (actual_free_btc * 0.998) / len(sell_levels)
        except Exception as e:
            print(f"Failed to execute base market buy: {e}")
            return {}, ratio
    else:
        btc_per_sell = 0.0

    for price in buy_levels:
        try:
            qty = float(exchange.amount_to_precision(symbol, usdc_per_line / price))
            price_prec = float(exchange.price_to_precision(symbol, price))
            order = await exchange.create_limit_buy_order(symbol, qty, price_prec)
            active_orders[order['id']] = {
                'price': price_prec,
                'side': 'BUY',
                'usdc_size': usdc_per_line
            }
        except Exception as e:
            print(f"Error placing buy order at {price}: {e}")

    if btc_per_sell > 0:
        btc_qty = float(exchange.amount_to_precision(symbol, btc_per_sell))
        for price in sell_levels:
            try:
                price_prec = float(exchange.price_to_precision(symbol, price))
                order = await exchange.create_limit_sell_order(symbol, btc_qty, price_prec)
                active_orders[order['id']] = {
                    'price': price_prec,
                    'side': 'SELL',
                    'btc_size': btc_qty,
                    'usdc_size': usdc_per_line
                }
            except Exception as e:
                print(f"Error placing sell order at {price}: {e}")

    return active_orders, ratio


async def monitor_grid(exchange, symbol, active_orders, ratio, lower_bound, upper_bound):
    while True:
        try:
            ticker = await exchange.fetch_ticker(symbol)
            current_price = ticker['last']

            if current_price > upper_bound or current_price < (lower_bound * 0.998):
                reason = "TAKE PROFIT" if current_price > upper_bound else "STOP LOSS"
                print(f"Grid range broken ({reason}) at {current_price}. Closing grid...")

                for order_id in list(active_orders.keys()):
                    try:
                        await exchange.cancel_order(order_id, symbol)
                    except Exception as e:
                        print(f"Error canceling order {order_id}: {e}")

                balance = await exchange.fetch_balance()
                free_btc = balance['free'].get('BTC', 0.0)
                if free_btc > 0.0001:
                    qty = float(exchange.amount_to_precision(symbol, free_btc * 0.999))
                    try:
                        market_sell = await exchange.create_market_sell_order(symbol, qty)
                        await asyncio.sleep(0.5)
                        try:
                            fetched_sell = await exchange.fetch_order(market_sell['id'], symbol, params={'acknowledged': True})
                            add_transaction(fetched_sell)
                        except Exception:
                            add_transaction(market_sell)
                        print(f"Liquidated {qty} BTC to USDC.")
                    except Exception as e:
                        print(f"Error liquidating BTC: {e}")

                active_orders.clear()
                return reason

            open_orders = await exchange.fetch_open_orders(symbol)
            open_order_ids = set(order['id'] for order in open_orders)

            for order_id in list(active_orders.keys()):
                if order_id not in open_order_ids:
                    order_data = await exchange.fetch_order(order_id, symbol, params={'acknowledged': True})
                    status = order_data.get('status')

                    if status in ['canceled', 'rejected', 'expired']:
                        del active_orders[order_id]
                        continue

                    if status == 'closed':
                        order_info = active_orders[order_id]
                        price = order_info['price']
                        side = order_info['side']

                        print(f"Order filled: {side} @ {price}")
                        add_transaction(order_data)
                        del active_orders[order_id]

                        if side == 'BUY':
                            new_sell_price = float(exchange.price_to_precision(symbol, round(price * ratio, 2)))
                            filled_btc = order_data.get('filled', order_info['usdc_size'] / price)
                            qty = float(exchange.amount_to_precision(symbol, filled_btc * 0.999))

                            new_order = await exchange.create_limit_sell_order(symbol, qty, new_sell_price)
                            active_orders[new_order['id']] = {
                                'price': new_sell_price,
                                'side': 'SELL',
                                'btc_size': qty,
                                'usdc_size': order_info['usdc_size']
                            }
                            print(f"Placed new SELL order @ {new_sell_price}")

                        elif side == 'SELL':
                            new_buy_price = float(exchange.price_to_precision(symbol, round(price / ratio, 2)))
                            cost_usdc = order_data.get('cost', order_info.get('usdc_size', 0))
                            qty = float(exchange.amount_to_precision(symbol, (cost_usdc * 0.998) / new_buy_price))

                            new_order = await exchange.create_limit_buy_order(symbol, qty, new_buy_price)
                            active_orders[new_order['id']] = {
                                'price': new_buy_price,
                                'side': 'BUY',
                                'usdc_size': cost_usdc
                            }
                            print(f"Placed new BUY order @ {new_buy_price}")

            await asyncio.sleep(2)

        except Exception as e:
            print(f"Error in monitor_grid: {e}")
            await asyncio.sleep(5)