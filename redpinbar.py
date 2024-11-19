import pandas as pd
import requests
from datetime import datetime, timedelta
import ta
import pytz

# Function to fetch historical data from Binance Futures
def fetch_klines(symbol, interval, start_str, end_str):
    url = f"https://fapi.binance.com/fapi/v1/klines"
    params = {
        'symbol': symbol, 
        'interval': interval,
        'startTime': int(start_str.timestamp() * 1000),
        'endTime': int(end_str.timestamp() * 1000)
    }
    response = requests.get(url, params=params)
    data = response.json()
    df = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume', 
        'close_time', 'quote_asset_volume', 'number_of_trades', 
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df.set_index('timestamp', inplace=True)
    df = df[['open', 'high', 'low', 'close', 'volume']]
    df = df.astype(float)
    return df

# Function to check the new conditions
def check_conditions(df, time):
    index = df.index.get_loc(time)
    if index >= 1:  # Ensure there are at least 2 bars to check
        latest_bar = df.iloc[index]
        prev_bar = df.iloc[index-1]

        def is_red_pin_bar(bar):
            body_size = abs(bar['close'] - bar['open'])
            total_size = bar['high'] - bar['low']
            upper_wick = bar['high'] - max(bar['open'], bar['close'])
            lower_wick = min(bar['open'], bar['close']) - bar['low']
            return (
                bar['close'] < bar['open'] and  # Red candle
                bar['open'] < bar['ema21'] and  # Open price below EMA21
                upper_wick > body_size and  # Upper wick is greater than the body
                upper_wick > lower_wick and  # Upper wick is larger than lower wick
                bar['high'] > bar['ema21']  # Upper wick crosses EMA21
            )

        def is_blue_bar(bar):
            return bar['close'] > bar['open']

        if is_red_pin_bar(latest_bar) and is_blue_bar(prev_bar):
            return True
    return False

# Function to get all futures trading pairs from Binance Futures
def get_futures_trading_pairs():
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    response = requests.get(url)
    data = response.json()
    symbols = [symbol['symbol'] for symbol in data['symbols'] if symbol['status'] == 'TRADING']
    return symbols

# Specify the time for checking conditions
interval = '1h'
local_tz = pytz.timezone('Asia/Bangkok')  # Change to your local timezone
end_time = datetime.now(tz=pytz.utc)
start_time = end_time - timedelta(days=1)

# Get all futures trading pairs
symbols = get_futures_trading_pairs()

# Filter for trading pairs with USDT
usdt_symbols = [symbol for symbol in symbols if symbol.endswith('USDT')]

# Analyze each symbol
qualified_symbols = []

for symbol in usdt_symbols:
    try:
        # Fetch historical data
        df = fetch_klines(symbol, interval, start_time, end_time)

        # Calculate EMA21
        df['ema21'] = ta.trend.EMAIndicator(df['close'], window=21).ema_indicator()

        # Ensure timestamp column is timezone-aware
        df.index = df.index.tz_convert('UTC')

        # Analyze the latest time for the conditions
        specific_time_utc = df.index[-1]

        # Check for the conditions
        if check_conditions(df, specific_time_utc):
            # Convert specific_time_utc to local time
            specific_time_local = specific_time_utc.astimezone(local_tz)
            qualified_symbols.append((symbol, specific_time_local))
    except Exception as e:
        pass  # Ignore errors and move to the next symbol

# Print only the qualified pairs with their local times
for symbol, local_time in qualified_symbols:
    print(f"{symbol} qualified with conditions at local time: {local_time}")

print("Qualified symbols with conditions:", [symbol for symbol, _ in qualified_symbols])
