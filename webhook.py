# webhook.py
# Reçoit les notifications FedaPay et met à jour Supabase

import urllib.request
import os
import json
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


def activer_abonnement(email):
    """Active ou renouvelle l'abonnement d'un client pour 30 jours."""
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

                payload = json.dumps({
                    "transaction": {
                        "description": "Abonnement CryptoWatch Bénin — 1 mois",
                        "amount": 5500,
                        "currency": {"iso": "XOF"}
                    },
                    "customer": {"firstname": nom, "email": email}
                }).encode("utf-8")

                req = urllib.request.Request(
                    "https://api.fedapay.com/v1/transactions",
                    data=payload,
                    headers={
                        "Authorization": f"Bearer {FEDAPAY_API_KEY}",
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                )
                with urllib.request.urlopen(req) as resp:
                    data  = json.loads(resp.read())
                    token = data["v1"]["token"]
                    checkout_url = f"https://checkout.fedapay.com/{token}?public_key={os.getenv('FEDAPAY_PUBLIC_KEY')}"

                from inscription import inscrire_client
                inscrire_client(nom, email, cryptos.split(",") if cryptos else [])

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "token": token,
                    "url": f"https://checkout.fedapay.com/{token}"
                }).encode())

            except Exception as e:
                print(f"❌ Erreur création paiement : {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        else:
            # Webhook FedaPay — paiement confirmé
            try:
                data  = json.loads(raw_body)
                event = data.get("name", "")

                if event == "transaction.approved":
                    transaction = data.get("data", {}).get("object", {})
                    email       = transaction.get("customer", {}).get("email", "")
                    montant     = transaction.get("amount", 0)
                    print(f"💰 Paiement reçu — {email} — {montant} FCFA")
                    if email and montant >= 5500:
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