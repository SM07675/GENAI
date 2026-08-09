package com.genie.ai.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.genie.ai.core.security.KeystoreManager
import com.genie.ai.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    keystoreManager: KeystoreManager,
    onNavigateToProviders: () -> Unit,
    onClearMemory: () -> Unit
) {
    var selectedProvider by remember { mutableStateOf(keystoreManager.getSelectedProvider()) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings", fontWeight = FontWeight.Bold) },
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
            item {
                Text("AI Engine & Providers", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = GenieAccent)
                Spacer(modifier = Modifier.height(10.dp))
                SettingsItemCard(
                    icon = Icons.Default.SmartToy,
                    title = "AI Providers",
                    subtitle = "Active: $selectedProvider",
                    onClick = onNavigateToProviders
                )
                Spacer(modifier = Modifier.height(20.dp))
            }

            item {
                Text("Voice & Speech", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = GenieAccent)
                Spacer(modifier = Modifier.height(10.dp))
                SettingsItemCard(
                    icon = Icons.Default.RecordVoiceOver,
                    title = "Wake Word",
                    subtitle = "\"Hey Genie\" (Offline detection enabled)",
                    onClick = {}
                )
                Spacer(modifier = Modifier.height(8.dp))
                SettingsItemCard(
                    icon = Icons.Default.VolumeUp,
                    title = "Text To Speech (TTS)",
                    subtitle = "Engine: Android Native TTS / Edge-TTS",
                    onClick = {}
                )
                Spacer(modifier = Modifier.height(20.dp))
            }

            item {
                Text("Privacy & Security", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = GenieAccent)
                Spacer(modifier = Modifier.height(10.dp))
                SettingsItemCard(
                    icon = Icons.Default.Lock,
                    title = "Hardware Keystore",
                    subtitle = "API Keys stored with AES-256 GCM",
                    onClick = {}
                )
                Spacer(modifier = Modifier.height(8.dp))
                SettingsItemCard(
                    icon = Icons.Default.DeleteSweep,
                    title = "Clear Conversation Memory",
                    subtitle = "Wipe local cached messages & history",
                    onClick = onClearMemory
                )
                Spacer(modifier = Modifier.height(20.dp))
            }

            item {
                Text("About", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = GenieAccent)
                Spacer(modifier = Modifier.height(10.dp))
                SettingsItemCard(
                    icon = Icons.Default.Info,
                    title = "Genie AI Companion",
                    subtitle = "Version 1.0.0 (Production Native Build)",
                    onClick = {}
                )
            }
        }
    }
}

@Composable
fun SettingsItemCard(
    icon: ImageVector,
    title: String,
    subtitle: String,
    onClick: () -> Unit
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = GenieSurfaceDark),
        shape = RoundedCornerShape(16.dp),
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick)
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(icon, contentDescription = null, tint = GeniePrimary, modifier = Modifier.size(28.dp))
            Spacer(modifier = Modifier.width(16.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(title, fontWeight = FontWeight.SemiBold, fontSize = 16.sp)
                Text(subtitle, fontSize = 13.sp, color = Color(0xFF94A3B8))
            }
            Icon(Icons.Default.ChevronRight, contentDescription = null, tint = Color(0xFF64748B))
        }
    }
}
