from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from flask_login import (
    current_user,
    login_user,
    logout_user,
)

from models import db
from models.user import User
from forms.auth_forms import LoginForm, RegisterForm


auth_bp = Blueprint("auth", __name__)


def _user_dashboard_url():
    """
    Return the URL for the normal user's dashboard.
    """
    return url_for("dashboard.index")


def _safe_next_url(next_url):
    """
    Allow only local relative URLs.

    This prevents an external URL from being used as
    the post-login redirect target.
    """
    if (
        next_url
        and next_url.startswith("/")
        and not next_url.startswith("//")
    ):
        return next_url

    return None


# ============================================================
# USER LOGIN
# ============================================================

@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    # If a normal user is already logged in,
    # do not show the login page again.
    if current_user.is_authenticated:
        return redirect(_user_dashboard_url())

    # Create the WTForms login form.
    form = LoginForm()

    if form.validate_on_submit():

        email = (form.email.data or "").strip().lower()
        password = form.password.data or ""

        # IMPORTANT:
        # Only regular users can log in from /login.
        #
        # Administrator authentication is handled separately
        # by /admin/login.
        user = User.query.filter_by(
            email=email,
            is_admin=False,
        ).first()

        if user and user.check_password(password):

            # Login the normal Flask-Login user.
            login_user(
                user,
                remember=form.remember_me.data,
            )

            flash(
                "Welcome back!",
                "success",
            )

            # Handle optional local next URL.
            next_page = _safe_next_url(
                request.args.get("next")
            )

            if next_page:
                return redirect(next_page)

            return redirect(
                _user_dashboard_url()
            )

        flash(
            "Invalid email or password.",
            "danger",
        )

    # IMPORTANT:
    # Pass the form object to the template.
    #
    # Your login.html uses:
    # {{ form.hidden_tag() }}
    # {{ form.email }}
    # {{ form.password }}
    #
    return render_template(
        "auth/login.html",
        form=form,
    )


# ============================================================
# USER REGISTER
# ============================================================

@auth_bp.route("/register", methods=["GET", "POST"])
def register():

    # Already authenticated users do not need registration.
    if current_user.is_authenticated:
        return redirect(_user_dashboard_url())

    # Create the WTForms registration form.
    form = RegisterForm()

    if form.validate_on_submit():

        full_name = (
            form.full_name.data or ""
        ).strip()

        username = (
            form.username.data or ""
        ).strip()

        email = (
            form.email.data or ""
        ).strip().lower()

        password = (
            form.password.data or ""
        )

        # ----------------------------------------------------
        # Extra database checks
        # ----------------------------------------------------

        existing_username = User.query.filter_by(
            username=username
        ).first()

        if existing_username:
            flash(
                "Username is already registered.",
                "danger",
            )

            return render_template(
                "auth/register.html",
                form=form,
            )

        existing_email = User.query.filter_by(
            email=email
        ).first()

        if existing_email:
            flash(
                "Email is already registered.",
                "danger",
            )

            return render_template(
                "auth/register.html",
                form=form,
            )

        # ----------------------------------------------------
        # Create normal user
        # ----------------------------------------------------

        # Every account created from the public registration
        # page is a NORMAL USER.
        #
        # It must never create an administrator.
        user = User(
            full_name=full_name,
            username=username,
            email=email,
            is_admin=False,
        )

        # Store the password using the User model's
        # password hashing method.
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash(
            "Account created successfully. Please log in.",
            "success",
        )

        return redirect(
            url_for("auth.login")
        )

    # IMPORTANT:
    # Pass the form object to the registration template.
    #
    # Your register.html uses:
    # {{ form.hidden_tag() }}
    # {{ form.full_name }}
    # {{ form.username }}
    # {{ form.email }}
    # {{ form.password }}
    # {{ form.confirm_password }}
    # {{ form.accept_terms }}
    #
    return render_template(
        "auth/register.html",
        form=form,
    )


# ============================================================
# USER LOGOUT
# ============================================================

@auth_bp.route("/logout")
def logout():

    # IMPORTANT:
    #
    # Do NOT use:
    #     session.clear()
    #
    # because the administrator session is stored separately.
    #
    # This call only logs out the normal Flask-Login user.
    logout_user()

    flash(
        "You have been logged out.",
        "success",
    )

    return redirect(
        url_for("auth.login")
    )