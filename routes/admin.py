import json
import os
import re
from datetime import datetime
from functools import wraps

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import inspect, or_, text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename

from models import db
from models.user import User
from models.admin_content import (
    ActivityLog,
    AppSetting,
    Chapter,
    ContentImport,
    Course,
    Example,
    Exercise,
    Language,
    Lesson,
    ProjectTemplate,
    Quiz,
    QuizQuestion,
)
from services.content_importer import import_content, parse_docx, summarize

try:
    from models.project import Project
except ImportError:
    Project = None


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
ADMIN_SESSION_KEY = "devworkspace_admin_user_id"


def ensure_users_admin_column():
    """One-time SQLite migration for installations created before is_admin existed."""
    try:
        inspector = inspect(db.engine)
        if "users" not in inspector.get_table_names():
            return
        columns = {column["name"] for column in inspector.get_columns("users")}
        if "is_admin" in columns:
            return
        dialect = db.engine.dialect.name
        if dialect == "sqlite":
            db.session.execute(
                text(
                    "ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"
                )
            )
            db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def get_admin_user():
    user_id = session.get(ADMIN_SESSION_KEY)
    if not user_id:
        return None
    user = db.session.get(User, int(user_id))
    if user is None or not getattr(user, "is_admin", False):
        session.pop(ADMIN_SESSION_KEY, None)
        return None
    return user


@admin_bp.app_context_processor
def inject_admin_context():
    return {"admin_user": get_admin_user()}


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if get_admin_user() is None:
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)

    return wrapper


def slugify(value):
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "item"


def unique_slug(model, value, current_id=None):
    base = slugify(value)
    slug = base
    number = 2
    while True:
        query = model.query.filter_by(slug=slug)
        if current_id is not None:
            query = query.filter(model.id != current_id)
        if query.first() is None:
            return slug
        slug = f"{base}-{number}"
        number += 1


def log_action(action, entity_type, entity_id=None):
    admin_user = get_admin_user()
    db.session.add(
        ActivityLog(
            user_id=admin_user.id if admin_user else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    )


def get_setting(key, default=""):
    item = AppSetting.query.filter_by(key=key).first()
    return item.value if item else default


def set_setting(key, value):
    item = AppSetting.query.filter_by(key=key).first()
    if item:
        item.value = str(value)
    else:
        db.session.add(AppSetting(key=key, value=str(value)))


def seed_languages():
    if Language.query.count():
        return
    defaults = [
        (
            "Python",
            "3.x",
            "General-purpose interpreted programming language.",
            "programming",
            "fa-brands fa-python",
        ),
        (
            "HTML",
            "HTML5",
            "Markup language used to structure web pages.",
            "web",
            "fa-brands fa-html5",
        ),
        (
            "CSS",
            "CSS3",
            "Stylesheet language used to design web interfaces.",
            "web",
            "fa-brands fa-css3-alt",
        ),
        (
            "JavaScript",
            "ES6+",
            "Programming language for interactive web applications.",
            "web",
            "fa-brands fa-js",
        ),
    ]
    for name, version, description, category, icon in defaults:
        db.session.add(
            Language(
                name=name,
                slug=slugify(name),
                version=version,
                description=description,
                category=category,
                icon=icon,
                status="published",
            )
        )
    db.session.commit()


def seed_admin():
    """
    Create the dedicated local administrator account.

    This account is separate from normal registered users.
    """

    admin = User.query.filter_by(
        email="admin@devworkspace.local"
    ).first()

    if admin is None:
        admin = User(
            full_name="Administrator",
            username="admin",
            email="admin@devworkspace.local",
            is_admin=True,
        )

        admin.set_password("admin123")

        db.session.add(admin)
        db.session.commit()
        return

    changed = False

    if not getattr(admin, "is_admin", False):
        admin.is_admin = True
        changed = True

    if not getattr(admin, "full_name", None):
        admin.full_name = "Administrator"
        changed = True

    if changed:
        db.session.commit()


# ---------------------------------------------------------------------------
# ADMIN LOGIN — intentionally separate from Flask-Login user sessions.
# ---------------------------------------------------------------------------
@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    ensure_users_admin_column()
    if get_admin_user() is not None:
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email, is_admin=True).first()
        if user and user.check_password(password):
            session[ADMIN_SESSION_KEY] = user.id
            session.permanent = True
            return redirect(url_for("admin.dashboard"))
        flash("Invalid administrator credentials.", "danger")

    return render_template("admin/login.html")


