package com.example.aihospitalassistant.chat

interface ChatRepository {
    suspend fun ask(question: String, contextHint: String? = null): ChatResult
}
