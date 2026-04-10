from flask import Flask, render_template, redirect, url_for, session, request, flash
from config import SECRET_KEY, SESSION_TIMEOUT
import database

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.permanent_session_lifetime = SESSION_TIMEOUT

# Make SESSION_TIMEOUT available in all templates
@app.context_processor
def inject_globals():
    return {"SESSION_TIMEOUT": SESSION_TIMEOUT}

# ── Blueprints ────────────────────────────────────────────────────────────────
from auth import auth_bp, seed_admin
from routes.clients import clients_bp
from routes.shipments import shipments_bp
from routes.settings import settings_bp
from routes.logs import logs_bp
from routes.dashboard import dashboard_bp

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(clients_bp)
app.register_blueprint(shipments_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(logs_bp)

# ── Session timeout enforcement ───────────────────────────────────────────────
from datetime import datetime

@app.before_request
def enforce_session_timeout():
    if "user" not in session:
        return
    last = session.get("last_active")
    if last:
        elapsed = (datetime.utcnow() - datetime.fromisoformat(last)).total_seconds()
        if elapsed > SESSION_TIMEOUT:
            session.clear()
            return redirect(url_for("auth.login", timeout=1))
    session["last_active"] = datetime.utcnow().isoformat()
    session.permanent = True

# ── Email agent manual trigger ────────────────────────────────────────────────
from auth import login_required

@app.route("/email/trigger", methods=["POST"])
@login_required
def email_trigger():
    from email_agent import run_email_agent
    result = run_email_agent(triggered_by=session["user"])
    if result["error"]:
        flash(f"Email agent error: {result['error']}", "danger")
    else:
        msg = f"Email check complete: {result['added']} client(s) added"
        if result["flagged"]:
            msg += f", {result['flagged']} flagged for review (see Logs)"
        flash(msg, "success")
    database.add_log(session["user"], "Email Agent — Manual Trigger",
                     f"Added: {result['added']}, Flagged: {result['flagged']}")
    return redirect(url_for("dashboard.dashboard"))

# ── Root redirect ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("dashboard.dashboard"))
    return redirect(url_for("auth.login"))

# ── Error handlers ────────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return render_template("403.html"), 404

if __name__ == "__main__":
    database.init_db()
    seed_admin()
    from email_agent import start_scheduler
    start_scheduler()
    app.run(host="127.0.0.1", port=5000, debug=False)
