from __future__ import annotations

from datetime import datetime, timedelta

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


class StubKbJobRunner:
    def run(self, store: AppStore, job_id: int, reload_assistant) -> None:
        store.update_kb_update_job(job_id, status="success", append_log="stub job completed")
        reload_assistant()


def future_appointment_date() -> str:
    return (datetime.now() + timedelta(days=1)).replace(microsecond=0).isoformat(timespec="minutes")


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
    client = TestClient(create_app(assistant_factory=lambda: assistant, store_factory=lambda: store, kb_job_runner=StubKbJobRunner()))

    register = client.post(
        "/auth/register",
        json={"email": "patient@example.com", "full_name": "Patient User", "password": "secret123"},
    )
    assert register.status_code == 200
    token = register.json()["token"]
    assert register.json()["user"]["role"] == "patient"
    headers = {"Authorization": f"Bearer {token}"}

    chat = client.post("/chat", json={"question": "Bệnh viện A ở đâu?"}, headers=headers)
    assert chat.status_code == 200
    conversation_id = chat.json()["conversation_id"]
    assert conversation_id

    history = client.get("/chat/history", headers=headers)
    assert history.status_code == 200
    messages = history.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["text"] == "Bệnh viện A ở đâu?"

    conversations = client.get("/chat/conversations", headers=headers)
    assert conversations.status_code == 200
    assert conversations.json()["conversations"][0]["id"] == conversation_id

    conversation_messages = client.get(f"/chat/conversations/{conversation_id}/messages", headers=headers)
    assert conversation_messages.status_code == 200
    assert len(conversation_messages.json()["messages"]) == 2

    appointment = client.post(
        "/appointments",
        json={
            "patient_name": "Nguyễn Văn A",
            "phone": "0912345678",
            "department": "Khoa Nhi",
            "appointment_date": future_appointment_date(),
            "reason": "Khám tư vấn",
        },
        headers=headers,
    )
    assert appointment.status_code == 200
    assert appointment.json()["status"] == "pending"

    appointments = client.get("/appointments", headers=headers)
    assert appointments.status_code == 200
    assert appointments.json()["appointments"][0]["department"] == "Khoa Nhi"

    admin_login = client.post("/auth/login", json={"email": "admin", "password": "admin"})
    assert admin_login.status_code == 200
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['token']}"}

    kb_job = client.post("/admin/kb/update", json={"note": "Refresh KB"}, headers=admin_headers)
    assert kb_job.status_code == 200
    assert kb_job.json()["status"] == "queued"

    jobs = client.get("/admin/kb/jobs", headers=admin_headers)
    assert jobs.status_code == 200
    assert jobs.json()["jobs"][0]["note"] == "Refresh KB"
    assert jobs.json()["jobs"][0]["status"] == "success"
    assert "stub job completed" in jobs.json()["jobs"][0]["logs"]

    admin_appointments = client.get("/admin/appointments", headers=admin_headers)
    assert admin_appointments.status_code == 200
    assert admin_appointments.json()["appointments"][0]["phone"] == "0912345678"

    status_update = client.patch(
        f"/admin/appointments/{appointment.json()['id']}/status",
        json={"status": "confirmed"},
        headers=admin_headers,
    )
    assert status_update.status_code == 200
    assert status_update.json()["status"] == "confirmed"

    delete_conversation = client.delete(f"/chat/conversations/{conversation_id}", headers=headers)
    assert delete_conversation.status_code == 200
    assert client.get(f"/chat/conversations/{conversation_id}/messages", headers=headers).status_code == 404


def test_default_admin_exists_and_registered_users_are_patients(tmp_path) -> None:
    store = AppStore(tmp_path / "app.sqlite3")
    client = TestClient(create_app(assistant_factory=StubAssistant, store_factory=lambda: store))

    admin_login = client.post("/auth/login", json={"email": "admin", "password": "admin"})

    assert admin_login.status_code == 200
    assert admin_login.json()["user"]["email"] == "admin"
    assert admin_login.json()["user"]["role"] == "admin"

    register = client.post(
        "/auth/register",
        json={"email": "patient@example.com", "full_name": "Patient User", "password": "secret123"},
    )

    assert register.status_code == 200
    assert register.json()["user"]["role"] == "patient"


def test_logout_revokes_token_server_side(tmp_path) -> None:
    store = AppStore(tmp_path / "app.sqlite3")
    client = TestClient(create_app(assistant_factory=StubAssistant, store_factory=lambda: store))
    login = client.post("/auth/login", json={"email": "admin", "password": "admin"})
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    assert client.get("/me", headers=headers).status_code == 200

    logout = client.post("/auth/logout", headers=headers)

    assert logout.status_code == 200
    assert logout.json() == {"status": "ok"}
    assert client.get("/me", headers=headers).status_code == 401


def test_expired_token_is_rejected_and_removed(tmp_path) -> None:
    store = AppStore(tmp_path / "app.sqlite3", token_ttl_minutes=-1)
    client = TestClient(create_app(assistant_factory=StubAssistant, store_factory=lambda: store))
    login = client.post("/auth/login", json={"email": "admin", "password": "admin"})
    token = login.json()["token"]

    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    with store._connect() as connection:
        token_row = connection.execute("SELECT token FROM tokens WHERE token = ?", (token,)).fetchone()
    assert token_row is None


def test_register_rejects_weak_passwords(tmp_path) -> None:
    store = AppStore(tmp_path / "app.sqlite3")
    client = TestClient(create_app(assistant_factory=StubAssistant, store_factory=lambda: store))

    too_short = client.post(
        "/auth/register",
        json={"email": "short@example.com", "full_name": "Short Password", "password": "abc12"},
    )
    no_number = client.post(
        "/auth/register",
        json={"email": "nonumber@example.com", "full_name": "No Number", "password": "abcdefgh"},
    )

    assert too_short.status_code == 422
    assert no_number.status_code == 422


def test_appointment_rejects_invalid_phone_and_past_date(tmp_path) -> None:
    store = AppStore(tmp_path / "app.sqlite3")
    client = TestClient(create_app(assistant_factory=StubAssistant, store_factory=lambda: store))
    login = client.post("/auth/login", json={"email": "admin", "password": "admin"})
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    invalid_phone = client.post(
        "/appointments",
        json={
            "patient_name": "Nguyễn Văn A",
            "phone": "abc",
            "department": "Khoa Nhi",
            "appointment_date": future_appointment_date(),
            "reason": "Khám",
        },
        headers=headers,
    )
    past_date = client.post(
        "/appointments",
        json={
            "patient_name": "Nguyễn Văn A",
            "phone": "0912345678",
            "department": "Khoa Nhi",
            "appointment_date": "2020-01-01T08:00",
            "reason": "Khám",
        },
        headers=headers,
    )

    assert invalid_phone.status_code == 422
    assert past_date.status_code == 422


def test_non_admin_cannot_manage_all_appointments(tmp_path) -> None:
    store = AppStore(tmp_path / "app.sqlite3")
    client = TestClient(create_app(assistant_factory=StubAssistant, store_factory=lambda: store))
    register = client.post(
        "/auth/register",
        json={"email": "patient@example.com", "full_name": "Patient User", "password": "secret123"},
    )
    headers = {"Authorization": f"Bearer {register.json()['token']}"}

    assert client.get("/admin/appointments", headers=headers).status_code == 403
