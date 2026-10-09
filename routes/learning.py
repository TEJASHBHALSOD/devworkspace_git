from functools import wraps

from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required

from models.admin_content import Course, Language, Lesson

learning_bp = Blueprint("learning", __name__, url_prefix="/dashboard/learn")


@learning_bp.app_context_processor
def inject_published_learning_content():
    """Expose published catalog data to user dashboard templates globally."""
    try:
        languages = Language.query.filter_by(status="published").order_by(Language.name.asc()).all()
        courses = Course.query.filter_by(status="published").order_by(Course.title.asc()).all()
    except Exception:
        languages, courses = [], []
    return {
        "published_languages": languages,
        "published_courses": courses,
    }


def published_or_404(query):
    item = query.first()
    if item is None:
        abort(404)
    return item


@learning_bp.route("/")
@login_required
def index():
    return render_template(
        "dashboard/learning_home.html",
        languages=Language.query.filter_by(status="published").order_by(Language.name.asc()).all(),
        courses=Course.query.filter_by(status="published").order_by(Course.title.asc()).all(),
    )


@learning_bp.route("/languages/<slug>")
@login_required
def language_detail(slug):
    language = published_or_404(Language.query.filter_by(slug=slug, status="published"))
    courses = Course.query.filter_by(language_id=language.id, status="published").order_by(Course.title.asc()).all()
    return render_template("dashboard/learning_language.html", language=language, courses=courses)


@learning_bp.route("/courses/<int:course_id>")
@login_required
def course_detail(course_id):
    course = published_or_404(Course.query.filter_by(id=course_id, status="published"))
    return render_template("dashboard/learning_course.html", course=course)


@learning_bp.route("/lessons/<int:lesson_id>")
@login_required
def lesson_detail(lesson_id):
    lesson = published_or_404(Lesson.query.filter_by(id=lesson_id, status="published"))
    return render_template("dashboard/learning_lesson.html", lesson=lesson)
