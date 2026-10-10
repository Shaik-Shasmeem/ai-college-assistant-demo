"""Deterministic request routing to narrowly scoped assistant capabilities."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from app.llm_service import GroundedPolicyAnswerService
from app.tools import (
    ToolAuthorizationError,
    ToolValidationError,
    get_attendance,
    get_courses,
    search_policy,
)

logger = logging.getLogger(__name__)
MAX_TOOL_CALLS = 3
STUDENT_ID_PATTERN = re.compile(r"\bDEMO\d{4}\b", re.IGNORECASE)
POLICY_TERMS = re.compile(
    r"\b(policy|rule|requirement|eligibility|exam|examination|leave|"
    r"absence|minimum attendance|attendance percentage)\b",
    re.IGNORECASE,
)
ATTENDANCE_TERMS = re.compile(
    r"\b(attendance|attended|absent|absence|classes attended)\b", re.IGNORECASE
)
COURSE_TERMS = re.compile(
    r"\b(courses?|subjects?|enrolled|registered|class list)\b", re.IGNORECASE
)

UNSUPPORTED_RESPONSE = (
    "I can help with attendance, registered courses, or questions about college "
    "policies. I cannot perform that request."
)
TOOL_FAILURE_RESPONSE = "I could not complete that request. Please try again later."


def classify_request(message: str) -> str:
    """Classify a request without delegating tool selection to a language model."""
    if POLICY_TERMS.search(message):
        return "policy_question"
    if ATTENDANCE_TERMS.search(message):
        return "attendance"
    if COURSE_TERMS.search(message):
        return "courses"
    return "unsupported"


class AssistantService:
    """Run a bounded, application-controlled tool loop for assistant requests."""

    def __init__(
        self,
        database_path: Path,
        policy_dir: Path,
        policy_answer_service: GroundedPolicyAnswerService,
    ) -> None:
        self._database_path = database_path
        self._policy_dir = policy_dir
        self._policy_answer_service = policy_answer_service

    def respond(self, message: str, *, requester_id: str | None = None) -> dict:
        path = classify_request(message)
        if path == "unsupported":
            return {
                "path": path,
                "status": "unsupported",
                "message": UNSUPPORTED_RESPONSE,
            }

        tool_name, tool_arguments = self._select_tool(
            path, message, requester_id=requester_id
        )
        if tool_name is None:
            return {
                "path": path,
                "status": "needs_student_id",
                "message": "Please include your fictional student ID in DEMO#### format.",
            }
        observations: list[dict] = []
        tool_calls = 0

        while tool_name is not None and tool_calls < MAX_TOOL_CALLS:
            tool_calls += 1
            logger.info(
                "Agent selected tool=%s call=%d/%d",
                tool_name,
                tool_calls,
                MAX_TOOL_CALLS,
            )
            try:
                observation = self._invoke_approved_tool(tool_name, tool_arguments)
            except ToolAuthorizationError:
                logger.warning(
                    "Agent tool outcome tool=%s outcome=unauthorized",
                    tool_name,
                )
                raise
            except LookupError:
                logger.warning(
                    "Agent tool outcome tool=%s outcome=not_found",
                    tool_name,
                )
                raise
            except ToolValidationError:
                logger.warning(
                    "Agent tool outcome tool=%s outcome=invalid_input",
                    tool_name,
                )
                raise
            except Exception as exc:
                logger.error(
                    "Agent tool outcome tool=%s outcome=failed error_type=%s",
                    tool_name,
                    type(exc).__name__,
                )
                return {
                    "path": path,
                    "status": "tool_failed",
                    "message": TOOL_FAILURE_RESPONSE,
                }

            observations.append(observation)
            logger.info("Agent tool outcome tool=%s outcome=success", tool_name)
            tool_name = None

        if not observations:
            return {
                "path": path,
                "status": "tool_limit_reached",
                "message": TOOL_FAILURE_RESPONSE,
            }

        result = observations[-1]
        if path == "policy_question":
            answer = self._policy_answer_service.answer(message, result["results"])
            return {"path": path, **answer}

        return {"path": path, "status": "answered", "result": result}

    @staticmethod
    def _select_tool(
        path: str,
        message: str,
        *,
        requester_id: str | None,
    ) -> tuple[str | None, dict]:
        if path == "policy_question":
            return "search_policy", {"question": message}

        match = STUDENT_ID_PATTERN.search(message)
        if match is None:
            return None, {}
        arguments = {
            "student_id": match.group(0),
            "requester_id": requester_id,
        }
        if path == "attendance":
            return "get_attendance", arguments
        if path == "courses":
            return "get_courses", arguments
        return None, {}

    def _invoke_approved_tool(self, tool_name: str, arguments: dict) -> dict:
        if tool_name == "get_attendance":
            return get_attendance(
                arguments["student_id"],
                self._database_path,
                requester_id=arguments["requester_id"],
            )
        if tool_name == "get_courses":
            return get_courses(
                arguments["student_id"],
                self._database_path,
                requester_id=arguments["requester_id"],
            )
        if tool_name == "search_policy":
            return search_policy(arguments["question"], self._policy_dir)
        raise ToolValidationError("The selected tool is not approved.")
