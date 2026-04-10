import bcrypt
from flask import (Blueprint, render_template, request, redirect, url_for,
                   session, flash)
from functools import wraps
import database

auth_bp = Blueprint("auth", __name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def seed_admin():
    """Create a default admin account if no users exist."""
    if not database.user_exists():
        database.add_user("admin", hash_password("admin123"), role="admin")
        print("[INFO] Default admin created — username: admin  password: admin123")
        print("[INFO] Change this password immediately via the Settings page.")


# ── Decorators ────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("auth.login"))
        if session.get("role") != "admin":
            return render_template("403.html"), 403
        return f(*args, **kwargs)
    return decorated


# ── Routes ────────────────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    timeout = request.args.get("timeout")
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = database.get_user(username)
        if user and check_password(password, user["password_hash"]):
            session.clear()
            session["user"] = username
            session["role"] = user["role"]
            from datetime import datetime
            session["last_active"] = datetime.utcnow().isoformat()
            session.permanent = True
            database.add_log(username, "Login", "Successful login")
            return redirect(url_for("dashboard.dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html", timeout=timeout)


@auth_bp.route("/logout")
def logout():
    user = session.get("user", "unknown")
    database.add_log(user, "Logout", "")
    session.clear()
    return redirect(url_for("auth.login"))
