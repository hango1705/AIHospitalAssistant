package com.example.aihospitalassistant

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.remember
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.aihospitalassistant.chat.ChatScreen
import com.example.aihospitalassistant.chat.ChatServiceFactory
import com.example.aihospitalassistant.chat.ChatViewModel
import com.example.aihospitalassistant.chat.DefaultChatRepository
import com.example.aihospitalassistant.chat.SharedPreferencesChatHistoryStore
import com.example.aihospitalassistant.ui.theme.AIHospitalAssistantTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            AIHospitalAssistantTheme {
                val repository = remember {
                    DefaultChatRepository(
                        ChatServiceFactory.create(BuildConfig.CHAT_API_BASE_URL),
                    )
                }
                val historyStore = remember {
                    SharedPreferencesChatHistoryStore(applicationContext)
                }
                val viewModel: ChatViewModel = viewModel(
                    factory = ChatViewModel.Factory(repository, historyStore),
                )
                ChatScreen(viewModel = viewModel)
            }
        }
    }
}
