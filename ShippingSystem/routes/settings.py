from flask import (Blueprint, render_template, request, redirect, url_for,
                   session, flash)
from auth import admin_required
import database
from crypto import save_ups_credentials, load_ups_credentials

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    message = None
    ups_creds = load_ups_credentials()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "ups":
            client_id = request.form.get("ups_client_id", "").strip()
            client_secret = request.form.get("ups_client_secret", "").strip()
            account_number = request.form.get("ups_account_number", "").strip()
            shipper_name = request.form.get("shipper_name", "").strip()
            shipper_address = request.form.get("shipper_address", "").strip()
            shipper_city = request.form.get("shipper_city", "").strip()
            shipper_state = request.form.get("shipper_state", "").strip()
            shipper_zip = request.form.get("shipper_zip", "").strip()
            if client_id and client_secret and account_number:
                save_ups_credentials({
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "account_number": account_number,
                    "shipper_name": shipper_name,
                    "shipper_address": shipper_address,
                    "shipper_city": shipper_city,
                    "shipper_state": shipper_state,
                    "shipper_zip": shipper_zip,
                })
                database.add_log(session["user"], "Update UPS Credentials", "")
                flash("UPS credentials updated.", "success")
            else:
                flash("Client ID, Secret, and Account Number are required.", "danger")
            return redirect(url_for("settings.settings"))

        if action == "add_user":
            username = request.form.get("new_username", "").strip()
            password = request.form.get("new_password", "").strip()
            role = request.form.get("new_role", "employee")
            if username and password:
                existing = database.get_user(username)
                if existing:
                    flash(f"Username '{username}' already exists.", "danger")
                else:
                    from auth import hash_password
                    database.add_user(username, hash_password(password), role)
                    database.add_log(session["user"], "Add User",
                                     f"Created user {username} role={role}")
                    flash(f"User '{username}' created.", "success")
            else:
                flash("Username and password are required.", "danger")
            return redirect(url_for("settings.settings"))

        if action == "delete_user":
            username = request.form.get("del_username", "").strip()
            if username == session["user"]:
                flash("You cannot delete your own account.", "danger")
            elif username:
                database.delete_user(username)
                database.add_log(session["user"], "Delete User",
                                 f"Deleted user {username}")
                flash(f"User '{username}' deleted.", "success")
            return redirect(url_for("settings.settings"))

        if action == "change_password":
            target = request.form.get("target_username", "").strip()
            new_pw = request.form.get("new_pw", "").strip()
            if target and new_pw:
                from auth import hash_password
                database.update_user_password(target, hash_password(new_pw))
                database.add_log(session["user"], "Change Password",
                                 f"Changed password for {target}")
                flash(f"Password updated for '{target}'.", "success")
            else:
                flash("Username and new password are required.", "danger")
            return redirect(url_for("settings.settings"))

    users = database.get_all_users()
    return render_template("settings.html", users=users, ups_creds=ups_creds,
                           user=session["user"], role=session["role"])
