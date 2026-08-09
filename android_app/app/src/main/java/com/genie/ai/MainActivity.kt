package com.genie.ai

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.genie.ai.core.network.models.AssistantState
import com.genie.ai.core.network.models.HardwareStatus
import com.genie.ai.core.network.models.SecurityConfirmationRequest
import com.genie.ai.domain.voice.VoiceAssistantEngine
import com.genie.ai.ui.screens.*
import com.genie.ai.ui.theme.GenieAITheme
import com.genie.ai.ui.theme.GenieBackgroundDark
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private lateinit var app: GenieApplication
    private var voiceEngine: VoiceAssistantEngine? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate()
        app = application as GenieApplication

        setContent {
            GenieAITheme {
                val navController = rememberNavController()

                var assistantState by remember { mutableStateOf(AssistantState.IDLE) }
                var pcStatus by remember { mutableStateOf(HardwareStatus()) }
                var lastResponse by remember { mutableStateOf("Hello! I am Genie, your AI companion across phone & computer.") }
                var securityConfirmation by remember { mutableStateOf<SecurityConfirmationRequest?>(null) }

                val scope = rememberCoroutineScope()

                val discoveredPc by app.mdnsDiscoveryManager.discoveredPc.collectAsState()

                // Initialize Voice Engine
                DisposableEffect(Unit) {
                    voiceEngine = VoiceAssistantEngine(this@MainActivity) { text ->
                        assistantState = AssistantState.THINKING
                        lastResponse = "Processing voice command: '$text'..."

                        scope.launch {
                            val ip = app.keystoreManager.getPcIp() ?: "192.168.1.100"
                            val port = app.keystoreManager.getPcPort()
                            val res = app.apiClient.sendAssistantCommand(ip, port, text)

                            if (res["status"] == "requires_confirmation") {
                                securityConfirmation = SecurityConfirmationRequest(
                                    requestId = res["request_id"] as? String ?: "",
                                    confirmationToken = res["confirmation_token"] as? String ?: "",
                                    action = res["action"] as? String ?: "",
                                    message = res["message"] as? String ?: ""
                                )
                                assistantState = AssistantState.ERROR
                            } else {
                                lastResponse = (res["message"] as? String) ?: "Executed command."
                                assistantState = AssistantState.SUCCESS
                                voiceEngine?.speak(lastResponse)
                            }
                        }
                    }
                    app.mdnsDiscoveryManager.startDiscovery()

                    onDispose {
                        voiceEngine?.destroy()
                        app.mdnsDiscoveryManager.stopDiscovery()
                    }
                }

                // Poll hardware telemetry & WS listener
                LaunchedEffect(Unit) {
                    val ip = app.keystoreManager.getPcIp() ?: "192.168.1.100"
                    val port = app.keystoreManager.getPcPort()
                    val devId = app.keystoreManager.getDeviceId() ?: "dev_android_01"
                    app.webSocketManager.connect(ip, port, devId)

                    launch {
                        while (true) {
                            val status = app.apiClient.fetchPcStatus(ip, port)
                            pcStatus = status
                            if (!status.isOnline && assistantState == AssistantState.IDLE) {
                                assistantState = AssistantState.OFFLINE
                            } else if (status.isOnline && assistantState == AssistantState.OFFLINE) {
                                assistantState = AssistantState.IDLE
                            }
                            kotlinx.coroutines.delay(5000)
                        }
                    }

                    launch {
                        app.webSocketManager.incomingMessages.collectLatest { wsMsg ->
                            if (wsMsg.type == "security_confirmation_required") {
                                securityConfirmation = SecurityConfirmationRequest(
                                    requestId = wsMsg.requestId ?: "",
                                    confirmationToken = wsMsg.confirmationToken ?: "",
                                    action = wsMsg.action ?: "",
                                    message = wsMsg.message ?: "Security confirmation required."
                                )
                            } else if (wsMsg.type == "task_completed") {
                                assistantState = AssistantState.SUCCESS
                                lastResponse = wsMsg.message ?: "Task completed."
                            }
                        }
                    }
                }

                val navBackStackEntry by navController.currentBackStackEntryAsState()
                val currentRoute = navBackStackEntry?.destination?.route

                Scaffold(
                    bottomBar = {
                        NavigationBar(containerColor = GenieBackgroundDark) {
                            NavigationBarItem(
                                icon = { Icon(Icons.Default.Assistant, contentDescription = "Assistant") },
                                label = { Text("Genie") },
                                selected = currentRoute == "main",
                                onClick = { navController.navigate("main") }
                            )
                            NavigationBarItem(
                                icon = { Icon(Icons.Default.Devices, contentDescription = "Devices") },
                                label = { Text("Devices") },
                                selected = currentRoute == "devices",
                                onClick = { navController.navigate("devices") }
                            )
                            NavigationBarItem(
                                icon = { Icon(Icons.Default.Settings, contentDescription = "Settings") },
                                label = { Text("Settings") },
                                selected = currentRoute == "settings",
                                onClick = { navController.navigate("settings") }
                            )
                        }
                    }
                ) { paddingValues ->
                    NavHost(
                        navController = navController,
                        startDestination = "main",
                        modifier = Modifier.padding(paddingValues)
                    ) {
                        composable("main") {
                            MainAssistantScreen(
                                assistantState = assistantState,
                                pcStatus = pcStatus,
                                lastResponse = lastResponse,
                                securityConfirmation = securityConfirmation,
                                onMicClicked = {
                                    if (voiceEngine?.isListening?.value == true) {
                                        voiceEngine?.stopListening()
                                        assistantState = AssistantState.IDLE
                                    } else {
                                        assistantState = AssistantState.LISTENING
                                        voiceEngine?.startListening()
                                    }
                                },
                                onSendPrompt = { prompt ->
                                    assistantState = AssistantState.THINKING
                                    lastResponse = "Processing: '$prompt'..."
                                    scope.launch {
                                        val ip = app.keystoreManager.getPcIp() ?: "192.168.1.100"
                                        val port = app.keystoreManager.getPcPort()
                                        val res = app.apiClient.sendAssistantCommand(ip, port, prompt)

                                        if (res["status"] == "requires_confirmation") {
                                            securityConfirmation = SecurityConfirmationRequest(
                                                requestId = res["request_id"] as? String ?: "",
                                                confirmationToken = res["confirmation_token"] as? String ?: "",
                                                action = res["action"] as? String ?: "",
                                                message = res["message"] as? String ?: ""
                                            )
                                            assistantState = AssistantState.ERROR
                                        } else {
                                            lastResponse = (res["message"] as? String) ?: "Done."
                                            assistantState = AssistantState.SUCCESS
                                        }
                                    }
                                },
                                onConfirmSecurityAction = { conf ->
                                    securityConfirmation = null
                                    assistantState = AssistantState.EXECUTING
                                    scope.launch {
                                        val ip = app.keystoreManager.getPcIp() ?: "192.168.1.100"
                                        val port = app.keystoreManager.getPcPort()
                                        val res = app.apiClient.sendAssistantCommand(
                                            ip, port, "Confirmed action ${conf.action}", confirmed = true, token = conf.confirmationToken
                                        )
                                        lastResponse = (res["message"] as? String) ?: "Confirmed and executed."
                                        assistantState = AssistantState.SUCCESS
                                    }
                                },
                                onDismissSecurityAction = {
                                    securityConfirmation = null
                                    assistantState = AssistantState.IDLE
                                },
                                onNavigateToPairing = { navController.navigate("pairing") }
                            )
                        }

                        composable("pairing") {
                            QRPairingScreen(
                                discoveredPc = discoveredPc,
                                onBackClicked = { navController.popBackStack() },
                                onManualConnect = { ip, port ->
                                    app.keystoreManager.saveDeviceCredentials("dev_android_01", "token", ip, port)
                                    app.webSocketManager.connect(ip, port, "dev_android_01")
                                    navController.popBackStack()
                                },
                                onPairWithToken = { token, ip, port ->
                                    scope.launch {
                                        val res = app.apiClient.confirmPair(ip, port, token, "dev_android_01", "My Android Phone")
                                        if (res != null) {
                                            app.keystoreManager.saveDeviceCredentials(res.first, res.second, ip, port)
                                            app.webSocketManager.connect(ip, port, res.first)
                                            navController.popBackStack()
                                        }
                                    }
                                }
                            )
                        }

                        composable("devices") {
                            DevicesScreen(
                                pcStatus = pcStatus,
                                pcIp = app.keystoreManager.getPcIp() ?: "192.168.1.100",
                                pcPort = app.keystoreManager.getPcPort(),
                                onReconnect = {
                                    val ip = app.keystoreManager.getPcIp() ?: "192.168.1.100"
                                    val port = app.keystoreManager.getPcPort()
                                    val devId = app.keystoreManager.getDeviceId() ?: "dev_android_01"
                                    app.webSocketManager.connect(ip, port, devId)
                                },
                                onDisconnect = { app.webSocketManager.disconnect() }
                            )
                        }

                        composable("settings") {
                            SettingsScreen(
                                keystoreManager = app.keystoreManager,
                                onNavigateToProviders = { navController.navigate("providers") },
                                onClearMemory = {
                                    scope.launch { app.database.conversationDao().clearAll() }
                                }
                            )
                        }

                        composable("providers") {
                            AIProvidersScreen(
                                keystoreManager = app.keystoreManager,
                                onBackClicked = { navController.popBackStack() }
                            )
                        }
                    }
                }
            }
        }
    }
}
