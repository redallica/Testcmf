# -*- coding: utf-8 -*-
"""
Created on Thu Nov 22 18:36:48 2018

@author: r_ben
"""

import os
import sys
import numpy as np
import pandas as pd
import ccxt 
import time
import talib as ta
#from datetime import datetime
# Import smtplib for the actual sending function
import smtplib

# Import the email modules we'll need
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def current_price2(symbol):
    ticker = exchange.fetch_ticker(symbol)
    return ticker['last']

def CMF(high, low, close, volume, periods):
    vectorSize = high.shape[0]; 
    moneyFlowMultiplier = ((close - low) - (high - close)).values.reshape((vectorSize,1)) * np.linalg.pinv((high - low).values.reshape((vectorSize,1)));
    moneyFlowVolume = np.dot(moneyFlowMultiplier,volume.values.reshape((vectorSize,1)));
    cmf = np.zeros(vectorSize);
    cmf[:] = np.NAN;
    for i in range((periods-1),vectorSize):   
        cmf[i] = sum(moneyFlowVolume[i-periods+1:i+1]) / sum(volume[i-periods+1:i+1])
    return cmf

def send_report(cmf, T3, cci):
    now = time.strftime('%d-%m-%Y %H:%M')
    # Last BTC price
    tick = exchange.fetch_ticker(symbol)
    last_ticker = tick['last']
    # Pull balance
    updated_balance = exchange.fetch_balance()
    new_balance = updated_balance['BTC']['total']
    # Pull current position
    current_position = exchange.private_get_position()
    position = current_position[0]['currentQty']
    # Open orders status
    open_order = exchange.fetchOpenOrders(symbol)
    open_orders = len(open_order)
    # Pull technical indicators
    last_cmf = cmf[-1]
    last_T3 = T3[-1]
    last_cci = cci.iloc[-1]

    # Text message
    #msg = MIMEText('Le rapport Trading Bot pour la journée de ', now)
               
    me ='bluseeapps@gmail.com'
    you = 'r_benkirane@hotmail.com'
    msg = MIMEMultipart()
    msg['Subject'] = 'Trading Bot Report for {}'.format(now) 
    msg['From'] = me
    msg['To'] = you

    # Send the message via Gmail SMTP server.
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()

    #Next, log in to the server
    server.login("bluseeapps@gmail.com", "bEbinoux_00")
    message = 'Le cours de BTC est: {} $. \n\nLa balance du compte Bitmex est: {} BTC. \n\nLa position actuelle est de {} contrats. \n\nLe nombre de position ouverte est de {}. \n\nLa dernière valeur du CMF est {}. \n\nLa dernière valeur du T3 est {}. \n\nLa dernière valeur du CCI est {}.'.format(last_ticker, new_balance, position, open_orders, last_cmf, last_T3, last_cci)
    msg.attach(MIMEText(message, 'plain'))
    server.send_message(msg, me, you)
    print('Daily report sent at: {}'.format(now))

    # Terminate the SMTP session and close the connection
    server.quit()
    
def create_order(symbol, type, side, amount, price):
    
    mx_try = 3
    nb_try = 1
    
    for i in range (mx_try):
        try:
                
            print('order: attempt number {}'.format(nb_try))
            order = exchange.create_order(symbol, type, side, amount, price)
            return order
            break
        except (ccxt.ExchangeNotAvailable, ccxt.DDoSProtection, ccxt.ExchangeError) as e:
        # add your handling or do nothing and retry
            print(e.args)
            print('waiting 10 seconds')
            time.sleep(10.0)
            nb_try += 1
            if nb_try == mx_try + 1:
                print('order rejected')
                break
                
                
def check_balance():
    
    mx_try = 3
    nb_try = 1
    
    for i in range (mx_try):
        try:
            print('checking current balance ...')    
            balance = exchange.fetch_balance()
            current_balance = balance['BTC']['total']
            return current_balance
            break
        except (ccxt.ExchangeNotAvailable, ccxt.DDoSProtection, ccxt.ExchangeError) as e:
        # add your handling or do nothing and retry
            print(e.args)
            print('waiting 10 seconds')
            time.sleep(10.0)
            nb_try += 1
            print('nb try = ', nb_try)
            if nb_try == mx_try + 1:
                print('checking balance failed')
                break
    
    
