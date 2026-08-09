package com.genie.ai.domain.providers

import com.genie.ai.core.network.GenieApiClient

interface AIProvider {
    val id: String
    val displayName: String
    val requiresApiKey: Boolean

    suspend fun generateResponse(prompt: String, apiKey: String?, pcIp: String, pcPort: Int): String
}

class PCGenieProvider(private val apiClient: GenieApiClient) : AIProvider {
    override val id = "PCGenieProvider"
    override val displayName = "Genie PC Hub Agent (Default)"
    override val requiresApiKey = false

    override suspend fun generateResponse(prompt: String, apiKey: String?, pcIp: String, pcPort: Int): String {
        val result = apiClient.sendAssistantCommand(pcIp, pcPort, prompt)
        return (result["message"] as? String) ?: "Processed by Genie PC Hub."
    }
}

class GeminiProvider : AIProvider {
    override val id = "GeminiProvider"
    override val displayName = "Google Gemini (Direct)"
    override val requiresApiKey = true

    override suspend fun generateResponse(prompt: String, apiKey: String?, pcIp: String, pcPort: Int): String {
        if (apiKey.isNull_or_empty()) return "Error: Gemini API Key not configured."
        return "Gemini Direct response for: '$prompt'"
    }
}

class OpenAIProvider : AIProvider {
    override val id = "OpenAIProvider"
    override val displayName = "OpenAI GPT-4o (Direct)"
    override val requiresApiKey = true

    override suspend fun generateResponse(prompt: String, apiKey: String?, pcIp: String, pcPort: Int): String {
        if (apiKey.isNull_or_empty()) return "Error: OpenAI API Key not configured."
        return "OpenAI Direct response for: '$prompt'"
    }
}

class MistralProvider : AIProvider {
    override val id = "MistralProvider"
    override val displayName = "Mistral AI (Direct)"
    override val requiresApiKey = true

    override suspend fun generateResponse(prompt: String, apiKey: String?, pcIp: String, pcPort: Int): String {
        if (apiKey.isNull_or_empty()) return "Error: Mistral API Key not configured."
        return "Mistral response for: '$prompt'"
    }
}

class OpenRouterProvider : AIProvider {
    override val id = "OpenRouterProvider"
    override val displayName = "OpenRouter Hub (Direct)"
    override val requiresApiKey = true

    override suspend fun generateResponse(prompt: String, apiKey: String?, pcIp: String, pcPort: Int): String {
        if (apiKey.isNull_or_empty()) return "Error: OpenRouter Key not configured."
        return "OpenRouter response for: '$prompt'"
    }
}

class CustomProvider : AIProvider {
    override val id = "CustomProvider"
    override val displayName = "Custom Provider"
    override val requiresApiKey = true

    override suspend fun generateResponse(prompt: String, apiKey: String?, pcIp: String, pcPort: Int): String {
        return "Custom Provider response for: '$prompt'"
    }
}

private fun String?.isNull_or_empty(): Boolean = this == null || this.trim().isEmpty()
