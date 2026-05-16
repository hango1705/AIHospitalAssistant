# PRD: MVP Android + FastAPI cho chatbot hỗ trợ bệnh nhân

## Problem Statement

Sinh viên đã hoàn thiện pipeline RAG chatbot cho đề tài "Ứng dụng mô hình ngôn ngữ lớn (LLM) trong xây dựng hệ thống chatbot hỗ trợ bệnh nhân tại bệnh viện", nhưng sản phẩm theo đề cương cần một ứng dụng mobile để người dùng cuối có thể tương tác tự nhiên bằng tiếng Việt.

Người dùng mục tiêu là bệnh nhân hoặc người nhà bệnh nhân cần tra cứu nhanh thông tin trước khi đến bệnh viện, gồm thông tin chung về bệnh viện, quy trình khám chữa bệnh, giá dịch vụ cơ bản, thủ tục khám và thông tin khoa phòng. MVP cần chứng minh được luồng hoàn chỉnh: mobile app gửi câu hỏi, backend gọi pipeline RAG/LLM hiện có, app hiển thị câu trả lời và nguồn tham khảo.

## Solution

Xây dựng MVP gồm Android app dùng Jetpack Compose và backend FastAPI chạy local. Android app cung cấp giao diện chat tiếng Việt, gửi câu hỏi đến FastAPI, hiển thị trạng thái đang trả lời, lỗi kết nối, câu trả lời và nguồn tham khảo. FastAPI bọc `HospitalAssistant.answer()` từ pipeline Python hiện có và trả về JSON theo schema tương thích với `AnswerResult`.

MVP chạy local để phục vụ demo đồ án: backend chạy trên laptop qua Uvicorn, Android emulator gọi `http://10.0.2.2:8000`, còn điện thoại thật có thể gọi IP LAN của laptop.

## User Stories

1. As a patient, I want to type a Vietnamese question, so that I can ask about hospital information naturally.
2. As a patient, I want to send my question from the mobile app, so that I can receive an answer from the RAG chatbot.
3. As a patient, I want to see the chatbot answer in a chat conversation, so that the interaction feels familiar.
4. As a patient, I want to know when the chatbot is generating an answer, so that I understand the app is processing my request.
5. As a patient, I want to see a clear error when the backend is unavailable, so that I know the problem is a connection issue.
6. As a patient, I want to retry a failed question, so that I do not need to type the same question again.
7. As a patient, I want suggested questions about common hospital topics, so that I can quickly test and use the app.
8. As a patient, I want to ask about the hospital address, so that I know where to go before visiting.
9. As a patient, I want to ask about the hospital phone number or contact information, so that I can contact the hospital if needed.
10. As a patient, I want to ask about examination procedures, so that I can prepare before visiting the hospital.
11. As a patient, I want to ask about basic medical service prices, so that I can estimate costs.
12. As a patient, I want to ask about departments, so that I can find the right unit for my needs.
13. As a patient, I want answers in clear Vietnamese, so that the information is easy to understand.
14. As a patient, I want the answer to include source references, so that I can trust where the information came from.
15. As a patient, I want source titles and locators to be readable, so that I can inspect the retrieved evidence.
16. As a patient, I want follow-up questions like "gia bao nhieu?" or "so dien thoai?" to work after a topic question, so that the chat feels conversational.
17. As a demo evaluator, I want a health endpoint, so that I can quickly check whether the backend is running.
18. As a demo evaluator, I want the Android app to call a local backend reliably, so that the product can be demonstrated without cloud deployment.
19. As a developer, I want a simple API contract, so that Android integration is straightforward.
20. As a developer, I want backend request and response schemas, so that client and server behavior stays stable.
21. As a developer, I want backend errors to map to understandable Android UI states, so that users are not shown raw stack traces.
22. As a developer, I want Android state to be handled in a ViewModel, so that UI rendering remains predictable.
23. As a developer, I want API access isolated behind a repository, so that network code is not mixed into Compose UI.
24. As a developer, I want retry behavior tested, so that transient failures do not break the main chat flow.
25. As a developer, I want backend tests with a mocked assistant, so that API behavior can be verified without calling the LLM.

## Implementation Decisions

- Build a FastAPI backend module that wraps the existing `HospitalAssistant.answer()` pipeline.
- Keep RAG, FAISS, LangChain, and OpenAI API key usage on the backend. Android must not embed the Python pipeline or store OpenAI secrets.
- Expose `GET /health` for runtime checks.
- Expose `POST /chat` for chatbot answers.
- Use this request shape for `POST /chat`:

```json
{
  "question": "Gia kham benh tai Benh vien A la bao nhieu?",
  "context_hint": null
}
```

- Use the existing answer shape from `AnswerResult`:

```json
{
  "question": "...",
  "answer": "...",
  "sources": [
    {
      "source_id": "Nguon 1",
      "title": "...",
      "locator": "...",
      "source_url": "...",
      "origin_path": null,
      "record_type": "...",
      "chunk_id": "..."
    }
  ]
}
```

- Treat `context_hint` as optional. Android keeps the latest explicit topic question and sends it only for short follow-up questions.
- Run backend locally with Uvicorn on port `8000`.
- Use `http://10.0.2.2:8000` as the Android emulator default base URL.
- Allow replacing the base URL for a real Android phone on the same LAN.
- Enable cleartext HTTP only for the debug/local MVP path.
- Build the Android UI with Jetpack Compose in the existing Android project.
- Use `ViewModel` and `StateFlow` for chat screen state.
- Use Retrofit and OkHttp for network calls.
- Add a `ChatApi` module for `GET /health` and `POST /chat`.
- Add a `ChatRepository` module to wrap API calls and map transport errors.
- Add a `ChatViewModel` module to manage messages, loading, retry, and `context_hint`.
- Add Compose UI components for chat messages, input bar, source list, loading state, error state, retry action, and suggested questions.
- Keep the MVP stateless on the backend; no database is required.
- Do not implement login, cloud chat history, appointment booking, or push notifications in this MVP.

## Testing Decisions

- Backend tests should verify API behavior through FastAPI TestClient with a mocked assistant, not real OpenAI calls.
- Backend tests should cover:
  - `GET /health` returns status `ok`.
  - `POST /chat` validates non-empty questions.
  - `POST /chat` returns answer and sources in the expected shape.
  - Backend maps assistant failures to a controlled API error.
- Android unit tests should focus on `ChatViewModel` external behavior:
  - Sending a question adds a user message and assistant response.
  - Loading state is active while the request is running.
  - Network failure creates a visible error state.
  - Retry resends the failed question.
  - Topic context updates after explicit topic questions.
  - Short follow-up questions send the current `context_hint`.
- Android repository tests should verify error mapping from HTTP/network exceptions.
- MVP does not require UI automation unless time remains after core functionality is stable.

## Out of Scope

- User login and account management.
- Persistent cloud chat history.
- Appointment booking.
- Push notifications.
- Admin dashboard for managing knowledge base data.
- Cloud deployment, domain setup, HTTPS, and production authentication.
- Full medical diagnosis or treatment recommendation beyond the existing hospital information knowledge base.
- Rebuilding or replacing the completed RAG pipeline.

## Further Notes

- The MVP directly satisfies the product requirement in the graduation outline: a mobile chatbot that accepts Vietnamese questions and returns RAG-grounded answers about hospital information.
- The local demo architecture is intentionally simple because the project goal is to show the complete AI application flow, not production infrastructure.
- Future iterations can add login, persisted chat sessions, appointment booking, and deployment after the MVP is complete and verified.
