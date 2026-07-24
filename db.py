import json
import sqlite3
from datetime import datetime

DB_NAME = 'database.db'


def init_db():
    db = sqlite3.connect(DB_NAME)
    cursor = db.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            type_transaction TEXT NOT NULL,
            asset TEXT NOT NULL,
            crypto_amount REAL NOT NULL,
            payment_currency TEXT NOT NULL,
            payment_amount REAL NOT NULL,
            exchange_rate REAL NOT NULL,
            fee REAL NOT NULL,
            fee_currency TEXT NOT NULL,
            fee_in_usdt REAL NOT NULL,
            date TEXT NOT NULL
        );
    ''')
    db.commit()
    db.close()


def add_transaction(order_data): #bnb_price=0.0):
    status = order_data.get('status')
    if status != 'closed':
        print(f"Order {order_data.get('id')} has status '{status}' (is not closed). Does not save it")
        return

    try:
        order_id = order_data.get('id')
        type_trans = order_data.get('side').upper()

        symbol_parts = order_data.get('symbol').split('/')
        asset = symbol_parts[0]
        payment_currency = symbol_parts[1]

        crypto_amount = order_data.get('filled')
        price = order_data.get('average')
        payment_amount = order_data.get('cost')

        fee_data = order_data.get('fee')

        if None in (order_id, type_trans, symbol_parts, crypto_amount, price, payment_amount):
            raise ValueError("One of the values in Json is None")

        if fee_data and fee_data.get('cost') is not None:
            fee_cost = fee_data.get('cost')
            fee_curr = fee_data.get('currency')
            if not fee_curr or fee_cost is None:
                raise ValueError("There is missing information about fee currency or cost ")
        else:
            fee_cost = 0.0
            fee_curr = payment_currency

        if fee_curr == 'USDT':
            fee_in_usdt = fee_cost
        elif fee_curr == asset:
            fee_in_usdt = fee_cost * price
        #elif fee_curr == 'BNB':
            #fee_in_usdt = fee_cost * bnb_price
        else:
            fee_in_usdt = fee_cost

        date_str = datetime.fromtimestamp(order_data['timestamp'] / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except (KeyError, ValueError, TypeError, AttributeError) as e:
        print(f"Data Error. Order {order_id} is incomplete. Save this log to failed_orders.json")
        with open("failed_orders.json", "a") as f:
            log = {
                "error_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "error_message": str(e),
                "raw_order_data": order_data
            }
            json.dump(log, f)
            f.write("\n")
        return
    db = sqlite3.connect(DB_NAME)
    cursor = db.cursor()
    try:
        cursor.execute('''
            INSERT INTO transactions(
                order_id, type_transaction, asset, crypto_amount, 
                payment_currency, payment_amount, exchange_rate, 
                fee, fee_currency, fee_in_usdt, date
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            order_id, type_trans, asset, crypto_amount,
            payment_currency, payment_amount, price,
            fee_cost, fee_curr, fee_in_usdt, date_str
        ))
        db.commit()
        print(f" Saved in database: {order_id} ({type_trans} {crypto_amount} {asset})")
    except sqlite3.IntegrityError:
        print(f" Transaction {order_id} already exists in database")
    finally:
        db.close()


init_db()
