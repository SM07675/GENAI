package com.genie.ai.core.security

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Hardware-backed security manager utilizing Android KeyStore & EncryptedSharedPreferences.
 * Stores sensitive API keys, device credentials, and pairing secrets without plaintext exposure.
 */
class KeystoreManager(context: Context) {

    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val encryptedPrefs = EncryptedSharedPreferences.create(
        context,
        "genie_secure_prefs",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    fun saveApiKey(providerId: String, apiKey: String) {
        encryptedPrefs.edit().putString("key_$providerId", apiKey).apply()
    }

    fun getApiKey(providerId: String): String? {
        return encryptedPrefs.getString("key_$providerId", null)
    }

    fun removeApiKey(providerId: String) {
        encryptedPrefs.edit().remove("key_$providerId").apply()
    }

    fun saveDeviceCredentials(deviceId: String, deviceToken: String, pcIp: String, pcPort: Int) {
        encryptedPrefs.edit()
            .putString("device_id", deviceId)
            .putString("device_token", deviceToken)
            .putString("pc_ip", pcIp)
            .putInt("pc_port", pcPort)
            .apply()
    }

    fun getDeviceId(): String? = encryptedPrefs.getString("device_id", null)
    fun getDeviceToken(): String? = encryptedPrefs.getString("device_token", null)
    fun getPcIp(): String? = encryptedPrefs.getString("pc_ip", "192.168.1.100")
    fun getPcPort(): Int = encryptedPrefs.getInt("pc_port", 8000)

    fun saveSelectedProvider(providerId: String) {
        encryptedPrefs.edit().putString("selected_provider", providerId).apply()
    }

    fun getSelectedProvider(): String {
        return encryptedPrefs.getString("selected_provider", "PCGenieProvider") ?: "PCGenieProvider"
    }

    fun clearAllData() {
        encryptedPrefs.edit().clear().apply()
    }
}
