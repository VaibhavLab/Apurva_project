import re

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import User

_DUMMY_HASH = generate_password_hash("unusable-dummy-password")


class AuthenticationService:
    """Normalize identifiers and keep password handling out of controllers."""

    @staticmethod
    def register(form):
        name = form.get("full_name", "").strip()
        username = form.get("username", "").strip().lower()
        email = form.get("email", "").strip().lower()
        password = form.get("password", "")
        errors = {}
        if not 1 <= len(name) <= 100:
            errors["full_name"] = "Enter your name (up to 100 characters)."
        if not re.fullmatch(r"[a-z0-9_]{3,40}", username):
            errors["username"] = "Use 3–40 letters, numbers, or underscores."
        try:
            email = validate_email(email, check_deliverability=False).normalized.lower()
            if len(email) > 254:
                raise ValueError()
        except (EmailNotValidError, ValueError):
            errors["email"] = "Enter a valid email address."
        if not 8 <= len(password) <= 128:
            errors["password"] = "Use between 8 and 128 characters."
        if password != form.get("confirm_password", ""):
            errors["confirm_password"] = "Passwords don't match."
        if errors:
            return None, errors
        if db.session.scalar(db.select(User).filter_by(username=username)):
            errors["username"] = "This username is already taken."
        if db.session.scalar(db.select(User).filter_by(email=email)):
            errors["email"] = "An account with this email already exists."
        if errors:
            return None, errors
        user = User(full_name=name, username=username, email=email,
                    password_hash=generate_password_hash(password))
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return None, {"form": "That username or email is already registered."}
        return user, {}

    @staticmethod
    def authenticate(identifier: str, password: str):
        if len(identifier) > 254 or len(password) > 128:
            return None
        identifier = identifier.strip().lower()
        user = db.session.scalar(db.select(User).where(or_(User.username == identifier, User.email == identifier)))
        valid = check_password_hash(user.password_hash if user else _DUMMY_HASH, password)
        return user if user and valid else None
