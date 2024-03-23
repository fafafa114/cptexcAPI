from functools import wraps
from decimal import Decimal

from flask import Flask, jsonify, request, send_file, abort
import requests
from query_script import kline, search_symbol
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib

def get_db_connection():
    return psycopg2.connect(
        dbname='postgres',
        user='postgres',
        password='123123',
        host='localhost',
        port='5432',
        cursor_factory=RealDictCursor
    )



def kline_command(name: str):
    msg = kline.get_kline(name, '1h')
    if msg == "Symbol not found":
        abort(404, description='Symbol not found')
    else:
        filepath = 'kl.jpg'
        return send_file(filepath, mimetype='image/jpeg')

app = Flask(__name__)

# users_balance = {}

# users_positions = {}

users = {
    "admin": "password"
}


def check_auth(username, password):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user:
        password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        return user['password_hash'] == password_hash
    return False


def add_user(username, password):
    conn = get_db_connection()
    cur = conn.cursor()
    password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
    try:
        cur.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, password_hash))
        cur.execute("INSERT INTO user_balances (user_id, balance) VALUES (%s, %s)", (username, 0))
        conn.commit()
        success = True
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        conn.rollback()
        success = False
    finally:
        cur.close()
        conn.close()
    return success

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
@requires_auth
def buy():
    user_id = request.args.get("user_id")
    currency = request.args.get("currency", "BTC")
    try:
        amount = float(request.args.get("amount", 1))
        if amount <= 0:
            raise ValueError("Amount must be a positive number.")
    except ValueError as e:
        return jsonify({"error": "Invalid amount. Please provide a valid positive number."}), 400
    price = get_price(currency)

    if price is None:
        return jsonify({"error": "Unable to fetch current price"}), 500

    price = float(price)
    required_balance = amount * price

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT balance FROM user_balances WHERE user_id = %s", (user_id,))
    user_balance = cur.fetchone()
    if user_balance is None or user_balance['balance'] + Decimal(1e-4) < required_balance:
        cur.close()
        conn.close()
        return jsonify({"error": "Not enough balance"}), 400

    new_balance = _update_balance(user_id, -required_balance)
    new_position = _update_position(user_id, currency, amount)

    return jsonify({
        "user_id": user_id,
        "action": "buy",
        "currency": currency,
        "amount": amount,
        "price": price,
        "new_balance": new_balance,
        "new_position": new_position
    })


@app.route("/sell")
@requires_auth
def sell():

    user_id = request.args.get("user_id")
    currency = request.args.get("currency", "BTC")
    try:
        amount = float(request.args.get("amount", 1))
        if amount <= 0:
            raise ValueError("Amount must be a positive number.")
    except ValueError as e:
        return jsonify({"error": "Invalid amount. Please provide a valid positive number."}), 400
    price = get_price(currency)

    if price is None:
        return jsonify({"error": "Unable to fetch current price"}), 500

    price = float(price)

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT amount FROM user_positions WHERE user_id = %s AND currency = %s", (user_id, currency))
    user_position = cur.fetchone()
    # print(f"amount: {amount}")
    if user_position is None or user_position['amount'] + Decimal(1e-6) < amount:
        cur.close()
        conn.close()
        return jsonify({"error": "Not enough position"}), 400

    total_sale = amount * price

    new_position = _update_position(user_id, currency, -amount)
    new_balance = _update_balance(user_id, total_sale)

    return jsonify({
        "user_id": user_id,
        "action": "sell",
        "currency": currency,
        "amount": amount,
        "price": price,
        "new_balance": new_balance,
        "new_position": new_position
    })
def _update_position(user_id, currency, amount):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT amount FROM user_positions WHERE user_id = %s AND currency = %s", (user_id, currency))
    result = cur.fetchone()
    if result:
        amount_decimal = Decimal(str(amount))
        new_amount = result['amount'] + amount_decimal
        # print(new_amount)
        if new_amount < 1e-8:
            cur.execute("DELETE FROM user_positions WHERE user_id = %s AND currency = %s", (user_id, currency))
            new_amount = 0
        else:
            cur.execute("UPDATE user_positions SET amount = %s WHERE user_id = %s AND currency = %s RETURNING amount", (new_amount, user_id, currency))
            new_amount = cur.fetchone()['amount']
    else:
        if amount > 0:
            cur.execute("INSERT INTO user_positions (user_id, currency, amount) VALUES (%s, %s, %s) RETURNING amount", (user_id, currency, amount))
            new_amount = cur.fetchone()['amount']
        else:
            assert(False)
    conn.commit()
    cur.close()
    conn.close()
    return new_amount

@app.route("/query_balance")
@requires_auth
def query_balance():
    user_id = request.args.get("user_id")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM user_balances WHERE user_id = %s", (user_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    balance = result['balance'] if result else 0
    return jsonify({"user_id": user_id, "balance": balance})

@app.route("/top_up", methods=["GET"])
@requires_auth
def top_up():
    user_id = request.args.get("user_id")
    amount = float(request.args.get("amount", 0))
    new_balance = _update_balance(user_id, amount)
    return jsonify({"user_id": user_id, "top_up_amount": amount, "new_balance": new_balance})

def _update_balance(user_id, amount):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE user_balances SET balance = balance + %s WHERE user_id = %s RETURNING balance", (amount, user_id))
    new_balance = cur.fetchone()['balance']
    conn.commit()
    cur.close()
    conn.close()
    return new_balance

def initialize_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS user_positions CASCADE")
    cur.execute("DROP TABLE IF EXISTS user_balances CASCADE")
    cur.execute("DROP TABLE IF EXISTS users CASCADE")
    cur.execute("""
        CREATE TABLE users (
            username VARCHAR(50) PRIMARY KEY,
            password_hash VARCHAR(255) NOT NULL
        );
        CREATE TABLE user_balances (
            user_id VARCHAR(50) PRIMARY KEY,
            balance DECIMAL(15, 3) NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(username)
        );
        CREATE TABLE user_positions (
            user_id VARCHAR(50),
            currency VARCHAR(50),
            amount DECIMAL(25, 9) NOT NULL,
            PRIMARY KEY (user_id, currency),
            FOREIGN KEY (user_id) REFERENCES users(username)
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

    add_user('q123', '123123')



if __name__ == "__main__":
    initialize_db()
    app.run(host="127.0.0.1", port=8080, debug=True)
