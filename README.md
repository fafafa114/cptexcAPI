# Trading API

## Intro
APIs for simulating basic transactions. It supports querying, plotting price charts, buying/selling currencies.

## Features & Examples

### Query Price
- **GET** `/query_price?currency=ETH`
  - Fetches current price for specified currency (default: BTC).

### Plot Price Chart
- **GET** `/plot_price?currency=ETH`
  - Generates a price chart for the specified currency

### Buy Currency
- **GET** `/buy?user_id=123&currency=ETH&amount=2`
  - Buys a specified amount of currency for a user

### Sell Currency
- **GET** `/sell?user_id=123&currency=ETH&amount=1`
  - Sells a specified amount of currency for a user

### Query Balance
- **GET** `/query_balance?user_id=123`
  - Query the balance

### Top Up Balance
- **GET** `/top_up?user_id=123&amount=1000`
  - Top up the user's balance

