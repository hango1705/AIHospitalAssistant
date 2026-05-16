from __future__ import annotations

from fastapi.testclient import TestClient

from hospital_assistant.api import create_app
from hospital_assistant.schemas import AnswerResult, RetrievedSource
from hospital_assistant.server_store import AppStore


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


def test_auth_chat_history_appointment_and_admin_kb_update(tmp_path) -> None:
    assistant = StubAssistant()
    store = AppStore(tmp_path / "app.sqlite3")
    client = TestClient(create_app(assistant_factory=lambda: assistant, store_factory=lambda: store))

    register = client.post(
        "/auth/register",
        json={"email": "admin@example.com", "full_name": "Admin User", "password": "secret123"},
    )
    assert register.status_code == 200
    token = register.json()["token"]
    assert register.json()["user"]["role"] == "admin"
    headers = {"Authorization": f"Bearer {token}"}

    chat = client.post("/chat", json={"question": "Bệnh viện A ở đâu?"}, headers=headers)
    assert chat.status_code == 200

    history = client.get("/chat/history", headers=headers)
    assert history.status_code == 200
    messages = history.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["text"] == "Bệnh viện A ở đâu?"

    appointment = client.post(
        "/appointments",
        json={
            "patient_name": "Nguyễn Văn A",
            "phone": "0912345678",
            "department": "Khoa Nhi",
            "appointment_date": "2026-05-20 08:00",
            "reason": "Khám tư vấn",
        },
        headers=headers,
    )
    assert appointment.status_code == 200
    assert appointment.json()["status"] == "pending"

    appointments = client.get("/appointments", headers=headers)
    assert appointments.status_code == 200
    assert appointments.json()["appointments"][0]["department"] == "Khoa Nhi"

    kb_job = client.post("/admin/kb/update", json={"note": "Refresh KB"}, headers=headers)
    assert kb_job.status_code == 200
    assert kb_job.json()["status"] == "queued"

    jobs = client.get("/admin/kb/jobs", headers=headers)
    assert jobs.status_code == 200
    assert jobs.json()["jobs"][0]["note"] == "Refresh KB"
