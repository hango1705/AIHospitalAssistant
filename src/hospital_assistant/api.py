from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
import uuid
from typing import Protocol

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .assistant import HospitalAssistant
from .schemas import AnswerResult
from .server_store import AppStore


class AssistantLike(Protocol):
    def answer(self, question: str, context_hint: str | None = None) -> AnswerResult:
        ...


class HealthResponse(BaseModel):
    status: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    context_hint: str | None = None
    conversation_id: str | None = None

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be blank")
        return normalized

    @field_validator("context_hint")
    @classmethod
    def context_hint_blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ErrorResponse(BaseModel):
    detail: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


class RegisterRequest(BaseModel):
    email: str
    full_name: str
    password: str = Field(min_length=6)

    @field_validator("email")
    @classmethod
    def email_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized or "@" not in normalized:
            raise ValueError("email must be valid")
        return normalized

    @field_validator("full_name")
    @classmethod
    def full_name_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("full_name must not be blank")
        return normalized


class LoginRequest(BaseModel):
    email: str
    password: str


class ChatMessageResponse(BaseModel):
    id: int
    conversation_id: str
    role: str
    text: str
    sources: list[dict] = Field(default_factory=list)
    created_at: str


class ChatHistoryResponse(BaseModel):
    messages: list[ChatMessageResponse]


class AppointmentRequest(BaseModel):
    patient_name: str
    phone: str
    department: str
    appointment_date: str
    reason: str = ""

    @field_validator("patient_name", "phone", "department", "appointment_date")
    @classmethod
    def required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("field must not be blank")
        return normalized


class AppointmentResponse(BaseModel):
    id: int
    patient_name: str
    phone: str
    department: str
    appointment_date: str
    reason: str
    status: str
    created_at: str


class AppointmentListResponse(BaseModel):
    appointments: list[AppointmentResponse]


class KbUpdateRequest(BaseModel):
    note: str = "Admin requested knowledge base update"


class KbUpdateJobResponse(BaseModel):
    id: int
    admin_user_id: int
    note: str
    status: str
    created_at: str


class KbUpdateJobListResponse(BaseModel):
    jobs: list[KbUpdateJobResponse]


