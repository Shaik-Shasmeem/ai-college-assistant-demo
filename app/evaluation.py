"""Deterministic local evaluation runner for the AI College Assistant."""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.llm_service import GroundedPolicyAnswerService, INSUFFICIENT_CONTEXT_ANSWER
from app.main import BASE_DIR, create_app

DEFAULT_DATASET_PATH = BASE_DIR / "data" / "evaluation" / "assistant_cases.json"
APPROVED_TOOLS = {"get_attendance", "get_courses", "search_policy"}
TOOL_SELECTION_PATTERN = re.compile(
    r"Agent selected tool=(\w+) call=\d+/\d+"
)
TOOL_OUTCOME_PATTERN = re.compile(r"Agent tool outcome tool=(\w+) outcome=([a-z_]+)")


class EvaluationModel:
    """Fake model that only emits a case's expected phrase if context contains it."""

    def __init__(self) -> None:
        self.expected_evidence = ""
        self.calls = 0
        self.estimated_input_tokens = 0
        self.estimated_output_tokens = 0
        self.last_context_contains_evidence = False

    def begin_case(self, expected_evidence: str = "") -> None:
        self.expected_evidence = expected_evidence
        self.calls = 0
        self.estimated_input_tokens = 0
        self.estimated_output_tokens = 0
        self.last_context_contains_evidence = False

    def generate(self, question: str, context: list[dict[str, str]]) -> str:
        self.calls += 1
        context_text = "\n".join(
            f"{item.get('source', '')} {item.get('section', '')} {item.get('text', '')}"
            for item in context
        )
        self.estimated_input_tokens += math.ceil(
            (len(question) + len(context_text)) / 4
        )
        self.last_context_contains_evidence = (
            bool(self.expected_evidence)
            and self.expected_evidence.casefold() in context_text.casefold()
        )
        if not self.last_context_contains_evidence:
            answer = "EVALUATION_GROUNDING_FAILURE"
        else:
            answer = f"The supplied policy passage states: {self.expected_evidence}."
        self.estimated_output_tokens += math.ceil(len(answer) / 4)
        return answer


class _AgentLogCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if message.startswith("Agent selected tool=") or message.startswith(
            "Agent tool outcome tool="
        ):
            self.messages.append(message)

    def reset(self) -> None:
        self.messages.clear()


