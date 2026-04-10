from flask import Blueprint, render_template, session
from auth import login_required
import database

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    stats = database.get_stats()
    pending = database.get_pending_shipments()
    return render_template("dashboard.html", stats=stats, pending=pending,
                           user=session["user"], role=session["role"])
