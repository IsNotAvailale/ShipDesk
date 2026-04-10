import os
import secrets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE_PATH = os.path.join(BASE_DIR, "shipping.db")
LABELS_DIR = os.path.join(BASE_DIR, "labels")
CREDENTIALS_DIR = os.path.join(BASE_DIR, "credentials")

# Flask session secret — generated once, stable across restarts via file
_SECRET_FILE = os.path.join(CREDENTIALS_DIR, "flask_secret.key")

def get_secret_key():
    if os.path.exists(_SECRET_FILE):
        with open(_SECRET_FILE, "rb") as f:
            return f.read()
    key = secrets.token_bytes(32)
    os.makedirs(CREDENTIALS_DIR, exist_ok=True)
    with open(_SECRET_FILE, "wb") as f:
        f.write(key)
    return key

SECRET_KEY = get_secret_key()

# Session timeout in seconds (15 minutes)
SESSION_TIMEOUT = 15 * 60

# Email agent schedule interval in minutes
EMAIL_AGENT_INTERVAL = 30

# UPS shipment defaults
UPS_SERVICE_CODE = "01"          # Next Day Air
UPS_PACKAGE_CODE = "02"          # My Packaging (customer-supplied)
UPS_WEIGHT_LBS = "1"
UPS_LENGTH = "14"
UPS_WIDTH = "10"
UPS_HEIGHT = "1"