def create_app(
    assistant_factory: Callable[[], AssistantLike] = HospitalAssistant,
    store_factory: Callable[[], AppStore] | None = None,
) -> FastAPI:
    app = FastAPI(
        title="AI Hospital Assistant API",
        version="0.1.0",
        description="Local FastAPI wrapper for the hospital RAG chatbot pipeline.",
    )
    app.state.assistant_factory = assistant_factory
    app.state.assistant = None
    app.state.store_factory = store_factory or (lambda: AppStore(Path("data/app/app.sqlite3")))
    app.state.store = None

    def get_assistant() -> AssistantLike:
        if app.state.assistant is None:
            app.state.assistant = app.state.assistant_factory()
        return app.state.assistant

    def get_store() -> AppStore:
        if app.state.store is None:
            app.state.store = app.state.store_factory()
        return app.state.store

    def current_user(
        authorization: str | None = Header(default=None),
        store: AppStore = Depends(get_store),
    ) -> dict:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Authentication required.")
        token = authorization.split(" ", 1)[1].strip()
        user = store.get_user_by_token(token)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid authentication token.")
        return user

    def admin_user(user: dict = Depends(current_user)) -> dict:
        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin role required.")
        return user

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.post("/auth/register", response_model=AuthResponse)
    def register(request: RegisterRequest, store: AppStore = Depends(get_store)) -> AuthResponse:
        try:
            user = store.create_user(request.email, request.full_name, request.password)
        except Exception as exc:
            raise HTTPException(status_code=409, detail="Email already registered.") from exc
        auth = store.authenticate(request.email, request.password)
        if auth is None:
            raise HTTPException(status_code=503, detail="Could not create session.")
        token = str(auth.pop("token"))
        return AuthResponse(token=token, user=UserResponse(**auth))

    @app.post("/auth/login", response_model=AuthResponse)
    def login(request: LoginRequest, store: AppStore = Depends(get_store)) -> AuthResponse:
        auth = store.authenticate(request.email, request.password)
        if auth is None:
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        token = str(auth.pop("token"))
        return AuthResponse(token=token, user=UserResponse(**auth))

    @app.get("/me", response_model=UserResponse)
    def me(user: dict = Depends(current_user)) -> UserResponse:
        return UserResponse(**user)

    @app.post(
        "/chat",
        response_model=AnswerResult,
        responses={503: {"model": ErrorResponse}},
    )
    def chat(
        request: ChatRequest,
        authorization: str | None = Header(default=None),
        store: AppStore = Depends(get_store),
    ) -> AnswerResult:
        try:
            result = get_assistant().answer(
                request.question,
                context_hint=request.context_hint,
            )
            if authorization and authorization.lower().startswith("bearer "):
                user = store.get_user_by_token(authorization.split(" ", 1)[1].strip())
                if user is not None:
                    conversation_id = request.conversation_id or str(uuid.uuid4())
                    store.save_chat_message(int(user["id"]), conversation_id, "user", request.question)
                    store.save_chat_message(
                        int(user["id"]),
                        conversation_id,
                        "assistant",
                        result.answer,
                        sources_json=json.dumps([source.model_dump() for source in result.sources], ensure_ascii=False),
                    )
            return result
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="Chatbot service is temporarily unavailable.",
            ) from exc

    @app.get("/chat/history", response_model=ChatHistoryResponse)
    def chat_history(
        user: dict = Depends(current_user),
        store: AppStore = Depends(get_store),
    ) -> ChatHistoryResponse:
        messages = []
        for item in store.list_chat_history(int(user["id"])):
            messages.append(
                ChatMessageResponse(
                    id=int(item["id"]),
                    conversation_id=str(item["conversation_id"]),
                    role=str(item["role"]),
                    text=str(item["text"]),
                    sources=json.loads(str(item["sources_json"] or "[]")),
                    created_at=str(item["created_at"]),
                )
            )
        return ChatHistoryResponse(messages=messages)

    @app.delete("/chat/history", response_model=HealthResponse)
    def clear_chat_history(
        user: dict = Depends(current_user),
        store: AppStore = Depends(get_store),
    ) -> HealthResponse:
        store.clear_chat_history(int(user["id"]))
        return HealthResponse(status="ok")

    @app.post("/appointments", response_model=AppointmentResponse)
    def create_appointment(
        request: AppointmentRequest,
        user: dict = Depends(current_user),
        store: AppStore = Depends(get_store),
    ) -> AppointmentResponse:
        return AppointmentResponse(
            **store.create_appointment(
                int(user["id"]),
                request.patient_name,
                request.phone,
                request.department,
                request.appointment_date,
                request.reason,
            )
        )

    @app.get("/appointments", response_model=AppointmentListResponse)
    def list_appointments(
        user: dict = Depends(current_user),
        store: AppStore = Depends(get_store),
    ) -> AppointmentListResponse:
        return AppointmentListResponse(appointments=[AppointmentResponse(**item) for item in store.list_appointments(int(user["id"]))])

    @app.post("/admin/kb/update", response_model=KbUpdateJobResponse)
    def create_kb_update_job(
        request: KbUpdateRequest,
        user: dict = Depends(admin_user),
        store: AppStore = Depends(get_store),
    ) -> KbUpdateJobResponse:
        return KbUpdateJobResponse(**store.create_kb_update_job(int(user["id"]), request.note.strip()))

    @app.get("/admin/kb/jobs", response_model=KbUpdateJobListResponse)
    def list_kb_update_jobs(
        _: dict = Depends(admin_user),
        store: AppStore = Depends(get_store),
    ) -> KbUpdateJobListResponse:
        return KbUpdateJobListResponse(jobs=[KbUpdateJobResponse(**item) for item in store.list_kb_update_jobs()])

    return app


app = create_app()
