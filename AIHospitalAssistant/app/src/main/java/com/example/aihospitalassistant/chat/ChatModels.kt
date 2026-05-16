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
    val conversationId: String? = null,
)

data class UserSession(
    val token: String,
    val email: String,
    val fullName: String,
    val role: String,
)

data class KbUpdateJob(
    val id: Int,
    val note: String,
    val status: String,
    val createdAt: String,
    val logs: String = "",
    val startedAt: String? = null,
    val completedAt: String? = null,
)

data class Appointment(
    val id: Int,
    val userId: Int,
    val patientName: String,
    val phone: String,
    val department: String,
    val appointmentDate: String,
    val reason: String,
    val status: String,
    val createdAt: String,
)

data class ConversationSummary(
    val id: String,
    val title: String,
    val createdAt: String,
    val updatedAt: String,
)

sealed interface ChatResult {
    data class Success(val answer: ChatAnswer) : ChatResult
    data class Failure(val message: String) : ChatResult
}

sealed interface OperationResult {
    data object Success : OperationResult
    data class Failure(val message: String) : OperationResult
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
    val session: UserSession? = null,
    val isAuthLoading: Boolean = false,
    val authErrorMessage: String? = null,
    val operationMessage: String? = null,
    val isAdminMode: Boolean = false,
    val kbJobs: List<KbUpdateJob> = emptyList(),
    val appointments: List<Appointment> = emptyList(),
    val conversations: List<ConversationSummary> = emptyList(),
    val activeConversationId: String? = null,
    val suggestions: List<String> = defaultSuggestions,
)

val defaultSuggestions = listOf(
    "Bệnh viện A Thái Nguyên ở đâu?",
    "Quy trình khám bệnh như thế nào?",
    "Giá khám bệnh tại Bệnh viện A là bao nhiêu?",
    "Khoa Nhi có số điện thoại nào?",
)
