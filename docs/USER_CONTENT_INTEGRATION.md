# User Dashboard Content Integration

The new `routes/learning.py` blueprint makes published administrator content available to the user side.

## Register the blueprint

In `app.py`:

```python
from routes.learning import learning_bp
```

and:

```python
app.register_blueprint(learning_bp)
```

## What it provides

- `/dashboard/learn/` — learning center
- `/dashboard/learn/languages/<slug>` — language catalog
- `/dashboard/learn/courses/<course_id>` — course outline
- `/dashboard/learn/lessons/<lesson_id>` — lesson content, examples and exercises

The blueprint also exposes these template variables globally:

- `published_languages`
- `published_courses`

That allows your existing `/languages` and `/courses` dashboard routes to render current database content without hard-coding languages or courses.

## Template replacement

The package includes dynamic replacements for:

```text
templates/dashboard/languages.html
templates/dashboard/courses.html
```

They use the existing user desktop theme and display only published content.

The three `learning_*.html` templates are the detail pages used by the new learning blueprint.
