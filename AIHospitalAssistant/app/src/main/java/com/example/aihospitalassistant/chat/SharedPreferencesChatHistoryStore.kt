package com.example.aihospitalassistant.chat

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

class SharedPreferencesChatHistoryStore(
    context: Context,
) : ChatHistoryStore {
    private val preferences = context.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)

    override fun loadMessages(): List<ChatMessage> {
        val raw = preferences.getString(KEY_MESSAGES, null) ?: return emptyList()
        return runCatching {
            val array = JSONArray(raw)
            buildList {
                for (index in 0 until array.length()) {
                    val item = array.optJSONObject(index) ?: continue
                    val role = runCatching {
                        ChatRole.valueOf(item.optString("role"))
                    }.getOrNull() ?: continue
                    add(
                        ChatMessage(
                            id = item.optLong("id"),
                            role = role,
                            text = item.optString("text"),
                            sources = item.optJSONArray("sources").toSources(),
                            isError = item.optBoolean("isError", false),
                        ),
                    )
                }
            }
        }.getOrDefault(emptyList())
    }

    override fun saveMessages(messages: List<ChatMessage>) {
        val array = JSONArray()
        messages
            .filterNot { it.isError }
            .takeLast(MAX_STORED_MESSAGES)
            .forEach { message ->
                array.put(
                    JSONObject()
                        .put("id", message.id)
                        .put("role", message.role.name)
                        .put("text", message.text)
                        .put("isError", message.isError)
                        .put("sources", message.sources.toJsonArray()),
                )
            }
        preferences.edit().putString(KEY_MESSAGES, array.toString()).apply()
    }

    override fun clear() {
        preferences.edit().remove(KEY_MESSAGES).apply()
    }

    private fun JSONArray?.toSources(): List<ChatSource> {
        if (this == null) {
            return emptyList()
        }
        return buildList {
            for (index in 0 until length()) {
                val item = optJSONObject(index) ?: continue
                add(
                    ChatSource(
                        sourceId = item.optString("sourceId"),
                        title = item.optString("title"),
                        locator = item.optString("locator"),
                        sourceUrl = item.optStringOrNull("sourceUrl"),
                        originPath = item.optStringOrNull("originPath"),
                        recordType = item.optString("recordType"),
                        chunkId = item.optString("chunkId"),
                    ),
                )
            }
        }
    }

    private fun List<ChatSource>.toJsonArray(): JSONArray {
        val array = JSONArray()
        forEach { source ->
            array.put(
                JSONObject()
                    .put("sourceId", source.sourceId)
                    .put("title", source.title)
                    .put("locator", source.locator)
                    .put("sourceUrl", source.sourceUrl)
                    .put("originPath", source.originPath)
                    .put("recordType", source.recordType)
                    .put("chunkId", source.chunkId),
            )
        }
        return array
    }

    private fun JSONObject.optStringOrNull(name: String): String? {
        if (isNull(name)) {
            return null
        }
        return optString(name).takeIf { it.isNotBlank() }
    }

    private companion object {
        const val PREFERENCES_NAME = "chat_history"
        const val KEY_MESSAGES = "messages"
        const val MAX_STORED_MESSAGES = 100
    }
}
