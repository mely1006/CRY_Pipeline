# webhook.py
# Reçoit les notifications FedaPay et met à jour Supabase

import os
import json
import requests
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

DB_USER      = os.getenv("DB_USER", "postgres")
DB_PASSWORD  = quote_plus(os.getenv("DB_PASSWORD", ""))
DB_HOST      = os.getenv("DB_HOST", "")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/postgres"
engine       = create_engine(DATABASE_URL)

FEDAPAY_API_KEY = os.getenv("FEDAPAY_API_KEY")
FEDAPAY_BASE    = "https://sandbox-api.fedapay.com/v1"


def fedapay_headers():
    return {
        "Authorization": f"Bearer {FEDAPAY_API_KEY}",
        "Content-Type": "application/json"
    }


def activer_abonnement(email):
    with engine.connect() as conn:
        client = conn.execute(
            text("SELECT id, date_expiration FROM clients WHERE email = :email"),
            {"email": email}
        ).fetchone()

        if not client:
            print(f"⚠️  Client {email} non trouvé.")
            return False

        aujourd_hui = datetime.now().date()
        if client.date_expiration and client.date_expiration > aujourd_hui:
            nouvelle_date = client.date_expiration + timedelta(days=30)
        else:
            nouvelle_date = aujourd_hui + timedelta(days=30)

        conn.execute(text("""
            UPDATE clients
            SET abonnement_actif = true,
                date_expiration  = :date_expiration
            WHERE email = :email
        """), {"date_expiration": nouvelle_date, "email": email})
        conn.commit()

    print(f"✅ Abonnement activé pour {email} jusqu'au {nouvelle_date.strftime('%d/%m/%Y')}")
    return True


class WebhookHandler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)

        if self.path == "/creer-paiement":
            try:
                body    = json.loads(raw_body)
                nom     = body.get("nom", "")
                email   = body.get("email", "")
                cryptos = body.get("cryptos", "")

                resp = requests.post(
                    f"{FEDAPAY_BASE}/transactions",
                    headers=fedapay_headers(),
                    json={
                        "description": "Abonnement CryptoWatch Bénin — 1 mois",
                        "amount": 100,
                        "currency": {"iso": "XOF"},
                        "customer": {"firstname": nom, "email": email}
                    }
                )

                print(f"FedaPay status: {resp.status_code}")
                print(f"FedaPay response: {resp.text}")

                resp.raise_for_status()
                transaction = resp.json()["v1/transaction"]
                payment_url = transaction["payment_url"]

                from inscription import inscrire_client
                inscrire_client(nom, email, [c.strip() for c in cryptos.split(",")] if cryptos else [])

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"url": payment_url}).encode())

            except Exception as e:
                print(f"❌ Erreur création paiement : {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        else:
            try:
                data  = json.loads(raw_body)
                event = data.get("name", "")

                if event == "transaction.approved":
                    transaction = data.get("data", {}).get("object", {})
                    email       = transaction.get("customer", {}).get("email", "")
                    montant     = transaction.get("amount", 0)
                    print(f"💰 Paiement reçu — {email} — {montant} FCFA")
                    if email and montant >= 100:
                        activer_abonnement(email)

                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")

            except Exception as e:
                print(f"❌ Erreur webhook : {e}")
                self.send_response(500)
                self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Webhook en écoute sur le port {port}...")
    HTTPServer(("0.0.0.0", port), WebhookHandler).serve_forever()