package com.genie.ai.ui.components

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.text.font.FontWeight
import com.genie.ai.core.network.models.SecurityConfirmationRequest

/**
 * Material 3 Security Confirmation Dialog for dangerous operations.
 * Displays "Genie wants to perform this action" prompt with [Cancel] and [Allow] choices.
 */
@Composable
fun SecurityConfirmationDialog(
    request: SecurityConfirmationRequest,
    onConfirm: (SecurityConfirmationRequest) -> Unit,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        icon = {
            Icon(
                imageVector = Icons.Default.Warning,
                contentDescription = "Warning",
                tint = MaterialTheme.colorScheme.error
            )
        },
        title = {
            Text(
                text = "Confirmation Required",
                fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.headlineMedium
            )
        },
        text = {
            Text(
                text = request.message,
                style = MaterialTheme.typography.bodyLarge
            )
        },
        confirmButton = {
            Button(
                onClick = { onConfirm(request) },
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
            ) {
                Text("Allow Action")
            }
        },
        dismissButton = {
            OutlinedButton(onClick = onDismiss) {
                Text("Cancel")
            }
        }
    )
}
