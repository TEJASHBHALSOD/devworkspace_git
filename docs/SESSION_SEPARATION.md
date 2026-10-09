# Session Separation: User vs Administrator

## What changed

DevWorkspace now uses two independent authentication states inside the same browser session:

- **User portal:** Flask-Login (`current_user`)
- **Admin portal:** normal Flask session key `devworkspace_admin_user_id`

The administrator portal does **not** call `login_user()` or `logout_user()`.

## Required user logout route

Keep your normal user logout route like this:

```python
from flask_login import login_required, logout_user

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
```

Do not use this inside user logout:

```python
session.clear()
```

`session.clear()` would also remove the independent administrator session key.

## Required user login rule

Use `login_user(user)` for the user account. Do not manually write the administrator session key from the normal user login/register routes.

This gives the intended behavior:

| Action | User login state | Admin login state |
|---|---|---|
| User signs in | Signed in | Unchanged |
| User signs out | Signed out | Unchanged |
| Admin signs in | Unchanged | Signed in |
| Admin signs out | Unchanged | Signed out |

## Admin templates

Admin pages use `admin_user`, not `current_user`. This is important because the user and admin identities can be active at the same time.
