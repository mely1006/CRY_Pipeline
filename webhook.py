# webhook.py
# Reçoit les notifications FedaPay et met à jour Supabase

import os
import hmac
import hashlib
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
        # Vérifier si le client existe
        client = conn.execute(
            text("SELECT id, date_expiration FROM clients WHERE email = :email"),
            {"email": email}
        ).fetchone()

        if not client:
            print(f"⚠️  Client {email} non trouvé.")
            return False

        # Si abonnement encore actif, on prolonge depuis la date actuelle
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
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
            event = data.get("name", "")
            
            # FedaPay envoie "transaction.approved" quand le paiement est confirmé
            if event == "transaction.approved":
                transaction = data.get("data", {}).get("object", {})
                email = transaction.get("customer", {}).get("email", "")
                montant = transaction.get("amount", 0)
                
                print(f"💰 Paiement reçu — {email} — {montant} FCFA")
                
                if email and montant >= 5500:
                    activer_abonnement(email)
                else:
                    print(f"⚠️  Montant insuffisant ou email manquant.")

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

        except Exception as e:
            print(f"❌ Erreur webhook : {e}")
            self.send_response(500)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Silence les logs HTTP par défaut


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Webhook en écoute sur le port {port}...")
    HTTPServer(("0.0.0.0", port), WebhookHandler).serve_forever()