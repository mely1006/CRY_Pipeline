# pipeline_once.py
# Version sans boucle pour GitHub Actions — fait le travail et s'arrête

import os, requests
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

# Encode le mot de passe pour éviter les bugs avec les caractères spéciaux
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = quote_plus(os.getenv("DB_PASSWORD", ""))
DB_HOST     = os.getenv("DB_HOST", "")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/postgres"

engine = create_engine(DATABASE_URL)

def extraire():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {"vs_currency": "usd", "per_page": 20, "page": 1, "order": "market_cap_desc"}
    reponse = requests.get(url, params=params, timeout=15)
    reponse.raise_for_status()
    return pd.DataFrame(reponse.json())

def transformer(df):
    colonnes = ["id", "name", "symbol", "current_price", "market_cap",
                "price_change_percentage_24h", "total_volume", "high_24h", "low_24h"]
    df = df[colonnes].dropna().copy()
    df.rename(columns={
        "current_price": "prix_usd",
        "price_change_percentage_24h": "variation_24h",
        "total_volume": "volume_24h",
        "high_24h": "haut_24h",
        "low_24h": "bas_24h"
    }, inplace=True)
    df["prix_usd"]      = df["prix_usd"].round(2)
    df["variation_24h"] = df["variation_24h"].round(2)
    df["collecte_le"]   = datetime.now()
    return df

def charger(df):
    df.to_sql("prix_cryptos", engine, if_exists="append", index=False, method="multi")

# ── Exécution directe — pas de boucle, pas de schedule ──
heure = datetime.now().strftime("%d/%m/%Y %H:%M")
print(f"[{heure}] Démarrage du pipeline...")
try:
    df_brut  = extraire()
    df_propre = transformer(df_brut)
    charger(df_propre)
    print(f"✓ {len(df_propre)} cryptos sauvegardées dans PostgreSQL.")
except Exception as e:
    print(f"Erreur : {e}")
    raise  # raise pour que GitHub Actions marque le job comme échoué