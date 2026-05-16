package com.example.aihospitalassistant.chat

interface ChatRepository {
    fun currentSession(): UserSession?
    suspend fun register(email: String, fullName: String, password: String): OperationResult
    suspend fun login(email: String, password: String): OperationResult
    suspend fun logout(): OperationResult
    suspend fun ask(question: String, contextHint: String? = null, conversationId: String? = null): ChatResult
    suspend fun loadServerHistory(): Result<List<ChatMessage>>
    suspend fun clearServerHistory(): OperationResult
    suspend fun loadConversations(): Result<List<ConversationSummary>>
    suspend fun loadConversationMessages(conversationId: String): Result<List<ChatMessage>>
    suspend fun deleteConversation(conversationId: String): OperationResult
    suspend fun createAppointment(patientName: String, phone: String, department: String, appointmentDate: String, reason: String): OperationResult
    suspend fun loadAppointments(): Result<List<Appointment>>
    suspend fun updateAppointmentStatus(appointmentId: Int, status: String): OperationResult
    suspend fun requestKbUpdate(note: String): OperationResult
    suspend fun loadKbUpdateJobs(): Result<List<KbUpdateJob>>
}
