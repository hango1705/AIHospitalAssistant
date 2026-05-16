package com.example.aihospitalassistant.chat

import java.io.IOException

class DefaultChatRepository(
    private val api: ChatApi,
    private val sessionStore: SessionStore = NoOpSessionStore(),
) : ChatRepository {
    private var session: UserSession? = sessionStore.load()

    override fun currentSession(): UserSession? = session

    override suspend fun register(email: String, fullName: String, password: String): OperationResult {
        return authenticate {
            api.register(RegisterRequestDto(email = email, fullName = fullName, password = password))
        }
    }

    override suspend fun login(email: String, password: String): OperationResult {
        return authenticate {
            api.login(LoginRequestDto(email = email, password = password))
        }
    }

    private suspend fun authenticate(call: suspend () -> retrofit2.Response<AuthResponseDto>): OperationResult {
        return try {
            val response = call()
            if (!response.isSuccessful) {
                return OperationResult.Failure("Đăng nhập/đăng ký không thành công (${response.code()}).")
            }
            val body = response.body() ?: return OperationResult.Failure("Backend không trả về phiên đăng nhập.")
            val userSession = UserSession(
                token = body.token,
                email = body.user.email,
                fullName = body.user.fullName,
                role = body.user.role,
            )
            session = userSession
            sessionStore.save(userSession)
            OperationResult.Success
        } catch (_: IOException) {
            OperationResult.Failure("Không kết nối được backend.")
        } catch (_: RuntimeException) {
            OperationResult.Failure("Không xử lý được phản hồi đăng nhập.")
        }
    }

    override fun logout() {
        session = null
        sessionStore.clear()
    }

    override suspend fun ask(question: String, contextHint: String?): ChatResult {
        return try {
            val response = api.chat(
                ChatRequestDto(
                    question = question,
                    contextHint = contextHint,
                ),
                authorization = session?.authorizationHeader(),
            )
            if (!response.isSuccessful) {
                return ChatResult.Failure("Backend trả về lỗi ${response.code()}.")
            }
            val body = response.body()
                ?: return ChatResult.Failure("Backend không trả về nội dung.")
            ChatResult.Success(
                ChatAnswer(
                    answer = body.answer,
                    sources = body.sources.map { it.toDomain() },
                ),
            )
        } catch (_: IOException) {
            ChatResult.Failure("Không kết nối được backend.")
        } catch (_: RuntimeException) {
            ChatResult.Failure("Không xử lý được phản hồi từ backend.")
        }
    }

    override suspend fun loadServerHistory(): Result<List<ChatMessage>> {
        val auth = session?.authorizationHeader() ?: return Result.success(emptyList())
        return try {
            val response = api.chatHistory(auth)
            if (!response.isSuccessful) {
                return Result.failure(IllegalStateException("Backend trả về lỗi ${response.code()}."))
            }
            val messages = response.body()?.messages.orEmpty().map { it.toDomain() }
            Result.success(messages)
        } catch (exc: IOException) {
            Result.failure(exc)
        } catch (exc: RuntimeException) {
            Result.failure(exc)
        }
    }

    override suspend fun clearServerHistory(): OperationResult {
        val auth = session?.authorizationHeader() ?: return OperationResult.Failure("Bạn cần đăng nhập.")
        return try {
            val response = api.clearChatHistory(auth)
            if (response.isSuccessful) OperationResult.Success else OperationResult.Failure("Không xóa được lịch sử server.")
        } catch (_: IOException) {
            OperationResult.Failure("Không kết nối được backend.")
        }
    }

    override suspend fun createAppointment(
        patientName: String,
        phone: String,
        department: String,
        appointmentDate: String,
        reason: String,
    ): OperationResult {
        val auth = session?.authorizationHeader() ?: return OperationResult.Failure("Bạn cần đăng nhập.")
        return try {
            val response = api.createAppointment(
                auth,
                AppointmentRequestDto(patientName, phone, department, appointmentDate, reason),
            )
            if (response.isSuccessful) OperationResult.Success else OperationResult.Failure("Không gửi được lịch hẹn.")
        } catch (_: IOException) {
            OperationResult.Failure("Không kết nối được backend.")
        }
    }

    override suspend fun requestKbUpdate(note: String): OperationResult {
        val auth = session?.authorizationHeader() ?: return OperationResult.Failure("Bạn cần đăng nhập.")
        return try {
            val response = api.requestKbUpdate(auth, KbUpdateRequestDto(note))
            if (response.isSuccessful) OperationResult.Success else OperationResult.Failure("Không tạo được yêu cầu cập nhật KB.")
        } catch (_: IOException) {
            OperationResult.Failure("Không kết nối được backend.")
        }
    }

    override suspend fun loadKbUpdateJobs(): Result<List<KbUpdateJob>> {
        val auth = session?.authorizationHeader() ?: return Result.success(emptyList())
        return try {
            val response = api.kbUpdateJobs(auth)
            if (!response.isSuccessful) {
                return Result.failure(IllegalStateException("Backend trả về lỗi ${response.code()}."))
            }
            Result.success(response.body()?.jobs.orEmpty().map { it.toDomain() })
        } catch (exc: IOException) {
            Result.failure(exc)
        } catch (exc: RuntimeException) {
            Result.failure(exc)
        }
    }
}

private fun ChatSourceDto.toDomain(): ChatSource {
    return ChatSource(
        sourceId = sourceId,
        title = title,
        locator = locator,
        sourceUrl = sourceUrl,
        originPath = originPath,
        recordType = recordType,
        chunkId = chunkId,
    )
}

private fun UserSession.authorizationHeader(): String = "Bearer $token"

private fun ServerChatMessageDto.toDomain(): ChatMessage {
    return ChatMessage(
        id = id,
        role = if (role == "user") ChatRole.User else ChatRole.Assistant,
        text = text,
        sources = sources.map { it.toDomain() },
    )
}

private fun KbUpdateJobResponseDto.toDomain(): KbUpdateJob {
    return KbUpdateJob(
        id = id,
        note = note,
        status = status,
        createdAt = createdAt,
    )
}
