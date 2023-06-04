import sys
sys.path.append('/home/ubuntu/.ssh/essai')
import ccxt
import ta
import pandas as pd
from utilities.perp_bitget import PerpBitget
from utilities.custom_indicators import get_n_columns
from datetime import datetime
import time
import json

# Obtenir la date et l'heure actuelles
now = datetime.now()
current_time = now.strftime("%d/%m/%Y %H:%M:%S")
print("--- Heure de début d'exécution :", current_time, "---")

# Charger les informations d'authentification à partir d'un fichier secret
with open("/home/ubuntu/.ssh/essai/secret.json") as f:
    secret = json.load(f)

account_to_select = "bitget_exemple"
production = True

pair = "ETH/USDT:USDT"
timeframe = "1h"
leverage = 0.5

print(f"--- {pair} {timeframe} Levier x {leverage} ---")

position_type = ["long", "short"]
long_ema_window = 500
short_ema_window = 110
min_bol_spread = 0
trix_window = 18

def open_long(row):
    """
    Condition pour ouvrir une position longue (achat).
    Cette fonction retourne True si la condition est vérifiée, sinon False.
    """
    if (
        row['close'] > row['long_ema']
        and row['trix'].iloc[-1] > 0
        and row['n1_trix'].iloc[-1] > 0
        and row['n2_trix'].iloc[-1] > 0
):

    ):
        return True
    else:
        return False

def close_long(row):
    """
    Condition pour fermer une position longue (vente).
    Cette fonction retourne True si la condition est vérifiée, sinon False.
    """
    if row['close'] < row['short_ema']:
        return True
    return False

def open_short(row):
    """
    Condition pour ouvrir une position courte (vente à découvert).
    Cette fonction retourne True si la condition est vérifiée, sinon False.
    """
    if (
        row['close'] < row['short_ema']
        and row['trix'] < 0
        and row['n1_trix'] < 0
        and row['n2_trix'] < 0
    ):
        return True
    return False

def close_short(row):
    """
    Condition pour fermer une position courte (rachat).
    Cette fonction retourne True si la condition est vérifiée, sinon False.
    """
    if row['close'] > row['long_ema']:
        return True
    return False

bitget = PerpBitget(
    apiKey=secret[account_to_select]["apiKey"],
    secret=secret[account_to_select]["secret"],
    password=secret[account_to_select]["password"],
)

# Obtenir les données historiques
df = bitget.get_more_last_historical_async(pair, timeframe, 1000)

# Calculer les indicateurs techniques
df.drop(columns=df.columns.difference(['open', 'high', 'low', 'close', 'volume']), inplace=True)

df['long_ema'] = ta.trend.ema_indicator(close=df['close'], window=long_ema_window)
df['short_ema'] = ta.trend.ema_indicator(close=df['close'], window=short_ema_window)

df['trix'] = ta.trend.TRIXIndicator(close=df['close'], window=trix_window)
df['n1_trix'] = df['trix'].shift(1)
df['n2_trix'] = df['trix'].shift(2)

usd_balance = float(bitget.get_usdt_equity())
print("Solde en USD :", round(usd_balance, 2), "$")

positions_data = bitget.get_open_position()
position = [
    {
        "side": d["side"],
        "size": float(d["contracts"]) * float(d["contractSize"]),
        "market_price": d["info"]["marketPrice"],
        "usd_size": float(d["contracts"]) * float(d["contractSize"]) * float(d["info"]["marketPrice"])
    }
    for d in positions_data if d["symbol"] == pair
]

row = df.iloc[-2]

if len(position) > 0:
    position = position[0]
    print(f"Position actuelle : {position}")
    if position["side"] == "long" and close_long(row):
        close_long_market_price = float(df.iloc[-1]["close"])
        close_long_quantity = float(
            bitget.convert_amount_to_precision(pair, position["size"])
        )
        exchange_close_long_quantity = close_long_quantity * close_long_market_price
        print(
            f"Passer un ordre de vente au marché pour fermer la position longue : {close_long_quantity} {pair[:-5]} au prix de {close_long_market_price}$ ~{round(exchange_close_long_quantity, 2)}$"
        )
        if production:
            bitget.place_market_order(pair, "sell", close_long_quantity, reduce=True)

    if position["side"] == "short" and close_short(row):
        close_short_market_price = float(df.iloc[-1]["close"])
        close_short_quantity = float(
            bitget.convert_amount_to_precision(pair, position["size"])
        )
        exchange_close_short_quantity = close_short_quantity * close_short_market_price
        print(
            f"Passer un ordre de rachat au marché pour fermer la position courte : {close_short_quantity} {pair[:-5]} au prix de {close_short_market_price}$ ~{round(exchange_close_short_quantity, 2)}$"
        )
        if production:
            bitget.place_market_order(pair, "buy", close_short_quantity, reduce=True)

else:
    print("Aucune position ouverte")
    if open_long(row) and "long" in position_type:
        long_market_price = float(df.iloc[-1]["close"])
        long_quantity_in_usd = usd_balance * leverage
        long_quantity = float(bitget.convert_amount_to_precision(pair, float(
            bitget.convert_amount_to_precision(pair, long_quantity_in_usd / long_market_price)
        )))
        
        exchange_long_quantity = long_quantity * long_market_price
        print(
            f"Passer un ordre d'achat au marché pour ouvrir une position longue : {long_quantity} {pair[:-5]} au prix de {long_market_price}$ ~{round(exchange_long_quantity, 2)}$"
        )
        if production:
            bitget.place_market_order(pair, "buy", long_quantity, reduce=False)

    elif open_short(row) and "short" in position_type:
        short_market_price = float(df.iloc[-1]["close"])
        short_quantity_in_usd = usd_balance * leverage
        short_quantity = float(bitget.convert_amount_to_precision(pair, float(
            bitget.convert_amount_to_precision(pair, short_quantity_in_usd / short_market_price)
        )))
        exchange_short_quantity = short_quantity * short_market_price
        print(
            f"Passer un ordre de vente au marché pour ouvrir une position courte : {short_quantity} {pair[:-5]} au prix de {short_market_price}$ ~{round(exchange_short_quantity, 2)}$"
        )
        if production:
            bitget.place_market_order(pair, "sell", short_quantity, reduce=False)

now = datetime.now()
current_time = now.strftime("%d/%m/%Y %H:%M:%S")
print("--- Heure de fin d'exécution :", current_time, "---")
