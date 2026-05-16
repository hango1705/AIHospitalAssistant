package com.example.aihospitalassistant.chat

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ChatViewModelTest {
    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun sendQuestionAddsUserAndAssistantMessages() = runTest(dispatcher) {
        val repository = FakeChatRepository()
        val viewModel = ChatViewModel(repository)

        viewModel.sendQuestion("Bệnh viện A Thái Nguyên ở đâu?")
        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertFalse(state.isLoading)
        assertEquals(null, state.errorMessage)
        assertEquals(2, state.messages.size)
        assertEquals(ChatRole.User, state.messages[0].role)
        assertEquals("Bệnh viện A Thái Nguyên ở đâu?", state.messages[0].text)
        assertEquals(ChatRole.Assistant, state.messages[1].role)
        assertEquals("Bệnh viện A nằm trên đường Quang Trung [Nguon 1].", state.messages[1].text)
        assertEquals("Nguon 1", state.messages[1].sources.single().sourceId)
        assertEquals(listOf(ChatRequestCall("Bệnh viện A Thái Nguyên ở đâu?", null)), repository.calls)
    }

    @Test
    fun shortFollowUpQuestionUsesLatestTopicAsContextHint() = runTest(dispatcher) {
        val repository = FakeChatRepository()
        val viewModel = ChatViewModel(repository)

        viewModel.sendQuestion("Khoa Nhi Bệnh viện A có số điện thoại nào?")
        advanceUntilIdle()
        viewModel.sendQuestion("Email thì sao?")
        advanceUntilIdle()

        assertEquals(
            listOf(
                ChatRequestCall("Khoa Nhi Bệnh viện A có số điện thoại nào?", null),
                ChatRequestCall("Email thì sao?", "Khoa Nhi Bệnh viện A có số điện thoại nào?"),
            ),
            repository.calls,
        )
    }

    @Test
    fun failureShowsErrorAndRetryResendsLastQuestion() = runTest(dispatcher) {
        val repository = FakeChatRepository(
            results = ArrayDeque(
                listOf(
                    ChatResult.Failure("Không kết nối được backend."),
                    ChatResult.Success(
                        ChatAnswer(
                            answer = "Backend đã phản hồi.",
                            sources = emptyList(),
                        ),
                    ),
                ),
            ),
        )
        val viewModel = ChatViewModel(repository)

        viewModel.sendQuestion("Quy trình khám bệnh như thế nào?")
        advanceUntilIdle()

        assertEquals("Không kết nối được backend.", viewModel.uiState.value.errorMessage)
        assertTrue(viewModel.uiState.value.messages.any { it.isError })

        viewModel.retryLastQuestion()
        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertEquals(null, state.errorMessage)
        assertEquals("Backend đã phản hồi.", state.messages.last().text)
        assertEquals(
            listOf(
                ChatRequestCall("Quy trình khám bệnh như thế nào?", null),
                ChatRequestCall("Quy trình khám bệnh như thế nào?", null),
            ),
            repository.calls,
        )
    }
}

private data class ChatRequestCall(
    val question: String,
    val contextHint: String?,
)

private class FakeChatRepository(
    private val results: ArrayDeque<ChatResult> = ArrayDeque(
        listOf(
            ChatResult.Success(
                ChatAnswer(
                    answer = "Bệnh viện A nằm trên đường Quang Trung [Nguon 1].",
                    sources = listOf(
                        ChatSource(
                            sourceId = "Nguon 1",
                            title = "Liên hệ",
                            locator = "https://benhvienathainguyen.com.vn/contact",
                        ),
                    ),
                ),
            ),
        ),
    ),
) : ChatRepository {
    val calls = mutableListOf<ChatRequestCall>()

    override suspend fun ask(question: String, contextHint: String?): ChatResult {
        calls += ChatRequestCall(question, contextHint)
        return if (results.isEmpty()) {
            ChatResult.Success(ChatAnswer(answer = "OK", sources = emptyList()))
        } else {
            results.removeFirst()
        }
    }
}
