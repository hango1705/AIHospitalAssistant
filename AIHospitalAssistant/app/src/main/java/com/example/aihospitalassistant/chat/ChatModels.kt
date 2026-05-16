package com.example.aihospitalassistant.chat

enum class ChatRole {
    User,
    Assistant,
}

data class ChatSource(
    val sourceId: String,
    val title: String,
    val locator: String,
    val sourceUrl: String? = null,
    val originPath: String? = null,
    val recordType: String = "",
    val chunkId: String = "",
)

data class ChatAnswer(
    val answer: String,
    val sources: List<ChatSource>,
)

sealed interface ChatResult {
    data class Success(val answer: ChatAnswer) : ChatResult
    data class Failure(val message: String) : ChatResult
}

data class ChatMessage(
    val id: Long,
    val role: ChatRole,
    val text: String,
    val sources: List<ChatSource> = emptyList(),
    val isError: Boolean = false,
)

data class ChatUiState(
    val messages: List<ChatMessage> = emptyList(),
    val isLoading: Boolean = false,
    val errorMessage: String? = null,
    val suggestions: List<String> = defaultSuggestions,
)

val defaultSuggestions = listOf(
    "Bệnh viện A Thái Nguyên ở đâu?",
    "Quy trình khám bệnh như thế nào?",
    "Giá khám bệnh tại Bệnh viện A là bao nhiêu?",
    "Khoa Nhi có số điện thoại nào?",
)
