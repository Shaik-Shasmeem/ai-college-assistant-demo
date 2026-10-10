import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.attendance import calculate_attendance
from app.database import attendance_rows, initialize_database, seed_attendance_data
from app.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client(tmp_path):
    knowledge_path = PROJECT_ROOT / "data" / "policies.json"
    database_path = tmp_path / "attendance.sqlite3"
    app = create_app(
        knowledge_path,
        database_path,
        PROJECT_ROOT / "data" / "attendance.json",
    )
    with TestClient(app) as test_client:
        yield test_client


def test_health_and_static_page(client):
    assert client.get("/health").json() == {"status": "ok"}
    page = client.get("/")
    assert "AI College Assistant" in page.text
    assert "login" not in page.text.lower()
    assert "Show my attendance" in page.text
    assert client.get("/static/style.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_public_assistant_answers_without_login(client):
    answer = client.post(
        "/api/assistant/ask", json={"question": "When does the library open?"}
    )
    assert answer.status_code == 200
    assert answer.json()["status"] == "answered"
    assert "fictional demonstration" in answer.json()["answer"]
    assert "not real college policy" in answer.json()["sources"][0]["notice"]

    unknown = client.post(
        "/api/assistant/ask", json={"question": "What is the graduation policy?"}
    )
    assert unknown.json() == {
        "status": "insufficient_evidence",
        "answer": "The source does not provide enough information.",
        "sources": [],
    }


@pytest.mark.parametrize(
    ("question", "expected_title", "answer_fragment"),
    [
        ("When does the library open?", "Fictional Demo Library Hours", "Monday to Friday"),
        ("How do I reserve a lab workstation?", "Fictional Demo Lab Booking", "department office"),
        ("When are faculty consultation hours?", "Fictional Demo Office Hours", "notice board"),
    ],
)
def test_each_fictional_faq_has_a_grounded_answer(
    client, question, expected_title, answer_fragment
):
    response = client.post("/api/assistant/ask", json={"question": question})

    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    assert answer_fragment in response.json()["answer"]
    assert response.json()["sources"][0]["title"] == expected_title


@pytest.mark.parametrize("question", ["", "   ", "x" * 501])
def test_invalid_questions_have_safe_validation_response(client, question):
    response = client.post("/api/assistant/ask", json={"question": question})
    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "Request data is missing or invalid.",
        }
    }


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"question": None},
        {"question": 42},
        {"question": ["library"]},
    ],
)
def test_malformed_question_payloads_are_rejected(client, body):
    response = client.post("/api/assistant/ask", json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_malformed_json_and_unknown_routes_use_api_error_format(client):
    malformed_json = client.post(
        "/api/assistant/ask",
        content=b'{"question":',
        headers={"Content-Type": "application/json"},
    )
    missing_route = client.get("/api/not-a-route")
    wrong_method = client.get("/api/assistant/ask")

    for response, expected_status in (
        (malformed_json, 422),
        (missing_route, 404),
        (wrong_method, 405),
    ):
        assert response.status_code == expected_status
        assert set(response.json()) == {"error"}
        assert set(response.json()["error"]) == {"code", "message"}


def test_unreadable_knowledge_source_returns_generic_error(tmp_path):
    missing_source = tmp_path / "missing.json"
    app = create_app(missing_source)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        health = test_client.get("/health")
        ask = test_client.post(
            "/api/assistant/ask", json={"question": "When is the library open?"}
        )

    for response in (health, ask):
        assert response.status_code == 500
        assert response.json() == {
            "error": {
                "code": "internal_error",
                "message": "The request could not be completed.",
            }
        }


def test_authentication_and_attendance_endpoints_are_removed(client):
    removed_routes = [
        ("POST", "/api/auth/login"),
        ("POST", "/api/auth/logout"),
        ("GET", "/api/auth/me"),
        ("GET", "/api/courses"),
    ]
    for method, path in removed_routes:
        response = client.request(method, path)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "http_error"


def test_ambiguous_policy_match_falls_back(client, tmp_path):
    knowledge_path = tmp_path / "ambiguous.json"
    knowledge_path.write_text(
        json.dumps(
            [
                {"title": "A", "keywords": ["schedule"], "answer": "Answer A"},
                {"title": "B", "keywords": ["schedule"], "answer": "Answer B"},
            ]
        ),
        encoding="utf-8",
    )
    app = create_app(knowledge_path)
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/assistant/ask", json={"question": "schedule"}
        )
    assert response.json()["status"] == "insufficient_evidence"


def test_attendance_api_returns_database_counts_and_percentages(client):
    response = client.post("/api/attendance", json={"student_id": "demo1001"})

    assert response.status_code == 200
    assert response.json() == {
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


def test_attendance_api_rejects_invalid_and_unknown_student_ids(client):
    invalid = client.post("/api/attendance", json={"student_id": "NOT-A-STUDENT"})
    unknown = client.post("/api/attendance", json={"student_id": "DEMO9999"})

    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"
    assert unknown.status_code == 404
    assert unknown.json() == {
        "error": {"code": "http_error", "message": "Student ID not found."}
    }


def test_attendance_seed_is_idempotent(tmp_path):
    database_path = tmp_path / "seed.sqlite3"
    sample_data_path = PROJECT_ROOT / "data" / "attendance.json"
    initialize_database(database_path)

    seed_attendance_data(database_path, sample_data_path)
    seed_attendance_data(database_path, sample_data_path)

    records = attendance_rows(database_path, "DEMO1001")
    assert records is not None
    report = calculate_attendance("DEMO1001", records)
    assert [item["total_classes"] for item in report["subjects"]] == [4, 0, 4]


def test_attendance_seed_reconciles_changed_and_removed_fixture_data(tmp_path):
    database_path = tmp_path / "reconciled.sqlite3"
    sample_data_path = tmp_path / "attendance.json"
    original_data = json.loads(
        (PROJECT_ROOT / "data" / "attendance.json").read_text(encoding="utf-8")
    )
    sample_data_path.write_text(json.dumps(original_data), encoding="utf-8")

    initialize_database(database_path)
    seed_attendance_data(database_path, sample_data_path)

    changed_data = original_data
    changed_data["students"] = [changed_data["students"][0]]
    changed_data["students"][0]["subjects"][0]["classes"] = [False, False]
    sample_data_path.write_text(json.dumps(changed_data), encoding="utf-8")
    seed_attendance_data(database_path, sample_data_path)

    records = attendance_rows(database_path, "DEMO1001")
    assert records is not None
    report = calculate_attendance("DEMO1001", records)
    computing = next(row for row in report["subjects"] if row["subject_code"] == "CS101")
    assert computing["attended_classes"] == 0
    assert computing["total_classes"] == 2
    assert attendance_rows(database_path, "DEMO1002") is None


def test_nonfictional_fixture_is_rejected_without_changing_existing_database(tmp_path):
    database_path = tmp_path / "fictional-only.sqlite3"
    sample_data_path = tmp_path / "attendance.json"
    original_data = json.loads(
        (PROJECT_ROOT / "data" / "attendance.json").read_text(encoding="utf-8")
    )
    sample_data_path.write_text(json.dumps(original_data), encoding="utf-8")

    initialize_database(database_path)
    seed_attendance_data(database_path, sample_data_path)
    sample_data_path.write_text(
        json.dumps(
            {
                "students": [
                    {
                        **original_data["students"][0],
                        "student_id": "STUDENT1",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="fictional DEMO"):
        seed_attendance_data(database_path, sample_data_path)

    assert attendance_rows(database_path, "DEMO1001") is not None
    assert attendance_rows(database_path, "STUDENT1") is None
