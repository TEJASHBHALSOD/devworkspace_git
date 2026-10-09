import os
import re
from copy import deepcopy

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    Document = None
    DOCX_AVAILABLE = False

from models import db
from models.admin_content import (
    Chapter,
    Course,
    Example,
    Exercise,
    Language,
    Lesson,
    Quiz,
    QuizQuestion,
)


def slugify(value):
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "item"


def unique_slug(model, value, current_id=None):
    base = slugify(value)
    candidate = base
    counter = 2
    while True:
        query = model.query.filter_by(slug=candidate)
        if current_id is not None:
            query = query.filter(model.id != current_id)
        if query.first() is None:
            return candidate
        candidate = f"{base}-{counter}"
        counter += 1


def clean(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def clean_multiline(lines):
    out = []
    for line in lines:
        line = (line or "").rstrip()
        if line.strip():
            out.append(line)
        elif out and out[-1] != "":
            out.append("")
    return "\n".join(out).strip()


def style_level(paragraph):
    style = getattr(getattr(paragraph, "style", None), "name", "") or ""
    match = re.search(r"heading\s*([1-6])", style, re.I)
    if match:
        return int(match.group(1))
    if style.strip().lower() == "title":
        return 1
    if style.strip().lower() in {"subtitle", "sub title"}:
        return 2
    return 0


def is_code_style(paragraph):
    style = getattr(getattr(paragraph, "style", None), "name", "") or ""
    return "code" in style.lower() or "preformatted" in style.lower()


def strip_prefix(text, names):
    pattern = r"^\s*(?:" + "|".join(re.escape(x) for x in names) + r")\s*[:\-]\s*(.+)$"
    match = re.match(pattern, text, re.I)
    return clean(match.group(1)) if match else None


def read_blocks(document):
    blocks = []
    for paragraph in document.paragraphs:
        text = paragraph.text.rstrip()
        if not text.strip():
            blocks.append({"text": "", "level": 0, "code": is_code_style(paragraph)})
            continue
        blocks.append(
            {
                "text": text,
                "level": style_level(paragraph),
                "code": is_code_style(paragraph),
            }
        )
    return blocks


def parse_code_fence(text, state):
    """Return (handled, mode, payload)."""
    stripped = text.strip()
    if stripped.startswith("```"):
        if state.get("code_mode"):
            return True, None, None
        return True, "code", []
    if state.get("code_mode"):
        return True, "code", [text]
    return False, None, None


def new_example(title):
    return {"title": title or "Code Example", "code": "", "explanation": ""}


def new_exercise(title):
    return {
        "title": title or "Practice Exercise",
        "instructions": "",
        "starter_code": "",
        "expected_output": "",
    }


def new_quiz(title):
    return {"title": title or "Quiz", "pass_mark": 60, "questions": []}


def new_question(text):
    return {
        "question": text,
        "option_a": "",
        "option_b": "",
        "option_c": "",
        "option_d": "",
        "correct_answer": "A",
        "marks": 1,
    }


def parse_docx(file_stream, filename=None):
    """Parse a structured Word document into the DevWorkspace learning hierarchy.

    The importer is deliberately rule-based (no ML dependency). It understands
    Word heading styles and common labels so an administrator can review the
    extracted structure before writing anything to the database.
    """
    if not DOCX_AVAILABLE:
        raise RuntimeError(
            "Word document support is not installed. "
            "Run: python -m pip install python-docx"
        )

    document = Document(file_stream)
    blocks = read_blocks(document)

    result = {
        "language": {
            "name": "",
            "version": "1.0",
            "category": "programming",
            "description": "",
        },
        "course": {
            "title": "",
            "description": "",
            "level": "beginner",
        },
        "chapters": [],
    }

    source_name = os.path.splitext(os.path.basename(filename or "Imported Course"))[0]
    result["course"]["title"] = source_name.replace("_", " ").replace("-", " ").strip() or "Imported Course"

    current_chapter = None
    current_lesson = None
    current_example = None
    current_exercise = None
    current_quiz = None
    current_question = None
    current_mode = None
    code_buffer = []
    explanation_buffer = []
    exercise_buffer = []
    question_buffer = []
    meta_description = []
    seen_course_heading = False
    in_code_fence = False

    def flush_example():
        nonlocal current_example, explanation_buffer, code_buffer
        if not current_example or current_lesson is None:
            explanation_buffer = []
            code_buffer = []
            current_example = None
            return
        if code_buffer:
            current_example["code"] = clean_multiline(code_buffer)
        if explanation_buffer:
            current_example["explanation"] = clean_multiline(explanation_buffer)
        if current_example["code"] or current_example["explanation"]:
            current_lesson["examples"].append(current_example)
        current_example = None
        code_buffer = []
        explanation_buffer = []

    def flush_exercise():
        nonlocal current_exercise, exercise_buffer
        if not current_exercise or current_lesson is None:
            exercise_buffer = []
            current_exercise = None
            return
        if exercise_buffer:
            current_exercise["instructions"] = clean_multiline(exercise_buffer)
        if current_exercise["instructions"] or current_exercise["starter_code"] or current_exercise["expected_output"]:
            current_lesson["exercises"].append(current_exercise)
        current_exercise = None
        exercise_buffer = []

    def flush_question():
        nonlocal current_question, question_buffer
        if not current_question or current_quiz is None:
            question_buffer = []
            current_question = None
            return
        if question_buffer:
            current_question["question"] = clean_multiline([current_question["question"]] + question_buffer)
        if current_question["question"]:
            current_quiz["questions"].append(current_question)
        current_question = None
        question_buffer = []

    def flush_quiz():
        nonlocal current_quiz
        flush_question()
        if current_quiz and current_lesson is not None and current_quiz["questions"]:
            current_lesson["quizzes"].append(current_quiz)
        current_quiz = None

    def flush_lesson():
        nonlocal current_lesson
        flush_example()
        flush_exercise()
        flush_quiz()
        if current_lesson and current_chapter is not None:
            current_lesson["content"] = clean_multiline(current_lesson.pop("_content_lines", []))
            current_lesson.pop("_mode", None)
            current_chapter["lessons"].append(current_lesson)
        current_lesson = None

    def flush_chapter():
        nonlocal current_chapter
        flush_lesson()
        if current_chapter:
            current_chapter["description"] = clean_multiline(current_chapter.pop("_description_lines", []))
            result["chapters"].append(current_chapter)
        current_chapter = None

    for block in blocks:
        text = block["text"]
        level = block["level"]
        is_code = block["code"]

        handled, fence_mode, _ = parse_code_fence(text, {"code_mode": in_code_fence})
        if handled and text.strip().startswith("```"):
            in_code_fence = not in_code_fence
            current_mode = "code" if in_code_fence else None
            continue
        if in_code_fence:
            if current_example is not None:
                code_buffer.append(text)
            elif current_exercise is not None:
                current_exercise["starter_code"] = (
                    current_exercise["starter_code"] + "\n" + text
                ).strip()
            elif current_lesson is not None:
                current_lesson.setdefault("_content_lines", []).append(text)
            continue

        # Global metadata labels.
        language_name = strip_prefix(text, ["Language", "Programming Language", "Technology"])
        if language_name:
            result["language"]["name"] = language_name
            current_mode = None
            continue
        version = strip_prefix(text, ["Version"])
        if version:
            result["language"]["version"] = version
            continue
        category = strip_prefix(text, ["Category"])
        if category:
            result["language"]["category"] = category.lower()
            continue
        course_label = strip_prefix(text, ["Course", "Course Title"])
        if course_label and current_chapter is None and current_lesson is None:
            result["course"]["title"] = course_label
            seen_course_heading = True
            continue
        course_description = strip_prefix(text, ["Course Description"])
        if course_description:
            result["course"]["description"] = course_description
            continue
        level_label = strip_prefix(text, ["Level"])
        if level_label and current_lesson is None:
            low = level_label.lower()
            result["course"]["level"] = low if low in {"beginner", "intermediate", "advanced"} else "beginner"
            continue

        # Explicit content labels take priority over heading levels.
        chapter_label = strip_prefix(text, ["Chapter"])
        lesson_label = strip_prefix(text, ["Lesson", "Topic"])
        example_label = strip_prefix(text, ["Example", "Code Example", "Example Code"])
        exercise_label = strip_prefix(text, ["Exercise", "Practice", "Task"])
        quiz_label = strip_prefix(text, ["Quiz", "Assessment"])

        if chapter_label:
            flush_chapter()
            current_chapter = {
                "title": chapter_label,
                "description": "",
                "lessons": [],
                "_description_lines": [],
            }
            current_mode = "chapter"
            continue

        if lesson_label:
            if current_chapter is None:
                current_chapter = {
                    "title": "Chapter 1",
                    "description": "",
                    "lessons": [],
                    "_description_lines": [],
                }
            flush_lesson()
            current_lesson = {
                "title": lesson_label,
                "content": "",
                "expected_output": "",
                "examples": [],
                "exercises": [],
                "quizzes": [],
                "_content_lines": [],
            }
            current_mode = "lesson"
            continue

        if example_label:
            if current_lesson is None:
                continue
            flush_exercise()
            flush_quiz()
            flush_example()
            current_example = new_example(example_label)
            current_mode = "example"
            continue

        if exercise_label:
            if current_lesson is None:
                continue
            flush_example()
            flush_quiz()
            flush_exercise()
            current_exercise = new_exercise(exercise_label)
            current_mode = "exercise"
            continue

        if quiz_label:
            if current_lesson is None:
                continue
            flush_example()
            flush_exercise()
            flush_quiz()
            current_quiz = new_quiz(quiz_label)
            current_mode = "quiz"
            continue

        # Word heading styles.
        if level == 1:
            if not result["course"]["title"] or (not seen_course_heading and current_chapter is None):
                result["course"]["title"] = clean(text)
                seen_course_heading = True
                current_mode = "course"
            else:
                flush_chapter()
                current_chapter = {
                    "title": clean(text),
                    "description": "",
                    "lessons": [],
                    "_description_lines": [],
                }
                current_mode = "chapter"
            continue

        if level == 2:
            if current_chapter is None:
                current_chapter = {
                    "title": "Chapter 1",
                    "description": "",
                    "lessons": [],
                    "_description_lines": [],
                }
            flush_lesson()
            current_lesson = {
                "title": clean(text),
                "content": "",
                "expected_output": "",
                "examples": [],
                "exercises": [],
                "quizzes": [],
                "_content_lines": [],
            }
            current_mode = "lesson"
            continue

        if level == 3 and current_lesson is not None:
            label = clean(text)
            lowered = label.lower()
            if lowered.startswith(("example", "code example")):
                flush_example()
                current_example = new_example(re.sub(r"^\s*(?:code\s+)?example\s*[:\-]?\s*", "", label, flags=re.I))
                current_mode = "example"
            elif lowered.startswith(("exercise", "practice", "task")):
                flush_exercise()
                current_exercise = new_exercise(re.sub(r"^\s*(?:exercise|practice|task)\s*[:\-]?\s*", "", label, flags=re.I))
                current_mode = "exercise"
            elif lowered.startswith(("quiz", "assessment")):
                flush_quiz()
                current_quiz = new_quiz(re.sub(r"^\s*(?:quiz|assessment)\s*[:\-]?\s*", "", label, flags=re.I))
                current_mode = "quiz"
            else:
                # A Heading 3 that is not a special section becomes an example.
                flush_example()
                current_example = new_example(label)
                current_mode = "example"
            continue

        # Quiz question labels and options.
        if current_quiz is not None:
            question_match = re.match(r"^\s*(?:Q\.?\s*\d*|Question\s*\d*)\s*[:\-]\s*(.+)$", text, re.I)
            if question_match:
                flush_question()
                current_question = new_question(clean(question_match.group(1)))
                continue
            option_match = re.match(r"^\s*([ABCD])\s*[\)\.:\-]\s*(.+)$", text, re.I)
            if option_match and current_question is not None:
                current_question[f"option_{option_match.group(1).lower()}"] = clean(option_match.group(2))
                continue
            answer_match = re.match(r"^\s*(?:Answer|Correct Answer)\s*[:\-]\s*([ABCD])\b", text, re.I)
            if answer_match and current_question is not None:
                current_question["correct_answer"] = answer_match.group(1).upper()
                continue
            marks_match = re.match(r"^\s*Marks?\s*[:\-]\s*(\d+)\b", text, re.I)
            if marks_match and current_question is not None:
                current_question["marks"] = int(marks_match.group(1))
                continue
            if current_question is not None:
                question_buffer.append(text)
                continue

        # Expected output label.
        expected = strip_prefix(text, ["Expected Output", "Output"])
        if expected and current_lesson is not None:
            current_lesson["expected_output"] = expected
            current_mode = "lesson"
            continue
        if expected and current_exercise is not None:
            current_exercise["expected_output"] = expected
            continue

        # Code/explanation handling for examples/exercises.
        if current_example is not None:
            if is_code or current_mode == "example_code":
                code_buffer.append(text)
                current_mode = "example_code"
            else:
                code_label = strip_prefix(text, ["Code", "Source Code"])
                if code_label:
                    if code_label:
                        code_buffer.append(code_label)
                    current_mode = "example_code"
                elif current_mode == "example_code":
                    code_buffer.append(text)
                else:
                    explanation_buffer.append(text)
            continue

        if current_exercise is not None:
            code_label = strip_prefix(text, ["Starter Code", "Code"])
            expected_ex = strip_prefix(text, ["Expected Output", "Output"])
            if code_label:
                current_exercise["starter_code"] = code_label
                current_mode = "exercise_code"
            elif expected_ex:
                current_exercise["expected_output"] = expected_ex
            elif is_code or current_mode == "exercise_code":
                current_exercise["starter_code"] = (current_exercise["starter_code"] + "\n" + text).strip()
            else:
                exercise_buffer.append(text)
            continue

        if current_lesson is not None:
            current_lesson.setdefault("_content_lines", []).append(text)
            continue

        if current_chapter is not None:
            current_chapter.setdefault("_description_lines", []).append(text)
            continue

        meta_description.append(text)

    flush_chapter()

    if not result["language"]["name"]:
        # Best-effort guess from common filename patterns.
        filename_match = re.match(r"(?:learn|course|tutorial|lesson)?[_\- ]*([A-Za-z][A-Za-z0-9+#. ]{1,40}?)(?:[_\- ]*(?:course|tutorial|basics|fundamentals))?$", source_name, re.I)
        result["language"]["name"] = clean(filename_match.group(1)) if filename_match else "Imported Language"

    if meta_description and not result["language"]["description"]:
        result["language"]["description"] = clean_multiline(meta_description[:3])

    # Remove implementation-only keys and normalize ordering.
    for index, chapter in enumerate(result["chapters"], start=1):
        chapter.pop("_description_lines", None)
        for lesson_index, lesson in enumerate(chapter["lessons"], start=1):
            lesson.pop("_content_lines", None)
            lesson["order_no"] = lesson_index
        chapter["order_no"] = index

    # Never return an empty learning tree: create a reviewable course/chapter/lesson.
    if not result["chapters"]:
        result["chapters"] = [
            {
                "title": "Chapter 1",
                "description": "",
                "order_no": 1,
                "lessons": [
                    {
                        "title": "Lesson 1",
                        "content": result["language"]["description"] or "Imported content. Review and edit this lesson.",
                        "expected_output": "",
                        "order_no": 1,
                        "examples": [],
                        "exercises": [],
                        "quizzes": [],
                    }
                ],
            }
        ]

    return result


def summarize(parsed):
    course = parsed.get("course", {})
    chapters = parsed.get("chapters", [])
    lesson_count = sum(len(ch.get("lessons", [])) for ch in chapters)
    example_count = sum(
        len(lesson.get("examples", []))
        for ch in chapters
        for lesson in ch.get("lessons", [])
    )
    exercise_count = sum(
        len(lesson.get("exercises", []))
        for ch in chapters
        for lesson in ch.get("lessons", [])
    )
    quiz_count = sum(
        len(lesson.get("quizzes", []))
        for ch in chapters
        for lesson in ch.get("lessons", [])
    )
    question_count = sum(
        len(quiz.get("questions", []))
        for ch in chapters
        for lesson in ch.get("lessons", [])
        for quiz in lesson.get("quizzes", [])
    )
    return {
        "language": parsed.get("language", {}).get("name", ""),
        "course": course.get("title", ""),
        "chapters": len(chapters),
        "lessons": lesson_count,
        "examples": example_count,
        "exercises": exercise_count,
        "quizzes": quiz_count,
        "questions": question_count,
    }


def _first_by_name(query, model, name):
    return query.filter(db.func.lower(model.name) == (name or "").lower()).first()


def import_content(parsed, content_status="published", update_existing=True):
    """Upsert the parsed Word structure into Language -> Course -> ... tables."""
    content_status = content_status if content_status in {"draft", "published"} else "published"
    language_data = parsed.get("language", {})
    course_data = parsed.get("course", {})

    language_name = clean(language_data.get("name")) or "Imported Language"
    language = _first_by_name(Language.query, Language, language_name)
    if language is None:
        language = Language(
            name=language_name,
            slug=unique_slug(Language, language_name),
            version=clean(language_data.get("version")) or "1.0",
            description=language_data.get("description", ""),
            category=clean(language_data.get("category")) or "programming",
            icon="fa-solid fa-code",
            status=content_status,
        )
        db.session.add(language)
        db.session.flush()
    elif update_existing:
        language.version = clean(language_data.get("version")) or language.version
        if language_data.get("description"):
            language.description = language_data["description"]
        if language_data.get("category"):
            language.category = clean(language_data["category"])
        language.status = content_status

    course_title = clean(course_data.get("title")) or f"{language.name} Course"
    course = (
        Course.query.filter_by(language_id=language.id)
        .filter(db.func.lower(Course.title) == course_title.lower())
        .first()
    )
    if course is None:
        course = Course(
            language_id=language.id,
            title=course_title,
            slug=unique_slug(Course, course_title),
            description=course_data.get("description", ""),
            level=course_data.get("level", "beginner") or "beginner",
            status=content_status,
        )
        db.session.add(course)
        db.session.flush()
    elif update_existing:
        course.description = course_data.get("description", course.description)
        course.level = course_data.get("level", course.level) or course.level
        course.status = content_status

    for chapter_index, chapter_data in enumerate(parsed.get("chapters", []), start=1):
        chapter_title = clean(chapter_data.get("title")) or f"Chapter {chapter_index}"
        chapter = (
            Chapter.query.filter_by(course_id=course.id)
            .filter(db.func.lower(Chapter.title) == chapter_title.lower())
            .first()
        )
        if chapter is None:
            chapter = Chapter(
                course_id=course.id,
                title=chapter_title,
                description=chapter_data.get("description", ""),
                order_no=chapter_data.get("order_no", chapter_index) or chapter_index,
                status=content_status,
            )
            db.session.add(chapter)
            db.session.flush()
        elif update_existing:
            chapter.description = chapter_data.get("description", chapter.description)
            chapter.order_no = chapter_data.get("order_no", chapter.order_no) or chapter.order_no
            chapter.status = content_status

        for lesson_index, lesson_data in enumerate(chapter_data.get("lessons", []), start=1):
            lesson_title = clean(lesson_data.get("title")) or f"Lesson {lesson_index}"
            lesson = (
                Lesson.query.filter_by(chapter_id=chapter.id)
                .filter(db.func.lower(Lesson.title) == lesson_title.lower())
                .first()
            )
            if lesson is None:
                lesson = Lesson(
                    chapter_id=chapter.id,
                    title=lesson_title,
                    slug=unique_slug(Lesson, lesson_title),
                    content=lesson_data.get("content", ""),
                    expected_output=lesson_data.get("expected_output", ""),
                    order_no=lesson_data.get("order_no", lesson_index) or lesson_index,
                    status=content_status,
                )
                db.session.add(lesson)
                db.session.flush()
            elif update_existing:
                lesson.content = lesson_data.get("content", lesson.content)
                lesson.expected_output = lesson_data.get("expected_output", lesson.expected_output)
                lesson.order_no = lesson_data.get("order_no", lesson.order_no) or lesson.order_no
                lesson.status = content_status

            for example_data in lesson_data.get("examples", []):
                example_title = clean(example_data.get("title")) or "Code Example"
                example = (
                    Example.query.filter_by(lesson_id=lesson.id)
                    .filter(db.func.lower(Example.title) == example_title.lower())
                    .first()
                )
                if example is None:
                    db.session.add(
                        Example(
                            lesson_id=lesson.id,
                            title=example_title,
                            code=example_data.get("code", ""),
                            explanation=example_data.get("explanation", ""),
                        )
                    )
                elif update_existing:
                    example.code = example_data.get("code", example.code)
                    example.explanation = example_data.get("explanation", example.explanation)

            for exercise_data in lesson_data.get("exercises", []):
                exercise_title = clean(exercise_data.get("title")) or "Practice Exercise"
                exercise = (
                    Exercise.query.filter_by(lesson_id=lesson.id)
                    .filter(db.func.lower(Exercise.title) == exercise_title.lower())
                    .first()
                )
                if exercise is None:
                    db.session.add(
                        Exercise(
                            lesson_id=lesson.id,
                            title=exercise_title,
                            instructions=exercise_data.get("instructions", ""),
                            starter_code=exercise_data.get("starter_code", ""),
                            expected_output=exercise_data.get("expected_output", ""),
                        )
                    )
                elif update_existing:
                    exercise.instructions = exercise_data.get("instructions", exercise.instructions)
                    exercise.starter_code = exercise_data.get("starter_code", exercise.starter_code)
                    exercise.expected_output = exercise_data.get("expected_output", exercise.expected_output)

            for quiz_data in lesson_data.get("quizzes", []):
                quiz_title = clean(quiz_data.get("title")) or "Quiz"
                quiz = (
                    Quiz.query.filter_by(lesson_id=lesson.id)
                    .filter(db.func.lower(Quiz.title) == quiz_title.lower())
                    .first()
                )
                if quiz is None:
                    quiz = Quiz(
                        lesson_id=lesson.id,
                        title=quiz_title,
                        pass_mark=int(quiz_data.get("pass_mark") or 60),
                        status=content_status,
                    )
                    db.session.add(quiz)
                    db.session.flush()
                elif update_existing:
                    quiz.pass_mark = int(quiz_data.get("pass_mark") or quiz.pass_mark or 60)
                    quiz.status = content_status

                for question_data in quiz_data.get("questions", []):
                    question_text = clean(question_data.get("question"))
                    if not question_text:
                        continue
                    question = (
                        QuizQuestion.query.filter_by(quiz_id=quiz.id)
                        .filter(db.func.lower(QuizQuestion.question) == question_text.lower())
                        .first()
                    )
                    if question is None:
                        db.session.add(
                            QuizQuestion(
                                quiz_id=quiz.id,
                                question=question_text,
                                option_a=question_data.get("option_a", ""),
                                option_b=question_data.get("option_b", ""),
                                option_c=question_data.get("option_c", ""),
                                option_d=question_data.get("option_d", ""),
                                correct_answer=(question_data.get("correct_answer") or "A").upper()[:1],
                                marks=int(question_data.get("marks") or 1),
                            )
                        )
                    elif update_existing:
                        question.option_a = question_data.get("option_a", question.option_a)
                        question.option_b = question_data.get("option_b", question.option_b)
                        question.option_c = question_data.get("option_c", question.option_c)
                        question.option_d = question_data.get("option_d", question.option_d)
                        question.correct_answer = (question_data.get("correct_answer") or question.correct_answer or "A").upper()[:1]
                        question.marks = int(question_data.get("marks") or question.marks or 1)

    db.session.commit()
    return language, course
