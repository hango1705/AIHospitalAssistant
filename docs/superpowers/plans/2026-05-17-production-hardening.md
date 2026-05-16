# Production Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the MVP toward a production-ready local deployment with hardened auth, complete appointment management, conversation-based history, executable knowledge-base jobs, and environment-driven configuration.

**Architecture:** Keep FastAPI as the backend boundary and SQLite as the local persistence layer for this project version. Implement changes in small vertical slices that each update backend contracts, Android repository/viewmodel/UI, and tests before commit.

**Tech Stack:** FastAPI, Pydantic v2, SQLite, pytest, Android Kotlin, Retrofit, Jetpack Compose, Gradle unit tests.

---

### Task 1: Auth Session Hardening

**Files:**
- Modify: `src/hospital_assistant/server_store.py`
- Modify: `src/hospital_assistant/api.py`
- Modify: `src/hospital_assistant/settings.py`
- Modify: `AIHospitalAssistant/app/src/main/java/com/example/aihospitalassistant/chat/ChatApi.kt`
- Modify: `AIHospitalAssistant/app/src/main/java/com/example/aihospitalassistant/chat/ChatRepository.kt`
- Modify: `AIHospitalAssistant/app/src/main/java/com/example/aihospitalassistant/chat/DefaultChatRepository.kt`
- Modify: `AIHospitalAssistant/app/src/main/java/com/example/aihospitalassistant/chat/ChatViewModel.kt`
- Modify: `AIHospitalAssistant/app/src/main/java/com/example/aihospitalassistant/chat/ChatScreen.kt`
- Test: `tests/test_api.py`
- Test: `AIHospitalAssistant/app/src/test/java/com/example/aihospitalassistant/chat/ChatViewModelTest.kt`

- [x] Add `expires_at` to the `tokens` table and reject expired tokens in `get_user_by_token`.
- [x] Add `POST /auth/logout` and delete the bearer token server-side.
- [x] Enforce registration passwords with at least 8 characters, one letter, and one number.
- [x] Keep local default admin configurable while preserving `admin/admin` for the requested local account.
- [x] Update Android logout to call backend logout and clear local token.
- [x] Run backend and Android tests.
- [ ] Commit Task 1.

### Task 2: Appointment Management

**Files:**
- Modify: `src/hospital_assistant/server_store.py`
- Modify: `src/hospital_assistant/api.py`
- Modify: `AIHospitalAssistant/app/src/main/java/com/example/aihospitalassistant/chat/ChatApi.kt`
- Modify: `AIHospitalAssistant/app/src/main/java/com/example/aihospitalassistant/chat/ChatModels.kt`
- Modify: `AIHospitalAssistant/app/src/main/java/com/example/aihospitalassistant/chat/DefaultChatRepository.kt`
- Modify: `AIHospitalAssistant/app/src/main/java/com/example/aihospitalassistant/chat/ChatViewModel.kt`
- Modify: `AIHospitalAssistant/app/src/main/java/com/example/aihospitalassistant/chat/ChatScreen.kt`
- Test: `tests/test_api.py`
- Test: `AIHospitalAssistant/app/src/test/java/com/example/aihospitalassistant/chat/ChatViewModelTest.kt`

- [x] Validate phone numbers as 9-11 digits after removing spaces, dots, and dashes.
- [x] Validate appointment datetime as a future ISO-like local datetime.
- [x] Add admin endpoint to list all appointments.
- [x] Add admin endpoint to update status to `pending`, `confirmed`, or `cancelled`.
- [x] Add Android admin appointment list and status actions in the existing admin dashboard.
- [x] Run backend and Android tests.
- [ ] Commit Task 2.

### Task 3: Conversation-Based Chat History

**Files:**
- Modify: `src/hospital_assistant/server_store.py`
- Modify: `src/hospital_assistant/api.py`
- Modify: `AIHospitalAssistant/app/src/main/java/com/example/aihospitalassistant/chat/ChatApi.kt`
- Modify: `AIHospitalAssistant/app/src/main/java/com/example/aihospitalassistant/chat/ChatModels.kt`
- Modify: `AIHospitalAssistant/app/src/main/java/com/example/aihospitalassistant/chat/DefaultChatRepository.kt`
- Modify: `AIHospitalAssistant/app/src/main/java/com/example/aihospitalassistant/chat/ChatViewModel.kt`
- Modify: `AIHospitalAssistant/app/src/main/java/com/example/aihospitalassistant/chat/ChatScreen.kt`
- Test: `tests/test_api.py`
- Test: `AIHospitalAssistant/app/src/test/java/com/example/aihospitalassistant/chat/ChatViewModelTest.kt`

- [x] Add a `conversations` table with owner, title, and timestamps.
- [x] Ensure `/chat` attaches each turn to one conversation and returns `conversation_id`.
- [x] Add endpoints to list, read, and delete individual conversations.
- [x] Update Android to select conversations and avoid mixing all messages into one list.
- [x] Run backend and Android tests.
- [ ] Commit Task 3.

### Task 4: Knowledge Base Job Execution

**Files:**
- Modify: `src/hospital_assistant/server_store.py`
- Modify: `src/hospital_assistant/api.py`
- Create: `src/hospital_assistant/kb_jobs.py`
- Modify: `AIHospitalAssistant/app/src/main/java/com/example/aihospitalassistant/chat/ChatModels.kt`
- Modify: `AIHospitalAssistant/app/src/main/java/com/example/aihospitalassistant/chat/ChatScreen.kt`
- Test: `tests/test_api.py`

- [x] Add KB job status transitions `queued -> running -> success/failed`.
- [x] Store job logs and timestamps for started/completed states.
- [x] Start the queued job in a FastAPI background task.
- [x] Reload the in-process assistant after successful KB rebuild.
- [x] Show job logs and status in Android admin dashboard.
- [x] Run backend and Android tests.
- [ ] Commit Task 4.

### Task 5: Production Configuration Documentation

**Files:**
- Create: `.env.example`
- Modify: `README_HOSPITAL_ASSISTANT.md`

- [x] Add `.env.example` with database, auth, admin, and OpenAI settings.
- [x] Document first-run setup, default admin rotation, local database backup, and Android base URL.
- [x] Run final full verification.
- [ ] Commit Task 5.
