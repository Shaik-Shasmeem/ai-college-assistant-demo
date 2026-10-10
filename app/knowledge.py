"""Small deterministic retrieval over explicitly fictional policy examples."""

import json
import re
from pathlib import Path

STOP_WORDS = {
    "a", "an", "and", "are", "can", "do", "does", "for", "how", "i", "is",
    "it", "me", "my", "of", "on", "the", "to", "what", "when", "where",
    "which", "who", "you",
}
INSUFFICIENT_ANSWER = "The source does not provide enough information."


def _terms(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z0-9]+", text.lower())
        if word not in STOP_WORDS
    }


def answer_question(question: str, knowledge_path: Path) -> dict:
    with knowledge_path.open(encoding="utf-8") as source_file:
        documents = json.load(source_file)

    question_terms = _terms(question)
    scored = []
    for document in documents:
        keywords = {term.lower() for term in document["keywords"]}
        score = len(question_terms & keywords)
        if score:
            scored.append((score, document))

    if not scored:
        return {"status": "insufficient_evidence", "answer": INSUFFICIENT_ANSWER, "sources": []}

    highest_score = max(score for score, _ in scored)
    best_documents = [doc for score, doc in scored if score == highest_score]
    if len(best_documents) != 1:
        return {"status": "insufficient_evidence", "answer": INSUFFICIENT_ANSWER, "sources": []}

    document = best_documents[0]
    return {
        "status": "answered",
        "answer": document["answer"],
        "sources": [
            {
                "title": document["title"],
                "notice": "Fictional demonstration content; not real college policy.",
            }
        ],
    }
