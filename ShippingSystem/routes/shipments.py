from flask import (Blueprint, render_template, request, redirect, url_for,
                   session, flash, send_file)
from auth import login_required, admin_required
import database, os

shipments_bp = Blueprint("shipments", __name__)


@shipments_bp.route("/shipments")
@login_required
def shipments():
    pending = database.get_pending_shipments()
    return render_template("shipments.html", shipments=pending,
                           user=session["user"], role=session["role"])


@shipments_bp.route("/shipments/process", methods=["POST"])
@admin_required
def process_shipments():
    """Admin confirms and processes all pending shipments via UPS API."""
    from ups_api import process_all_pending
    results = process_all_pending(session["user"])
    success = sum(1 for r in results if r["ok"])
    failed = len(results) - success
    if success:
        flash(f"{success} shipment(s) processed successfully.", "success")
    if failed:
        flash(f"{failed} shipment(s) failed — check logs.", "danger")
    return redirect(url_for("shipments.shipments"))


@shipments_bp.route("/shipments/<int:shipment_id>/label")
@login_required
def download_label(shipment_id):
    shipment = database.get_shipment(shipment_id)
    if not shipment or not shipment["label_pdf_path"]:
        flash("Label not found.", "danger")
        return redirect(url_for("shipments.shipments"))
    path = shipment["label_pdf_path"]
    if not os.path.exists(path):
        flash("Label file missing from disk.", "danger")
        return redirect(url_for("shipments.shipments"))
    return send_file(path, as_attachment=True,
                     download_name=os.path.basename(path))


@shipments_bp.route("/shipments/history")
@login_required
def history():
    all_shipments = database.get_all_shipments()
    return render_template("history.html", shipments=all_shipments,
                           user=session["user"], role=session["role"])
