import secrets
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from app.config import Config
from app.extensions import csrf, db, login_manager


def create_app(test_config: dict | None = None) -> Flask:
    """Create an independently configurable app with a local development database."""
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    app.config.update(Config.environment())
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if app.config.get("SECRET_KEY") in (None, "", "change-this-secret-key"):
        if app.config.get("PRODUCTION"):
            raise RuntimeError("Set a strong SECRET_KEY before running in production.")
        # Persist the local key so demo sessions survive a server restart.
        key_path = Path(app.instance_path) / "development-secret"
        try:
            with key_path.open("x", encoding="utf-8") as key_file:
                key_file.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        app.config["SECRET_KEY"] = key_path.read_text(encoding="utf-8")

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"

    from app.models import User
    from app.routes.auth import auth_bp
    from app.routes.chat import chat_bp
    from app.routes.conversations import conversation_bp
    from app.routes.main import main_bp

    for blueprint in (main_bp, auth_bp, chat_bp, conversation_bp):
        app.register_blueprint(blueprint)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id)) if user_id.isdigit() else None

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api/"):
            return jsonify(success=False, error="Your session has expired. Please log in again."), 401
        return redirect(url_for("auth.login"))

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        if request.path.startswith("/api/"):
            return jsonify(success=False, error="Your session needs refreshing. Reload the page and try again."), 400
        return render_template("error.html", code=400, heading="Let's refresh your session.",
                               message="Reload the form before trying again."), 400

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        db.session.rollback()
        # Do not log exception text: SQL errors can contain private message content.
        app.logger.error("Database operation failed (%s)", type(error).__name__)
        return error_response(503, "We couldn't save that right now. Please try again shortly.")

    def error_response(code, message):
        if request.path.startswith("/api/"):
            return jsonify(success=False, error=message), code
        return render_template("error.html", code=code, heading="A little pause.", message=message), code

    @app.errorhandler(HTTPException)
    def http_error(error):
        if error.code == 404 and not request.path.startswith("/api/"):
            return render_template("404.html"), 404
        messages = {400: "Please check your request.", 404: "That conversation could not be found.",
                    405: "This action is not available.", 413: "That message is too large.",
                    415: "Please send a JSON request."}
        return error_response(error.code, messages.get(error.code, "We couldn't complete that request."))

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return error_response(500, "Something went wrong. Please try again.")

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        response.headers["Cache-Control"] = "no-store"
        if app.config["SESSION_COOKIE_SECURE"]:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    with app.app_context():
        db.create_all()
    return app
