package com.genie.ai.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.QrCode
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.genie.ai.core.network.DiscoveredPC
import com.genie.ai.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun QRPairingScreen(
    discoveredPc: DiscoveredPC?,
    onBackClicked: () -> Unit,
    onManualConnect: (String, Int) -> Unit,
    onPairWithToken: (String, String, Int) -> Unit
) {
    var ipInput by remember { mutableStateOf(discoveredPc?.hostAddress ?: "192.168.1.100") }
    var portInput by remember { mutableStateOf(discoveredPc?.port?.toString() ?: "8000") }
    var qrTokenInput by remember { mutableStateOf("") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Pair PC Genie Hub", fontWeight = FontWeight.Bold) },
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
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(20.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {

            // Discovered Service Banner
            discoveredPc?.let { pc ->
                Card(
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF10B981).copy(alpha = 0.15f)),
                    shape = RoundedCornerShape(16.dp),
                    modifier = Modifier.fillMaxWidth().padding(bottom = 20.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(Icons.Default.Wifi, contentDescription = null, tint = Color(0xFF10B981))
                        Spacer(modifier = Modifier.width(12.dp))
                        Column {
                            Text("Discovered Genie PC on Wi-Fi!", fontWeight = FontWeight.Bold, color = Color(0xFF10B981))
                            Text("${pc.serviceName} (${pc.hostAddress}:${pc.port})", fontSize = 13.sp, color = Color.White)
                        }
                    }
                }
            }

            // QR Scanner Simulation / Code Input Section
            Card(
                colors = CardDefaults.cardColors(containerColor = GenieSurfaceDark),
                shape = RoundedCornerShape(20.dp),
                modifier = Modifier.fillMaxWidth().padding(bottom = 20.dp)
            ) {
                Column(
                    modifier = Modifier.padding(20.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Icon(
                        imageVector = Icons.Default.QrCode,
                        contentDescription = "QR Scanner",
                        modifier = Modifier.size(64.dp),
                        tint = GenieAccent
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    Text("Scan QR Code from PC", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                    Text("Point camera at PC screen QR code (GENIE://PAIR)", fontSize = 13.sp, color = Color(0xFF94A3B8))

                    Spacer(modifier = Modifier.height(16.dp))

                    OutlinedTextField(
                        value = qrTokenInput,
                        onValueChange = { qrTokenInput = it },
                        label = { Text("Paste QR Pairing Token") },
                        placeholder = { Text("qr_abc123...") },
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp)
                    )

                    Spacer(modifier = Modifier.height(12.dp))

                    Button(
                        onClick = {
                            if (qrTokenInput.isNotEmpty()) {
                                onPairWithToken(qrTokenInput, ipInput, portInput.toIntOrNull() ?: 8000)
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                        enabled = qrTokenInput.isNotEmpty(),
                        colors = ButtonDefaults.buttonColors(containerColor = GeniePrimary)
                    ) {
                        Text("Complete Pairing")
                    }
                }
            }

            // Manual Connection Fallback
            Card(
                colors = CardDefaults.cardColors(containerColor = GenieSurfaceDark),
                shape = RoundedCornerShape(20.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Text("Manual IP Connection", fontWeight = FontWeight.Bold, fontSize = 16.sp)
                    Spacer(modifier = Modifier.height(12.dp))

                    OutlinedTextField(
                        value = ipInput,
                        onValueChange = { ipInput = it },
                        label = { Text("PC IP Address") },
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp)
                    )

                    Spacer(modifier = Modifier.height(8.dp))

                    OutlinedTextField(
                        value = portInput,
                        onValueChange = { portInput = it },
                        label = { Text("Port") },
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp)
                    )

                    Spacer(modifier = Modifier.height(16.dp))

                    OutlinedButton(
                        onClick = { onManualConnect(ipInput, portInput.toIntOrNull() ?: 8000) },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text("Connect directly to IP")
                    }
                }
            }
        }
    }
}