@admin_bp.route("/logout", methods=["GET", "POST"])
def logout():
    # Do NOT call flask_login.logout_user() here. That would log out the user too.
    session.pop(ADMIN_SESSION_KEY, None)
    return redirect(url_for("admin.login"))


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------
@admin_bp.route("/")
@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    seed_languages()
    regular_users = User.query.filter_by(is_admin=False)
    return render_template(
        "admin/dashboard.html",
        registered_user_count=regular_users.count(),
        total_languages=Language.query.count(),
        total_courses=Course.query.count(),
        total_chapters=Chapter.query.count(),
        total_lessons=Lesson.query.count(),
        total_projects=Project.query.count() if Project else 0,
        published_languages=Language.query.filter_by(status="published").count(),
        published_courses=Course.query.filter_by(status="published").count(),
        recent_users=regular_users.order_by(User.id.desc()).limit(8).all(),
        recent_languages=Language.query.order_by(Language.id.desc()).limit(5).all(),
        current_admin=get_admin_user(),
    )


# ---------------------------------------------------------------------------
# USERS — only registered non-admin users appear here.
# ---------------------------------------------------------------------------
def registered_user_or_404(user_id):
    return User.query.filter_by(id=user_id, is_admin=False).first_or_404()


@admin_bp.route("/users")
@admin_required
def users():
    search = request.args.get("search", "").strip()
    query = User.query.filter_by(is_admin=False)
    if search:
        query = query.filter(
            or_(
                User.username.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
            )
        )
    items = query.order_by(User.id.desc()).all()
    return render_template("admin/users.html", users=items, search=search)


@admin_bp.route("/users/create", methods=["GET", "POST"])
@admin_required
def create_user():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not username or not email or not password:
            flash("Username, email and password are required.", "danger")
            return render_template("admin/user_form.html", user=None)
        if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
            flash("Username or email already exists.", "danger")
            return render_template("admin/user_form.html", user=None)

        # Admin-created accounts are regular users by design.
        user = User(username=username, email=email, is_admin=False)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        log_action("Created registered user", "user", user.id)
        db.session.commit()
        flash("User created successfully.", "success")
        return redirect(url_for("admin.users"))

    return render_template("admin/user_form.html", user=None)


@admin_bp.route("/users/<int:user_id>")
@admin_required
def user_detail(user_id):
    user = registered_user_or_404(user_id)
    project_count = 0
    if Project:
        try:
            project_count = Project.query.filter_by(user_id=user.id).count()
        except Exception:
            project_count = 0
    return render_template(
        "admin/user_detail.html",
        user=user,
        project_count=project_count,
    )


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_user(user_id):
    user = registered_user_or_404(user_id)
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not username or not email:
            flash("Username and email are required.", "danger")
            return render_template("admin/user_form.html", user=user)
        if User.query.filter(User.username == username, User.id != user.id).first() or User.query.filter(
            User.email == email, User.id != user.id
        ).first():
            flash("Username or email already belongs to another user.", "danger")
            return render_template("admin/user_form.html", user=user)

        user.username = username
        user.email = email
        user.is_admin = False
        if password:
            user.set_password(password)
        log_action("Updated registered user", "user", user.id)
        db.session.commit()
        flash("User updated successfully.", "success")
        return redirect(url_for("admin.user_detail", user_id=user.id))

    return render_template("admin/user_form.html", user=user)


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    user = registered_user_or_404(user_id)
    db.session.delete(user)
    log_action("Deleted registered user", "user", user.id)
    db.session.commit()
    flash("User deleted successfully.", "success")
    return redirect(url_for("admin.users"))


# ---------------------------------------------------------------------------
# LANGUAGES
# ---------------------------------------------------------------------------
@admin_bp.route("/languages")
@admin_required
def languages():
    seed_languages()
    search = request.args.get("search", "").strip()
    query = Language.query
    if search:
        query = query.filter(
            or_(
                Language.name.ilike(f"%{search}%"),
                Language.category.ilike(f"%{search}%"),
                Language.version.ilike(f"%{search}%"),
            )
        )
    return render_template(
        "admin/languages.html",
        languages=query.order_by(Language.name.asc()).all(),
        search=search,
    )


@admin_bp.route("/languages/create", methods=["GET", "POST"])
@admin_required
def create_language():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Language name is required.", "danger")
            return render_template("admin/language_form.html", language=None)
        if Language.query.filter_by(name=name).first():
            flash("A language with this name already exists.", "danger")
            return render_template("admin/language_form.html", language=None)

        language = Language(
            name=name,
            slug=unique_slug(Language, name),
            version=request.form.get("version", "1.0").strip() or "1.0",
            description=request.form.get("description", "").strip(),
            category=request.form.get("category", "programming"),
            icon=request.form.get("icon", "fa-solid fa-code").strip() or "fa-solid fa-code",
            status=request.form.get("status", "draft"),
        )
        db.session.add(language)
        db.session.flush()
        log_action("Created language", "language", language.id)
        db.session.commit()
        flash("Language created successfully.", "success")
        return redirect(url_for("admin.languages"))

    return render_template("admin/language_form.html", language=None)


