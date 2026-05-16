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

    override suspend fun logout(): OperationResult {
        val auth = session?.authorizationHeader()
        if (auth != null) {
            try {
                api.logout(auth)
            } catch (_: IOException) {
                // Local logout must still clear the token even when the network is unavailable.
            } catch (_: RuntimeException) {
                // Keep logout idempotent for malformed backend responses.
            }
        }
        session = null
        sessionStore.clear()
        return OperationResult.Success
    }

    override suspend fun ask(question: String, contextHint: String?, conversationId: String?): ChatResult {
        return try {
            val response = api.chat(
                ChatRequestDto(
                    question = question,
                    contextHint = contextHint,
                    conversationId = conversationId,
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
                    conversationId = body.conversationId,
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

    override suspend fun loadConversations(): Result<List<ConversationSummary>> {
        val auth = session?.authorizationHeader() ?: return Result.success(emptyList())
        return try {
            val response = api.conversations(auth)
            if (!response.isSuccessful) {
                return Result.failure(IllegalStateException("Backend trả về lỗi ${response.code()}."))
            }
            Result.success(response.body()?.conversations.orEmpty().map { it.toDomain() })
        } catch (exc: IOException) {
            Result.failure(exc)
        } catch (exc: RuntimeException) {
            Result.failure(exc)
        }
    }

    override suspend fun loadConversationMessages(conversationId: String): Result<List<ChatMessage>> {
        val auth = session?.authorizationHeader() ?: return Result.success(emptyList())
        return try {
            val response = api.conversationMessages(auth, conversationId)
            if (!response.isSuccessful) {
                return Result.failure(IllegalStateException("Backend trả về lỗi ${response.code()}."))
            }
            Result.success(response.body()?.messages.orEmpty().map { it.toDomain() })
        } catch (exc: IOException) {
            Result.failure(exc)
        } catch (exc: RuntimeException) {
            Result.failure(exc)
        }
    }

    override suspend fun deleteConversation(conversationId: String): OperationResult {
        val auth = session?.authorizationHeader() ?: return OperationResult.Failure("Bạn cần đăng nhập.")
        return try {
            val response = api.deleteConversation(auth, conversationId)
            if (response.isSuccessful) OperationResult.Success else OperationResult.Failure("Không xóa được cuộc trò chuyện.")
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

    override suspend fun loadAppointments(): Result<List<Appointment>> {
        val auth = session?.authorizationHeader() ?: return Result.success(emptyList())
        return try {
            val response = if (session?.role == "admin") {
                api.adminAppointments(auth)
            } else {
                api.appointments(auth)
            }
            if (!response.isSuccessful) {
                return Result.failure(IllegalStateException("Backend trả về lỗi ${response.code()}."))
            }
            Result.success(response.body()?.appointments.orEmpty().map { it.toDomain() })
        } catch (exc: IOException) {
            Result.failure(exc)
        } catch (exc: RuntimeException) {
            Result.failure(exc)
        }
    }

    override suspend fun updateAppointmentStatus(appointmentId: Int, status: String): OperationResult {
        val auth = session?.authorizationHeader() ?: return OperationResult.Failure("Bạn cần đăng nhập.")
        if (session?.role != "admin") {
            return OperationResult.Failure("Chỉ admin được cập nhật trạng thái lịch hẹn.")
        }
        return try {
            val response = api.updateAppointmentStatus(auth, appointmentId, AppointmentStatusUpdateDto(status))
            if (response.isSuccessful) OperationResult.Success else OperationResult.Failure("Không cập nhật được lịch hẹn.")
        } catch (_: IOException) {
            OperationResult.Failure("Không kết nối được backend.")
        } catch (_: RuntimeException) {
            OperationResult.Failure("Không xử lý được phản hồi lịch hẹn.")
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
        logs = logs,
        startedAt = startedAt,
        completedAt = completedAt,
    )
}

private fun AppointmentResponseDto.toDomain(): Appointment {
    return Appointment(
        id = id,
        userId = userId,
        patientName = patientName,
        phone = phone,
        department = department,
        appointmentDate = appointmentDate,
        reason = reason,
        status = status,
        createdAt = createdAt,
    )
}

private fun ConversationResponseDto.toDomain(): ConversationSummary {
    return ConversationSummary(
        id = id,
        title = title,
        createdAt = createdAt,
        updatedAt = updatedAt,
    )
}
