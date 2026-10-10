"""Provider-neutral grounded-answer service for retrieved policy passages."""

from typing import Protocol


INSUFFICIENT_CONTEXT_ANSWER = (
    "The available college documents do not provide enough information."
)


class TextGenerationModel(Protocol):
    def generate(self, question: str, context: list[dict[str, str]]) -> str: ...


class LLMNotConfiguredError(RuntimeError):
    """Raised when a grounded answer is requested without a configured model."""


class LLMProviderError(RuntimeError):
    """Raised when the configured provider cannot return an answer."""


class GroundedPolicyAnswerService:
    def __init__(self, model: TextGenerationModel | None) -> None:
        self._model = model

    def answer(self, question: str, context: list[dict[str, str]]) -> dict:
        sources = [
            {"source": passage["source"], "section": passage["section"]}
            for passage in context
        ]
        if not context:
            return {
                "status": "insufficient_information",
                "answer": INSUFFICIENT_CONTEXT_ANSWER,
                "sources": [],
            }
        if self._model is None:
            raise LLMNotConfiguredError(
                "Policy answering is unavailable because no model is configured."
            )

        answer = self._model.generate(question, context).strip()
        if not answer:
            raise RuntimeError("The configured model returned an empty answer.")
        return {
            "status": "answered",
            "answer": answer,
            "sources": sources,
        }
