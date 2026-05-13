import os, requests, schedule, time
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Charge les variables du fichier .env
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Crée le moteur de connexion PostgreSQL (une seule fois)
engine = create_engine(DATABASE_URL)

# ────────────────────────────────────────────────────
#  EXTRACT — récupère les données depuis l'API
# ────────────────────────────────────────────────────
def extraire():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "per_page": 20,
        "page": 1,
        "order": "market_cap_desc"
    }
    # timeout=15 : abandonne si l'API ne répond pas en 15s
    reponse = requests.get(url, params=params, timeout=15)
    reponse.raise_for_status() # lève une erreur si statut != 200
    return pd.DataFrame(reponse.json())

# ────────────────────────────────────────────────────
#  TRANSFORM — nettoie et structure les données
# ────────────────────────────────────────────────────
def transformer(df):
    colonnes = [
        "id", "name", "symbol", "current_price",
        "market_cap", "price_change_percentage_24h",
        "total_volume", "high_24h", "low_24h"
    ]
    df = df[colonnes].dropna().copy()
    df.rename(columns={
        "current_price": "prix_usd",
        "price_change_percentage_24h": "variation_24h",
        "total_volume": "volume_24h",
        "high_24h": "haut_24h",
        "low_24h": "bas_24h"
    }, inplace=True)
    df["prix_usd"] = df["prix_usd"].round(2)
    df["variation_24h"] = df["variation_24h"].round(2)
    df["collecte_le"] = datetime.now()
    return df

# ────────────────────────────────────────────────────
#  LOAD — sauvegarde dans PostgreSQL
# ────────────────────────────────────────────────────
def charger(df):
    # if_exists="append" = ajoute sans jamais effacer l'historique
    df.to_sql(
        "prix_cryptos",
        engine,
        if_exists="append",
        index=False,
        method="multi"  # insère plusieurs lignes en un seul appel = plus rapide
    )

# ────────────────────────────────────────────────────
#  ORCHESTRATION — assemble tout
# ────────────────────────────────────────────────────
def run_pipeline():
    heure = datetime.now().strftime("%d/%m/%Y %H:%M")
    print(f"\n[{heure}] Démarrage du pipeline...")
    try:
        df_brut = extraire()
        df_propre = transformer(df_brut)
        charger(df_propre)
        print(f"✓ {len(df_propre)} cryptos sauvegardées dans PostgreSQL.")
    except Exception as e:
        # On log l'erreur mais on ne plante pas : le pipeline continue
        print(f"Erreur pipeline : {e}")

# Lance immédiatement au démarrage, puis toutes les heures
run_pipeline()
schedule.every(1).hours.do(run_pipeline)

while True:
    schedule.run_pending()
    time.sleep(60)