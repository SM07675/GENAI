"""
Aura AI 2.0 – Real-Time Communication Engine.

This package implements the full voice conversation pipeline:

    Microphone audio
        → Voice Activity Detection   (voice_activity.py)
        → Speech-to-Text             (speech_to_text.py)
        → Context Building           (context_builder.py)
        → AI Gateway                 (ai_gateway.py)
        → Response Streaming         (streaming.py)
        → Text-to-Speech             (text_to_speech.py)
        → WebSocket audio output

The engine is coordinated by SessionManager (session_manager.py) and
orchestrated per-session by VoiceConversationManager (conversation_manager.py).
All state transitions are enforced by StateMachine (state_machine.py).

Public entry points
-------------------
VoiceSession          — one live voice conversation
SessionRegistry       — registry of all active sessions
VoiceWebSocketManager — WebSocket protocol handler (used by the API route)
"""

from app.communication.session_manager import SessionRegistry, VoiceSession
from app.communication.state_machine import CommunicationState, StateMachine
from app.communication.websocket_manager import VoiceWebSocketManager

__all__ = [
    "CommunicationState",
    "StateMachine",
    "VoiceSession",
    "SessionRegistry",
    "VoiceWebSocketManager",
]
