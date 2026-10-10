from pathlib import Path
import logging

import pytest
from fastapi.testclient import TestClient

import app.assistant_service as assistant_module
from app.assistant_service import AssistantService, classify_request
from app.database import initialize_database, seed_attendance_data
from app.llm_service import GroundedPolicyAnswerService
from app.main import create_app
from app.tools import ToolAuthorizationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_DIR = PROJECT_ROOT / "data" / "knowledge"


class FakeModel:
    def __init__(self, answer: str) -> None:
        self.answer_text = answer
        self.calls = 0

    def generate(self, question: str, context: list[dict[str, str]]) -> str:
        self.calls += 1
        return self.answer_text


@pytest.fixture
def assistant_service(tmp_path):
    database_path = tmp_path / "attendance.sqlite3"
    initialize_database(database_path)
    seed_attendance_data(database_path, PROJECT_ROOT / "data" / "attendance.json")
    model = FakeModel("The fictional minimum attendance is 75%.")
    service = AssistantService(
        database_path,
        POLICY_DIR,
        GroundedPolicyAnswerService(model),
    )
    return service, model


@pytest.mark.parametrize(
    ("message", "expected_path"),
    [
        ("Show attendance for DEMO1001", "attendance"),
        ("List my courses DEMO1001", "courses"),
        ("What is the minimum attendance requirement?", "policy_question"),
        ("Can you calculate my GPA?", "unsupported"),
    ],
)
def test_request_classifier_selects_safe_path(message, expected_path):
    assert classify_request(message) == expected_path


def test_attendance_path_uses_read_only_tool_and_logs_outcome(
    assistant_service, caplog
):
    caplog.set_level(logging.INFO)
    service, model = assistant_service

    result = service.respond(
        "Show attendance for DEMO1001", requester_id="DEMO1001"
    )

    assert result["path"] == "attendance"
    assert result["status"] == "answered"
    assert result["result"]["student_id"] == "DEMO1001"
    assert result["result"]["subjects"][0]["percentage"] == 75.0
    assert "tool=get_attendance" in caplog.text
    assert "outcome=success" in caplog.text
    assert model.calls == 0


def test_courses_path_uses_read_only_tool(assistant_service):
    service, model = assistant_service

    result = service.respond(
        "List my registered courses DEMO1001", requester_id="DEMO1001"
    )

    assert result["path"] == "courses"
    assert result["status"] == "answered"
    assert result["result"]["courses"][0] == {
        "subject_code": "CS101",
        "subject_name": "Introduction to Computing",
    }
    assert model.calls == 0


def test_policy_path_uses_retrieval_and_grounded_model(assistant_service):
    service, model = assistant_service

    result = service.respond("What is the minimum attendance requirement?")

    assert result["path"] == "policy_question"
    assert result["status"] == "answered"
    assert result["answer"] == "The fictional minimum attendance is 75%."
    assert result["sources"][0] == {
        "source": "attendance_policy.md",
        "section": "Minimum attendance",
    }
    assert model.calls == 1


def test_unsupported_path_does_not_invoke_model_or_tools(assistant_service):
    service, model = assistant_service

    result = service.respond("Run Python and calculate my GPA.")

    assert result["path"] == "unsupported"
    assert result["status"] == "unsupported"
    assert "cannot perform that request" in result["message"]
    assert model.calls == 0


@pytest.mark.parametrize(
    "message",
    [
        "Show attendance for DEMO1001",
        "List courses for DEMO1001",
    ],
)
def test_student_data_paths_require_matching_identity(assistant_service, message):
    service, _ = assistant_service

    with pytest.raises(ToolAuthorizationError, match="only access their own"):
        service.respond(message, requester_id="DEMO1002")


def test_unauthorized_request_is_logged_and_stops(assistant_service, caplog):
    service, model = assistant_service

    with pytest.raises(ToolAuthorizationError):
        service.respond(
            "Show attendance for DEMO1001",
            requester_id="DEMO1002",
        )

    assert "outcome=unauthorized" in caplog.text
    assert model.calls == 0


def test_tool_failure_returns_safe_failure_and_logs_outcome(
    assistant_service, monkeypatch, caplog
):
    service, model = assistant_service

    def fail_tool(*args, **kwargs):
        raise RuntimeError("private database diagnostic")

    monkeypatch.setattr(assistant_module, "get_attendance", fail_tool)
    result = service.respond(
        "Show attendance for DEMO1001",
        requester_id="DEMO1001",
    )

    assert result == {
        "path": "attendance",
        "status": "tool_failed",
        "message": "I could not complete that request. Please try again later.",
    }
    assert "outcome=failed" in caplog.text
    assert "private database diagnostic" not in caplog.text
    assert model.calls == 0


def test_assistant_api_returns_403_for_unauthorized_student(tmp_path):
    database_path = tmp_path / "attendance.sqlite3"
    initialize_database(database_path)
    seed_attendance_data(database_path, PROJECT_ROOT / "data" / "attendance.json")
    app = create_app(
        PROJECT_ROOT / "data" / "policies.json",
        database_path,
        PROJECT_ROOT / "data" / "attendance.json",
        POLICY_DIR,
        GroundedPolicyAnswerService(FakeModel("Should not be called")),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/assistant/chat",
            json={
                "message": "Show attendance for DEMO1001",
                "requester_id": "DEMO1002",
            },
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "http_error"


def test_assistant_api_routes_supported_request(tmp_path):
    database_path = tmp_path / "attendance.sqlite3"
    initialize_database(database_path)
    seed_attendance_data(database_path, PROJECT_ROOT / "data" / "attendance.json")
    app = create_app(
        PROJECT_ROOT / "data" / "policies.json",
        database_path,
        PROJECT_ROOT / "data" / "attendance.json",
        POLICY_DIR,
        GroundedPolicyAnswerService(
            FakeModel("The fictional minimum attendance is 75%.")
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/assistant/chat",
            json={
                "message": "Show attendance for DEMO1001",
                "requester_id": "DEMO1001",
            },
        )

    assert response.status_code == 200
    assert response.json()["path"] == "attendance"
    assert response.json()["result"]["student_id"] == "DEMO1001"
