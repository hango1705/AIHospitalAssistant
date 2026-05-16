package com.example.aihospitalassistant.chat

import com.google.gson.annotations.SerializedName
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

interface ChatApi {
    @GET("health")
    suspend fun health(): HealthResponseDto

    @POST("chat")
    suspend fun chat(@Body request: ChatRequestDto): Response<ChatResponseDto>
}

data class HealthResponseDto(
    val status: String,
)

data class ChatRequestDto(
    val question: String,
    @SerializedName("context_hint")
    val contextHint: String? = null,
)

data class ChatResponseDto(
    val question: String,
    val answer: String,
    val sources: List<ChatSourceDto> = emptyList(),
)

data class ChatSourceDto(
    @SerializedName("source_id")
    val sourceId: String,
    val title: String,
    val locator: String,
    @SerializedName("source_url")
    val sourceUrl: String? = null,
    @SerializedName("origin_path")
    val originPath: String? = null,
    @SerializedName("record_type")
    val recordType: String = "",
    @SerializedName("chunk_id")
    val chunkId: String = "",
)
