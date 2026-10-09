from datetime import datetime

from models import db


def _find_mapped_model_by_table(table_name):
    """Return an already-mapped SQLAlchemy model for a table, if one exists."""
    for mapper in list(db.Model.registry.mappers):
        try:
            if mapper.local_table.name == table_name:
                return mapper.class_
        except Exception:
            continue
    return None


# Your project may already define this model/table in models.project.
# Reuse it instead of declaring project_templates a second time.
ExistingProjectTemplate = _find_mapped_model_by_table("project_templates")
ExistingProjectTemplateTable = db.metadata.tables.get("project_templates")


class Language(db.Model):
    __tablename__ = "languages"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    version = db.Column(db.String(50), default="1.0", nullable=False)
    description = db.Column(db.Text, default="", nullable=False)
    category = db.Column(db.String(50), default="programming", nullable=False)
    icon = db.Column(db.String(120), default="fa-solid fa-code", nullable=False)
    status = db.Column(db.String(20), default="published", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    courses = db.relationship(
        "Course",
        back_populates="language",
        cascade="all, delete-orphan",
        order_by="Course.title",
    )


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    language_id = db.Column(db.Integer, db.ForeignKey("languages.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False)
    description = db.Column(db.Text, default="", nullable=False)
    level = db.Column(db.String(30), default="beginner", nullable=False)
    status = db.Column(db.String(20), default="draft", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    language = db.relationship("Language", back_populates="courses")
    chapters = db.relationship(
        "Chapter",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Chapter.order_no",
    )


class Chapter(db.Model):
    __tablename__ = "chapters"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="", nullable=False)
    order_no = db.Column(db.Integer, default=1, nullable=False)
    status = db.Column(db.String(20), default="published", nullable=False)

    course = db.relationship("Course", back_populates="chapters")
    lessons = db.relationship(
        "Lesson",
        back_populates="chapter",
        cascade="all, delete-orphan",
        order_by="Lesson.order_no",
    )


class Lesson(db.Model):
    __tablename__ = "lessons"

    id = db.Column(db.Integer, primary_key=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapters.id"), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    content = db.Column(db.Text, default="", nullable=False)
    expected_output = db.Column(db.Text, default="", nullable=False)
    order_no = db.Column(db.Integer, default=1, nullable=False)
    status = db.Column(db.String(20), default="draft", nullable=False)

    chapter = db.relationship("Chapter", back_populates="lessons")
    examples = db.relationship(
        "Example", back_populates="lesson", cascade="all, delete-orphan"
    )
    exercises = db.relationship(
        "Exercise", back_populates="lesson", cascade="all, delete-orphan"
    )
    quizzes = db.relationship(
        "Quiz", back_populates="lesson", cascade="all, delete-orphan"
    )


class Example(db.Model):
    __tablename__ = "examples"

    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    code = db.Column(db.Text, default="", nullable=False)
    explanation = db.Column(db.Text, default="", nullable=False)

    lesson = db.relationship("Lesson", back_populates="examples")


class Exercise(db.Model):
    __tablename__ = "exercises"

    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    instructions = db.Column(db.Text, default="", nullable=False)
    starter_code = db.Column(db.Text, default="", nullable=False)
    expected_output = db.Column(db.Text, default="", nullable=False)

    lesson = db.relationship("Lesson", back_populates="exercises")


class Quiz(db.Model):
    __tablename__ = "quizzes"

    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    pass_mark = db.Column(db.Integer, default=60, nullable=False)
    status = db.Column(db.String(20), default="draft", nullable=False)

    lesson = db.relationship("Lesson", back_populates="quizzes")
    questions = db.relationship(
        "QuizQuestion", back_populates="quiz", cascade="all, delete-orphan"
    )


class QuizQuestion(db.Model):
    __tablename__ = "quiz_questions"

    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id"), nullable=False)
    question = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(500), default="", nullable=False)
    option_b = db.Column(db.String(500), default="", nullable=False)
    option_c = db.Column(db.String(500), default="", nullable=False)
    option_d = db.Column(db.String(500), default="", nullable=False)
    correct_answer = db.Column(db.String(1), default="A", nullable=False)
    marks = db.Column(db.Integer, default=1, nullable=False)

    quiz = db.relationship("Quiz", back_populates="questions")


if ExistingProjectTemplate is not None:
    # Reuse the model already registered by the project.
    ProjectTemplate = ExistingProjectTemplate
elif ExistingProjectTemplateTable is not None:
    # Reuse an existing table object if the project has defined its table but
    # the mapped class is not yet registered at import time.
    class ProjectTemplate(db.Model):
        __table__ = ExistingProjectTemplateTable
else:
    class ProjectTemplate(db.Model):
        __tablename__ = "project_templates"

        id = db.Column(db.Integer, primary_key=True)
        language_id = db.Column(db.Integer, db.ForeignKey("languages.id"), nullable=False)
        name = db.Column(db.String(160), nullable=False)
        project_type = db.Column(db.String(80), default="general", nullable=False)
        description = db.Column(db.Text, default="", nullable=False)
        definition_json = db.Column(db.Text, default="{}", nullable=False)
        status = db.Column(db.String(20), default="draft", nullable=False)


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    action = db.Column(db.String(160), nullable=False)
    entity_type = db.Column(db.String(80), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class AppSetting(db.Model):
    __tablename__ = "app_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(120), unique=True, nullable=False)
    value = db.Column(db.Text, default="", nullable=False)


class ContentImport(db.Model):
    """Saved preview/import record for a Word learning-content import."""

    __tablename__ = "content_imports"

    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(30), default="docx", nullable=False)
    status = db.Column(db.String(30), default="previewed", nullable=False)
    admin_user_id = db.Column(db.Integer, nullable=True)
    parsed_json = db.Column(db.Text, nullable=False)
    summary_json = db.Column(db.Text, default="{}", nullable=False)
    message = db.Column(db.Text, default="", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    imported_at = db.Column(db.DateTime, nullable=True)
