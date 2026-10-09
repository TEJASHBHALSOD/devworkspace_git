# App Integration

Your existing `app.py` already contains the main Flask factory. Do not replace the whole file with a new application. Add the following pieces.

## 1. Imports

```python
from routes.admin import admin_bp, ensure_users_admin_column, seed_admin, seed_languages
from routes.learning import learning_bp
```

## 2. Register blueprints

```python
app.register_blueprint(admin_bp)
app.register_blueprint(learning_bp)
```

Keep your existing `auth_bp`, `public_bp`, and `dashboard_bp` registrations.

## 3. Database initialization

Inside your existing app context:

```python
with app.app_context():
    import models.user
    import models.project
    import models.admin_content

    db.create_all()
    ensure_users_admin_column()
    seed_admin()
    seed_languages()
```

`db.create_all()` creates the new `content_imports` table automatically. `ensure_users_admin_column()` is a one-time SQLite compatibility check for older `users` tables.

## 4. Default administrator

```text
Email:    admin@devworkspace.local
Password: admin123
```

Change the password after your first local login if you keep this deployment beyond development.

## 5. Install the Word parser dependency

Inside your project's activated virtual environment:

```powershell
python -m pip install python-docx
```

Then start Flask normally:

```powershell
python app.py
```

## 6. Do not replace your normal user authentication

Your user portal should continue using Flask-Login.

Your administrator portal should use the `devworkspace_admin_user_id` session key from `routes/admin.py`.

The two login systems intentionally do not call each other's login/logout functions.
