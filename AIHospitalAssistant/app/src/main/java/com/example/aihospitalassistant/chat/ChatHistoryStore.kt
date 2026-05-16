package com.example.aihospitalassistant.chat

interface ChatHistoryStore {
    fun loadMessages(): List<ChatMessage>
    fun saveMessages(messages: List<ChatMessage>)
    fun clear()
}

class NoOpChatHistoryStore : ChatHistoryStore {
    override fun loadMessages(): List<ChatMessage> = emptyList()

    override fun saveMessages(messages: List<ChatMessage>) = Unit

    override fun clear() = Unit
}
