"""
    Description: Contains functions on APIs and turning that into candlestick data.
"""
import requests
from cryptolytic.util import date
from cryptolytic.data import sql
import time
import os
import requests
import json
from datetime import datetime
import numpy as np
import pandas as pd


# Json conversion dictionary for cryptocurrency abbreviations
crypto_name_table = None
with open('data/cryptocurrencies.json', 'r', encoding='utf-8') as f:
    crypto_name_table = json.load(f)
assert crypto_name_table.keys()

"""
If you are having timeout issues connecting to the AWS RDS instance, make sure
to configure your AWS VPC security groups to allow outside access
"""
api_info = None
with open('data/api_info.json', 'r') as f:
    api_info = json.load(f)
assert len(api_info) > 1

# TODO consider putting into a more general file
def crypto_full_name(crypto_short):
    """crypto_short: e.g. eth, btc
       result: e.g. Ethereum, Bitcoin"""
    #print(crypto_name_table)
    lookup = crypto_name_table.get(crypto_short.upper())
    return lookup

def trading_pair_info(api, x):
    """Returns full info for the trading pair necessary for the exchange.
    x: e.g. btc_eth
    """
    # btcheth style trading pairs
    baseId, quoteId = x.split('_')
    handled = False

    if api in {'cryptowatch', 'hitbtc', 'bitfinex'}:
        x = x.replace('_', '')
        handled = True
    if api in {'poloniex', 'hitbtc', 'bitfinex'}:
        x = x.upper()
        handled = True
    if api in {'coincap'}:
        baseId = crypto_full_name(baseId).lower()
        quoteId = crypto_full_name(quoteId).lower()
        handled = True
    if not handled:
        raise Exception('API not supported ', api)

    return {'baseId' : baseId,
            'quoteId' : quoteId,
            'trading_pair' : x}

def convert_candlestick(candlestick, api, timestamp):
    # dict with keys :open, :high, :low, :close, :volume, :quoteVolume, :timestamp
    candlestick = candlestick.copy()

    if api=='poloniex':
        pass
    elif api=='coincap':
        pass
    elif api=='cryptowatch':
        candlestick = {
            'close' : candlestick[0],
            'open'  : candlestick[1],
            'high'  : candlestick[2],
            'low'   : candlestick[3],
            'volume' : candlestick[4],
        }
    elif api=='bitfinex':
        candlestick = {
            'open'  : candlestick[1],
            'close' : candlestick[2],
            'high'  : candlestick[3],
            'low'   : candlestick[4],
            'volume' : candlestick[5],
        }
    elif api=='hitbtc':
        candlestick['high'] = candlestick.pop('max')
        candlestick['low'] = candlestick.pop('min')
    else:
        raise Exception('API not supported ', api)

    candlestick['timestamp'] = timestamp
    return candlestick

def format_apiurl(api, params={}):
    url = None
    params = params.copy()
    # Coincap expects milliseconds in its url query
    if api in {'coincap'}:
        params['start'] *= 1000
        params['end'] *= 1000
    # Standard URL query
    if api in {'cryptowatch', 'poloniex', 'coincap', 'hitbtc', 'bitfinex'}:
        url = api_info[api]['api_call'].format(**params)
    # Hasn't been verified
    else:
        raise Exception('API not supported', api)
    print(url)
    return url

# Coincap uses time intervals like h1, m15 etc. so need a function to convert to the seconds to that format
def get_time_interval(api, period):
    """For coincap, hitbtc, etc. which use a format like 'm1' instead of period like 60 for 60 seconds."""
    minutes = period / 60
    hours = minutes / 60
    days = hours / 24
    weeks = days / 7

    accepted_values = {
        'coincap' : {
            'weeks' : [1],
            'days' : [1],
            'hours' : [1, 2, 4, 8, 12],
            'minutes' : [1, 5, 15, 30],
        },
        'hitbtc' : {
            'days' : [1, 7],
            'hours' : [1, 4],
            'minutes' : [1, 3, 5, 15, 30]
        },
        'bitfinex' : {
            'minutes' : [1, 5, 15, 30],
            'hours' : [1, 3, 6, 12],
            'days' : [1, 7, 14],
        }
    }.get(api)


    if accepted_values == None:
        raise Exception('API not supported', api)
    elif weeks >= 1 and accepted_values.has('weeks'):
        x = list(filter(lambda x: x<weeks, accepted_values['weeks']))
        interval = 'w'+str(np.max(x))
    elif days >= 1:
        x = list(filter(lambda x: x<days, accepted_values['days']))
        interval = 'd'+str(np.max(x))
    elif hours >= 1:
        x = list(filter(lambda x: x<hours, accepted_values['hours']))
        interval = 'h'+str(np.max(x))
    else:
        x = [1] + list(filter(lambda x: x<minutes, accepted_values['minutes']))
        interval = 'm'+str(np.max(x))

    # expects uppercase like 'M1' for 1 minute
    if api in {'hitbtc'}:
        interval = interval.upper()
    if api in {'bitfinex'}: # expect 1m format instead
        interval = interval[1:] + interval[0]

    return interval

