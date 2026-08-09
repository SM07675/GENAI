package com.genie.ai.ui.screens

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.genie.ai.core.network.models.AssistantState
import com.genie.ai.core.network.models.HardwareStatus
import com.genie.ai.core.network.models.SecurityConfirmationRequest
import com.genie.ai.ui.components.GenieOrbView
import com.genie.ai.ui.components.SecurityConfirmationDialog
import com.genie.ai.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainAssistantScreen(
    assistantState: AssistantState,
    pcStatus: HardwareStatus,
    lastResponse: String,
    securityConfirmation: SecurityConfirmationRequest?,
    onMicClicked: () -> Unit,
    onSendPrompt: (String) -> Unit,
    onConfirmSecurityAction: (SecurityConfirmationRequest) -> Unit,
    onDismissSecurityAction: () -> Unit,
    onNavigateToPairing: () -> Unit
) {
    var promptInput by remember { mutableStateOf("") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("Genie AI", fontWeight = FontWeight.Bold)
                        Spacer(modifier = Modifier.width(12.dp))

                        // PC Connection Status Pill
                        Surface(
                            shape = RoundedCornerShape(16.dp),
                            color = if (pcStatus.isOnline) Color(0xFF10B981).copy(alpha = 0.15f) else Color(0xFFEF4444).copy(alpha = 0.15f),
                            border = androidx.compose.foundation.BorderStroke(
                                1.dp,
                                if (pcStatus.isOnline) Color(0xFF10B981) else Color(0xFFEF4444)
                            )
                        ) {
                            Row(
                                modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Box(
                                    modifier = Modifier
                                        .size(8.dp)
                                        .clip(CircleShape)
                                        .background(if (pcStatus.isOnline) Color(0xFF10B981) else Color(0xFFEF4444))
                                )
                                Spacer(modifier = Modifier.width(6.dp))
                                Text(
                                    text = if (pcStatus.isOnline) "PC Online" else "PC Offline",
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.Medium,
                                    color = if (pcStatus.isOnline) Color(0xFF10B981) else Color(0xFFEF4444)
                                )
                            }
                        }
                    }
                },
                actions = {
                    IconButton(onClick = onNavigateToPairing) {
                        Icon(Icons.Default.QrCodeScanner, contentDescription = "Pair PC")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = GenieBackgroundDark)
            )
        },
        containerColor = GenieBackgroundDark
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.SpaceBetween
        ) {

            // Top Status Bar (Telemetry: CPU / RAM / GPU)
            if (pcStatus.isOnline) {
                Card(
                    colors = CardDefaults.cardColors(containerColor = GenieSurfaceDark),
                    shape = RoundedCornerShape(16.dp),
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        horizontalArrangement = Arrangement.SpaceAround
                    ) {
                        TelemetryItem(label = "CPU", value = "${pcStatus.cpuPercent.toInt()}%")
                        TelemetryItem(label = "RAM", value = "${pcStatus.ramPercent.toInt()}%")
                        TelemetryItem(label = "GPU", value = "${pcStatus.gpuPercent}%")
                    }
                }
            } else {
                Spacer(modifier = Modifier.height(1.dp))
            }

            // Central Genie Orb UI
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
                modifier = Modifier.weight(1f)
            ) {
                GenieOrbView(state = assistantState)

                Spacer(modifier = Modifier.height(24.dp))

                // Assistant State Label
                Surface(
                    shape = RoundedCornerShape(20.dp),
                    color = GenieSurfaceDark
                ) {
                    Text(
                        text = assistantState.name,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Bold,
                        color = GenieAccent,
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp)
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))

                // Response text bubble
                if (lastResponse.isNotEmpty()) {
                    Card(
                        colors = CardDefaults.cardColors(containerColor = GenieSurfaceDark),
                        shape = RoundedCornerShape(18.dp),
                        modifier = Modifier.fillMaxWidth(0.9f)
                    ) {
                        Text(
                            text = lastResponse,
                            style = MaterialTheme.typography.bodyLarge,
                            modifier = Modifier.padding(16.dp)
                        )
                    }
                }
            }

            // Bottom Input Controls: Mic Button & Text Prompt
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 20.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    OutlinedTextField(
                        value = promptInput,
                        onValueChange = { promptInput = it },
                        placeholder = { Text("Ask Genie anything...", color = Color(0xFF64748B)) },
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(24.dp),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedContainerColor = GenieSurfaceDark,
                            unfocusedContainerColor = GenieSurfaceDark,
                            focusedBorderColor = GeniePrimary,
                            unfocusedBorderColor = GenieCardBorder
                        ),
                        trailingIcon = {
                            if (promptInput.isNotEmpty()) {
                                IconButton(onClick = {
                                    onSendPrompt(promptInput)
                                    promptInput = ""
                                }) {
                                    Icon(Icons.Default.Send, contentDescription = "Send", tint = GenieAccent)
                                }
                            }
                        }
                    )

                    Spacer(modifier = Modifier.width(12.dp))

                    // Microphone FAB Button
                    FloatingActionButton(
                        onClick = onMicClicked,
                        containerColor = if (assistantState == AssistantState.LISTENING) OrbListening else GeniePrimary,
                        shape = CircleShape
                    ) {
                        Icon(
                            imageVector = if (assistantState == AssistantState.LISTENING) Icons.Default.MicOff else Icons.Default.Mic,
                            contentDescription = "Microphone",
                            tint = Color.White
                        )
                    }
                }
            }
        }
    }

    // Security Confirmation Dialog Overlay
    securityConfirmation?.let { confReq ->
        SecurityConfirmationDialog(
            request = confReq,
            onConfirm = onConfirmSecurityAction,
            onDismiss = onDismissSecurityAction
        )
    }
}

@Composable
fun TelemetryItem(label: String, value: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(text = label, fontSize = 11.sp, color = Color(0xFF94A3B8))
        Text(text = value, fontSize = 15.sp, fontWeight = FontWeight.Bold, color = Color.White)
    }
}
