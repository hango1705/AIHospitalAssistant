from __future__ import annotations

from fastapi.testclient import TestClient

from hospital_assistant.api import create_app
from hospital_assistant.schemas import AnswerResult, RetrievedSource


class StubAssistant:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[tuple[str, str | None]] = []

    def answer(self, question: str, context_hint: str | None = None) -> AnswerResult:
        self.calls.append((question, context_hint))
        if self.should_fail:
            raise RuntimeError("assistant unavailable")
        return AnswerResult(
            question=question,
            answer="Bệnh viện A Thái Nguyên nằm trên đường Quang Trung [Nguon 1].",
            sources=[
                RetrievedSource(
                    source_id="Nguon 1",
                    title="Liên hệ",
                    locator="https://benhvienathainguyen.com.vn/contact",
                    source_url="https://benhvienathainguyen.com.vn/contact",
                    origin_path=None,
                    record_type="web_document",
                    chunk_id="contact-1",
                )
            ],
        )


def test_health_returns_ok() -> None:
    client = TestClient(create_app(assistant_factory=StubAssistant))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_returns_answer_and_sources() -> None:
    assistant = StubAssistant()
    client = TestClient(create_app(assistant_factory=lambda: assistant))

    response = client.post(
        "/chat",
        json={
            "question": "Bệnh viện A Thái Nguyên ở đâu?",
            "context_hint": "Thông tin chung về Bệnh viện A Thái Nguyên",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["question"] == "Bệnh viện A Thái Nguyên ở đâu?"
    assert body["answer"] == "Bệnh viện A Thái Nguyên nằm trên đường Quang Trung [Nguon 1]."
    assert body["sources"][0]["source_id"] == "Nguon 1"
    assert body["sources"][0]["title"] == "Liên hệ"
    assert assistant.calls == [
        (
            "Bệnh viện A Thái Nguyên ở đâu?",
            "Thông tin chung về Bệnh viện A Thái Nguyên",
        )
    ]


def test_chat_rejects_blank_question() -> None:
    client = TestClient(create_app(assistant_factory=StubAssistant))

    response = client.post("/chat", json={"question": "   ", "context_hint": None})

    assert response.status_code == 422
    assert "question" in response.text


def test_chat_maps_assistant_failure_to_service_unavailable() -> None:
    client = TestClient(create_app(assistant_factory=lambda: StubAssistant(should_fail=True)))

    response = client.post("/chat", json={"question": "Bệnh viện A ở đâu?"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Chatbot service is temporarily unavailable."}
