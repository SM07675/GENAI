package com.genie.ai.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Key
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.genie.ai.core.security.KeystoreManager
import com.genie.ai.ui.theme.*

data class ProviderOption(
    val id: String,
    val name: String,
    val description: String,
    val requiresKey: Boolean
)

val PROVIDERS_LIST = listOf(
    ProviderOption("PCGenieProvider", "Genie PC Hub Agent", "Delegates reasoning to PC server & local agent tools", false),
    ProviderOption("GeminiProvider", "Google Gemini 1.5/2.0", "Direct Google Gemini AI API provider", true),
    ProviderOption("OpenAIProvider", "OpenAI GPT-4o / GPT-4o-mini", "Direct OpenAI API provider", true),
    ProviderOption("MistralProvider", "Mistral AI", "Direct Mistral Large / Codestral provider", true),
    ProviderOption("OpenRouterProvider", "OpenRouter AI Hub", "Unified OpenRouter API hub provider", true),
    ProviderOption("CustomProvider", "Custom OpenAI-Compatible Endpoint", "User-specified custom endpoint", true)
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AIProvidersScreen(
    keystoreManager: KeystoreManager,
    onBackClicked: () -> Unit
) {
    var selectedProvider by remember { mutableStateOf(keystoreManager.getSelectedProvider()) }
    var keyInputMap by remember {
        mutableStateOf(PROVIDERS_LIST.associate { it.id to (keystoreManager.getApiKey(it.id) ?: "") })
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("AI Providers & Keys", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBackClicked) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = GenieBackgroundDark)
            )
        },
        containerColor = GenieBackgroundDark
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(20.dp)
        ) {
            items(PROVIDERS_LIST.size) { idx ->
                val prov = PROVIDERS_LIST[idx]
                val isSelected = selectedProvider == prov.id
                val currentKey = keyInputMap[prov.id] ?: ""

                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = if (isSelected) GenieSurfaceDark else GenieBackgroundDark
                    ),
                    shape = RoundedCornerShape(18.dp),
                    border = androidx.compose.foundation.BorderStroke(
                        1.5.dp,
                        if (isSelected) GeniePrimary else GenieCardBorder
                    ),
                    modifier = Modifier.fillMaxWidth().padding(bottom = 16.dp)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            RadioButton(
                                selected = isSelected,
                                onClick = {
                                    selectedProvider = prov.id
                                    keystoreManager.saveSelectedProvider(prov.id)
                                }
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Column(modifier = Modifier.weight(1f)) {
                                Text(prov.name, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                                Text(prov.description, fontSize = 12.sp, color = Color(0xFF94A3B8))
                            }
                        }

                        if (prov.requiresKey) {
                            Spacer(modifier = Modifier.height(12.dp))
                            OutlinedTextField(
                                value = currentKey,
                                onValueChange = { newKey ->
                                    val updatedMap = keyInputMap.toMutableMap()
                                    updatedMap[prov.id] = newKey
                                    keyInputMap = updatedMap
                                    keystoreManager.saveApiKey(prov.id, newKey)
                                },
                                label = { Text("API Key") },
                                placeholder = { Text("Enter ${prov.name} Key...") },
                                visualTransformation = PasswordVisualTransformation(),
                                leadingIcon = { Icon(Icons.Default.Key, contentDescription = null, tint = GenieAccent) },
                                trailingIcon = {
                                    if (currentKey.isNotEmpty()) {
                                        Icon(Icons.Default.Check, contentDescription = "Saved", tint = Color(0xFF10B981))
                                    }
                                },
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(12.dp)
                            )
                        }
                    }
                }
            }
        }
    }
}
