package com.genie.ai.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Computer
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.genie.ai.core.network.models.HardwareStatus
import com.genie.ai.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DevicesScreen(
    pcStatus: HardwareStatus,
    pcIp: String,
    pcPort: Int,
    onReconnect: () -> Unit,
    onDisconnect: () -> Unit
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Connected Devices", fontWeight = FontWeight.Bold) },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = GenieBackgroundDark)
            )
        },
        containerColor = GenieBackgroundDark
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(20.dp)
        ) {
            Card(
                colors = CardDefaults.cardColors(containerColor = GenieSurfaceDark),
                shape = RoundedCornerShape(20.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.Computer,
                            contentDescription = "PC",
                            tint = GenieAccent,
                            modifier = Modifier.size(36.dp)
                        )
                        Spacer(modifier = Modifier.width(16.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            Text("Primary PC Hub", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                            Text("$pcIp:$pcPort", fontSize = 13.sp, color = Color(0xFF94A3B8))
                        }
                        Surface(
                            shape = RoundedCornerShape(12.dp),
                            color = if (pcStatus.isOnline) Color(0xFF10B981).copy(alpha = 0.2f) else Color(0xFFEF4444).copy(alpha = 0.2f)
                        ) {
                            Text(
                                text = if (pcStatus.isOnline) "Online" else "Offline",
                                modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                color = if (pcStatus.isOnline) Color(0xFF10B981) else Color(0xFFEF4444)
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(20.dp))
                    Divider(color = GenieCardBorder)
                    Spacer(modifier = Modifier.height(16.dp))

                    Text("System Performance Telemetry", fontSize = 14.sp, fontWeight = FontWeight.SemiBold, color = GenieAccent)
                    Spacer(modifier = Modifier.height(12.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        MetricCard(title = "CPU Usage", value = "${pcStatus.cpuPercent.toInt()}%")
                        MetricCard(title = "RAM Usage", value = "${pcStatus.ramPercent.toInt()}%")
                        MetricCard(title = "GPU (${pcStatus.gpuName})", value = "${pcStatus.gpuPercent}%")
                    }

                    Spacer(modifier = Modifier.height(24.dp))

                    Row(modifier = Modifier.fillMaxWidth()) {
                        OutlinedButton(
                            onClick = onReconnect,
                            modifier = Modifier.weight(1f)
                        ) {
                            Icon(Icons.Default.Refresh, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(6.dp))
                            Text("Reconnect")
                        }
                        Spacer(modifier = Modifier.width(12.dp))
                        Button(
                            onClick = onDisconnect,
                            modifier = Modifier.weight(1f),
                            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
                        ) {
                            Text("Disconnect")
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun MetricCard(title: String, value: String) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = GenieBackgroundDark,
        modifier = Modifier.padding(4.dp)
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(title, fontSize = 11.sp, color = Color(0xFF94A3B8))
            Text(value, fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Color.White)
        }
    }
}
