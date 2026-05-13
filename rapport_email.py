import os, smtplib, schedule, time
import pandas as pd
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))
EXPEDITEUR = os.getenv("EMAIL_EXPEDITEUR")
MOT_DE_PASSE = os.getenv("EMAIL_MOT_DE_PASSE")

# Liste de tes clients : nom + email
CLIENTS = [
    {"nom": "Mélysane", "email": "lantonkpodemelysane@gmail.com"},
    #{"nom": "Aminata", "email": "aminata@example.com"},
]

def construire_rapport(prenom):
    # Récupère la dernière collecte depuis PostgreSQL
    df = pd.read_sql("""
        SELECT DISTINCT ON (name) name, symbol, prix_usd,
               variation_24h, volume_24h
        FROM prix_cryptos
        ORDER BY name, collecte_le DESC
    """, engine)

    hausse = df[df["variation_24h"] > 0]
    baisse = df[df["variation_24h"] < 0]
    top_hausse = df.nlargest(1, "variation_24h").iloc[0]
    top_baisse = df.nsmallest(1, "variation_24h").iloc[0]
    vol_total = df["volume_24h"].sum() / 1e9

    lignes = []
    for _, r in df.head(5).iterrows():
        fleche = "↑" if r["variation_24h"] > 0 else "↓"
        prix = f"${r['prix_usd']:>10,.2f}"
        var = f"{fleche} {r['variation_24h']:+.2f}%"
        lignes.append(f"  {r['name']:<16}: {prix}  {var}")

    date = datetime.now().strftime("%A %d %B %Y, %Hh%M")
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

def envoyer_rapports():
    print(f"Envoi des rapports — {datetime.now().strftime('%H:%M')}")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as serveur:
        serveur.login(EXPEDITEUR, MOT_DE_PASSE)
        for client in CLIENTS:
            date, corps = construire_rapport(client["nom"])
            msg = MIMEMultipart()
            msg["From"] = f"CryptoWatch Bénin <{EXPEDITEUR}>"
            msg["To"] = client["email"]
            msg["Subject"] = f"📊 Rapport Crypto — {date}"
            msg.attach(MIMEText(corps, "plain", "utf-8"))
            serveur.send_message(msg)
            print(f"  ✓ Envoyé à {client['nom']} ({client['email']})")

# Envoie chaque matin à 08h00
schedule.every().day.at("08:00").do(envoyer_rapports)
print("Système d'emails actif. Envoi chaque matin à 08h00.")

while True:
    schedule.run_pending()
    time.sleep(30)