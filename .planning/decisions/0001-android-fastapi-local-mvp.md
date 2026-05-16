# Decision 0001: Android + FastAPI Local MVP

## Status

Accepted

## Context

The RAG chatbot pipeline is already implemented in Python with LangChain, FAISS, and OpenAI-backed LLM calls. The graduation outline requires a mobile app that lets users ask Vietnamese questions and receive grounded chatbot answers.

## Decision

Build the MVP as an Android Jetpack Compose client plus a local FastAPI backend. The backend wraps the existing Python `HospitalAssistant.answer()` pipeline and exposes `GET /health` and `POST /chat`. Android calls the local backend through `http://10.0.2.2:8000` on emulator, or the laptop LAN IP on a real phone.

## Consequences

- OpenAI API keys and Python dependencies stay on the backend.
- Android implementation remains focused on UI, state, and HTTP integration.
- The MVP can be demonstrated locally without cloud deployment.
- Future production deployment will need HTTPS, hosting, and authentication decisions.
