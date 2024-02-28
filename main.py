from flask import Flask, jsonify, request

app = Flask(__name__)

users_balance = {}

users_positions = {}


@app.route("/")
def homepage():
    return "Welcome to the homepage. Available APIs: /query_price, /plot_price, /buy, /sell, /query_balance, /top_up"


@app.route("/query_price")
def query_price():
    currency = request.args.get("currency", "BTC")
    return f"Querying prices for {currency}."


@app.route("/plot_price")
def plot_price():
    currency = request.args.get("currency", "BTC")
    return f"Plotting price chart for {currency}."


@app.route("/buy")
def buy():
    user_id = request.args.get("user_id")
    currency = request.args.get("currency", "BTC")
    amount = float(request.args.get("amount", 1))
    price = 100

    required_balance = amount * price
    current_balance = users_balance.get(user_id, 0)

    if current_balance < required_balance:
        return jsonify({"error": "No enough balance"}), 400

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
            "balance": users_balance[user_id],
        }
    )


@app.route("/sell")
def sell():
    user_id = request.args.get("user_id")
    currency = request.args.get("currency", "BTC")
    amount = float(request.args.get("amount", 1))
    price = 100

    current_position = users_positions.get(user_id, {}).get(currency, 0)

    if current_position < amount:
        return jsonify({"error": "No enough position"}), 400

    _update_balance(user_id, amount * price)
    users_positions[user_id][currency] -= amount

    return jsonify(
        {
            "user_id": user_id,
            "action": "sell",
            "currency": currency,
            "amount": amount,
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
