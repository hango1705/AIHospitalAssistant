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
                ChatRequestCall("Email thì sao?", "Khoa Nhi Bệnh viện A"),
            ),
            repository.calls,
        )
    }

    @Test
    fun departmentRoleFollowUpUsesDepartmentAnchorAsContextHint() = runTest(dispatcher) {
        val repository = FakeChatRepository()
        val viewModel = ChatViewModel(repository)

        viewModel.sendQuestion("Khoa Nhi có bao nhiêu giường bệnh?")
        advanceUntilIdle()
        viewModel.sendQuestion("Trưởng khoa là ai?")
        advanceUntilIdle()

        assertEquals(
            listOf(
                ChatRequestCall("Khoa Nhi có bao nhiêu giường bệnh?", null),
                ChatRequestCall("Trưởng khoa là ai?", "Khoa Nhi"),
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

    @Test
    fun initializesWithStoredChatHistory() = runTest(dispatcher) {
        val historyStore = FakeChatHistoryStore(
            initialMessages = listOf(
                ChatMessage(id = 7, role = ChatRole.User, text = "Khoa Nhi"),
                ChatMessage(id = 8, role = ChatRole.Assistant, text = "Thông tin Khoa Nhi.", sources = emptyList()),
            ),
        )

        val viewModel = ChatViewModel(FakeChatRepository(), historyStore)

        assertEquals(2, viewModel.uiState.value.messages.size)
        assertEquals("Khoa Nhi", viewModel.uiState.value.messages.first().text)
    }

    @Test
    fun successfulConversationIsPersistedToHistoryStore() = runTest(dispatcher) {
        val historyStore = FakeChatHistoryStore()
        val viewModel = ChatViewModel(FakeChatRepository(), historyStore)

        viewModel.sendQuestion("Bệnh viện A Thái Nguyên ở đâu?")
        advanceUntilIdle()

        assertEquals(2, historyStore.savedMessages.size)
        assertEquals("Bệnh viện A Thái Nguyên ở đâu?", historyStore.savedMessages[0].text)
        assertEquals("Bệnh viện A nằm trên đường Quang Trung [Nguon 1].", historyStore.savedMessages[1].text)
    }

    @Test
    fun restoredTopicIsUsedForFollowUpQuestion() = runTest(dispatcher) {
        val historyStore = FakeChatHistoryStore(
            initialMessages = listOf(
                ChatMessage(id = 1, role = ChatRole.User, text = "Khoa Nhi có bao nhiêu giường bệnh?"),
                ChatMessage(id = 2, role = ChatRole.Assistant, text = "Khoa Nhi có trên 156 giường."),
            ),
        )
        val repository = FakeChatRepository()
        val viewModel = ChatViewModel(repository, historyStore)

        viewModel.sendQuestion("Trưởng khoa là ai?")
        advanceUntilIdle()

        assertEquals(
            ChatRequestCall("Trưởng khoa là ai?", "Khoa Nhi"),
            repository.calls.single(),
        )
    }

    @Test
    fun clearHistoryRemovesMessagesAndStoreContent() = runTest(dispatcher) {
        val historyStore = FakeChatHistoryStore(
            initialMessages = listOf(
                ChatMessage(id = 1, role = ChatRole.User, text = "Khoa Nhi"),
            ),
        )
        val viewModel = ChatViewModel(FakeChatRepository(), historyStore)

        viewModel.clearHistory()
        advanceUntilIdle()

        assertTrue(viewModel.uiState.value.messages.isEmpty())
        assertTrue(historyStore.wasCleared)
        assertTrue(historyStore.savedMessages.isEmpty())
    }

    @Test
    fun loginUpdatesSessionState() = runTest(dispatcher) {
        val repository = FakeChatRepository()
        val viewModel = ChatViewModel(repository)

        viewModel.login("user@example.com", "secret123")
        advanceUntilIdle()

        assertEquals("user@example.com", viewModel.uiState.value.session?.email)
    }

    @Test
    fun appointmentShowsOperationMessage() = runTest(dispatcher) {
        val repository = FakeChatRepository(session = UserSession("token", "user@example.com", "User", "patient"))
        val viewModel = ChatViewModel(repository)

        viewModel.createAppointment("Nguyễn Văn A", "0912345678", "Khoa Nhi", "2026-05-20 08:00", "Khám")
        advanceUntilIdle()

        assertEquals("Đã gửi yêu cầu đặt lịch khám.", viewModel.uiState.value.operationMessage)
    }

    @Test
    fun adminModeLoadsKbJobs() = runTest(dispatcher) {
        val repository = FakeChatRepository(
            session = UserSession("token", "admin@example.com", "Admin", "admin"),
            kbJobs = listOf(KbUpdateJob(1, "Refresh KB", "queued", "2026-05-17T00:00:00Z")),
        )
        val viewModel = ChatViewModel(repository)

        viewModel.showAdmin()
        advanceUntilIdle()

        assertTrue(viewModel.uiState.value.isAdminMode)
        assertEquals("Refresh KB", viewModel.uiState.value.kbJobs.single().note)
    }
}

private data class ChatRequestCall(
    val question: String,
    val contextHint: String?,
)

private class FakeChatRepository(
    private var session: UserSession? = null,
    private val kbJobs: List<KbUpdateJob> = emptyList(),
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

    override fun currentSession(): UserSession? = session

    override suspend fun register(email: String, fullName: String, password: String): OperationResult {
        session = UserSession("token", email, fullName, "patient")
        return OperationResult.Success
    }

    override suspend fun login(email: String, password: String): OperationResult {
        session = UserSession("token", email, "User", "patient")
        return OperationResult.Success
    }

    override fun logout() {
        session = null
    }

    override suspend fun ask(question: String, contextHint: String?): ChatResult {
        calls += ChatRequestCall(question, contextHint)
        return if (results.isEmpty()) {
            ChatResult.Success(ChatAnswer(answer = "OK", sources = emptyList()))
        } else {
            results.removeFirst()
        }
    }

    override suspend fun loadServerHistory(): Result<List<ChatMessage>> = Result.success(emptyList())

    override suspend fun clearServerHistory(): OperationResult = OperationResult.Success

    override suspend fun createAppointment(
        patientName: String,
        phone: String,
        department: String,
        appointmentDate: String,
        reason: String,
    ): OperationResult = OperationResult.Success

    override suspend fun requestKbUpdate(note: String): OperationResult = OperationResult.Success

    override suspend fun loadKbUpdateJobs(): Result<List<KbUpdateJob>> = Result.success(kbJobs)
}

private class FakeChatHistoryStore(
    initialMessages: List<ChatMessage> = emptyList(),
) : ChatHistoryStore {
    var savedMessages = initialMessages
    var wasCleared = false

    override fun loadMessages(): List<ChatMessage> = savedMessages

    override fun saveMessages(messages: List<ChatMessage>) {
        savedMessages = messages
    }

    override fun clear() {
        wasCleared = true
        savedMessages = emptyList()
    }
}
