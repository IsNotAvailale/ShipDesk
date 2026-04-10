import sqlite3
from datetime import datetime
from config import DATABASE_PATH


def get_conn():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS clients (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                company     TEXT,
                address     TEXT,
                city        TEXT,
                state       TEXT,
                zip         TEXT,
                email       TEXT,
                phone       TEXT,
                date_added  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS shipments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id       INTEGER NOT NULL REFERENCES clients(id),
                date_requested  TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'pending',
                tracking_number TEXT,
                label_pdf_path  TEXT,
                date_processed  TEXT
            );

            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'employee',
                created_at    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS logs (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                username  TEXT NOT NULL,
                action    TEXT NOT NULL,
                details   TEXT
            );
        """)


# ── Clients ──────────────────────────────────────────────────────────────────

def add_client(name, company="", address="", city="", state="", zip_code="",
               email="", phone=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO clients (name, company, address, city, state, zip,
               email, phone, date_added) VALUES (?,?,?,?,?,?,?,?,?)""",
            (name, company, address, city, state, zip_code, email, phone, now)
        )
        return cur.lastrowid


def get_all_clients(search=""):
    with get_conn() as conn:
        if search:
            pattern = f"%{search}%"
            return conn.execute(
                """SELECT * FROM clients WHERE name LIKE ? OR company LIKE ?
                   OR address LIKE ? OR city LIKE ? OR email LIKE ?
                   ORDER BY date_added DESC""",
                (pattern, pattern, pattern, pattern, pattern)
            ).fetchall()
        return conn.execute(
            "SELECT * FROM clients ORDER BY date_added DESC"
        ).fetchall()


def get_client(client_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM clients WHERE id = ?", (client_id,)
        ).fetchone()


def update_client(client_id, **fields):
    allowed = {"name", "company", "address", "city", "state", "zip",
               "email", "phone"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    cols = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [client_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE clients SET {cols} WHERE id = ?", vals)


def delete_client(client_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))


# ── Shipments ─────────────────────────────────────────────────────────────────

def add_shipment(client_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO shipments (client_id, date_requested, status)
               VALUES (?, ?, 'pending')""",
            (client_id, now)
        )
        return cur.lastrowid


def get_pending_shipments():
    with get_conn() as conn:
        return conn.execute(
            """SELECT s.*, c.name, c.company, c.address, c.city, c.state,
               c.zip, c.email, c.phone
               FROM shipments s JOIN clients c ON s.client_id = c.id
               WHERE s.status = 'pending'
               ORDER BY s.date_requested ASC"""
        ).fetchall()


def get_all_shipments():
    with get_conn() as conn:
        return conn.execute(
            """SELECT s.*, c.name, c.company
               FROM shipments s JOIN clients c ON s.client_id = c.id
               ORDER BY s.date_requested DESC"""
        ).fetchall()


def complete_shipment(shipment_id, tracking_number, label_pdf_path):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        conn.execute(
            """UPDATE shipments SET status='completed', tracking_number=?,
               label_pdf_path=?, date_processed=? WHERE id=?""",
            (tracking_number, label_pdf_path, now, shipment_id)
        )


def get_shipment(shipment_id):
    with get_conn() as conn:
        return conn.execute(
            """SELECT s.*, c.name, c.company, c.address, c.city, c.state,
               c.zip, c.email, c.phone
               FROM shipments s JOIN clients c ON s.client_id = c.id
               WHERE s.id = ?""",
            (shipment_id,)
        ).fetchone()


# ── Users ─────────────────────────────────────────────────────────────────────

def add_user(username, password_hash, role="employee"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO users (username, password_hash, role, created_at)
               VALUES (?, ?, ?, ?)""",
            (username, password_hash, role, now)
        )


def get_user(username):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()


def get_all_users():
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, username, role, created_at FROM users ORDER BY created_at"
        ).fetchall()


def update_user_password(username, new_hash):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (new_hash, username)
        )


def update_user_role(username, role):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET role = ? WHERE username = ?", (role, username)
        )


def delete_user(username):
    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE username = ?", (username,))


def user_exists():
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0


# ── Logs ──────────────────────────────────────────────────────────────────────

def add_log(username, action, details=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO logs (timestamp, username, action, details) VALUES (?,?,?,?)",
            (now, username, action, details)
        )


def get_logs(limit=500):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM logs ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()


# ── Dashboard stats ───────────────────────────────────────────────────────────

def get_stats():
    with get_conn() as conn:
        total_clients = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM shipments WHERE status='pending'"
        ).fetchone()[0]
        completed_today = conn.execute(
            "SELECT COUNT(*) FROM shipments WHERE status='completed' AND date_processed LIKE ?",
            (datetime.now().strftime("%Y-%m-%d") + "%",)
        ).fetchone()[0]
        return {
            "total_clients": total_clients,
            "pending_shipments": pending,
            "completed_today": completed_today,
        }
