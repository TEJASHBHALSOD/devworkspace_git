# Word Content Import Format

DevWorkspace reads `.docx` files with a rule-based parser. It does not use machine learning. The goal is to turn a Word learning document into a reviewable structure before writing it to the database.

## Recommended structure

```text
Language: Python
Version: 3.x
Category: programming
Level: beginner
Course: Python Fundamentals
Course Description: Learn Python from the basics.

Heading 1: Chapter 1 - Basics
Heading 2: Lesson 1 - Variables

Explanation paragraphs go here.

Example: Create a variable
Code:
name = "DevWorkspace"
print(name)
This example explains variable assignment.

Exercise: Create your own variable
Write a program that stores your name.
Starter Code:
name = ""
Expected Output: Your name

Quiz: Variables Quiz
Q1: Which symbol assigns a value?
A) ==
B) =
C) =>
D) :=
Answer: B
Marks: 1
```

## The importer understands

- Word `Title`, `Heading 1`, `Heading 2` and `Heading 3` styles.
- `Language:`, `Version:`, `Category:`, `Level:` and `Course:` labels.
- `Chapter:`, `Lesson:`, `Topic:` labels.
- `Example:`, `Code Example:` and `Code:` labels.
- `Exercise:`, `Practice:` and `Task:` labels.
- `Quiz:`, `Q1:` / `Question 1:` labels.
- Multiple-choice options `A)`, `B)`, `C)`, `D)`.
- `Answer:` and `Marks:` for quiz questions.
- `Expected Output:` / `Output:`.
- Fenced code blocks using triple backticks.
- Word paragraphs using a style containing `Code` or `Preformatted`.

## Import behavior

1. The administrator uploads the `.docx` file.
2. DevWorkspace extracts the structure and saves a preview.
3. The administrator reviews chapters, lessons, examples, exercises and quizzes.
4. The administrator chooses `Published` or `Draft`.
5. The importer creates or updates:

```text
Language
  └── Course
      └── Chapter
          └── Lesson
              ├── Example (reference code)
              ├── Exercise (practice)
              └── Quiz (assessment)
                    └── Question
```

Matching content is identified by title within the same parent, which prevents ordinary repeated imports from creating a new copy of every item.