#params
symbol = 'BTC/USD'  # bitcoin contract according to https://github.com/ccxt/ccxt/wiki/Manual#symbols-and-market-ids
type = 'Limit'  # or 'Market', or 'Stop' or 'StopLimit'
side_short = 'sell'  # or 'buy'
side_long = 'buy'
params = {'partial': 0}  # ←--------  no reversal
timeframe = '1m'
limit = 750 # retrieve the last 63 1m candles

T3_length = 5
T3_Ev_EMA = 24
Volume_Factor = 0.51
ma_s = 200 
EMA_OBV = 13
CCI_Length = 10
CCI_Max = 0
CCI_Min = -15
CMF_L = 30

print('Initiating BITMEX API connections ...')

exchange = ccxt.bitmex({
    'apiKey': 'B-Z2ka9S5uCnqBNot5aAVa71',
    'secret': 'e9nE4CJIIXYy6XPsoJcC1t0DDN7LnWyBfyZ5snPgZiKFEUcf',
    'enableRateLimit': True,})

if 'test' in exchange.urls:
    exchange.urls['api'] = exchange.urls['test'] # ←----- switch the base URL to testnet

print('Connections established successfully')    

#Check and return current balance
current_balance = check_balance()
print('current balance = {} BTC'.format(current_balance))

print('current price = ', current_price2(symbol))
# balance = exchange.fetch_balance()
# current_balance = balance['BTC']['total']
amount = int(current_balance * 0.01 * current_price2(symbol))
print('position size = ', amount)


# Algo logic

