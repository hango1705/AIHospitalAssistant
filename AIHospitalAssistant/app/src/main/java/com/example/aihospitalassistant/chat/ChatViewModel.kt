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
) : ViewModel() {
    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState: StateFlow<ChatUiState> = _uiState.asStateFlow()

    private var nextMessageId = 1L
    private var latestTopicQuestion: String? = null
    private var lastFailedQuestion: PendingQuestion? = null

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
            state.copy(
                messages = if (addUserMessage) {
                    cleanedMessages + ChatMessage(
                        id = nextMessageId++,
                        role = ChatRole.User,
                        text = question,
                    )
                } else {
                    cleanedMessages
                },
                isLoading = true,
                errorMessage = null,
            )
        }

        viewModelScope.launch {
            when (val result = repository.ask(question, contextHint)) {
                is ChatResult.Success -> {
                    if (!isFollowUpQuestion(question)) {
                        latestTopicQuestion = question
                    }
                    _uiState.update { state ->
                        state.copy(
                            messages = state.messages + ChatMessage(
                                id = nextMessageId++,
                                role = ChatRole.Assistant,
                                text = result.answer.answer,
                                sources = result.answer.sources,
                            ),
                            isLoading = false,
                            errorMessage = null,
                        )
                    }
                }

                is ChatResult.Failure -> {
                    lastFailedQuestion = PendingQuestion(question, contextHint)
                    _uiState.update { state ->
                        state.copy(
                            messages = state.messages + ChatMessage(
                                id = nextMessageId++,
                                role = ChatRole.Assistant,
                                text = result.message,
                                isError = true,
                            ),
                            isLoading = false,
                            errorMessage = result.message,
                        )
                    }
                }
            }
        }
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
        if (tokens.size <= 8 && shortFollowUpPrefixes.any { normalized.startsWith(it) }) {
            return explicitTopicMarkers.none { it in normalized }
        }
        return tokens.size <= 6 && explicitTopicMarkers.none { it in normalized }
    }

    class Factory(
        private val repository: ChatRepository,
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            if (modelClass.isAssignableFrom(ChatViewModel::class.java)) {
                return ChatViewModel(repository) as T
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
