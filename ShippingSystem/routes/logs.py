from flask import Blueprint, render_template, request, session
from auth import admin_required
import database

logs_bp = Blueprint("logs", __name__)


@logs_bp.route("/logs")
@admin_required
def logs():
    search = request.args.get("search", "").strip()
    all_logs = database.get_logs(limit=1000)
    if search:
        s = search.lower()
        all_logs = [l for l in all_logs
                    if s in l["action"].lower()
                    or s in l["username"].lower()
                    or s in (l["details"] or "").lower()]
    return render_template("logs.html", logs=all_logs, search=search,
                           user=session["user"], role=session["role"])
