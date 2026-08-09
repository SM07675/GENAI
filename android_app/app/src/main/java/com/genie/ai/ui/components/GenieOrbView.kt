package com.genie.ai.ui.components

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.genie.ai.core.network.models.AssistantState
import com.genie.ai.ui.theme.*

/**
 * Custom Animated GPU-efficient Canvas Genie Orb rendering 8 distinct states:
 * IDLE, LISTENING, THINKING, SPEAKING, EXECUTING, SUCCESS, ERROR, OFFLINE.
 */
@Composable
fun GenieOrbView(
    state: AssistantState,
    modifier: Modifier = Modifier,
    size: Dp = 220.dp
) {
    val infiniteTransition = rememberInfiniteTransition(label = "GenieOrbTransition")

    // Pulse animation
    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 0.92f,
        targetValue = 1.08f,
        animationSpec = infiniteRepeatable(
            animation = tween(1400, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "OrbPulse"
    )

    // Rotation animation for THINKING / EXECUTING
    val rotationAngle by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(3000, easing = LinearEasing)
        ),
        label = "OrbRotation"
    )

    // Secondary ripple scale for LISTENING
    val rippleScale by infiniteTransition.animateFloat(
        initialValue = 0.8f,
        targetValue = 1.4f,
        animationSpec = infiniteRepeatable(
            animation = tween(1000, easing = FastOutLinearInEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "OrbRipple"
    )

    val (primaryColor, secondaryColor) = when (state) {
        AssistantState.IDLE -> Pair(OrbIdle, GenieAccent)
        AssistantState.LISTENING -> Pair(OrbListening, Color(0xFF38BDF8))
        AssistantState.THINKING -> Pair(OrbThinking, Color(0xFFA855F7))
        AssistantState.SPEAKING -> Pair(OrbSpeaking, Color(0xFFF472B6))
        AssistantState.EXECUTING -> Pair(OrbExecuting, Color(0xFFFBBF24))
        AssistantState.SUCCESS -> Pair(OrbSuccess, Color(0xFF34D399))
        AssistantState.ERROR -> Pair(OrbError, Color(0xFFF87171))
        AssistantState.OFFLINE -> Pair(OrbOffline, Color(0xFF94A3B8))
    }

    Box(
        modifier = modifier.size(size),
        contentAlignment = Alignment.Center
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val center = Offset(size.toPx() / 2f, size.toPx() / 2f)
            val baseRadius = (size.toPx() / 2f) * 0.55f

            // 1. Draw outer ripple for Listening state
            if (state == AssistantState.LISTENING) {
                drawCircle(
                    color = primaryColor.copy(alpha = (1.4f - rippleScale).coerceIn(0f, 0.4f)),
                    radius = baseRadius * rippleScale,
                    center = center,
                    style = Stroke(width = 4f)
                )
            }

            // 2. Draw outer rotating orbital ring for Thinking state
            if (state == AssistantState.THINKING || state == AssistantState.EXECUTING) {
                drawCircle(
                    brush = Brush.sweepGradient(
                        colors = listOf(primaryColor, secondaryColor, Color.Transparent, primaryColor)
                    ),
                    radius = baseRadius * 1.25f,
                    center = center,
                    style = Stroke(width = 6f)
                )
            }

            // 3. Main Glowing Core
            val currentRadius = when (state) {
                AssistantState.SPEAKING, AssistantState.LISTENING -> baseRadius * pulseScale
                AssistantState.OFFLINE -> baseRadius * 0.85f
                else -> baseRadius * pulseScale
            }

            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        secondaryColor.copy(alpha = 0.9f),
                        primaryColor.copy(alpha = 0.7f),
                        primaryColor.copy(alpha = 0.0f)
                    ),
                    center = center,
                    radius = currentRadius * 1.3f
                ),
                radius = currentRadius * 1.3f,
                center = center
            )

            drawCircle(
                brush = Brush.linearGradient(
                    colors = listOf(primaryColor, secondaryColor),
                    start = Offset(center.x - currentRadius, center.y - currentRadius),
                    end = Offset(center.x + currentRadius, center.y + currentRadius)
                ),
                radius = currentRadius,
                center = center
            )
        }
    }
}
