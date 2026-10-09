from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    BooleanField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    ValidationError,
)

from models.user import User


class RegisterForm(FlaskForm):
    full_name = StringField(
        "Full Name",
        validators=[
            DataRequired(message="Full name is required."),
            Length(
                min=2,
                max=100,
                message="Full name must be between 2 and 100 characters.",
            ),
        ],
    )

    username = StringField(
        "Username",
        validators=[
            DataRequired(message="Username is required."),
            Length(
                min=3,
                max=50,
                message="Username must be between 3 and 50 characters.",
            ),
        ],
    )

    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email is required."),
            Email(message="Enter a valid email address."),
            Length(
                max=120,
                message="Email is too long.",
            ),
        ],
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(
                min=6,
                max=128,
                message="Password must be between 6 and 128 characters.",
            ),
        ],
    )

    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo(
                "password",
                message="Passwords do not match.",
            ),
        ],
    )

    accept_terms = BooleanField(
        "I accept the Terms & Conditions",
        validators=[
            DataRequired(
                message="You must accept the Terms & Conditions."
            )
        ],
    )

    submit = SubmitField("Register")

    def validate_username(self, username):
        username_value = (username.data or "").strip()

        if User.query.filter_by(
            username=username_value
        ).first():
            raise ValidationError(
                "Username already exists. Please choose another."
            )

    def validate_email(self, email):
        email_value = (email.data or "").strip().lower()

        if User.query.filter_by(
            email=email_value
        ).first():
            raise ValidationError(
                "Email already registered. Please login."
            )


class LoginForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email is required."),
            Email(message="Enter a valid email address."),
        ],
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
        ],
    )

    remember_me = BooleanField(
        "Remember Me",
        default=False,
    )

    submit = SubmitField("Login")