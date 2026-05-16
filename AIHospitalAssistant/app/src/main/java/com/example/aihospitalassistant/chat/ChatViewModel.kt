package com.example.aihospitalassistant.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.text.Normalizer

class ChatViewModel(
    private val repository: ChatRepository,
    private val historyStore: ChatHistoryStore = NoOpChatHistoryStore(),
) : ViewModel() {
    private val initialMessages = historyStore.loadMessages()
    private val _uiState = MutableStateFlow(
        ChatUiState(
            messages = initialMessages,
            session = repository.currentSession(),
        ),
    )
    val uiState: StateFlow<ChatUiState> = _uiState.asStateFlow()

    private var nextMessageId = (initialMessages.maxOfOrNull { it.id } ?: 0L) + 1L
    private var latestTopicQuestion: String? = topicAnchorFrom(initialMessages)
    private var lastFailedQuestion: PendingQuestion? = null

    init {
        if (repository.currentSession() != null) {
            loadConversations()
            loadServerHistory()
            loadAppointments()
        }
    }

    fun login(email: String, password: String) {
        authenticate { repository.login(email.trim(), password) }
    }

    fun register(email: String, fullName: String, password: String) {
        authenticate { repository.register(email.trim(), fullName.trim(), password) }
    }

    private fun authenticate(call: suspend () -> OperationResult) {
        if (_uiState.value.isAuthLoading) {
            return
        }
        _uiState.update { it.copy(isAuthLoading = true, authErrorMessage = null) }
        viewModelScope.launch {
            when (val result = call()) {
                OperationResult.Success -> {
                    val session = repository.currentSession()
                    _uiState.update {
                        it.copy(
                            session = session,
                            isAuthLoading = false,
                            authErrorMessage = null,
                            operationMessage = "Đăng nhập thành công.",
                        )
                    }
                    loadServerHistory()
                    loadConversations()
                    loadAppointments()
                    if (session?.role == "admin") {
                        loadKbUpdateJobs()
                    }
                }

                is OperationResult.Failure -> {
                    _uiState.update {
                        it.copy(
                            isAuthLoading = false,
                            authErrorMessage = result.message,
                        )
                    }
                }
            }
        }
    }

    fun logout() {
        viewModelScope.launch {
            repository.logout()
            historyStore.clear()
            latestTopicQuestion = null
            lastFailedQuestion = null
            _uiState.update {
                it.copy(
                    messages = emptyList(),
                    session = null,
                    errorMessage = null,
                    authErrorMessage = null,
                    operationMessage = null,
                isAdminMode = false,
                kbJobs = emptyList(),
                appointments = emptyList(),
                conversations = emptyList(),
                activeConversationId = null,
            )
        }
    }
    }

    fun showChat() {
        _uiState.update { it.copy(isAdminMode = false) }
    }

    fun showAdmin() {
        if (_uiState.value.session?.role != "admin") {
            return
        }
        _uiState.update { it.copy(isAdminMode = true) }
        loadKbUpdateJobs()
        loadAppointments()
    }

    private fun loadServerHistory() {
        viewModelScope.launch {
            repository.loadServerHistory()
                .onSuccess { messages ->
                    if (messages.isNotEmpty()) {
                        latestTopicQuestion = topicAnchorFrom(messages)
                        historyStore.saveMessages(messages)
                        _uiState.update { it.copy(messages = messages) }
                    }
                }
        }
    }

    fun loadConversations() {
        if (_uiState.value.session == null) {
            return
        }
        viewModelScope.launch {
            repository.loadConversations()
                .onSuccess { conversations ->
                    _uiState.update { it.copy(conversations = conversations) }
                }
        }
    }

    fun startNewConversation() {
        historyStore.clear()
        latestTopicQuestion = null
        lastFailedQuestion = null
        _uiState.update {
            it.copy(
                messages = emptyList(),
                activeConversationId = null,
                errorMessage = null,
                operationMessage = null,
            )
        }
    }

    fun selectConversation(conversationId: String) {
        viewModelScope.launch {
            repository.loadConversationMessages(conversationId)
                .onSuccess { messages ->
                    latestTopicQuestion = topicAnchorFrom(messages)
                    historyStore.saveMessages(messages)
                    _uiState.update {
                        it.copy(
                            messages = messages,
                            activeConversationId = conversationId,
                            errorMessage = null,
                        )
                    }
                }
                .onFailure { error ->
                    _uiState.update { it.copy(operationMessage = error.message ?: "Không tải được cuộc trò chuyện.") }
                }
        }
    }

    fun deleteConversation(conversationId: String) {
        viewModelScope.launch {
            val result = repository.deleteConversation(conversationId)
            if (result == OperationResult.Success && _uiState.value.activeConversationId == conversationId) {
                historyStore.clear()
                latestTopicQuestion = null
                _uiState.update { it.copy(messages = emptyList(), activeConversationId = null) }
            }
            _uiState.update {
                it.copy(
                    operationMessage = when (result) {
                        OperationResult.Success -> "Đã xóa cuộc trò chuyện."
                        is OperationResult.Failure -> result.message
                    },
                )
            }
            loadConversations()
        }
    }

    fun sendQuestion(rawQuestion: String) {
        val question = rawQuestion.trim()
        if (question.isEmpty() || _uiState.value.isLoading) {
            return
        }

        val contextHint = latestTopicQuestion.takeIf { isFollowUpQuestion(question) }
        ask(question, contextHint, addUserMessage = true)
    }

    fun retryLastQuestion() {
        val pending = lastFailedQuestion ?: return
        if (_uiState.value.isLoading) {
            return
        }
        ask(
            question = pending.question,
            contextHint = pending.contextHint,
            addUserMessage = false,
        )
    }

    private fun ask(question: String, contextHint: String?, addUserMessage: Boolean) {
        lastFailedQuestion = null
        _uiState.update { state ->
            val cleanedMessages = state.messages.filterNot { it.isError }
            val updatedMessages = if (addUserMessage) {
                cleanedMessages + ChatMessage(
                    id = nextMessageId++,
                    role = ChatRole.User,
                    text = question,
                )
            } else {
                cleanedMessages
            }
            persistMessages(updatedMessages)
            state.copy(
                messages = updatedMessages,
                isLoading = true,
                errorMessage = null,
            )
        }

        viewModelScope.launch {
            when (val result = repository.ask(question, contextHint, _uiState.value.activeConversationId)) {
                is ChatResult.Success -> {
                    if (!isFollowUpQuestion(question)) {
                        latestTopicQuestion = contextAnchorFor(question)
                    }
                    val conversationId = result.answer.conversationId ?: _uiState.value.activeConversationId
                    _uiState.update { state ->
                        val updatedMessages = state.messages + ChatMessage(
                            id = nextMessageId++,
                            role = ChatRole.Assistant,
                            text = result.answer.answer,
                            sources = result.answer.sources,
                        )
                        persistMessages(updatedMessages)
                        state.copy(
                            messages = updatedMessages,
                            activeConversationId = conversationId,
                            isLoading = false,
                            errorMessage = null,
                        )
                    }
                    loadConversations()
                }

                is ChatResult.Failure -> {
                    lastFailedQuestion = PendingQuestion(question, contextHint)
                    _uiState.update { state ->
                        val updatedMessages = state.messages + ChatMessage(
                            id = nextMessageId++,
                            role = ChatRole.Assistant,
                            text = result.message,
                            isError = true,
                        )
                        persistMessages(updatedMessages)
                        state.copy(
                            messages = updatedMessages,
                            isLoading = false,
                            errorMessage = result.message,
                        )
                    }
                }
            }
        }
    }

    fun clearHistory() {
        viewModelScope.launch {
            repository.clearServerHistory()
            historyStore.clear()
            latestTopicQuestion = null
            lastFailedQuestion = null
            _uiState.update {
                it.copy(
                    messages = emptyList(),
                    conversations = emptyList(),
                    activeConversationId = null,
                    isLoading = false,
                    errorMessage = null,
                    operationMessage = "Đã xóa lịch sử chat.",
                )
            }
        }
    }

    fun createAppointment(patientName: String, phone: String, department: String, appointmentDate: String, reason: String) {
        viewModelScope.launch {
            val result = repository.createAppointment(patientName, phone, department, appointmentDate, reason)
            _uiState.update {
                it.copy(
                    operationMessage = when (result) {
                        OperationResult.Success -> "Đã gửi yêu cầu đặt lịch khám."
                        is OperationResult.Failure -> result.message
                    },
                )
            }
            if (result == OperationResult.Success) {
                loadAppointments()
            }
        }
    }

    fun loadAppointments() {
        if (_uiState.value.session == null) {
            return
        }
        viewModelScope.launch {
            repository.loadAppointments()
                .onSuccess { appointments ->
                    _uiState.update { it.copy(appointments = appointments) }
                }
                .onFailure { error ->
                    _uiState.update { it.copy(operationMessage = error.message ?: "Không tải được danh sách lịch hẹn.") }
                }
        }
    }

    fun updateAppointmentStatus(appointmentId: Int, status: String) {
        viewModelScope.launch {
            val result = repository.updateAppointmentStatus(appointmentId, status)
            _uiState.update {
                it.copy(
                    operationMessage = when (result) {
                        OperationResult.Success -> "Đã cập nhật trạng thái lịch hẹn."
                        is OperationResult.Failure -> result.message
                    },
                )
            }
            if (result == OperationResult.Success) {
                loadAppointments()
            }
        }
    }

    fun requestKnowledgeBaseUpdate(note: String) {
        viewModelScope.launch {
            val result = repository.requestKbUpdate(note.ifBlank { "Admin requested knowledge base update" })
            _uiState.update {
                it.copy(
                    operationMessage = when (result) {
                        OperationResult.Success -> "Đã tạo yêu cầu cập nhật knowledge base."
                        is OperationResult.Failure -> result.message
                    },
                )
            }
            if (result == OperationResult.Success) {
                loadKbUpdateJobs()
            }
        }
    }

    fun loadKbUpdateJobs() {
        if (_uiState.value.session?.role != "admin") {
            return
        }
        viewModelScope.launch {
            repository.loadKbUpdateJobs()
                .onSuccess { jobs ->
                    _uiState.update { it.copy(kbJobs = jobs) }
                }
                .onFailure { error ->
                    _uiState.update { it.copy(operationMessage = error.message ?: "Không tải được danh sách job KB.") }
                }
        }
    }

    private fun persistMessages(messages: List<ChatMessage>) {
        historyStore.saveMessages(messages)
    }

    private fun topicAnchorFrom(messages: List<ChatMessage>): String? {
        var anchor: String? = null
        messages
            .filter { it.role == ChatRole.User && !it.isError }
            .forEach { message ->
                if (!isFollowUpQuestion(message.text)) {
                    anchor = contextAnchorFor(message.text)
                }
            }
        return anchor
    }

    private fun isFollowUpQuestion(question: String): Boolean {
        val normalized = question.normalizedForMatch()
        val tokens = normalized.split(" ").filter { it.isNotBlank() }
        val explicitTopicMarkers = listOf(
            "benh vien",
            "khoa ",
            "phong ",
            "trung tam ",
            "don nguyen ",
            "ban giam doc",
            "quy trinh",
            "vaccine",
            "tiem ",
            "bao hiem",
            "bhyt",
            "bang gia",
            "ngay giuong",
        )
        val shortFollowUpPrefixes = listOf(
            "gia bao nhieu",
            "bao nhieu",
            "o dau",
            "la gi",
            "nhu the nao",
            "co khong",
            "so dien thoai",
            "dien thoai",
            "hotline",
            "email",
            "lien he",
            "can mang theo gi",
        )
        val padded = " $normalized "
        val referentialMarkers = listOf(
            " do ",
            " ay ",
            " nay ",
            " thi sao",
            " nguoi do",
            " khoa do",
            " phong do",
            " trung tam do",
        )

        if (referentialMarkers.any { it in padded }) {
            return true
        }
        if (tokens.size <= 6 && listOf("truong khoa", "truong phong", "phu trach").any { it in normalized }) {
            return true
        }
        if (tokens.size <= 8 && shortFollowUpPrefixes.any { normalized.startsWith(it) }) {
            return explicitTopicMarkers.none { it in normalized }
        }
        return tokens.size <= 6 && explicitTopicMarkers.none { it in normalized }
    }

    private fun contextAnchorFor(question: String): String {
        val trimmed = question.trim()
        val patterns = listOf(
            Regex("""\b(Khoa\s+.+?)(?=\s+có|\s+là|\s+ở|\s+hiện|\s+gồm|\?|$)""", RegexOption.IGNORE_CASE),
            Regex("""\b(Phòng\s+.+?)(?=\s+có|\s+là|\s+ở|\s+hiện|\s+gồm|\?|$)""", RegexOption.IGNORE_CASE),
            Regex("""\b(Trung tâm\s+.+?)(?=\s+có|\s+là|\s+ở|\s+hiện|\s+gồm|\?|$)""", RegexOption.IGNORE_CASE),
            Regex("""\b(Đơn nguyên\s+.+?)(?=\s+có|\s+là|\s+ở|\s+hiện|\s+gồm|\?|$)""", RegexOption.IGNORE_CASE),
        )
        for (pattern in patterns) {
            val anchor = pattern.find(trimmed)
                ?.groupValues
                ?.getOrNull(1)
                ?.trim(' ', '.', ',', '?', '!')
            if (!anchor.isNullOrBlank()) {
                return anchor
            }
        }
        return trimmed
    }

    class Factory(
        private val repository: ChatRepository,
        private val historyStore: ChatHistoryStore = NoOpChatHistoryStore(),
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            if (modelClass.isAssignableFrom(ChatViewModel::class.java)) {
                return ChatViewModel(repository, historyStore) as T
            }
            throw IllegalArgumentException("Unknown ViewModel class: ${modelClass.name}")
        }
    }
}

private data class PendingQuestion(
    val question: String,
    val contextHint: String?,
)

private fun String.normalizedForMatch(): String {
    val decomposed = Normalizer.normalize(lowercase(), Normalizer.Form.NFD)
    val withoutMarks = decomposed.replace(Regex("\\p{Mn}+"), "")
    return withoutMarks
        .replace("đ", "d")
        .replace(Regex("[^a-z0-9\\s]"), " ")
        .replace(Regex("\\s+"), " ")
        .trim()
}
