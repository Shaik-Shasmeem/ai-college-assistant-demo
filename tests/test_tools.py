from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import initialize_database, seed_attendance_data
from app.main import create_app
from app.tools import (
    ToolAuthorizationError,
    ToolValidationError,
    get_attendance,
    get_courses,
    search_policy,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_DIR = PROJECT_ROOT / "data" / "knowledge"


@pytest.fixture
def seeded_db(tmp_path):
    database_path = tmp_path / "attendance.sqlite3"
    initialize_database(database_path)
    seed_attendance_data(database_path, PROJECT_ROOT / "data" / "attendance.json")
    return database_path


def test_get_attendance_tool_returns_expected_summary(seeded_db):
    result = get_attendance(
        "DEMO1001", seeded_db, requester_id="DEMO1001"
    )

    assert result == {
        "student_id": "DEMO1001",
        "subjects": [
            {
                "subject_code": "CS101",
                "subject": "Introduction to Computing",
                "attended_classes": 3,
                "total_classes": 4,
                "percentage": 75.0,
            },
            {
                "subject_code": "MA105",
                "subject": "Discrete Mathematics",
                "attended_classes": 0,
                "total_classes": 0,
                "percentage": 0.0,
            },
            {
                "subject_code": "SE201",
                "subject": "Software Engineering Basics",
                "attended_classes": 4,
                "total_classes": 4,
                "percentage": 100.0,
            },
        ],
    }


def test_get_attendance_tool_validates_and_authorizes(seeded_db):
    with pytest.raises(ToolValidationError, match="fictional DEMO"):
        get_attendance("STUDENT1", seeded_db, requester_id="DEMO1001")

    with pytest.raises(ToolAuthorizationError, match="only access their own"):
        get_attendance("DEMO1001", seeded_db, requester_id="DEMO1002")
    with pytest.raises(ToolAuthorizationError, match="identity is required"):
        get_attendance("DEMO1001", seeded_db)


def test_get_courses_tool_returns_minimal_course_data(seeded_db):
    result = get_courses("DEMO1001", seeded_db, requester_id="DEMO1001")

    assert result == {
        "student_id": "DEMO1001",
        "courses": [
            {"subject_code": "CS101", "subject_name": "Introduction to Computing"},
            {"subject_code": "MA105", "subject_name": "Discrete Mathematics"},
            {"subject_code": "SE201", "subject_name": "Software Engineering Basics"},
        ],
    }


def test_search_policy_tool_returns_passages_for_known_question():
    result = search_policy("What is the minimum attendance requirement?", POLICY_DIR)

    assert result["question"] == "What is the minimum attendance requirement?"
    assert result["results"][0]["source"] == "attendance_policy.md"
    assert "at least 75%" in result["results"][0]["text"]


def test_search_policy_tool_rejects_blank_question():
    with pytest.raises(ToolValidationError, match="Question cannot be blank"):
        search_policy("   ", POLICY_DIR)


def test_tool_endpoints_are_available_and_secure(tmp_path):
    database_path = tmp_path / "attendance.sqlite3"
    initialize_database(database_path)
    seed_attendance_data(database_path, PROJECT_ROOT / "data" / "attendance.json")
    app = create_app(
        PROJECT_ROOT / "data" / "policies.json",
        database_path,
        PROJECT_ROOT / "data" / "attendance.json",
        POLICY_DIR,
    )

    with TestClient(app) as client:
        attendance = client.post(
            "/api/tools/get_attendance",
            json={"student_id": "DEMO1001", "requester_id": "DEMO1001"},
        )
        assert attendance.status_code == 200
        assert attendance.json()["student_id"] == "DEMO1001"

        unauthorized = client.post(
            "/api/tools/get_attendance",
            json={"student_id": "DEMO1001", "requester_id": "DEMO1002", "requester_role": "student"},
        )
        assert unauthorized.status_code == 403

        courses = client.post(
            "/api/tools/get_courses",
            json={"student_id": "DEMO1001", "requester_id": "DEMO1001"},
        )
        assert courses.status_code == 200
        assert courses.json()["courses"][0]["subject_code"] == "CS101"

        policy = client.post(
            "/api/tools/search_policy",
            json={"question": "What is the minimum attendance requirement?"},
        )
        assert policy.status_code == 200
        assert policy.json()["results"][0]["source"] == "attendance_policy.md"
