package com.genie.ai.core.network

import com.genie.ai.core.network.models.ConnectionStatus
import com.genie.ai.core.network.models.WSMessage
import com.google.gson.Gson
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import okhttp3.*
import java.util.concurrent.TimeUnit
import kotlin.math.min
import kotlin.math.pow

/**
 * Enterprise OkHttp WebSocket client supporting auto-reconnect, exponential backoff,
 * keep-alive heartbeats, and reactive StateFlow event streaming.
 */
class GenieWebSocketManager(
    private val gson: Gson = Gson()
) : WebSocketListener() {

    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .connectTimeout(10, TimeUnit.SECONDS)
        .build()

    private var webSocket: WebSocket? = null
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var reconnectJob: Job? = null
    private var heartbeatJob: Job? = null
    private var reconnectAttempts = 0

    private var serverUrl: String = ""

    private val _connectionStatus = MutableStateFlow(ConnectionStatus.DISCONNECTED)
    val connectionStatus: StateFlow<ConnectionStatus> = _connectionStatus.asStateFlow()

    private val _incomingMessages = MutableSharedFlow<WSMessage>(extraBufferCapacity = 64)
    val incomingMessages: SharedFlow<WSMessage> = _incomingMessages.asSharedFlow()

    fun connect(ip: String, port: Int, deviceId: String) {
        serverUrl = "ws://$ip:$port/api/v1/ws/android/$deviceId"
        reconnectAttempts = 0
        initiateConnection()
    }

    private fun initiateConnection() {
        if (serverUrl.isEmpty()) return
        _connectionStatus.value = ConnectionStatus.CONNECTING

        val request = Request.Builder()
            .url(serverUrl)
            .build()

        webSocket = client.newWebSocket(request, this)
    }

    override fun onOpen(webSocket: WebSocket, response: Response) {
        reconnectAttempts = 0
        _connectionStatus.value = ConnectionStatus.CONNECTED
        startHeartbeat()
    }

    override fun onMessage(webSocket: WebSocket, text: String) {
        try {
            val msg = gson.fromJson(text, WSMessage::class.java)
            scope.launch {
                _incomingMessages.emit(msg)
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
        _connectionStatus.value = ConnectionStatus.DISCONNECTED
    }

    override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
        _connectionStatus.value = ConnectionStatus.DISCONNECTED
        scheduleReconnect()
    }

    override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
        _connectionStatus.value = ConnectionStatus.ERROR
        scheduleReconnect()
    }

    fun sendMessage(msg: WSMessage) {
        val json = gson.toJson(msg)
        webSocket?.send(json)
    }

    fun disconnect() {
        reconnectJob?.cancel()
        heartbeatJob?.cancel()
        webSocket?.close(1000, "User disconnected")
        webSocket = null
        _connectionStatus.value = ConnectionStatus.DISCONNECTED
    }

    private fun startHeartbeat() {
        heartbeatJob?.cancel()
        heartbeatJob = scope.launch {
            while (isActive && _connectionStatus.value == ConnectionStatus.CONNECTED) {
                delay(15000) // 15s interval
                sendMessage(WSMessage(type = "heartbeat"))
            }
        }
    }

    private fun scheduleReconnect() {
        reconnectJob?.cancel()
        reconnectJob = scope.launch {
            _connectionStatus.value = ConnectionStatus.RECONNECTING
            reconnectAttempts++
            val backoffSec = min(30.0, 2.0.pow(reconnectAttempts.toDouble())).toLong()
            delay(backoffSec * 1000)
            if (_connectionStatus.value != ConnectionStatus.CONNECTED) {
                initiateConnection()
            }
        }
    }
}
