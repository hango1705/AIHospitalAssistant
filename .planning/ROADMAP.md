# Roadmap

## MVP: Android + FastAPI Chatbot

### Phase 1: FastAPI Backend

- Add `GET /health`.
- Add `POST /chat`.
- Wrap the existing `HospitalAssistant.answer()` pipeline.
- Add backend request and response schemas.
- Add backend tests with a mocked assistant.

### Phase 2: Android Chat UI

- Replace the default Compose sample screen.
- Add chat message list.
- Add input bar and send action.
- Add loading state.
- Add error state and retry action.
- Add suggested questions.
- Add source rendering below assistant answers.

### Phase 3: Android API Integration

- Add Retrofit and OkHttp.
- Add `ChatApi`.
- Add `ChatRepository`.
- Add `ChatViewModel`.
- Connect Compose UI to backend state.
- Support optional `context_hint` for short follow-up questions.

### Phase 4: Verification

- Run backend tests.
- Run Android unit tests.
- Start local FastAPI backend on port `8000`.
- Test Android emulator with `http://10.0.2.2:8000`.
- Validate representative demo questions from the graduation outline.

## Future Work

- Login.
- Persistent chat history.
- Appointment booking.
- Cloud deployment.
- Admin knowledge-base management.

