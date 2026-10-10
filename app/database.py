"""SQLite schema, sample-data loading, and attendance reads."""

import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DEMO_STUDENT_ID_PATTERN = re.compile(r"DEMO[0-9]{4}")

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS subjects (
    subject_code TEXT PRIMARY KEY,
    subject_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS student_subjects (
    student_id TEXT NOT NULL REFERENCES students(student_id),
    subject_code TEXT NOT NULL REFERENCES subjects(subject_code),
    PRIMARY KEY (student_id, subject_code)
);

CREATE TABLE IF NOT EXISTS attendance_records (
    id INTEGER PRIMARY KEY,
    student_id TEXT NOT NULL,
    subject_code TEXT NOT NULL,
    class_number INTEGER NOT NULL,
    attended INTEGER NOT NULL CHECK (attended IN (0, 1)),
    FOREIGN KEY (student_id, subject_code)
        REFERENCES student_subjects(student_id, subject_code),
    UNIQUE (student_id, subject_code, class_number)
);
"""


@contextmanager
def connect(
    database_path: Path, *, read_only: bool = False
) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(database_path, timeout=5)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        if read_only:
            connection.execute("PRAGMA query_only = ON")
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(database_path) as connection:
        connection.executescript(SCHEMA)


def _validate_attendance_data(sample_data: object) -> list[dict]:
    if not isinstance(sample_data, dict) or not isinstance(
        sample_data.get("students"), list
    ):
        raise ValueError("Attendance fixture must contain a students list.")

    students = sample_data["students"]
    seen_student_ids: set[str] = set()
    subject_names: dict[str, str] = {}

    for student in students:
        if not isinstance(student, dict):
            raise ValueError("Each attendance fixture student must be an object.")
        student_id = student.get("student_id")
        if not isinstance(student_id, str) or not DEMO_STUDENT_ID_PATTERN.fullmatch(
            student_id
        ):
            raise ValueError("Attendance fixture IDs must use fictional DEMO#### IDs.")
        if student_id in seen_student_ids:
            raise ValueError(f"Duplicate student ID in attendance fixture: {student_id}.")
        seen_student_ids.add(student_id)

        subjects = student.get("subjects")
        if not isinstance(subjects, list):
            raise ValueError(f"Student {student_id} must have a subjects list.")
        seen_subjects: set[str] = set()
        for subject in subjects:
            if not isinstance(subject, dict):
                raise ValueError(f"Student {student_id} has an invalid subject entry.")
            subject_code = subject.get("subject_code")
            subject_name = subject.get("subject_name")
            classes = subject.get("classes")
            if (
                not isinstance(subject_code, str)
                or not subject_code.strip()
                or not isinstance(subject_name, str)
                or not subject_name.strip()
                or not isinstance(classes, list)
                or any(type(attended) is not bool for attended in classes)
            ):
                raise ValueError(f"Student {student_id} has invalid subject data.")
            if subject_code in seen_subjects:
                raise ValueError(
                    f"Duplicate subject {subject_code} for student {student_id}."
                )
            seen_subjects.add(subject_code)

            existing_name = subject_names.setdefault(subject_code, subject_name)
            if existing_name != subject_name:
                raise ValueError(
                    f"Conflicting names for subject {subject_code} in attendance fixture."
                )

    return students


def seed_attendance_data(database_path: Path, sample_data_path: Path) -> None:
    with sample_data_path.open(encoding="utf-8") as source_file:
        sample_data = json.load(source_file)
    students = _validate_attendance_data(sample_data)

    with connect(database_path) as connection:
        # The demo fixture is authoritative; replace its tables atomically on startup.
        connection.execute("DELETE FROM attendance_records")
        connection.execute("DELETE FROM student_subjects")
        connection.execute("DELETE FROM subjects")
        connection.execute("DELETE FROM students")

        inserted_subjects: set[str] = set()
        for student in students:
            connection.execute(
                "INSERT INTO students (student_id) VALUES (?)",
                (student["student_id"],),
            )
            for subject in student["subjects"]:
                if subject["subject_code"] not in inserted_subjects:
                    connection.execute(
                        """
                        INSERT INTO subjects (subject_code, subject_name)
                        VALUES (?, ?)
                        """,
                        (subject["subject_code"], subject["subject_name"]),
                    )
                    inserted_subjects.add(subject["subject_code"])
                connection.execute(
                    """
                    INSERT INTO student_subjects (student_id, subject_code)
                    VALUES (?, ?)
                    """,
                    (student["student_id"], subject["subject_code"]),
                )
                for class_number, attended in enumerate(subject["classes"], start=1):
                    connection.execute(
                        """
                        INSERT INTO attendance_records
                            (student_id, subject_code, class_number, attended)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            student["student_id"],
                            subject["subject_code"],
                            class_number,
                            int(attended),
                        ),
                    )


def attendance_rows(database_path: Path, student_id: str) -> list[dict] | None:
    """Return per-subject counts, or None if the student ID is not seeded."""
    with connect(database_path, read_only=True) as connection:
        student = connection.execute(
            "SELECT 1 FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        if student is None:
            return None

        rows = connection.execute(
            """
            SELECT
                s.subject_code,
                s.subject_name,
                COUNT(a.id) AS total_classes,
                COALESCE(SUM(a.attended), 0) AS attended_classes
            FROM student_subjects ss
            JOIN subjects s ON s.subject_code = ss.subject_code
            LEFT JOIN attendance_records a
                ON a.student_id = ss.student_id
                AND a.subject_code = ss.subject_code
            WHERE ss.student_id = ?
            GROUP BY s.subject_code, s.subject_name
            ORDER BY s.subject_code
            """,
            (student_id,),
        ).fetchall()
    return [dict(row) for row in rows]
