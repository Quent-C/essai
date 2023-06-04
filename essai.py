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
        and row['trix'] > 0
        and row['n1_trix'] > 0
        and row['n2_trix'] > 0
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

trix = ta.trend.TRIXIndicator(close=df['close'], window=trix_window)
df['trix'] = trix.trix()
df['n1_trix'], df['n2_trix'] = get_n_columns(df['trix'], 1, 2)

# Supprimer les lignes contenant des valeurs manquantes
df.dropna(inplace=True)

# Récupérer les données de position ouverte
positions_data = bitget.get_open_position()

if positions_data:
    position = [
        data
        for data in positions_data
        if data['symbol'] == pair and data['side'] in position_type
    ]
    if position:
        print("Solde en USD :", position[0]["unrealisedPnl"], "$")
        print("Position ouverte :", position[0])
    else:
        print("Solde en USD : 0.0 $")
        print("Aucune position ouverte")

while True:
    # Récupérer les dernières données de prix
    latest_data = bitget.get_latest_data(pair, timeframe)
    latest_close = float(latest_data["close"])

    # Ajouter les dernières données à la DataFrame
    df.loc[len(df)] = {
        "open": float(latest_data["open"]),
        "high": float(latest_data["high"]),
        "low": float(latest_data["low"]),
        "close": latest_close,
        "volume": float(latest_data["volume"])
    }

    # Calculer les indicateurs techniques pour les dernières données
    df['long_ema'].iloc[-1] = ta.trend.ema_indicator(close=df['close'], window=long_ema_window).iloc[-1]
    df['short_ema'].iloc[-1] = ta.trend.ema_indicator(close=df['close'], window=short_ema_window).iloc[-1]

    trix = ta.trend.TRIXIndicator(close=df['close'], window=trix_window)
    df['trix'].iloc[-1] = trix.trix().iloc[-1]
    df['n1_trix'].iloc[-1], df['n2_trix'].iloc[-1] = get_n_columns(df['trix'], 1, 2)

    # Supprimer les anciennes lignes pour maintenir la taille de la DataFrame
    if len(df) > 1000:
        df.drop(df.index[0], inplace=True)

    # Vérifier les conditions pour ouvrir ou fermer des positions
    if positions_data:
        position = [
            data
            for data in positions_data
            if data['symbol'] == pair and data['side'] in position_type
        ]
        if position:
            if close_long(df.iloc[-2]) and "long" in position_type:
                print("Fermeture de la position longue")
                result = bitget.close_position(pair, position[0]["positionId"], latest_close)
                if result:
                    print("Position fermée avec succès")
                else:
                    print("Échec de la fermeture de la position")
            elif close_short(df.iloc[-2]) and "short" in position_type:
                print("Fermeture de la position courte")
                result = bitget.close_position(pair, position[0]["positionId"], latest_close)
                if result:
                    print("Position fermée avec succès")
                else:
                    print("Échec de la fermeture de la position")
            else:
                print("Aucune action requise pour les positions ouvertes")
        else:
            if open_long(df.iloc[-2]) and "long" in position_type:
                print("Ouverture d'une position longue")
                result = bitget.open_position(pair, "buy", latest_close, leverage)
                if result:
                    print("Position ouverte avec succès")
                else:
                    print("Échec de l'ouverture de la position")
            elif open_short(df.iloc[-2]) and "short" in position_type:
                print("Ouverture d'une position courte")
                result = bitget.open_position(pair, "sell", latest_close, leverage)
                if result:
                    print("Position ouverte avec succès")
                else:
                    print("Échec de l'ouverture de la position")
            else:
                print("Aucune action requise pour les positions fermées")
    else:
        if open_long(df.iloc[-2]) and "long" in position_type:
            print("Ouverture d'une position longue")
            result = bitget.open_position(pair, "buy", latest_close, leverage)
            if result:
                print("Position ouverte avec succès")
            else:
                print("Échec de l'ouverture de la position")
        elif open_short(df.iloc[-2]) and "short" in position_type:
            print("Ouverture d'une position courte")
            result = bitget.open_position(pair, "sell", latest_close, leverage)
            if result:
                print("Position ouverte avec succès")
            else:
                print("Échec de l'ouverture de la position")
        else:
            print("Aucune action requise pour les positions fermées")

    # Pause de 1 minute avant la prochaine itération
    time.sleep(60)
