from functools import wraps

from flask import Flask, jsonify, request, send_file, abort
import requests
from query_script import kline, search_symbol
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib

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
    current_balance = users_balance.get(user_id, 0)

    if current_balance < required_balance:
        return jsonify({"error": "Not enough balance"}), 400

    _update_balance(user_id, -required_balance)
    users_positions[user_id] = users_positions.get(user_id, {})
    users_positions[user_id][currency] = (
            users_positions[user_id].get(currency, 0) + amount
    )

    return jsonify(
        {
            "user_id": user_id,
            "action": "buy",
            "currency": currency,
            "amount": amount,
            "price": price,
            "balance": users_balance[user_id],
        }
    )


@app.route("/sell")
def sell():
    user_id = request.args.get("user_id")
    currency = request.args.get("currency", "BTC")
    amount = float(request.args.get("amount", 1))
    price = get_price(currency)

    if price is None:
        return jsonify({"error": "Unable to fetch current price"}), 500

    price = float(price)
    current_position = users_positions.get(user_id, {}).get(currency, 0)

    if current_position < amount:
        return jsonify({"error": "Not enough position"}), 400

    _update_balance(user_id, amount * price)
    users_positions[user_id][currency] -= amount

    return jsonify(
        {
            "user_id": user_id,
            "action": "sell",
            "currency": currency,
            "amount": amount,
            "price": price,
            "balance": users_balance[user_id],
        }
    )

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
    users_balance[user_id] = users_balance.get(user_id, 0) + amount


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
