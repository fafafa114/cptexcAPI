from query_script.requests import get_exchange_info

def search(symbol) -> list:
    data = get_exchange_info()['symbols']
    symbol = symbol.upper()
    possible = [(item['symbol'], item['symbol'].find(symbol)) for item in data if symbol in item['symbol']]
    possible.sort(key=lambda x: x[1]) # sort by index of symbol
    possible = [item[0] for item in possible][:10]
    return possible