package com.example.aihospitalassistant.chat

import android.content.Context

class SharedPreferencesSessionStore(
    context: Context,
) : SessionStore {
    private val preferences = context.getSharedPreferences("user_session", Context.MODE_PRIVATE)

    override fun load(): UserSession? {
        val token = preferences.getString("token", null)?.takeIf { it.isNotBlank() } ?: return null
        return UserSession(
            token = token,
            email = preferences.getString("email", "") ?: "",
            fullName = preferences.getString("fullName", "") ?: "",
            role = preferences.getString("role", "patient") ?: "patient",
        )
    }

    override fun save(session: UserSession) {
        preferences.edit()
            .putString("token", session.token)
            .putString("email", session.email)
            .putString("fullName", session.fullName)
            .putString("role", session.role)
            .apply()
    }

    override fun clear() {
        preferences.edit().clear().apply()
    }
}
