package com.example.aihospitalassistant.chat

import com.google.gson.annotations.SerializedName
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST

interface ChatApi {
    @GET("health")
    suspend fun health(): HealthResponseDto

    @POST("chat")
    suspend fun chat(
        @Body request: ChatRequestDto,
        @Header("Authorization") authorization: String? = null,
    ): Response<ChatResponseDto>

    @POST("auth/register")
    suspend fun register(@Body request: RegisterRequestDto): Response<AuthResponseDto>

    @POST("auth/login")
    suspend fun login(@Body request: LoginRequestDto): Response<AuthResponseDto>

    @GET("chat/history")
    suspend fun chatHistory(@Header("Authorization") authorization: String): Response<ChatHistoryResponseDto>

    @DELETE("chat/history")
    suspend fun clearChatHistory(@Header("Authorization") authorization: String): Response<HealthResponseDto>

    @POST("appointments")
    suspend fun createAppointment(
        @Header("Authorization") authorization: String,
        @Body request: AppointmentRequestDto,
    ): Response<AppointmentResponseDto>

    @POST("admin/kb/update")
    suspend fun requestKbUpdate(
        @Header("Authorization") authorization: String,
        @Body request: KbUpdateRequestDto,
    ): Response<KbUpdateJobResponseDto>
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

data class RegisterRequestDto(
    val email: String,
    @SerializedName("full_name")
    val fullName: String,
    val password: String,
)

data class LoginRequestDto(
    val email: String,
    val password: String,
)

data class AuthResponseDto(
    val token: String,
    val user: UserDto,
)

data class UserDto(
    val id: Int,
    val email: String,
    @SerializedName("full_name")
    val fullName: String,
    val role: String,
)

data class ChatHistoryResponseDto(
    val messages: List<ServerChatMessageDto> = emptyList(),
)

data class ServerChatMessageDto(
    val id: Long,
    @SerializedName("conversation_id")
    val conversationId: String,
    val role: String,
    val text: String,
    val sources: List<ChatSourceDto> = emptyList(),
    @SerializedName("created_at")
    val createdAt: String,
)

data class AppointmentRequestDto(
    @SerializedName("patient_name")
    val patientName: String,
    val phone: String,
    val department: String,
    @SerializedName("appointment_date")
    val appointmentDate: String,
    val reason: String,
)

data class AppointmentResponseDto(
    val id: Int,
    val status: String,
)

data class KbUpdateRequestDto(
    val note: String,
)

data class KbUpdateJobResponseDto(
    val id: Int,
    val status: String,
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
