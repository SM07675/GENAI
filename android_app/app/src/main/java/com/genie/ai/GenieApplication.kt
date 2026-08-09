package com.genie.ai

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import com.genie.ai.core.database.AppDatabase
import com.genie.ai.core.network.GenieApiClient
import com.genie.ai.core.network.GenieWebSocketManager
import com.genie.ai.core.network.MDNSDiscoveryManager
import com.genie.ai.core.security.KeystoreManager

class GenieApplication : Application() {

    lateinit var keystoreManager: KeystoreManager
        private set
    lateinit var webSocketManager: GenieWebSocketManager
        private set
    lateinit var mdnsDiscoveryManager: MDNSDiscoveryManager
        private set
    lateinit var apiClient: GenieApiClient
        private set
    lateinit var database: AppDatabase
        private set

    override fun onCreate() {
        super.onCreate()
        keystoreManager = KeystoreManager(this)
        webSocketManager = GenieWebSocketManager()
        mdnsDiscoveryManager = MDNSDiscoveryManager(this)
        apiClient = GenieApiClient()
        database = AppDatabase.getInstance(this)

        createNotificationChannels()
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                "genie_tasks",
                "Genie Tasks & PC Status",
                NotificationManager.IMPORTANCE_DEFAULT
            ).apply {
                description = "Notifications for Genie cross-device execution and PC status updates"
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }
}