def conform_json_response(api, json_response):
    """Get the right data from the json response. Expects a list, either like [[],...], or like [{},..]"""
    if api=='cryptowatch':
        return json_response['result'][str(period)] # TODO fix
    elif api=='coincap':
        return json_response['data']
    elif api in {'poloniex', 'hitbtc', 'bitfinex'}:
        return json_response
    else:
        raise Exception('API not supported', api)
    return None

def get_from_api(api='cryptowatch', exchange='binance', trading_pair='btc_eth',
                 period=60, interval=None, apikey=None):
    """period : candlestick length in seconds. Default 4 hour period.
       interval : time interval, [start, end] either unix or %d-%m-%Y format
    """
    if api in {'cryptowatch'} and apikey==None:
        raise Exception('Missing API key')

    # Variable initialization
    pair_info = trading_pair_info(api, trading_pair)
    baseId = pair_info.get('baseId') # the first coin in the pair
    quoteId = pair_info.get('quoteId') # the second coin in the pair
    trading_pair = pair_info.get('trading_pair') # e.g. eth_usd in the form of what the api expects
    start = date.convert_datetime(interval[0]) # start time unix timestamp
    end = date.convert_datetime(interval[1])  # end time unix timestamp
    limit=100 # 100 limit by default, should change depending on the API later, by adding the limit information in data/api_info.json
    assert start < end

    # parameters for the url to get candle data from
    urlparams = dict(exchange=exchange, trading_pair=trading_pair, apikey=apikey,
                     period=period, end=start+(limit*period), baseId=baseId, quoteId=quoteId,
                     limit=limit)

    # The API uses another notation for period (like 1m for 1 minute)
    if api in {'coincap', 'hitbtc', 'bitfinex'}:
        urlparams['interval'] = get_time_interval(api, period)


    # Get all the candle sticks in the time period.
    current_timestamp = start
    candles = []
    while current_timestamp < end:
        urlparams['start']=current_timestamp
        urlparams['end']=current_timestamp+(limit*period)
        url = format_apiurl(api, urlparams)

        # TODO more error checking and rescheduling if there is an error and the current_timestamp has been updated at least one (i.e. > start)
        response = requests.get(url)
        if response.status_code != 200:
            print(f"""In function get_from_api, got bad response {response.status_code}. Exiting early.""")
            break

        # load and convert the candlestick info to be a common format
        json_response = json.loads(response.content)
        candlestick_info = conform_json_response(api, json_response)

        assert len(candlestick_info) > 0
        # Add to candles list.
        for i, candle in enumerate(candlestick_info):
            current_timestamp += period
            candlenew = convert_candlestick(candle, api, current_timestamp)
            candles.append(candlenew)


            # Check if candle schema is valid
            candle_schema = ['timestamp', 'open', 'close', 'volume', 'high', 'low']
            assert all(x in candles[0].keys() for x in candle_schema)

        # Sleep for a second to avoid timeout. Should improve later.
        time.sleep(1)

        # yield the candlestick information
        yield dict(
            api = api,
            exchange = exchange,
            candles=candles,
            last_timestamp    = current_timestamp,
            trading_pair = trading_pair,
            candles_collected = len(candles),
            period = period) # period in seconds
    
def live_update():
    """
        Updates the database based on the info in data/api_info.json with new candlestick info,
        grabbing data from the last timestamp until now, with the start date set at the start of 2019.
    """
    for api, api_data in api_info.items():
        api_exchanges = api_data['exchanges']
        for exchange_id, exchange_data in api_exchanges.items():
            for trading_pair in exchange_data['trading_pairs']:
                # timestamp is January 1st 2019
                start = sql.get_latest_date(exchange_id, trading_pair) or 1546300800 
                end = int(time.time()) # the time is now

                for candle_info in get_from_api(
                                        api=api,
                                        exchange=exchange_id,
                                        trading_pair=trading_pair,
                                        period=300,
                                        interval=[start, end]):

                    # Log the timestamp
                    ts = candle_info['last_timestamp']
                    print(datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S'))

                    # Insert into sql
                    try:
                        sql.candlestick_to_sql(candle_info)
                    except Exception as e:
                        print(e)

                # TODO, update dataframe with candle info and save that 
                # later to a csv
                return # TODO  remove

def test_get_candles():
    start = '01-01-2019'
    start = date.convert_datetime(start)
    end = start + 14400*2

    candle_info = get_from_api(api='bitfinex',
                            exchange='binance',
                            trading_pair ='eth_btc',
                            period=14400,
                            interval=[start, end],
                            apikey=os.getenv('_cryptowatch_private_key'))

    assert candle_info['candles'][0].keys()

    return candle_info