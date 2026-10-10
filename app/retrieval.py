"""Transparent keyword-based retrieval over local Markdown policy documents."""

import re
from dataclasses import dataclass
from pathlib import Path

STOP_WORDS = {
    "a", "about", "after", "an", "and", "are", "at", "be", "before", "can",
    "do", "does", "for", "from", "how", "i", "in", "is", "it", "me", "my",
    "of", "on", "or", "should", "the", "to", "what", "when", "where", "which",
    "who", "with", "would",
}
SYNONYM_GROUPS = (
    {"absent", "absence", "leave", "miss", "missed", "skip", "timeoff"},
    {"attendance", "attend", "present"},
    {"class", "classes", "lesson", "lessons", "session", "sessions"},
    {"exam", "examination", "test"},
    {"ill", "illness", "sick"},
    {"medical", "doctor", "physician"},
    {"notify", "inform", "contact"},
    {"percentage", "percent", "pct", "rate"},
    {"record", "records", "mark", "marks"},
    {"request", "apply", "application"},
)
MAX_RESULTS = 3


def _canonical_terms(text: str) -> set[str]:
    terms = {
        term
        for term in re.findall(r"[a-z0-9]+", text.lower())
        if term not in STOP_WORDS
    }
    for group in SYNONYM_GROUPS:
        if terms & group:
            terms.difference_update(group)
            terms.add(sorted(group)[0])
    return terms


@dataclass(frozen=True)
class Passage:
    source: str
    section: str
    text: str


def _read_passages(knowledge_dir: Path) -> list[Passage]:
    passages = []
    for path in sorted(knowledge_dir.glob("*.md")):
        section = path.stem.replace("_", " ").title()
        text_parts: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                if text_parts:
                    passages.append(
                        Passage(path.name, section, "\n".join(text_parts))
                    )
                    text_parts.clear()
                section = stripped.lstrip("#").strip() or section
            elif stripped:
                text_parts.append(stripped)
            elif text_parts:
                passages.append(Passage(path.name, section, "\n".join(text_parts)))
                text_parts.clear()
        if text_parts:
            passages.append(Passage(path.name, section, "\n".join(text_parts)))
    return passages


def retrieve_passages(question: str, knowledge_dir: Path) -> list[dict[str, str]]:
    """Return up to three highest-overlap source passages; source text is never executed."""
    query_terms = _canonical_terms(question)
    if not query_terms:
        return []

    ranked: list[tuple[int, Passage]] = []
    for passage in _read_passages(knowledge_dir):
        searchable_text = f"{passage.section} {passage.text}"
        matched_terms = query_terms & _canonical_terms(searchable_text)
        if matched_terms:
            ranked.append((len(matched_terms), passage))

    ranked.sort(key=lambda result: (-result[0], result[1].source, result[1].section))
    return [
        {
            "source": passage.source,
            "section": passage.section,
            "text": passage.text,
            "content_type": "untrusted_source_text",
        }
        for _, passage in ranked[:MAX_RESULTS]
    ]
