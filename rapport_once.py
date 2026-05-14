# rapport_once.py
# Envoie le rapport immédiatement et s'arrête — pas de schedule

import os, smtplib
import pandas as pd
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy import create_engine
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = quote_plus(os.getenv("DB_PASSWORD", ""))
DB_HOST     = os.getenv("DB_HOST", "")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/postgres"
engine       = create_engine(DATABASE_URL)

EXPEDITEUR   = os.getenv("EMAIL_EXPEDITEUR")
MOT_DE_PASSE = os.getenv("EMAIL_MOT_DE_PASSE")

CLIENTS = [
    {"nom": "Mélysane",    "email": "lantonkpodemelysane@gmail.com"},
    #{"nom": "Aminata", "email": "aminata@example.com"},
]

def construire_rapport(prenom):
    df = pd.read_sql("""
        SELECT DISTINCT ON (name) name, symbol, prix_usd, variation_24h, volume_24h
        FROM prix_cryptos
        ORDER BY name, collecte_le DESC
    """, engine)

    hausse     = df[df["variation_24h"] > 0]
    baisse     = df[df["variation_24h"] < 0]
    top_hausse = df.nlargest(1,  "variation_24h").iloc[0]
    top_baisse = df.nsmallest(1, "variation_24h").iloc[0]
    vol_total  = df["volume_24h"].sum() / 1e9

    lignes = []
    for _, r in df.head(5).iterrows():
        fleche = "↑" if r["variation_24h"] > 0 else "↓"
        lignes.append(
            f"  {r['name']:<16}: ${r['prix_usd']:>10,.2f}  {fleche} {r['variation_24h']:+.2f}%"
        )

    date  = datetime.now().strftime("%A %d %B %Y, %Hh%M")
    corps = f"""Bonjour {prenom},

Voici votre rapport crypto du jour :

── TOP MOUVEMENTS 24H ──────────────────────
{chr(10).join(lignes)}

── ALERTES DU JOUR ─────────────────────────
  🟢 Plus forte hausse : {top_hausse['name']} {top_hausse['variation_24h']:+.2f}%
  🔴 Plus forte baisse : {top_baisse['name']} {top_baisse['variation_24h']:+.2f}%
  📊 Volume total      : ${vol_total:.1f} milliards

── RÉSUMÉ ──────────────────────────────────
  {len(hausse)} cryptos en hausse / {len(baisse)} en baisse

Bonne journée et bon trading.
— CryptoWatch Bénin"""
    return date, corps

# ── Envoi direct — pas de schedule ──
print(f"Envoi des rapports — {datetime.now().strftime('%H:%M')}")
with smtplib.SMTP_SSL("smtp.gmail.com", 465) as serveur:
    serveur.login(EXPEDITEUR, MOT_DE_PASSE)
    for client in CLIENTS:
        date, corps = construire_rapport(client["nom"])
        msg = MIMEMultipart()
        msg["From"]    = f"CryptoWatch Bénin <{EXPEDITEUR}>"
        msg["To"]      = client["email"]
        msg["Subject"] = f"📊 Rapport Crypto — {date}"
        msg.attach(MIMEText(corps, "plain", "utf-8"))
        serveur.send_message(msg)
        print(f"  ✓ Envoyé à {client['nom']} ({client['email']})")

print("Terminé.")