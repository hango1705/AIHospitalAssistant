from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .assistant import HospitalAssistant
from .schemas import AnswerResult


class AssistantLike(Protocol):
    def answer(self, question: str, context_hint: str | None = None) -> AnswerResult:
        ...


class HealthResponse(BaseModel):
    status: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    context_hint: str | None = None

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


def create_app(
    assistant_factory: Callable[[], AssistantLike] = HospitalAssistant,
) -> FastAPI:
    app = FastAPI(
        title="AI Hospital Assistant API",
        version="0.1.0",
        description="Local FastAPI wrapper for the hospital RAG chatbot pipeline.",
    )
    app.state.assistant_factory = assistant_factory
    app.state.assistant = None

    def get_assistant() -> AssistantLike:
        if app.state.assistant is None:
            app.state.assistant = app.state.assistant_factory()
        return app.state.assistant

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.post(
        "/chat",
        response_model=AnswerResult,
        responses={503: {"model": ErrorResponse}},
    )
    def chat(request: ChatRequest) -> AnswerResult:
        try:
            return get_assistant().answer(
                request.question,
                context_hint=request.context_hint,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="Chatbot service is temporarily unavailable.",
            ) from exc

    return app


app = create_app()
