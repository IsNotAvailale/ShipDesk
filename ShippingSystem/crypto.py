"""Fernet-based encryption for storing UPS credentials locally."""
import os
import json
from cryptography.fernet import Fernet
from config import CREDENTIALS_DIR

_KEY_FILE = os.path.join(CREDENTIALS_DIR, "secret.key")
_CREDS_FILE = os.path.join(CREDENTIALS_DIR, "ups_credentials.enc")


def _get_fernet() -> Fernet:
    os.makedirs(CREDENTIALS_DIR, exist_ok=True)
    if not os.path.exists(_KEY_FILE):
        key = Fernet.generate_key()
        with open(_KEY_FILE, "wb") as f:
            f.write(key)
    with open(_KEY_FILE, "rb") as f:
        return Fernet(f.read())


def save_ups_credentials(creds: dict):
    f = _get_fernet()
    data = json.dumps(creds).encode()
    with open(_CREDS_FILE, "wb") as fh:
        fh.write(f.encrypt(data))


def load_ups_credentials() -> dict:
    if not os.path.exists(_CREDS_FILE):
        return {}
    try:
        f = _get_fernet()
        with open(_CREDS_FILE, "rb") as fh:
            return json.loads(f.decrypt(fh.read()).decode())
    except Exception:
        return {}