@admin_bp.route("/languages/<int:language_id>")
@admin_required
def language_detail(language_id):
    language = Language.query.get_or_404(language_id)
    template_count = 0
    try:
        template_count = ProjectTemplate.query.filter_by(language_id=language.id).count()
    except Exception:
        template_count = 0
    return render_template(
        "admin/language_detail.html",
        language=language,
        template_count=template_count,
    )


@admin_bp.route("/languages/<int:language_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_language(language_id):
    language = Language.query.get_or_404(language_id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Language name is required.", "danger")
            return render_template("admin/language_form.html", language=language)
        if Language.query.filter(Language.name == name, Language.id != language.id).first():
            flash("Another language already uses this name.", "danger")
            return render_template("admin/language_form.html", language=language)

        language.name = name
        language.slug = unique_slug(Language, name, language.id)
        language.version = request.form.get("version", "1.0").strip() or "1.0"
        language.description = request.form.get("description", "").strip()
        language.category = request.form.get("category", "programming")
        language.icon = request.form.get("icon", "fa-solid fa-code").strip() or "fa-solid fa-code"
        language.status = request.form.get("status", "draft")
        log_action("Updated language", "language", language.id)
        db.session.commit()
        flash("Language updated successfully.", "success")
        return redirect(url_for("admin.language_detail", language_id=language.id))

    return render_template("admin/language_form.html", language=language)


@admin_bp.route("/languages/<int:language_id>/delete", methods=["POST"])
@admin_required
def delete_language(language_id):
    language = Language.query.get_or_404(language_id)
    language_name = language.name
    db.session.delete(language)
    log_action("Deleted language", "language", language.id)
    db.session.commit()
    flash(f"Language '{language_name}' and its learning content were deleted.", "success")
    return redirect(url_for("admin.languages"))


@admin_bp.route("/languages/<int:language_id>/toggle-status", methods=["POST"])
@admin_required
def toggle_language_status(language_id):
    language = Language.query.get_or_404(language_id)
    language.status = "draft" if language.status == "published" else "published"
    log_action("Changed language publication status", "language", language.id)
    db.session.commit()
    return redirect(url_for("admin.languages"))


# ---------------------------------------------------------------------------
# COURSES → CHAPTERS → LESSONS → EXAMPLES / EXERCISES / QUIZZES
# ---------------------------------------------------------------------------
@admin_bp.route("/courses")
@admin_required
def courses():
    search = request.args.get("search", "").strip()
    language_id = request.args.get("language_id", type=int)
    query = Course.query
    if search:
        query = query.filter(Course.title.ilike(f"%{search}%"))
    if language_id:
        query = query.filter(Course.language_id == language_id)
    return render_template(
        "admin/courses.html",
        courses=query.order_by(Course.id.desc()).all(),
        languages=Language.query.order_by(Language.name.asc()).all(),
        search=search,
        language_id=language_id,
    )


@admin_bp.route("/courses/create", methods=["GET", "POST"])
@admin_required
def create_course():
    languages = Language.query.order_by(Language.name.asc()).all()
    default_status = get_setting("default_course_status", "draft")
    if request.method == "POST":
        language_id = request.form.get("language_id", type=int)
        title = request.form.get("title", "").strip()
        language = db.session.get(Language, language_id) if language_id else None
        if language is None or not title:
            flash("Language and course title are required.", "danger")
            return render_template("admin/course_form.html", course=None, languages=languages)
        if Course.query.filter_by(language_id=language.id, title=title).first():
            flash("This language already has a course with that title.", "danger")
            return render_template("admin/course_form.html", course=None, languages=languages)

        course = Course(
            language_id=language.id,
            title=title,
            slug=unique_slug(Course, title),
            description=request.form.get("description", "").strip(),
            level=request.form.get("level", "beginner"),
            status=request.form.get("status", default_status),
        )
        db.session.add(course)
        db.session.flush()
        log_action("Created course", "course", course.id)
        db.session.commit()
        flash("Course created successfully.", "success")
        return redirect(url_for("admin.course_detail", course_id=course.id))

    return render_template("admin/course_form.html", course=None, languages=languages)


@admin_bp.route("/courses/<int:course_id>")
@admin_required
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    return render_template("admin/course_detail.html", course=course)


@admin_bp.route("/courses/<int:course_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_course(course_id):
    course = Course.query.get_or_404(course_id)
    languages = Language.query.order_by(Language.name.asc()).all()
    if request.method == "POST":
        language_id = request.form.get("language_id", type=int)
        title = request.form.get("title", "").strip()
        language = db.session.get(Language, language_id) if language_id else None
        if language is None or not title:
            flash("Language and course title are required.", "danger")
            return render_template("admin/course_form.html", course=course, languages=languages)
        duplicate = Course.query.filter(
            Course.language_id == language.id,
            Course.title == title,
            Course.id != course.id,
        ).first()
        if duplicate:
            flash("This language already has a course with that title.", "danger")
            return render_template("admin/course_form.html", course=course, languages=languages)

        course.language_id = language.id
        course.title = title
        course.slug = unique_slug(Course, title, course.id)
        course.description = request.form.get("description", "").strip()
        course.level = request.form.get("level", "beginner")
        course.status = request.form.get("status", "draft")
        log_action("Updated course", "course", course.id)
        db.session.commit()
        flash("Course updated successfully.", "success")
        return redirect(url_for("admin.course_detail", course_id=course.id))

    return render_template("admin/course_form.html", course=course, languages=languages)


@admin_bp.route("/courses/<int:course_id>/delete", methods=["POST"])
@admin_required
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    db.session.delete(course)
    log_action("Deleted course", "course", course.id)
    db.session.commit()
    flash("Course and its chapters, lessons and learning items were deleted.", "success")
    return redirect(url_for("admin.courses"))


@admin_bp.route("/courses/<int:course_id>/chapters/create", methods=["GET", "POST"])
@admin_required
def create_chapter(course_id):
    course = Course.query.get_or_404(course_id)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Chapter title is required.", "danger")
            return render_template("admin/chapter_form.html", course=course, chapter=None)
        chapter = Chapter(
            course_id=course.id,
            title=title,
            description=request.form.get("description", "").strip(),
            order_no=request.form.get("order_no", type=int) or (len(course.chapters) + 1),
            status=request.form.get("status", "published"),
        )
        db.session.add(chapter)
        db.session.flush()
        log_action("Created chapter", "chapter", chapter.id)
        db.session.commit()
        return redirect(url_for("admin.course_detail", course_id=course.id))
    return render_template("admin/chapter_form.html", course=course, chapter=None)


@admin_bp.route("/chapters/<int:chapter_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_chapter(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    if request.method == "POST":
        chapter.title = request.form.get("title", "").strip()
        chapter.description = request.form.get("description", "").strip()
        chapter.order_no = request.form.get("order_no", type=int) or chapter.order_no
        chapter.status = request.form.get("status", "published")
        log_action("Updated chapter", "chapter", chapter.id)
        db.session.commit()
        return redirect(url_for("admin.course_detail", course_id=chapter.course_id))
    return render_template("admin/chapter_form.html", course=chapter.course, chapter=chapter)


@admin_bp.route("/chapters/<int:chapter_id>/delete", methods=["POST"])
@admin_required
def delete_chapter(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    course_id = chapter.course_id
    db.session.delete(chapter)
    log_action("Deleted chapter", "chapter", chapter.id)
    db.session.commit()
    return redirect(url_for("admin.course_detail", course_id=course_id))


@admin_bp.route("/chapters/<int:chapter_id>/lessons/create", methods=["GET", "POST"])
@admin_required
def create_lesson(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Lesson title is required.", "danger")
            return render_template("admin/lesson_form.html", chapter=chapter, lesson=None)
        lesson = Lesson(
            chapter_id=chapter.id,
            title=title,
            slug=unique_slug(Lesson, title),
            content=request.form.get("content", "").strip(),
            expected_output=request.form.get("expected_output", "").strip(),
            order_no=request.form.get("order_no", type=int) or (len(chapter.lessons) + 1),
            status=request.form.get("status", "draft"),
        )
        db.session.add(lesson)
        db.session.flush()
        log_action("Created lesson", "lesson", lesson.id)
        db.session.commit()
        return redirect(url_for("admin.lesson_detail", lesson_id=lesson.id))
    return render_template("admin/lesson_form.html", chapter=chapter, lesson=None)


@admin_bp.route("/lessons/<int:lesson_id>")
@admin_required
def lesson_detail(lesson_id):
    return render_template("admin/lesson_detail.html", lesson=Lesson.query.get_or_404(lesson_id))


@admin_bp.route("/lessons/<int:lesson_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if request.method == "POST":
        lesson.title = request.form.get("title", "").strip()
        lesson.slug = unique_slug(Lesson, lesson.title, lesson.id)
        lesson.content = request.form.get("content", "").strip()
        lesson.expected_output = request.form.get("expected_output", "").strip()
        lesson.order_no = request.form.get("order_no", type=int) or lesson.order_no
        lesson.status = request.form.get("status", "draft")
        log_action("Updated lesson", "lesson", lesson.id)
        db.session.commit()
        return redirect(url_for("admin.lesson_detail", lesson_id=lesson.id))
    return render_template("admin/lesson_form.html", chapter=lesson.chapter, lesson=lesson)


@admin_bp.route("/lessons/<int:lesson_id>/delete", methods=["POST"])
@admin_required
def delete_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    course_id = lesson.chapter.course_id
    db.session.delete(lesson)
    log_action("Deleted lesson", "lesson", lesson.id)
    db.session.commit()
    return redirect(url_for("admin.course_detail", course_id=course_id))


@admin_bp.route("/lessons/<int:lesson_id>/examples/create", methods=["GET", "POST"])
@admin_required
def create_example(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Example title is required.", "danger")
            return render_template("admin/example_form.html", lesson=lesson, example=None)
        example = Example(
            lesson_id=lesson.id,
            title=title,
            code=request.form.get("code", ""),
            explanation=request.form.get("explanation", ""),
        )
        db.session.add(example)
        db.session.flush()
        log_action("Created code example", "example", example.id)
        db.session.commit()
        return redirect(url_for("admin.lesson_detail", lesson_id=lesson.id))
    return render_template("admin/example_form.html", lesson=lesson, example=None)


@admin_bp.route("/examples/<int:example_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_example(example_id):
    example = Example.query.get_or_404(example_id)
    if request.method == "POST":
        example.title = request.form.get("title", "").strip()
        example.code = request.form.get("code", "")
        example.explanation = request.form.get("explanation", "")
        log_action("Updated code example", "example", example.id)
        db.session.commit()
        return redirect(url_for("admin.lesson_detail", lesson_id=example.lesson_id))
    return render_template("admin/example_form.html", lesson=example.lesson, example=example)


@admin_bp.route("/examples/<int:example_id>/delete", methods=["POST"])
@admin_required
def delete_example(example_id):
    example = Example.query.get_or_404(example_id)
    lesson_id = example.lesson_id
    db.session.delete(example)
    log_action("Deleted code example", "example", example.id)
    db.session.commit()
    return redirect(url_for("admin.lesson_detail", lesson_id=lesson_id))


@admin_bp.route("/lessons/<int:lesson_id>/exercises/create", methods=["GET", "POST"])
@admin_required
def create_exercise(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Exercise title is required.", "danger")
            return render_template("admin/exercise_form.html", lesson=lesson, exercise=None)
        exercise = Exercise(
            lesson_id=lesson.id,
            title=title,
            instructions=request.form.get("instructions", ""),
            starter_code=request.form.get("starter_code", ""),
            expected_output=request.form.get("expected_output", ""),
        )
        db.session.add(exercise)
        db.session.flush()
        log_action("Created exercise", "exercise", exercise.id)
        db.session.commit()
        return redirect(url_for("admin.lesson_detail", lesson_id=lesson.id))
    return render_template("admin/exercise_form.html", lesson=lesson, exercise=None)


@admin_bp.route("/exercises/<int:exercise_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_exercise(exercise_id):
    exercise = Exercise.query.get_or_404(exercise_id)
    if request.method == "POST":
        exercise.title = request.form.get("title", "").strip()
        exercise.instructions = request.form.get("instructions", "")
        exercise.starter_code = request.form.get("starter_code", "")
        exercise.expected_output = request.form.get("expected_output", "")
        log_action("Updated exercise", "exercise", exercise.id)
        db.session.commit()
        return redirect(url_for("admin.lesson_detail", lesson_id=exercise.lesson_id))
    return render_template("admin/exercise_form.html", lesson=exercise.lesson, exercise=exercise)


@admin_bp.route("/exercises/<int:exercise_id>/delete", methods=["POST"])
@admin_required
def delete_exercise(exercise_id):
    exercise = Exercise.query.get_or_404(exercise_id)
    lesson_id = exercise.lesson_id
    db.session.delete(exercise)
    log_action("Deleted exercise", "exercise", exercise.id)
    db.session.commit()
    return redirect(url_for("admin.lesson_detail", lesson_id=lesson_id))


@admin_bp.route("/lessons/<int:lesson_id>/quizzes/create", methods=["GET", "POST"])
@admin_required
def create_quiz(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Quiz title is required.", "danger")
            return render_template("admin/quiz_form.html", lesson=lesson, quiz=None)
        quiz = Quiz(
            lesson_id=lesson.id,
            title=title,
            pass_mark=request.form.get("pass_mark", type=int) or 60,
            status=request.form.get("status", "draft"),
        )
        db.session.add(quiz)
        db.session.flush()
        log_action("Created quiz", "quiz", quiz.id)
        db.session.commit()
        return redirect(url_for("admin.quiz_detail", quiz_id=quiz.id))
    return render_template("admin/quiz_form.html", lesson=lesson, quiz=None)


@admin_bp.route("/quizzes/<int:quiz_id>")
@admin_required
def quiz_detail(quiz_id):
    return render_template("admin/quiz_detail.html", quiz=Quiz.query.get_or_404(quiz_id))


@admin_bp.route("/quizzes/<int:quiz_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    if request.method == "POST":
        quiz.title = request.form.get("title", "").strip()
        quiz.pass_mark = request.form.get("pass_mark", type=int) or 60
        quiz.status = request.form.get("status", "draft")
        log_action("Updated quiz", "quiz", quiz.id)
        db.session.commit()
        return redirect(url_for("admin.quiz_detail", quiz_id=quiz.id))
    return render_template("admin/quiz_form.html", lesson=quiz.lesson, quiz=quiz)


@admin_bp.route("/quizzes/<int:quiz_id>/delete", methods=["POST"])
@admin_required
def delete_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    lesson_id = quiz.lesson_id
    db.session.delete(quiz)
    log_action("Deleted quiz", "quiz", quiz.id)
    db.session.commit()
    return redirect(url_for("admin.lesson_detail", lesson_id=lesson_id))


@admin_bp.route("/quizzes/<int:quiz_id>/questions/create", methods=["GET", "POST"])
@admin_required
def create_quiz_question(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    if request.method == "POST":
        question_text = request.form.get("question", "").strip()
        if not question_text:
            flash("Question text is required.", "danger")
            return render_template("admin/quiz_question_form.html", quiz=quiz, question_obj=None)
        item = QuizQuestion(
            quiz_id=quiz.id,
            question=question_text,
            option_a=request.form.get("option_a", ""),
            option_b=request.form.get("option_b", ""),
            option_c=request.form.get("option_c", ""),
            option_d=request.form.get("option_d", ""),
            correct_answer=request.form.get("correct_answer", "A"),
            marks=request.form.get("marks", type=int) or 1,
        )
        db.session.add(item)
        db.session.flush()
        log_action("Created quiz question", "quiz_question", item.id)
        db.session.commit()
        return redirect(url_for("admin.quiz_detail", quiz_id=quiz.id))
    return render_template("admin/quiz_question_form.html", quiz=quiz, question_obj=None)


@admin_bp.route("/quiz-questions/<int:question_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_quiz_question(question_id):
    item = QuizQuestion.query.get_or_404(question_id)
    if request.method == "POST":
        item.question = request.form.get("question", "").strip()
        item.option_a = request.form.get("option_a", "")
        item.option_b = request.form.get("option_b", "")
        item.option_c = request.form.get("option_c", "")
        item.option_d = request.form.get("option_d", "")
        item.correct_answer = request.form.get("correct_answer", "A")
        item.marks = request.form.get("marks", type=int) or 1
        log_action("Updated quiz question", "quiz_question", item.id)
        db.session.commit()
        return redirect(url_for("admin.quiz_detail", quiz_id=item.quiz_id))
    return render_template("admin/quiz_question_form.html", quiz=item.quiz, question_obj=item)


@admin_bp.route("/quiz-questions/<int:question_id>/delete", methods=["POST"])
@admin_required
def delete_quiz_question(question_id):
    item = QuizQuestion.query.get_or_404(question_id)
    quiz_id = item.quiz_id
    db.session.delete(item)
    log_action("Deleted quiz question", "quiz_question", item.id)
    db.session.commit()
    return redirect(url_for("admin.quiz_detail", quiz_id=quiz_id))


# ---------------------------------------------------------------------------
# WORD CONTENT IMPORT
# ---------------------------------------------------------------------------
@admin_bp.route("/content-import", methods=["GET", "POST"])
@admin_required
def content_import():
    if request.method == "POST":
        if get_setting("import_enabled", "enabled") == "disabled":
            flash("Word content import is disabled in Settings.", "danger")
            return redirect(url_for("admin.content_import"))

        upload = request.files.get("content_file")
        if upload is None or not upload.filename:
            flash("Choose a .docx Word file.", "danger")
            return redirect(url_for("admin.content_import"))

        filename = secure_filename(upload.filename)
        if not filename.lower().endswith(".docx"):
            flash("Only Microsoft Word .docx files are supported.", "danger")
            return redirect(url_for("admin.content_import"))

        max_mb = max(1, int(get_setting("import_max_mb", "10") or 10))
        upload.stream.seek(0, os.SEEK_END)
        size = upload.stream.tell()
        upload.stream.seek(0)
        if size > max_mb * 1024 * 1024:
            flash(f"The Word file is larger than the configured {max_mb} MB limit.", "danger")
            return redirect(url_for("admin.content_import"))

        try:
            parsed = parse_docx(upload.stream, filename=filename)
            summary = summarize(parsed)
            record = ContentImport(
                file_name=filename,
                file_type="docx",
                status="previewed",
                admin_user_id=get_admin_user().id,
                parsed_json=json.dumps(parsed, ensure_ascii=False),
                summary_json=json.dumps(summary, ensure_ascii=False),
            )
            db.session.add(record)
            db.session.flush()
            log_action("Previewed Word content import", "content_import", record.id)
            db.session.commit()
            flash("The Word file was read successfully. Review the structure before importing.", "success")
            return redirect(url_for("admin.content_import_preview", import_id=record.id))
        except Exception as exc:
            db.session.rollback()
            flash(f"Could not read the Word document: {exc}", "danger")

    history = ContentImport.query.order_by(ContentImport.id.desc()).limit(20).all()
    return render_template("admin/content_import.html", history=history)


@admin_bp.route("/content-import/<int:import_id>")
@admin_required
def content_import_preview(import_id):
    record = ContentImport.query.get_or_404(import_id)
    try:
        parsed = json.loads(record.parsed_json)
    except json.JSONDecodeError:
        flash("The saved import preview is invalid.", "danger")
        return redirect(url_for("admin.content_import"))
    summary = json.loads(record.summary_json or "{}")
    return render_template(
        "admin/content_import_preview.html",
        record=record,
        parsed=parsed,
        summary=summary,
    )


@admin_bp.route("/content-import/<int:import_id>/apply", methods=["POST"])
@admin_required
def content_import_apply(import_id):
    record = ContentImport.query.get_or_404(import_id)
    try:
        parsed = json.loads(record.parsed_json)
        status = request.form.get("content_status", get_setting("import_default_status", "published"))
        update_existing = request.form.get("update_existing") == "1"
        language, course = import_content(
            parsed,
            content_status=status,
            update_existing=update_existing,
        )
        record.status = "imported"
        record.imported_at = datetime.utcnow()
        record.message = f"Imported into {language.name} → {course.title}."
        log_action("Imported Word learning content", "content_import", record.id)
        db.session.commit()
        flash(record.message, "success")
        return redirect(url_for("admin.language_detail", language_id=language.id))
    except Exception as exc:
        db.session.rollback()
        record = db.session.get(ContentImport, import_id)
        if record:
            record.status = "failed"
            record.message = str(exc)
            db.session.commit()
        flash(f"The content could not be imported: {exc}", "danger")
        return redirect(url_for("admin.content_import_preview", import_id=import_id))


@admin_bp.route("/content-import/<int:import_id>/delete", methods=["POST"])
@admin_required
def content_import_delete(import_id):
    record = ContentImport.query.get_or_404(import_id)
    db.session.delete(record)
    log_action("Deleted content import record", "content_import", record.id)
    db.session.commit()
    flash("Import record deleted.", "success")
    return redirect(url_for("admin.content_import"))


# ---------------------------------------------------------------------------
# PROJECTS / PROJECT TEMPLATES
# ---------------------------------------------------------------------------
@admin_bp.route("/projects")
@admin_required
def projects():
    items = []
    if Project:
        for project in Project.query.order_by(Project.id.desc()).limit(200).all():
            owner = None
            user_id = getattr(project, "user_id", None)
            if user_id:
                owner = User.query.get(user_id)
            items.append(
                {
                    "id": project.id,
                    "name": getattr(project, "name", f"Project #{project.id}"),
                    "status": getattr(project, "status", "active"),
                    "owner": owner.username if owner else "-",
                }
            )
    return render_template("admin/projects.html", projects=items)


@admin_bp.route("/projects/<int:project_id>/delete", methods=["POST"])
@admin_required
def delete_project(project_id):
    if not Project:
        flash("Project model is not available.", "danger")
        return redirect(url_for("admin.projects"))
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    log_action("Deleted project", "project", project.id)
    db.session.commit()
    flash("Project deleted successfully.", "success")
    return redirect(url_for("admin.projects"))


@admin_bp.route("/templates")
@admin_required
def templates():
    return render_template(
        "admin/templates.html",
        templates=ProjectTemplate.query.order_by(ProjectTemplate.id.desc()).all(),
    )


@admin_bp.route("/templates/create", methods=["GET", "POST"])
@admin_required
def create_template():
    languages = Language.query.order_by(Language.name.asc()).all()
    if request.method == "POST":
        raw = request.form.get("definition_json", "{}").strip() or "{}"
        try:
            json.loads(raw)
        except json.JSONDecodeError:
            flash("Template definition must be valid JSON.", "danger")
            return render_template(
                "admin/template_form.html", template_obj=None, languages=languages
            )
        item = ProjectTemplate(
            language_id=request.form.get("language_id", type=int),
            name=request.form.get("name", "").strip(),
            project_type=request.form.get("project_type", "general"),
            description=request.form.get("description", ""),
            definition_json=raw,
            status=request.form.get("status", "draft"),
        )
        db.session.add(item)
        db.session.flush()
        log_action("Created project template", "project_template", item.id)
        db.session.commit()
        return redirect(url_for("admin.templates"))
    return render_template("admin/template_form.html", template_obj=None, languages=languages)


@admin_bp.route("/templates/<int:template_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_template(template_id):
    item = ProjectTemplate.query.get_or_404(template_id)
    languages = Language.query.order_by(Language.name.asc()).all()
    if request.method == "POST":
        raw = request.form.get("definition_json", "{}").strip() or "{}"
        try:
            json.loads(raw)
        except json.JSONDecodeError:
            flash("Template definition must be valid JSON.", "danger")
            return render_template(
                "admin/template_form.html", template_obj=item, languages=languages
            )
        item.language_id = request.form.get("language_id", type=int)
        item.name = request.form.get("name", "").strip()
        item.project_type = request.form.get("project_type", "general")
        item.description = request.form.get("description", "")
        item.definition_json = raw
        item.status = request.form.get("status", "draft")
        log_action("Updated project template", "project_template", item.id)
        db.session.commit()
        return redirect(url_for("admin.templates"))
    return render_template("admin/template_form.html", template_obj=item, languages=languages)


@admin_bp.route("/templates/<int:template_id>/delete", methods=["POST"])
@admin_required
def delete_template(template_id):
    item = ProjectTemplate.query.get_or_404(template_id)
    db.session.delete(item)
    log_action("Deleted project template", "project_template", item.id)
    db.session.commit()
    return redirect(url_for("admin.templates"))


# ---------------------------------------------------------------------------
# REPORTS / ACTIVITY / SETTINGS
# ---------------------------------------------------------------------------
@admin_bp.route("/reports")
@admin_required
def reports():
    return render_template(
        "admin/reports.html",
        users=User.query.filter_by(is_admin=False).count(),
        languages=Language.query.count(),
        courses=Course.query.count(),
        chapters=Chapter.query.count(),
        lessons=Lesson.query.count(),
        examples=Example.query.count(),
        exercises=Exercise.query.count(),
        quizzes=Quiz.query.count(),
        templates=ProjectTemplate.query.count(),
        projects=Project.query.count() if Project else 0,
    )


@admin_bp.route("/activity")
@admin_required
def activity():
    return render_template(
        "admin/activity.html",
        activities=ActivityLog.query.order_by(ActivityLog.id.desc()).limit(250).all(),
    )


@admin_bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    if request.method == "POST":
        values = {
            "application_name": request.form.get("application_name", "DevWorkspace").strip(),
            "default_language": request.form.get("default_language", "Python").strip(),
            "allow_registration": request.form.get("allow_registration", "enabled"),
            "default_course_status": request.form.get("default_course_status", "draft"),
            "import_enabled": request.form.get("import_enabled", "enabled"),
            "import_max_mb": request.form.get("import_max_mb", "10"),
            "import_default_status": request.form.get("import_default_status", "published"),
            "auto_update_existing": request.form.get("auto_update_existing", "enabled"),
            "maintenance_mode": request.form.get("maintenance_mode", "disabled"),
            "support_email": request.form.get("support_email", "").strip(),
        }
        try:
            values["import_max_mb"] = str(max(1, min(100, int(values["import_max_mb"]))))
        except ValueError:
            values["import_max_mb"] = "10"
        for key, value in values.items():
            set_setting(key, value)
        log_action("Updated application settings", "setting")
        db.session.commit()
        flash("Settings saved successfully.", "success")
        return redirect(url_for("admin.settings"))

    settings_map = {item.key: item.value for item in AppSetting.query.all()}
    return render_template("admin/settings.html", settings=settings_map)

admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
)

ADMIN_SESSION_KEY = "devworkspace_admin_user_id"