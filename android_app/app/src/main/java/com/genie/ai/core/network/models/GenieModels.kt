package com.genie.ai.core.network.models

import com.google.gson.annotations.SerializedName

enum class AssistantState {
    IDLE,
    LISTENING,
    THINKING,
    SPEAKING,
    EXECUTING,
    SUCCESS,
    ERROR,
    OFFLINE
}

enum class ConnectionStatus {
    CONNECTED,
    CONNECTING,
    RECONNECTING,
    AUTHENTICATING,
    DISCONNECTED,
    OFFLINE,
    ERROR
}

data class WSMessage(
    @SerializedName("request_id") val requestId: String? = null,
    @SerializedName("type") val type: String,
    @SerializedName("status") val status: String? = null,
    @SerializedName("intent") val intent: String? = null,
    @SerializedName("message") val message: String? = null,
    @SerializedName("parameters") val parameters: Map<String, Any>? = null,
    @SerializedName("prompt") val prompt: String? = null,
    @SerializedName("confirmed") val confirmed: Boolean? = null,
    @SerializedName("confirmation_token") val confirmationToken: String? = null,
    @SerializedName("action") val action: String? = null,
    @SerializedName("chunk") val chunk: String? = null,
    @SerializedName("cpu_percent") val cpuPercent: Double? = null,
    @SerializedName("ram_percent") val ramPercent: Double? = null,
    @SerializedName("gpu_percent") val gpuPercent: Int? = null,
    @SerializedName("active_task") val activeTask: String? = null
)

data class QRPairPayload(
    val token: String,
    val ip: String,
    val port: Int
)

data class HardwareStatus(
    val cpuPercent: Double = 0.0,
    val ramPercent: Double = 0.0,
    val gpuPercent: Int = 0,
    val gpuName: String = "N/A",
    val isOnline: Boolean = false,
    val activeTask: String = "Idle"
)

data class SecurityConfirmationRequest(
    val requestId: String,
    val confirmationToken: String,
    val action: String,
    val message: String
)
