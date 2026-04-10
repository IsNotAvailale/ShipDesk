from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from auth import login_required
import database

clients_bp = Blueprint("clients", __name__)


@clients_bp.route("/clients")
@login_required
def clients():
    search = request.args.get("search", "").strip()
    all_clients = database.get_all_clients(search)
    return render_template("clients.html", clients=all_clients, search=search,
                           user=session["user"], role=session["role"])


@clients_bp.route("/clients/add", methods=["GET", "POST"])
@login_required
def add_client():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Name is required.", "danger")
            return render_template("add_client.html", user=session["user"],
                                   role=session["role"], form=request.form)
        client_id = database.add_client(
            name=name,
            company=request.form.get("company", "").strip(),
            address=request.form.get("address", "").strip(),
            city=request.form.get("city", "").strip(),
            state=request.form.get("state", "").strip(),
            zip_code=request.form.get("zip", "").strip(),
            email=request.form.get("email", "").strip(),
            phone=request.form.get("phone", "").strip(),
        )
        database.add_log(session["user"], "Add Client",
                         f"Added client id={client_id} name={name}")
        flash(f"Client '{name}' added successfully.", "success")
        return redirect(url_for("clients.clients"))
    return render_template("add_client.html", user=session["user"],
                           role=session["role"], form={})


@clients_bp.route("/clients/<int:client_id>/edit", methods=["GET", "POST"])
@login_required
def edit_client(client_id):
    client = database.get_client(client_id)
    if not client:
        flash("Client not found.", "danger")
        return redirect(url_for("clients.clients"))
    if request.method == "POST":
        database.update_client(
            client_id,
            name=request.form.get("name", "").strip(),
            company=request.form.get("company", "").strip(),
            address=request.form.get("address", "").strip(),
            city=request.form.get("city", "").strip(),
            state=request.form.get("state", "").strip(),
            zip=request.form.get("zip", "").strip(),
            email=request.form.get("email", "").strip(),
            phone=request.form.get("phone", "").strip(),
        )
        database.add_log(session["user"], "Edit Client",
                         f"Edited client id={client_id}")
        flash("Client updated.", "success")
        return redirect(url_for("clients.clients"))
    return render_template("edit_client.html", client=client,
                           user=session["user"], role=session["role"])


@clients_bp.route("/clients/<int:client_id>/ship", methods=["POST"])
@login_required
def request_shipment(client_id):
    client = database.get_client(client_id)
    if not client:
        flash("Client not found.", "danger")
        return redirect(url_for("clients.clients"))
    shipment_id = database.add_shipment(client_id)
    database.add_log(session["user"], "Request Shipment",
                     f"Shipment id={shipment_id} for client id={client_id}")
    flash(f"Shipment request added for {client['name']}.", "success")
    return redirect(url_for("shipments.shipments"))
