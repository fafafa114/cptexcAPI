import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
import sys, os


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

def add_user(username, password):
    conn = get_db_connection()
    cur = conn.cursor()
    password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
    msg = "Successful!"
    try:
        cur.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, password_hash))
        cur.execute("INSERT INTO user_balances (user_id, balance) VALUES (%s, %s)", (username, 0))
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

initialize_db()