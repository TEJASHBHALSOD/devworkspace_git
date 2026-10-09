import os

from flask import Flask, render_template
from flask_login import LoginManager

from config import config_by_name
from models import db
from models.user import User
from routes.auth import auth_bp
from routes.public import public_bp
from routes.dashboard import dashboard_bp
from routes.admin import (
    admin_bp,
    ensure_users_admin_column,
    seed_admin,
    seed_languages,
)
from routes.learning import learning_bp


def create_app(config_name="development"):
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # -----------------------------
    # USER / PUBLIC BLUEPRINTS
    # -----------------------------
    app.register_blueprint(auth_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(dashboard_bp)

    # -----------------------------
    # ADMIN / LEARNING BLUEPRINTS
    # -----------------------------
    app.register_blueprint(admin_bp)
    app.register_blueprint(learning_bp)

    # -----------------------------
    # ERROR HANDLERS
    # -----------------------------
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template("public/403.html"), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template("public/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template("public/500.html"), 500

    # -----------------------------
    # DATABASE INITIALIZATION
    # -----------------------------
    with app.app_context():
        import models.user  # noqa: F401
        import models.project  # noqa: F401
        import models.admin_content  # noqa: F401

        db.create_all()

        # Add is_admin to old SQLite databases
        # if the column does not already exist.
        ensure_users_admin_column()

        # Create dedicated administrator.
        seed_admin()

        # Add default languages only when none exist.
        seed_languages()

    return app


if __name__ == "__main__":
    app = create_app(os.getenv("FLASK_ENV", "development"))
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )