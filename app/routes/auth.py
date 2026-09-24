from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.services.authentication_service import AuthenticationService

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("chat.dashboard"))
    errors = {}
    if request.method == "POST":
        user, errors = AuthenticationService.register(request.form)
        if user:
            flash("Your account is ready. Log in to start your first conversation.", "success")
            return redirect(url_for("auth.login"))
    return render_template("register.html", errors=errors), 400 if errors else 200


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("chat.dashboard"))
    error = None
    if request.method == "POST":
        user = AuthenticationService.authenticate(request.form.get("identifier", ""), request.form.get("password", ""))
        if user:
            session.clear()
            login_user(user)
            session.permanent = True
            return redirect(url_for("chat.dashboard"))
        error = "That email/username and password combination isn't right. Please try again."
    return render_template("login.html", error=error), 400 if error else 200


@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("main.index"))
