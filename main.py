from functools import wraps
from decimal import Decimal
from flask import Flask, request, render_template_string, redirect, url_for, jsonify, abort, session, send_file
from flask_session import Session
import requests
from query_script import kline, search_symbol
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
import sys, os
import time

def get_db_connection():
    dbname = os.getenv('POSTGRES_DB', 'postgres')
    user = os.getenv('POSTGRES_USER', 'postgres')
    password = os.getenv('POSTGRES_PASSWORD', '123123')
    host = os.getenv('DATABASE_HOST', 'localhost')
    port = os.getenv('DATABASE_PORT', '5432')
    return psycopg2.connect(
        dbname=dbname,
        user=user,
        password=password,
        host=host,
        port=port,
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
app.config["SECRET_KEY"] = os.urandom(24)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

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
    msg = "Successful!"
    try:
        # cur.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, password_hash))
        # cur.execute("INSERT INTO user_balances (user_id, balance) VALUES (%s, %s)", (username, 0))
        cur.execute(f"INSERT INTO users (username, password_hash) VALUES ('{username}', '{password_hash}')")
        cur.execute(f"INSERT INTO user_balances (user_id, balance) VALUES ('{username}', 0)")
        conn.commit()
        success = True
    except psycopg2.Error as e:
        msg = str(e)
        conn.rollback()
        success = False
    finally:
        cur.close()
        conn.close()
    return (success, msg)

def auth_fail():
    return jsonify({"message": "Auth failed"}), 401

def requires_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:  
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if check_auth(username, password):
            session['user_id'] = username
            return redirect(url_for("dashboard"))
        else:
            return "Login Failed", 401
    return '''
    <form method="post">
        Username: <input type="text" name="username"><br>
        Password: <input type="password" name="password"><br>
        <input type="submit" value="Login">
    </form>
    <a href="/register">Register</a>
    '''

@app.route("/logout")
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route("/dashboard")
@requires_auth
def dashboard():
    return '''
    <h1>Dashboard</h1>
    <a href="/query_price"><button>Query Price</button></a>
    <a href="/buy"><button>Buy</button></a>
    <a href="/sell"><button>Sell</button></a>
    <a href="/query_balance"><button>Query Balance</button></a>
    <a href="/position"><button>View Positions</button></a>
    <a href="/top_up"><button>Top Up Balance</button></a>
    <a href="/plot_price"><button>Plot Price</button></a>
    <a href="/logout"><button>Logout</button><a>
    '''


@app.route("/position", methods=["GET"])
@requires_auth
def non_zero_positions():
    user_id = session.get('user_id')
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT currency, amount FROM user_positions WHERE user_id = %s AND amount > 0", (user_id,))
        positions = cur.fetchall()
        if not positions:
            return jsonify({'message': 'No positions found.'})
        return jsonify({'positions': positions})
    except Exception as e:
        print(e)
        return jsonify({'error': 'Database error'}), 500
    finally:
        cur.close()
        conn.close()

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        flag, message = add_user(username, password)
        if not flag:
            return message, 500
        else:
            return message, 200
    return '''
    <form method="post">
        Username: <input type="text" name="username"><br>
        Password: <input type="password" name="password"><br>
        <input type="submit" value="Register">
    </form>
    '''

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

@app.route("/query_price", methods=["GET", "POST"])
def query_price():
    if request.method == "POST":
        currency = request.form["currency"]
        price = get_price(currency)
        if price:
            return jsonify({"currency": currency, "price": price})
        else:
            return jsonify({"error": "Wrong currency"}), 500
    return '''
    <form method="post">
        Currency: <input type="text" name="currency"><br>
        <input type="submit" value="Query Price">
    </form>
    '''
def calculate_load():
    start_time = time.time()
    # Perform a non-optimizable CPU-intensive task
    for i in range(1, 10000000):
        _ = i ** 2

@app.route("/plot_price", methods=["GET", "POST"])
@requires_auth
def plot_price():
    if request.method == "POST":
        currency = request.form["currency"]
        return kline_command(currency)
    return '''
    <form method="post">
        Currency: <input type="text" name="currency"><br>
        <input type="submit" value="Plot Price">
    </form>
    '''

@app.route("/buy", methods=["GET", "POST"])
@requires_auth
def buy():
    if request.method == "POST":
        user_id = session["user_id"]
        currency = request.form["currency"]
        amount = request.form["amount"]
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
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
        if user_balance is None or user_balance['balance'] < required_balance:
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
    return '''
    <form method="post">
        Currency: <input type="text" name="currency"><br>
        Amount: <input type="number" step="0.00000001" name="amount"><br>
        <input type="submit" value="Buy">
    </form>
    '''


@app.route("/sell", methods=["GET", "POST"])
@requires_auth
def sell():
    if request.method == "POST":
        user_id = session.get('user_id')
        currency = request.form["currency"]
        amount = request.form["amount"]
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            return jsonify({"error": "Invalid amount. Please provide a positive number."}), 400

        price = get_price(currency)
        if price is None:
            return jsonify({"error": "Unable to fetch current price"}), 500

        price = float(price)
        total_sale = amount * price

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT amount FROM user_positions WHERE user_id = %s AND currency = %s", (user_id, currency))
        # cur.execute(f"SELECT amount FROM user_positions WHERE user_id = '{user_id}' AND currency = '{currency}'")
        user_position = cur.fetchone()
        if user_position is None or user_position['amount'] < amount:
            cur.close()
            conn.close()
            return jsonify({"error": "Not enough position"}), 400

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
    return '''
    <form method="post">
        Currency: <input type="text" name="currency"><br>
        Amount: <input type="number" step="0.00000001" name="amount"><br>
        <input type="submit" value="Sell">
    </form>
    '''

def _update_position(user_id, currency, amount):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT amount FROM user_positions WHERE user_id = %s AND currency = %s", (user_id, currency))
    result = cur.fetchone()
    if result:
        amount_decimal = Decimal(str(amount))
        new_amount = result['amount'] + amount_decimal
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
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM user_balances WHERE user_id = %s", (user_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    balance = result['balance'] if result else 0
    return jsonify({"user_id": user_id, "balance": balance})

@app.route("/top_up", methods=["GET", "POST"])
@requires_auth
def top_up():
    if request.method == "POST":
        user_id = session.get('user_id')
        amount = request.form["amount"]
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            return jsonify({"error": "Invalid amount. Please provide a valid positive number."}), 400

        new_balance = _update_balance(user_id, amount)

        return jsonify({"user_id": user_id, "top_up_amount": amount, "new_balance": new_balance})
    return '''
    <form method="post">
        Amount: <input type="number" step="0.00001" name="amount"><br>
        <input type="submit" value="Top Up">
    </form>
    '''

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

