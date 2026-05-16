package com.example.aihospitalassistant.chat

import com.google.gson.annotations.SerializedName
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.PATCH
import retrofit2.http.Path
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

    @POST("auth/logout")
    suspend fun logout(@Header("Authorization") authorization: String): Response<HealthResponseDto>

    @GET("chat/history")
    suspend fun chatHistory(@Header("Authorization") authorization: String): Response<ChatHistoryResponseDto>

    @DELETE("chat/history")
    suspend fun clearChatHistory(@Header("Authorization") authorization: String): Response<HealthResponseDto>

    @GET("chat/conversations")
    suspend fun conversations(@Header("Authorization") authorization: String): Response<ConversationListResponseDto>

    @GET("chat/conversations/{conversationId}/messages")
    suspend fun conversationMessages(
        @Header("Authorization") authorization: String,
        @Path("conversationId") conversationId: String,
    ): Response<ChatHistoryResponseDto>

    @DELETE("chat/conversations/{conversationId}")
    suspend fun deleteConversation(
        @Header("Authorization") authorization: String,
        @Path("conversationId") conversationId: String,
    ): Response<HealthResponseDto>

    @POST("appointments")
    suspend fun createAppointment(
        @Header("Authorization") authorization: String,
        @Body request: AppointmentRequestDto,
    ): Response<AppointmentResponseDto>

    @GET("appointments")
    suspend fun appointments(@Header("Authorization") authorization: String): Response<AppointmentListResponseDto>

    @GET("admin/appointments")
    suspend fun adminAppointments(@Header("Authorization") authorization: String): Response<AppointmentListResponseDto>

    @PATCH("admin/appointments/{appointmentId}/status")
    suspend fun updateAppointmentStatus(
        @Header("Authorization") authorization: String,
        @Path("appointmentId") appointmentId: Int,
        @Body request: AppointmentStatusUpdateDto,
    ): Response<AppointmentResponseDto>

    @POST("admin/kb/update")
    suspend fun requestKbUpdate(
        @Header("Authorization") authorization: String,
        @Body request: KbUpdateRequestDto,
    ): Response<KbUpdateJobResponseDto>

    @GET("admin/kb/jobs")
    suspend fun kbUpdateJobs(@Header("Authorization") authorization: String): Response<KbUpdateJobListResponseDto>
}

data class HealthResponseDto(
    val status: String,
)

data class ChatRequestDto(
    val question: String,
    @SerializedName("context_hint")
    val contextHint: String? = null,
    @SerializedName("conversation_id")
    val conversationId: String? = null,
)

data class ChatResponseDto(
    val question: String,
    val answer: String,
    val sources: List<ChatSourceDto> = emptyList(),
    @SerializedName("conversation_id")
    val conversationId: String? = null,
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

data class ConversationResponseDto(
    val id: String,
    val title: String,
    @SerializedName("created_at")
    val createdAt: String,
    @SerializedName("updated_at")
    val updatedAt: String,
)

data class ConversationListResponseDto(
    val conversations: List<ConversationResponseDto> = emptyList(),
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
    @SerializedName("user_id")
    val userId: Int = 0,
    @SerializedName("patient_name")
    val patientName: String = "",
    val phone: String = "",
    val department: String = "",
    @SerializedName("appointment_date")
    val appointmentDate: String = "",
    val reason: String = "",
    val status: String,
    @SerializedName("created_at")
    val createdAt: String = "",
)

data class AppointmentListResponseDto(
    val appointments: List<AppointmentResponseDto> = emptyList(),
)

data class AppointmentStatusUpdateDto(
    val status: String,
)

data class KbUpdateRequestDto(
    val note: String,
)

data class KbUpdateJobResponseDto(
    val id: Int,
    val note: String = "",
    val status: String,
    val logs: String = "",
    @SerializedName("created_at")
    val createdAt: String = "",
    @SerializedName("started_at")
    val startedAt: String? = null,
    @SerializedName("completed_at")
    val completedAt: String? = null,
)

data class KbUpdateJobListResponseDto(
    val jobs: List<KbUpdateJobResponseDto> = emptyList(),
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