while True: # True to make it run
    
    # define price long and price short
    price_short = current_price2(symbol) + 0.5
    price_long = current_price2(symbol) - 0.5
    
    # set new order to False
    new_order = False
    
    # Check open orders status
    open_orders = exchange.fetchOpenOrders(symbol)
    nb_open_orders = len(open_orders)
    print('number of open orders = ', nb_open_orders)
    
    # pay attention to since with respect to limit if you're doing it in a loop
    since = exchange.milliseconds() - limit * 5 * 1000
    starttime = time.strftime('%Y-%m-%d %H:%M')
    print('start time = ', starttime)
    
    candles = exchange.fetch_ohlcv(symbol, timeframe, since, limit, params)
    header = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
    prices = pd.DataFrame(candles, columns=header)
    prices['Date'] = pd.to_datetime(prices['Time'], errors='coerce', unit='ms', utc=True)
    prices['Date'] = prices['Date'].dt.strftime('%Y-%m-%d %H:%M')
    prices.set_index('Date', inplace=True)
    prices.drop('Time', axis=1, inplace=True)
    prices.index = pd.to_datetime(prices.index)
    prices = prices.resample("1min").mean()
    prices.fillna(method="ffill", inplace=True)
    
    print(prices)
    
    H = prices['High']  
    L = prices['Low']  
    C = prices['Close'] 
    V = prices['Volume']

    my_prices = (H + L + 2*C) / 4 
    T3_btc_Adj = ta.T3(my_prices, timeperiod = T3_length, vfactor = Volume_Factor)
    #print('T3 = ', T3_btc_Adj)
    
    # T3Ev=T3-T3[1]
    T3_Ev_btc_Adj = np.ediff1d(T3_btc_Adj)
    #print('T3 EV = ', T3_Ev_btc_Adj)
    
    # ema=ema(T3Ev, T3_EMA)
    T3_ev_ema_Adj_close = ta.EMA(T3_Ev_btc_Adj, timeperiod = T3_Ev_EMA)
    #print('EMA T3 EV = ', T3_ev_ema_Adj_close)
    
    # CMF
    btc_OBV = ta.OBV(C, V)
    #print('OBV = ', btc_OBV)
    
    #btc_obv = obv(C, V)
    #print('OBV2 = ', btc_obv)
    
    #btc_obv_mean = obv_mean(C, V)
    #print('OBV3 = ', btc_obv_mean)
    
    #ema_OBV = ta.EMA(btc_OBV, timeperiod = EMA_OBV)
    btc_CMF = CMF(H, L, C, V, CMF_L)
    #print('CMF = ', btc_CMF)
    
    #btc_cmf = cmf(H, L, C, V, n=CMF_L)
    #print('CMF2 = ', btc_cmf)
    

    # CCI
    btc_CCI = ta.CCI(H, L, C, timeperiod = CCI_Length)
    #print('CCI = ', btc_CCI)
        
    current_position = exchange.private_get_position()
    #(btc_OBV[-1] > btc_OBV[-2]) & 
    
    if (btc_CMF[-1] >= btc_CMF[-2]) & (T3_Ev_btc_Adj[-1] > T3_Ev_btc_Adj[-2]) & (btc_CCI.iloc[-1] > CCI_Max):
        if current_position[0]['currentQty'] == 0:
            if nb_open_orders == 0:
                price_long = current_price2(symbol) - 0.5
                order = create_order(symbol, type, side_long, amount, price_long)
                print('order long at price : ', price_long)
                print('current price : ', current_price2(symbol))
                new_order = True
                current_position = exchange.private_get_position()
                print('current position after order long: ', current_position[0]['currentQty'])
            elif nb_open_orders > 0:
                pass
        elif current_position[0]['currentQty'] < 0:
            if nb_open_orders == 0:
                price_long = current_price2(symbol) - 0.5
                order = create_order(symbol, type, side_long, 2 * amount, price_long)
                print('order 2*long at price : ', price_long)
                print('current price : ', current_price2(symbol))
                new_order = True
                current_position = exchange.private_get_position()
                print('current position after order 2*long: ', current_position[0]['currentQty'])
            elif nb_open_orders > 0:
                pass
        elif current_position[0]['currentQty'] > 0:
            pass
            
    if (btc_CMF[-1] <= btc_CMF[-2]) & (T3_Ev_btc_Adj[-1] < T3_Ev_btc_Adj[-2]) & (btc_CCI.iloc[-1] < CCI_Min):
        if current_position[0]['currentQty'] == 0:
            if nb_open_orders == 0:
                price_short = current_price2(symbol) + 0.5
                order = create_order(symbol, type, side_short, amount, price_short)
                print('order short at price : ', price_short)
                print('current price : ', current_price2(symbol))
                new_order = True
                current_position = exchange.private_get_position()
                print('current position after order short: ', current_position[0]['currentQty'])
            elif nb_open_orders > 0:
                pass
        elif current_position[0]['currentQty'] > 0:
            if nb_open_orders == 0:
                price_short = current_price2(symbol) + 0.5
                order = create_order(symbol, type, side_short, 2 * amount, price_short)
                print('order 2*short at price : ', price_short)
                print('current price : ', current_price2(symbol))
                new_order = True
                current_position = exchange.private_get_position()
                print('current position after order 2*short: ', current_position[0]['currentQty'])
            elif nb_open_orders > 0:
                pass
        elif current_position[0]['currentQty'] < 0:
            pass
        
    if (current_position[0]['currentQty'] < 0) & ((T3_Ev_btc_Adj[-1] > T3_ev_ema_Adj_close[-1]) | (T3_ev_ema_Adj_close[-1] > T3_ev_ema_Adj_close[-2])):
        if (nb_open_orders == 0) & (new_order == False):
            order_close = create_order(symbol, type, side_long, current_position[0]['currentQty'], price_long)
            print('order close for short position at price : ', price_long)
            print('current price : ', current_price2(symbol))
            new_order = True
            current_position = exchange.private_get_position()
        elif nb_open_orders > 0:
            pass
        
    if (current_position[0]['currentQty'] > 0) & ((T3_Ev_btc_Adj[-1] < T3_ev_ema_Adj_close[-1]) | (T3_ev_ema_Adj_close[-1] < T3_ev_ema_Adj_close[-2])):
        if (nb_open_orders == 0) & (new_order == False):
            order_close = create_order(symbol, type, side_short, current_position[0]['currentQty'], price_short)
            print('order close for long position at price : ', price_short)
            print('current price : ', current_price2(symbol))
            new_order = True
        elif nb_open_orders > 0:
            pass
        
    updated_balance = exchange.fetch_balance()
    new_balance = updated_balance['BTC']['total']
    updated_orders = exchange.fetchOpenOrders(symbol)
    updated_open_orders = len(updated_orders)
    #print(prices)
    print('current position = ', current_position[0]['currentQty'])
    print('number of open orders after cycle = ', updated_open_orders)
    print('current price = ', current_price2(symbol))
    print('last CMF = ', btc_CMF[-1])
    print('second last CMF = ', btc_CMF[-2])
    print('last T3 EV = ', T3_Ev_btc_Adj[-1])
    print('second last T3 EV = ', T3_Ev_btc_Adj[-2])
    print('last CCI = ', btc_CCI.iloc[-1])
    
    # Send report
    send_report(btc_CMF, T3_Ev_btc_Adj, btc_CCI)
    #time.sleep(exchange.rateLimit * 30 / 1000) #30 to check price every minute
    time.sleep(60.0)