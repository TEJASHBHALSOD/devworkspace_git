from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)

from models import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    full_name = db.Column(
        db.String(120),
        nullable=False,
    )

    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False,
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False,
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # 0 = Normal User
    # 1 = Administrator
    #
    # Existing SQLite databases are migrated by the
    # admin initialization code if this column is missing.
    is_admin = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )

    def set_password(self, password):
        """
        Hash and store the user's password.
        """
        self.password_hash = generate_password_hash(
            password
        )

    def check_password(self, password):
        """
        Check a plain-text password against the stored hash.
        """
        return check_password_hash(
            self.password_hash,
            password,
        )

    def __repr__(self):
        return f"<User {self.username}>"