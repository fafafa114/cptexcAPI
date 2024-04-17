from query_script.config import *

# modified from the code of https://stackoverflow.com/a/74628882
def request_binance(ticker, interval, limit=250) -> pd.DataFrame:
    columns = ['time', 'open', 'high', 'low', 'close', 'vol', 'close_time',
               'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore']
    url = f'https://www.binance.com/api/v3/klines?symbol={ticker}&interval={interval}&limit={limit}'
    data = pd.DataFrame(requests.get(url).json(), columns=columns, dtype=float)
    data.time = [pd.to_datetime(x, unit='ms').strftime(
        '%Y-%m-%d %H:%M:%S') for x in data.time]
    usecols = ['time', 'open', 'high', 'low', 'close', 'vol']
    data = data[usecols]
    return data


def get_exchange_info():
    url = 'https://www.binance.com/api/v3/exchangeInfo'
    data = requests.get(url).json()
    return data