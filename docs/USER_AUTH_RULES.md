# Normal User Authentication Rules

The normal user portal must not authenticate administrator accounts.

In the existing `routes/auth.py`, the normal login query should select only `is_admin=False` users.

## Login

Change the user lookup from a broad email lookup to:

```python
user = User.query.filter_by(email=email, is_admin=False).first()
```

Then keep your normal password check and `login_user(user)` behavior.

## Registration

When creating a registered user, explicitly set:

```python
user = User(
    username=username,
    email=email,
    is_admin=False,
)
```

Do not accept `is_admin` from the public registration form.

## Logout

The normal user logout must only call Flask-Login logout:

```python
logout_user()
```

Do not use:

```python
session.clear()
```

The administrator session is intentionally stored separately under:

```python
session['devworkspace_admin_user_id']
```

This produces the intended separation:

```text
/admin/login  -> Administrator account only
/login        -> Registered User account only
```
