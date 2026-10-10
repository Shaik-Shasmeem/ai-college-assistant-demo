import json
from collections import Counter
import sqlite3

from app.database import connect
from app.evaluation import DEFAULT_DATASET_PATH, run_evaluation


def test_evaluation_dataset_contains_required_case_counts():
    dataset = json.loads(DEFAULT_DATASET_PATH.read_text(encoding="utf-8"))
    categories = Counter(case["category"] for case in dataset["cases"])

    assert categories["normal_policy"] >= 5
    assert categories["missing_evidence"] >= 3
    assert categories["attendance"] >= 3
    assert categories["authorization"] >= 3
    assert categories["prompt_injection"] >= 3
    assert categories["paraphrase"] >= 3


def test_local_evaluation_runner_passes_dataset():
    report = run_evaluation()

    assert report["total"] == 20
    assert report["passed"] == 20
    assert report["failed"] == 0
    assert report["estimated_api_cost_usd"] is None
    assert all(result["passed"] for result in report["results"])


def test_database_context_closes_connection_after_use(tmp_path):
    database_path = tmp_path / "connection.sqlite3"

    with connect(database_path) as connection:
        connection.execute("CREATE TABLE demo (value INTEGER)")

    try:
        connection.execute("SELECT 1")
    except sqlite3.ProgrammingError as exc:
        assert "closed" in str(exc).lower()
    else:
        raise AssertionError("Database context must close its connection.")
