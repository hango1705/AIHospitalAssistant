package com.example.aihospitalassistant.chat

import java.io.IOException

class DefaultChatRepository(
    private val api: ChatApi,
) : ChatRepository {
    override suspend fun ask(question: String, contextHint: String?): ChatResult {
        return try {
            val response = api.chat(
                ChatRequestDto(
                    question = question,
                    contextHint = contextHint,
                ),
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
