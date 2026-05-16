package com.example.aihospitalassistant.chat

interface SessionStore {
    fun load(): UserSession?
    fun save(session: UserSession)
    fun clear()
}

class NoOpSessionStore : SessionStore {
    override fun load(): UserSession? = null
    override fun save(session: UserSession) = Unit
    override fun clear() = Unit
}
