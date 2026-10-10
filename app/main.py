"""FastAPI entry point for the AI College Assistant demo."""

import json
import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.assistant_service import AssistantService
from app.attendance import calculate_attendance
from app.database import (
    attendance_rows,
    connect,
    initialize_database,
    seed_attendance_data,
)
from app.knowledge import answer_question
from app.llm_service import (
    GroundedPolicyAnswerService,
    LLMNotConfiguredError,
    LLMProviderError,
)
from app.retrieval import retrieve_passages
from app.tools import (
    ToolAuthorizationError,
    ToolValidationError,
    get_attendance,
    get_courses,
    search_policy,
)

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "app" / "static"
DEFAULT_KNOWLEDGE_PATH = BASE_DIR / "data" / "policies.json"
DEFAULT_POLICY_DIR = BASE_DIR / "data" / "knowledge"
DEFAULT_ATTENDANCE_DATA_PATH = BASE_DIR / "data" / "attendance.json"
DEFAULT_DATABASE_PATH = BASE_DIR / "data" / "demo.sqlite3"
STUDENT_ID_PATTERN = re.compile(r"DEMO[0-9]{4}")


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question cannot be blank.")
        return value


class AttendanceRequest(BaseModel):
    student_id: str = Field(min_length=1, max_length=32)

    @field_validator("student_id")
    @classmethod
    def student_id_must_be_fictional_format(cls, value: str) -> str:
        normalized_id = value.strip().upper()
        if not STUDENT_ID_PATTERN.fullmatch(normalized_id):
            raise ValueError("Student ID must use the fictional DEMO#### format.")
        return normalized_id


class AttendanceToolRequest(BaseModel):
    student_id: str = Field(min_length=1, max_length=32)
    requester_id: str = Field(min_length=1, max_length=32)

    @field_validator("student_id")
    @classmethod
    def student_id_must_be_fictional_format(cls, value: str) -> str:
        normalized_id = value.strip().upper()
        if not STUDENT_ID_PATTERN.fullmatch(normalized_id):
            raise ValueError("Student ID must use the fictional DEMO#### format.")
        return normalized_id

    @field_validator("requester_id")
    @classmethod
    def requester_id_must_be_valid(cls, value: str) -> str:
        normalized_id = value.strip().upper()
        if not STUDENT_ID_PATTERN.fullmatch(normalized_id):
            raise ValueError("Requester ID must use the fictional DEMO#### format.")
        return normalized_id


class AssistantRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    requester_id: str | None = Field(default=None, min_length=1, max_length=32)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        normalized_message = value.strip()
        if not normalized_message:
            raise ValueError("Message cannot be blank.")
        return normalized_message

    @field_validator("requester_id")
    @classmethod
    def requester_id_must_be_valid_if_present(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized_id = value.strip().upper()
        if not STUDENT_ID_PATTERN.fullmatch(normalized_id):
            raise ValueError("Requester ID must use the fictional DEMO#### format.")
        return normalized_id


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def create_app(
    knowledge_path: Path = DEFAULT_KNOWLEDGE_PATH,
    database_path: Path = DEFAULT_DATABASE_PATH,
    attendance_data_path: Path = DEFAULT_ATTENDANCE_DATA_PATH,
    policy_dir: Path = DEFAULT_POLICY_DIR,
    policy_answer_service: GroundedPolicyAnswerService | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        initialize_database(application.state.database_path)
        seed_attendance_data(
            application.state.database_path, application.state.attendance_data_path
        )
        yield

    app = FastAPI(title="AI College Assistant Demo", lifespan=lifespan)
    app.state.knowledge_path = Path(knowledge_path)
    app.state.database_path = Path(database_path)
    app.state.attendance_data_path = Path(attendance_data_path)
    app.state.policy_dir = Path(policy_dir)
    app.state.policy_answer_service = (
        policy_answer_service or GroundedPolicyAnswerService(None)
    )
    app.state.assistant_service = AssistantService(
        app.state.database_path,
        app.state.policy_dir,
        app.state.policy_answer_service,
    )
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        _: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        message = str(exc.detail) if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "http_error", "message": message}},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _: Request, __: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            422, "validation_error", "Request data is missing or invalid."
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled application error", exc_info=exc)
        return _error_response(
            500, "internal_error", "The request could not be completed."
        )

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health")
    def health() -> dict:
        with app.state.knowledge_path.open(encoding="utf-8") as source_file:
            json.load(source_file)
        with connect(app.state.database_path, read_only=True) as connection:
            connection.execute("SELECT 1").fetchone()
        return {"status": "ok"}

    @app.post("/api/assistant/ask")
    def ask(payload: QuestionRequest, request: Request) -> dict:
        return answer_question(payload.question, request.app.state.knowledge_path)

    @app.post("/api/assistant/chat")
    def assistant_chat(payload: AssistantRequest, request: Request) -> dict:
        try:
            result = request.app.state.assistant_service.respond(
                payload.message,
                requester_id=payload.requester_id,
            )
            if result["status"] == "tool_failed":
                raise StarletteHTTPException(
                    status_code=503,
                    detail="The selected tool could not complete the request.",
                )
            return result
        except ToolValidationError as exc:
            raise StarletteHTTPException(status_code=422, detail=str(exc)) from exc
        except ToolAuthorizationError as exc:
            raise StarletteHTTPException(status_code=403, detail=str(exc)) from exc
        except LookupError as exc:
            raise StarletteHTTPException(status_code=404, detail=str(exc)) from exc
        except (LLMNotConfiguredError, LLMProviderError) as exc:
            raise StarletteHTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/knowledge/search")
    def search_knowledge(payload: QuestionRequest, request: Request) -> dict:
        passages = retrieve_passages(payload.question, request.app.state.policy_dir)
        return {
            "status": "found" if passages else "insufficient_information",
            "passages": passages,
        }

    @app.post("/api/policy/ask")
    def ask_policy(payload: QuestionRequest, request: Request) -> dict:
        passages = retrieve_passages(payload.question, request.app.state.policy_dir)
        try:
            return request.app.state.policy_answer_service.answer(
                payload.question, passages
            )
        except LLMNotConfiguredError as exc:
            raise StarletteHTTPException(status_code=503, detail=str(exc)) from exc
        except LLMProviderError as exc:
            raise StarletteHTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/attendance")
    def attendance(payload: AttendanceRequest, request: Request) -> dict:
        records = attendance_rows(
            request.app.state.database_path, payload.student_id
        )
        if records is None:
            raise StarletteHTTPException(status_code=404, detail="Student ID not found.")
        return calculate_attendance(payload.student_id, records)

    @app.post("/api/tools/get_attendance")
    def attendance_tool(payload: AttendanceToolRequest, request: Request) -> dict:
        try:
            return get_attendance(
                payload.student_id,
                request.app.state.database_path,
                requester_id=payload.requester_id,
            )
        except ToolValidationError as exc:
            raise StarletteHTTPException(status_code=422, detail=str(exc)) from exc
        except ToolAuthorizationError as exc:
            raise StarletteHTTPException(status_code=403, detail=str(exc)) from exc
        except LookupError as exc:
            raise StarletteHTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/tools/get_courses")
    def courses_tool(payload: AttendanceToolRequest, request: Request) -> dict:
        try:
            return get_courses(
                payload.student_id,
                request.app.state.database_path,
                requester_id=payload.requester_id,
            )
        except ToolValidationError as exc:
            raise StarletteHTTPException(status_code=422, detail=str(exc)) from exc
        except ToolAuthorizationError as exc:
            raise StarletteHTTPException(status_code=403, detail=str(exc)) from exc
        except LookupError as exc:
            raise StarletteHTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/tools/search_policy")
    def policy_search_tool(payload: QuestionRequest, request: Request) -> dict:
        try:
            return search_policy(payload.question, request.app.state.policy_dir)
        except ToolValidationError as exc:
            raise StarletteHTTPException(status_code=422, detail=str(exc)) from exc

    return app


def _create_configured_policy_service() -> GroundedPolicyAnswerService:
    if not os.environ.get("OPENAI_API_KEY"):
        return GroundedPolicyAnswerService(None)

    from app.providers.openai_chat import OpenAIChatModel

    return GroundedPolicyAnswerService(OpenAIChatModel())


app = create_app(
    Path(os.environ.get("KNOWLEDGE_PATH", DEFAULT_KNOWLEDGE_PATH)),
    Path(os.environ.get("DATABASE_PATH", DEFAULT_DATABASE_PATH)),
    Path(os.environ.get("ATTENDANCE_DATA_PATH", DEFAULT_ATTENDANCE_DATA_PATH)),
    policy_answer_service=_create_configured_policy_service(),
)
