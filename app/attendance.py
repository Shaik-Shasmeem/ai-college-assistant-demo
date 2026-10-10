"""Attendance validation and presentation calculations."""

import re

STUDENT_ID_PATTERN = re.compile(r"DEMO[0-9]{4}")


def calculate_attendance(student_id: str, records: list[dict]) -> dict:
    """Build a display-ready report from trusted per-subject database counts."""
    normalized_id = student_id.strip().upper()
    if not STUDENT_ID_PATTERN.fullmatch(normalized_id):
        raise ValueError("Student ID must use the fictional DEMO#### format.")

    subjects = []
    for record in records:
        total = record["total_classes"]
        attended = record["attended_classes"]
        percentage = round(attended * 100 / total, 1) if total else 0.0
        subjects.append(
            {
                "subject_code": record["subject_code"],
                "subject": record["subject_name"],
                "attended_classes": attended,
                "total_classes": total,
                "percentage": percentage,
            }
        )
    return {"student_id": normalized_id, "subjects": subjects}
