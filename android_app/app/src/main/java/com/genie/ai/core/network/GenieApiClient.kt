package com.genie.ai.core.network

import com.genie.ai.core.network.models.HardwareStatus
import com.google.gson.Gson
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/**
 * REST Client for Genie PC Hub versioned v1 APIs.
 */
class GenieApiClient(
    private val gson: Gson = Gson()
) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    private val jsonMedia = "application/json; charset=utf-8".toMediaType()

    suspend fun getHealth(ip: String, port: Int): Boolean = withContext(Dispatchers.IO) {
        try {
            val req = Request.Builder().url("http://$ip:$port/api/v1/health").get().build()
            client.newCall(req).execute().use { resp ->
                return@withContext resp.isSuccessful
            }
        } catch (e: Exception) {
            return@withContext false
        }
    }

    suspend fun confirmPair(ip: String, port: Int, token: String, deviceId: String, deviceName: String): Pair<String, String>? = withContext(Dispatchers.IO) {
        try {
            val bodyObj = mapOf(
                "pairing_token" to token,
                "device_id" to deviceId,
                "device_name" to deviceName
            )
            val json = gson.toJson(bodyObj)
            val req = Request.Builder()
                .url("http://$ip:$port/api/v1/pair/confirm")
                .post(json.toRequestBody(jsonMedia))
                .build()

            client.newCall(req).execute().use { resp ->
                if (resp.isSuccessful) {
                    val respStr = resp.body?.string() ?: ""
                    val resultMap = gson.fromJson(respStr, Map::class.java)
                    val devId = resultMap["device_id"] as? String ?: deviceId
                    val devToken = resultMap["device_token"] as? String ?: ""
                    return@withContext Pair(devId, devToken)
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        return@withContext null
    }

    suspend fun fetchPcStatus(ip: String, port: Int): HardwareStatus = withContext(Dispatchers.IO) {
        try {
            val req = Request.Builder().url("http://$ip:$port/api/v1/pc/status").get().build()
            client.newCall(req).execute().use { resp ->
                if (resp.isSuccessful) {
                    val bodyStr = resp.body?.string() ?: ""
                    val map = gson.fromJson(bodyStr, Map::class.java)
                    return@withContext HardwareStatus(
                        cpuPercent = (map["cpu_percent"] as? Double) ?: 0.0,
                        ramPercent = (map["ram_percent"] as? Double) ?: 0.0,
                        gpuPercent = ((map["gpu_percent"] as? Double) ?: 0.0).toInt(),
                        gpuName = (map["gpu_name"] as? String) ?: "N/A",
                        isOnline = true,
                        activeTask = (map["active_task"] as? String) ?: "Idle"
                    )
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        return@withContext HardwareStatus(isOnline = false)
    }

    suspend fun sendAssistantCommand(
        ip: String,
        port: Int,
        prompt: String,
        confirmed: Boolean = false,
        token: String? = null
    ): Map<String, Any> = withContext(Dispatchers.IO) {
        try {
            val bodyMap = mutableMapOf<String, Any>(
                "prompt" to prompt,
                "confirmed" to confirmed
            )
            token?.let { bodyMap["confirmation_token"] = it }

            val req = Request.Builder()
                .url("http://$ip:$port/api/v1/assistant")
                .post(gson.toJson(bodyMap).toRequestBody(jsonMedia))
                .build()

            client.newCall(req).execute().use { resp ->
                val bodyStr = resp.body?.string() ?: ""
                @Suppress("UNCHECKED_CAST")
                return@withContext gson.fromJson(bodyStr, Map::class.java) as Map<String, Any>
            }
        } catch (e: Exception) {
            return@withContext mapOf("status" to "error", "message" to (e.message ?: "Network request failed"))
        }
    }
}
