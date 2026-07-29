from db import add_transaction
from grid_strategy import calculate_grid_levels
import asyncio


async def init_grid(exchange, grid_config):
    symbol = grid_config['symbol']
    min_limit = grid_config['min_limit']
    max_limit = grid_config['max_limit']
    count_of_levels = grid_config['count_of_levels']
    quantity = grid_config['quantity_per_grid']

    print(f"Initializing grid for symbol: {symbol}")

    ticker = await exchange.fetch_ticker(symbol)
    actual_price = ticker['last']

    grid = calculate_grid_levels(actual_price, min_limit, max_limit, count_of_levels)

    active_orders = {}

    for price in grid['buy_levels']:
        try:
            order = await exchange.create_limit_buy_order(symbol, quantity, price)
            active_orders[order['id']] = {'price': price, 'side': 'BUY'}
        except Exception as e:
            print(f"Error placing buy order at {price}, e= {e}")

    for price in grid['sell_levels']:
        try:
            order = await exchange.create_limit_sell_order(symbol, quantity, price)
            active_orders[order['id']] = {'price': price, 'side': 'SELL'}
        except Exception as e:
            print(f"Error placing sell order ast {price}, e={e}")

    return active_orders,grid['price_step']


'''async def monitor_grid(exchange, symbol, active_orders, price_step, quantity):
    while True:
        try:
            orders = await exchange.watch_orders(symbol)
            for order_data in orders:
                order_id = order_data['id']
                if order_id in active_orders and order_data['status'] == 'closed':
                    order_info = active_orders[order_id]
                    price = order_info['price']
                    side = order_info['side']

                    print(f"Order id: {order_id} side: {side} price: {price} is competed")

                    add_transaction(order_data)

                    del active_orders[order_id]

                    if side == 'BUY':
                        new_sell_price = round(price + price_step, 2)
                        new_order = await exchange.create_limit_sell_order(symbol, quantity, new_sell_price)
                        active_orders[new_order['id']] = {'price': new_sell_price, 'side': 'SELL'}
                    elif side == 'SELL':
                        new_buy_price = round(price - price_step, 2)
                        new_order = await exchange.create_limit_buy_order(symbol, quantity, new_buy_price)
                        active_orders[new_order['id']] = {'price': new_buy_price, 'side': 'BUY'}
        except Exception as e:
            print("WebSocket connection error ")
            await asyncio.sleep(5)'''


async def monitor_grid(exchange, symbol, active_orders, price_step, quantity):


    while True:
        try:
            open_orders = await exchange.fetch_open_orders(symbol)
            open_order_ids = [order['id'] for order in open_orders]

            for order_id in list(active_orders.keys()):
                if order_id not in open_order_ids:
                    order_data = await exchange.fetch_order(order_id, symbol,params={'acknowledged': True})

                    if order_data['status'] == 'closed':
                        order_info = active_orders[order_id]
                        price = order_info['price']
                        side = order_info['side']

                        print(f"Order id: {order_id} side: {side} price: {price} is completed")

                        add_transaction(order_data)
                        del active_orders[order_id]

                        if side == 'BUY':
                            new_sell_price = round(price + price_step, 2)
                            new_order = await exchange.create_limit_sell_order(symbol, quantity, new_sell_price)
                            active_orders[new_order['id']] = {'price': new_sell_price, 'side': 'SELL'}
                            print(f"Placing new order SELL at price:  {new_sell_price}")

                        elif side == 'SELL':
                            new_buy_price = round(price - price_step, 2)
                            new_order = await exchange.create_limit_buy_order(symbol, quantity, new_buy_price)
                            active_orders[new_order['id']] = {'price': new_buy_price, 'side': 'BUY'}
                            print(f"Placing new order BUY at price {new_buy_price}")

            await asyncio.sleep(3)

        except Exception as e:
            print(f"Błąd podczas połączenia: {e}")
            await asyncio.sleep(5)

