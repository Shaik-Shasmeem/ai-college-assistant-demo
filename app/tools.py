"""Narrow, read-only application tools for attendance and policy access."""

from __future__ import annotations

import re
from pathlib import Path

from app.attendance import calculate_attendance
from app.database import attendance_rows, connect
from app.retrieval import retrieve_passages

STUDENT_ID_PATTERN = re.compile(r"^DEMO\d{4}$")


class ToolValidationError(ValueError):
    """Raised when a tool input does not satisfy the allowed schema."""


class ToolAuthorizationError(PermissionError):
    """Raised when a caller requests data outside the authorized scope."""


def _normalize_student_id(student_id: str) -> str:
    if not isinstance(student_id, str):
        raise ToolValidationError("Student ID must be provided as a string.")
    normalized = student_id.strip().upper()
    if not STUDENT_ID_PATTERN.fullmatch(normalized):
        raise ToolValidationError("Student ID must use the fictional DEMO#### format.")
    return normalized


def _validate_question(question: str) -> str:
    if not isinstance(question, str):
        raise ToolValidationError("Question must be a string.")
    normalized = question.strip()
    if not normalized:
        raise ToolValidationError("Question cannot be blank.")
    return normalized


def _check_authorization(
    student_id: str,
    *,
    requester_id: str | None,
    requester_role: str,
) -> None:
    if requester_role not in {"student", "staff", "admin"}:
        raise ToolValidationError("Unsupported requester role.")
    if requester_role == "student":
        if requester_id is None:
            raise ToolAuthorizationError(
                "A student identity is required to access student records."
            )
        normalized_requester = _normalize_student_id(requester_id)
        if normalized_requester != student_id:
            raise ToolAuthorizationError(
                "Students can only access their own attendance and course records."
            )


def get_attendance(
    student_id: str,
    database_path: str | Path = "data/demo.sqlite3",
    *,
    requester_id: str | None = None,
    requester_role: str = "student",
) -> dict:
    """Return attendance for an authorized student or staff caller."""
    normalized_id = _normalize_student_id(student_id)
    _check_authorization(
        normalized_id,
        requester_id=requester_id,
        requester_role=requester_role,
    )

    records = attendance_rows(Path(database_path), normalized_id)
    if records is None:
        raise LookupError(f"No attendance records found for {normalized_id}.")
    return calculate_attendance(normalized_id, records)


def get_courses(
    student_id: str,
    database_path: str | Path = "data/demo.sqlite3",
    *,
    requester_id: str | None = None,
    requester_role: str = "student",
) -> dict:
    """Return the minimal course list for the requested student."""
    normalized_id = _normalize_student_id(student_id)
    _check_authorization(
        normalized_id,
        requester_id=requester_id,
        requester_role=requester_role,
    )

    with connect(Path(database_path), read_only=True) as connection:
        rows = connection.execute(
            """
            SELECT s.subject_code, s.subject_name
            FROM student_subjects ss
            JOIN subjects s ON s.subject_code = ss.subject_code
            WHERE ss.student_id = ?
            ORDER BY s.subject_code
            """,
            (normalized_id,),
        ).fetchall()

    if not rows:
        raise LookupError(f"No registered courses found for {normalized_id}.")

    return {
        "student_id": normalized_id,
        "courses": [
            {
                "subject_code": row["subject_code"],
                "subject_name": row["subject_name"],
            }
            for row in rows
        ],
    }


def search_policy(
    question: str,
    knowledge_dir: str | Path = "data/knowledge",
) -> dict:
    """Return up to three relevant policy passages for a user question."""
    normalized_question = _validate_question(question)
    passages = retrieve_passages(normalized_question, Path(knowledge_dir))
    return {
        "question": normalized_question,
        "results": passages,
    }
