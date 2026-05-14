# inscription.py
# Inscrit un nouveau client avec 2 jours d'essai gratuit

import os
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

DB_USER      = os.getenv("DB_USER", "postgres")
DB_PASSWORD  = quote_plus(os.getenv("DB_PASSWORD", ""))
DB_HOST      = os.getenv("DB_HOST", "")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/postgres"
engine       = create_engine(DATABASE_URL)

def inscrire_client(nom, email, cryptos=[]):
    """Inscrit un client avec 2 jours d'essai gratuit."""
    date_expiration = datetime.now() + timedelta(days=2)
    
    with engine.connect() as conn:
        # Vérifier si le client existe déjà
        existant = conn.execute(
            text("SELECT id FROM clients WHERE email = :email"),
            {"email": email}
        ).fetchone()
        
        if existant:
            print(f"⚠️  Client {email} existe déjà.")
            return False
        
        conn.execute(text("""
            INSERT INTO clients (nom, email, cryptos, abonnement_actif, date_expiration)
            VALUES (:nom, :email, :cryptos, true, :date_expiration)
        """), {
            "nom": nom,
            "email": email,
            "cryptos": cryptos,
            "date_expiration": date_expiration.date()
        })
        conn.commit()
    
    print(f"✅ Client {nom} inscrit — essai gratuit jusqu'au {date_expiration.strftime('%d/%m/%Y')}")
    return True

# Test
if __name__ == "__main__":
    inscrire_client(
        nom="Client Test",
        email="test@gmail.com",
        cryptos=["BTC", "ETH"]
    )