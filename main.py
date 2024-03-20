from functools import wraps

from flask import Flask, jsonify, request, send_file, abort
import requests
from query_script import kline, search_symbol
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib

def get_db_connection():
    return psycopg2.connect(
        dbname='trading',
        user='your_username',
        password='your_password',
        host='localhost',
        port='5432',
        cursor_factory=RealDictCursor
    )

def initialize_db():
    conn = psycopg2.connect(
        dbname='trading',
        user='123',
        password='123123',
        host='localhost',
        port='5432',
        cursor_factory=RealDictCursor
    )
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS user_positions, user_balances, users CASCADE;")

    cur.execute("""
        CREATE TABLE users (
            username VARCHAR(50) PRIMARY KEY,
            password_hash VARCHAR(255) NOT NULL
        );
        CREATE TABLE user_balances (
            user_id VARCHAR(50) PRIMARY KEY,
            balance DECIMAL(10, 2) NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(username)
        );
        CREATE TABLE user_positions (
            user_id VARCHAR(50),
            currency VARCHAR(50),
            amount DECIMAL(10, 2) NOT NULL,
            PRIMARY KEY (user_id, currency),
            FOREIGN KEY (user_id) REFERENCES users(username)
        );
    """)

    password = "123123"
    password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()  # 对密码进行哈希处理
    cur.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", ('123', password_hash))

    cur.execute("INSERT INTO user_balances (user_id, balance) VALUES (%s, %s)", ('123', 10000))

    conn.commit()
    cur.close()
    conn.close()


def kline_command(name: str):
    msg = kline.get_kline(name, '1h')
    if msg == "Symbol not found":
        abort(404, description='Symbol not found')
    else:
        filepath = 'kl.jpg'
        return send_file(filepath, mimetype='image/jpeg')

app = Flask(__name__)

users_balance = {}

users_positions = {}

users = {
    "admin": "password"
}


def check_auth(username, password):
    if username in users and users[username] == password:
        return True
    return False

def authenticate():
    return jsonify({"message": "Authentication required"}), 401


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)

    return decorated

@app.route("/")
def homepage():
    return "Welcome to the homepage. Available APIs: /query_price, /plot_price, /buy, /sell, /query_balance, /top_up"


def get_price(symbol):
    base_url = "https://www.binance.com/api/v3/ticker/price"
    try:
        response = requests.get(f"{base_url}?symbol={symbol}USDT")
        response.raise_for_status()
        data = response.json()
        return data.get("price")
    except requests.RequestException as e:
        print(f"Error fetching price data: {e}")
        return None

@app.route("/query_price")
def query_price():
    currency = request.args.get("currency", "BTC")
    price = get_price(currency)
    if price:
        return jsonify({"currency": currency, "price": price})
    else:
        return jsonify({"error": "Unable to fetch price data"}), 500

@app.route("/plot_price")
def plot_price():
    currency = request.args.get("symbol")
    if not currency:
        abort(400, description='No currency provided')
    return kline_command(currency)


@app.route("/buy")
def buy():
    user_id = request.args.get("user_id")
    currency = request.args.get("currency", "BTC")
    amount = float(request.args.get("amount", 1))
    price = get_price(currency)

    if price is None:
        return jsonify({"error": "Unable to fetch current price"}), 500

    price = float(price)
    required_balance = amount * price

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT balance FROM user_balances WHERE user_id = %s", (user_id,))
    user_balance = cur.fetchone()

    if user_balance is None or user_balance['balance'] < required_balance:
        cur.close()
        conn.close()
        return jsonify({"error": "Not enough balance"}), 400

    _update_balance(user_id, -required_balance)
    _update_position(user_id, currency, amount)

    return jsonify({"user_id": user_id, "action": "buy", "currency": currency, "amount": amount, "price": price, "balance": user_balance['balance'] - required_balance})


@app.route("/sell")
def sell():
    user_id = request.args.get("user_id")
    currency = request.args.get("currency", "BTC")
    amount = float(request.args.get("amount", 1))
    price = get_price(currency)

    if price is None:
        return jsonify({"error": "Unable to fetch current price"}), 500

    price = float(price)
    total_sale = amount * price

    _update_position(user_id, currency, -amount)
    _update_balance(user_id, total_sale)

    return jsonify({"user_id": user_id, "action": "sell", "currency": currency, "amount": amount, "price": price})

def _update_position(user_id, currency, amount):
    conn = get_db_connection()
    cur = conn.cursor()

    if amount < 0:
        cur.execute("SELECT amount FROM user_positions WHERE user_id = %s AND currency = %s", (user_id, currency))
        user_position = cur.fetchone()

        if user_position:
            new_amount = user_position['amount'] + amount
            if new_amount <= 1e-7:
                cur.execute("DELETE FROM user_positions WHERE user_id = %s AND currency = %s", (user_id, currency))
            else:
                cur.execute("UPDATE user_positions SET amount = %s WHERE user_id = %s AND currency = %s", (new_amount, user_id, currency))
    else:
        cur.execute("INSERT INTO user_positions (user_id, currency, amount) VALUES (%s, %s, %s) ON CONFLICT (user_id, currency) DO UPDATE SET amount = user_positions.amount + EXCLUDED.amount", (user_id, currency, amount))

    conn.commit()
    cur.close()
    conn.close()
@app.route("/query_balance")
def query_balance():
    user_id = request.args.get("user_id")
    balance = users_balance.get(user_id, 0)
    return jsonify({"user_id": user_id, "balance": balance})


@app.route("/top_up", methods=["GET"])
def top_up():
    user_id = request.args.get("user_id")
    amount = float(request.args.get("amount", 0))
    _update_balance(user_id, amount)
    return jsonify(
        {
            "user_id": user_id,
            "top_up_amount": amount,
            "new_balance": users_balance[user_id],
        }
    )


def _update_balance(user_id, amount):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE user_balances SET balance = balance + %s WHERE user_id = %s",
        (amount, user_id)
    )
    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