def _load_dataset(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as dataset_file:
        dataset = json.load(dataset_file)
    if not isinstance(dataset, dict) or not isinstance(dataset.get("cases"), list):
        raise ValueError("Evaluation dataset must contain a cases list.")
    return dataset


def _tool_events(messages: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
    selected = []
    outcomes = []
    for message in messages:
        selected_match = TOOL_SELECTION_PATTERN.fullmatch(message)
        if selected_match:
            selected.append(selected_match.group(1))
        outcome_match = TOOL_OUTCOME_PATTERN.fullmatch(message)
        if outcome_match:
            outcomes.append((outcome_match.group(1), outcome_match.group(2)))
    return selected, outcomes


def _evaluate_case(
    client: TestClient,
    case: dict[str, Any],
    model: EvaluationModel,
    log_capture: _AgentLogCapture,
    budgets: dict[str, int],
) -> dict[str, Any]:
    log_capture.reset()
    model.begin_case(case.get("expected_evidence", ""))
    payload = {"message": case["message"]}
    if "requester_id" in case:
        payload["requester_id"] = case["requester_id"]
    payload.update(case.get("extra_payload", {}))

    started_at = time.perf_counter()
    response = client.post("/api/assistant/chat", json=payload)
    latency_ms = (time.perf_counter() - started_at) * 1000
    body = response.json()
    selected_tools, tool_outcomes = _tool_events(log_capture.messages)
    tool_calls = len(selected_tools)
    model_calls = model.calls

    expected_tool = case.get("expected_tool")
    actual_status = body.get("status")
    actual_path = body.get("path")
    answer = body.get("answer", "")
    serialized_body = json.dumps(body, ensure_ascii=False)

    correctness = (
        response.status_code == case["expected_http_status"]
        and actual_path == case.get("expected_path")
        and actual_status == case.get("expected_status")
    )
    if case.get("expected_evidence"):
        correctness = correctness and case["expected_evidence"].casefold() in answer.casefold()
    if case.get("expected_result_contains"):
        correctness = (
            correctness
            and case["expected_result_contains"] in serialized_body
        )

    policy_case = case.get("expected_path") == "policy_question"
    if policy_case and case.get("expect_refusal"):
        groundedness = (
            actual_status == "insufficient_information"
            and answer == INSUFFICIENT_CONTEXT_ANSWER
            and body.get("sources") == []
            and model_calls == 0
        )
    elif policy_case:
        expected_source = case.get("expected_source", "")
        sources = body.get("sources", [])
        groundedness = (
            bool(case.get("expected_evidence"))
            and model.last_context_contains_evidence
            and case["expected_evidence"].casefold() in answer.casefold()
            and any(expected_source in item.get("source", "") for item in sources)
        )
    else:
        groundedness = None

    if case.get("expect_refusal"):
        if expected_tool is None:
            refusal = actual_status == "unsupported" and tool_calls == 0 and model_calls == 0
        else:
            refusal = (
                actual_status == "insufficient_information"
                and answer == INSUFFICIENT_CONTEXT_ANSWER
                and model_calls == 0
            )
    else:
        refusal = None

    authorization = (
        response.status_code == case["expected_http_status"]
        if case["category"] == "authorization"
        else None
    )
    tool_selection = (
        selected_tools == [expected_tool]
        if expected_tool is not None
        else selected_tools == []
    )
    if case.get("expected_tool_outcome"):
        tool_selection = tool_selection and (
            (expected_tool, case["expected_tool_outcome"]) in tool_outcomes
        )
    tool_selection = tool_selection and all(
        tool in APPROVED_TOOLS for tool in selected_tools
    )

    latency = latency_ms <= budgets["max_latency_ms"]
    cost_awareness = (
        tool_calls <= budgets["max_tool_calls"]
        and model_calls <= budgets["max_model_calls_per_case"]
        and model.estimated_input_tokens
        <= budgets["max_estimated_input_tokens"]
    )

    checks: dict[str, bool | None] = {
        "correctness": correctness,
        "groundedness": groundedness,
        "refusal_when_evidence_missing": refusal,
        "authorization": authorization,
        "tool_selection": tool_selection,
        "latency": latency,
        "cost_awareness": cost_awareness,
    }
    failed = [name for name, result in checks.items() if result is False]
    return {
        "id": case["id"],
        "category": case["category"],
        "passed": not failed,
        "failed_checks": failed,
        "checks": {
            name: ("n/a" if result is None else "pass" if result else "fail")
            for name, result in checks.items()
        },
        "http_status": response.status_code,
        "path": actual_path,
        "status": actual_status,
        "selected_tools": selected_tools,
        "tool_outcomes": [
            {"tool": tool, "outcome": outcome} for tool, outcome in tool_outcomes
        ],
        "latency_ms": round(latency_ms, 2),
        "model_calls": model_calls,
        "estimated_input_tokens": model.estimated_input_tokens,
        "estimated_output_tokens": model.estimated_output_tokens,
    }


def run_evaluation(dataset_path: Path = DEFAULT_DATASET_PATH) -> dict[str, Any]:
    dataset = _load_dataset(Path(dataset_path))
    model = EvaluationModel()
    logger = logging.getLogger("app.assistant_service")
    log_capture = _AgentLogCapture()
    original_level = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(log_capture)
    try:
        with tempfile.TemporaryDirectory(prefix="college-assistant-eval-") as temp_dir:
            app = create_app(
                database_path=Path(temp_dir) / "attendance.sqlite3",
                policy_answer_service=GroundedPolicyAnswerService(model),
            )
            with TestClient(app) as client:
                results = [
                    _evaluate_case(
                        client,
                        case,
                        model,
                        log_capture,
                        dataset["budgets"],
                    )
                    for case in dataset["cases"]
                ]
    finally:
        logger.removeHandler(log_capture)
        logger.setLevel(original_level)

    check_totals: Counter[str] = Counter()
    category_totals: Counter[str] = Counter()
    for result in results:
        category_totals[result["category"]] += 1
        for criterion, outcome in result["checks"].items():
            if outcome != "n/a":
                check_totals[f"{criterion}:{outcome}"] += 1

    passed = sum(result["passed"] for result in results)
    return {
        "dataset": str(dataset_path),
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "categories": dict(sorted(category_totals.items())),
        "criteria": dict(sorted(check_totals.items())),
        "budgets": dataset["budgets"],
        "estimated_api_cost_usd": None,
        "cost_note": (
            "No live model calls are made. Token estimates use characters / 4; "
            "dollar cost is omitted because provider pricing varies."
        ),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to the evaluation dataset JSON.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full machine-readable evaluation report as JSON.",
    )
    arguments = parser.parse_args()
    report = run_evaluation(arguments.dataset)

    if arguments.json:
        print(json.dumps(report, indent=2))
    else:
        for result in report["results"]:
            outcome = "PASS" if result["passed"] else "FAIL"
            failures = (
                f" ({', '.join(result['failed_checks'])})"
                if result["failed_checks"]
                else ""
            )
            print(f"{outcome} {result['id']}{failures}")
        print(
            f"\nSummary: {report['passed']}/{report['total']} passed; "
            f"{report['failed']} failed."
        )
        print(f"Categories: {report['categories']}")
        print(f"Criteria: {report['criteria']}")
        print(report["cost_note"])
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
