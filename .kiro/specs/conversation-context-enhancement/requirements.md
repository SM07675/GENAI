# Requirements Document

## Introduction

This feature enhances conversation context handling in the Genie AI assistant to ensure the system maintains conversational coherence across multiple user messages within a session. The current implementation maintains a session history list and injects the system prompt before each LLM call, but there are opportunities to improve how context is maintained, validated, and utilized for better conversational flow.

## Glossary

- **Session**: A persistent authenticated connection between a client and the Genie backend, identified by a session_id and associated token
- **Session_History**: The in-memory list of message dictionaries (role/content pairs) stored in the Session object
- **System_Prompt**: The instruction text loaded from `prompts/system_prompt.md` that defines Genie's behavior and capabilities
- **Message_Context**: The combined list of messages (system prompt + session history) sent to the LLM for each turn
- **Orchestrator**: The conversation handler module that manages the ReAct loop and tool calling flow
- **LLM_Client**: The module responsible for streaming chat completions from Gemini API
- **Turn**: A complete user-assistant interaction cycle, potentially including multiple tool calls

## Requirements

### Requirement 1: Conversation History Persistence

**User Story:** As a user, I want my conversation history to be maintained throughout my session, so that the assistant remembers what we've discussed.

#### Acceptance Criteria

1. WHEN a user message is received, THE Orchestrator SHALL append the message to Session_History before processing
2. WHEN an assistant response is generated, THE Orchestrator SHALL append the complete assistant message to Session_History after the turn completes
3. WHEN tool calls are executed, THE Orchestrator SHALL append both the tool_call message and the tool result message to Session_History
4. WHEN the LLM_Client constructs the Message_Context, THE LLM_Client SHALL include the System_Prompt followed by all messages from Session_History
5. THE Session_History SHALL maintain message order chronologically (oldest to newest)

### Requirement 2: Context Window Management

**User Story:** As a user, I want my conversations to work reliably even when they become lengthy, so that I can have extended interactions without errors.

#### Acceptance Criteria

1. WHEN Session_History exceeds a configured token limit, THE Orchestrator SHALL trim older messages while preserving recent context
2. THE Orchestrator SHALL preserve the System_Prompt regardless of history length
3. WHEN trimming Session_History, THE Orchestrator SHALL remove complete message pairs (user + assistant) to maintain conversational coherence
4. THE Orchestrator SHALL preserve at minimum the last N turns (configurable, default 10) in Session_History
5. WHERE token counting is available, THE Orchestrator SHALL use approximate token counts to determine when trimming is needed

### Requirement 3: Context Validation

**User Story:** As a developer, I want the system to validate conversation context, so that malformed messages don't cause errors or unexpected behavior.

#### Acceptance Criteria

1. WHEN a message is appended to Session_History, THE Orchestrator SHALL validate that the message contains required fields (role, content or tool_calls)
2. IF a message lacks required fields, THEN THE Orchestrator SHALL log a warning and normalize the message structure
3. WHEN constructing Message_Context, THE LLM_Client SHALL verify that tool_call messages are followed by corresponding tool result messages
4. IF the message sequence is invalid, THEN THE Orchestrator SHALL reconstruct a valid sequence or start a fresh context
5. THE Session SHALL maintain a validation state flag indicating whether Session_History is in a consistent state

### Requirement 4: Language Tag Consistency

**User Story:** As a user speaking Hindi or Hinglish, I want the assistant to maintain language awareness throughout the conversation, so that responses match my language preference.

#### Acceptance Criteria

1. WHEN a user message is detected as Hindi/Hinglish, THE Orchestrator SHALL tag the message with a language indicator
2. WHERE a language preference is detected, THE Session SHALL store the preferred language for the session
3. WHEN appending messages to Session_History, THE Orchestrator SHALL apply consistent language tagging based on session preference
4. THE System_Prompt SHALL include language-aware instructions for multilingual responses
5. WHEN a user switches languages mid-conversation, THE Orchestrator SHALL update the session language preference

### Requirement 5: Tool Call Context Preservation

**User Story:** As a user, I want the assistant to remember which tools it has used and their results, so that it can reason about previous actions and avoid redundant operations.

#### Acceptance Criteria

1. WHEN a tool is executed, THE Orchestrator SHALL append the tool_call message with function name and arguments to Session_History
2. WHEN a tool returns a result, THE Orchestrator SHALL append the tool result message with tool_call_id and content to Session_History
3. WHEN vision tool results are processed, THE Orchestrator SHALL append the vision model's interpretation to Session_History
4. THE Message_Context SHALL include all tool interactions so the LLM can reference previous tool usage
5. WHEN the same tool is called multiple times, THE Session_History SHALL maintain separate entries for each invocation

### Requirement 6: Session State Recovery

**User Story:** As a user reconnecting after a disconnection, I want to resume my conversation where I left off, so that I don't lose context.

#### Acceptance Criteria

1. WHEN a client reconnects with a valid session token, THE Session SHALL retrieve the existing Session_History
2. THE Session SHALL maintain Session_History in memory for the duration of the session token TTL
3. WHEN a session expires, THE System SHALL remove the Session and its Session_History from memory
4. WHERE a session_id is provided via REST API, THE System SHALL locate and reuse the existing Session_History
5. THE Session SHALL update the last_seen timestamp on each interaction to prevent premature expiration

### Requirement 7: Context Debugging and Observability

**User Story:** As a developer debugging conversation issues, I want visibility into the context being sent to the LLM, so that I can diagnose problems with context handling.

#### Acceptance Criteria

1. WHERE debug logging is enabled, THE Orchestrator SHALL log the Message_Context structure before each LLM call
2. THE Orchestrator SHALL log the size of Session_History (message count and approximate token count)
3. WHEN context trimming occurs, THE Orchestrator SHALL log which messages were removed
4. WHERE a validation error occurs, THE Orchestrator SHALL log the invalid message structure
5. THE System SHALL expose a debug endpoint that returns the current Session_History for a given session token (development only)

### Requirement 8: System Prompt Injection Strategy

**User Story:** As a developer, I want a consistent and efficient system prompt injection strategy, so that the LLM receives appropriate instructions without wasting tokens.

#### Acceptance Criteria

1. THE Orchestrator SHALL load System_Prompt once at module initialization and cache it
2. WHEN constructing Message_Context, THE LLM_Client SHALL inject System_Prompt as the first message with role "system"
3. THE System_Prompt SHALL include instructions for tool usage, language handling, and conversation style
4. WHERE the System_Prompt file is modified, THE System SHALL reload the prompt on the next server restart
5. THE System_Prompt SHALL be excluded from Session_History to avoid duplication

### Requirement 9: Conversation Coherence Testing

**User Story:** As a developer, I want automated tests for conversation coherence, so that I can verify context handling works correctly.

#### Acceptance Criteria

1. THE System SHALL include unit tests that verify Session_History maintenance across multiple turns
2. THE System SHALL include tests that verify tool call context is properly preserved
3. THE System SHALL include tests that verify context trimming preserves conversation coherence
4. THE System SHALL include tests that verify language tag consistency
5. THE System SHALL include integration tests that simulate multi-turn conversations with tool usage

### Requirement 10: Error Recovery in Context Handling

**User Story:** As a user, I want the assistant to recover gracefully from context-related errors, so that my conversation continues without interruption.

#### Acceptance Criteria

1. IF Session_History becomes corrupted, THEN THE Orchestrator SHALL start a fresh history while preserving the session
2. WHEN an LLM API error occurs due to context issues, THE Orchestrator SHALL retry with trimmed context
3. IF context construction fails, THEN THE Orchestrator SHALL notify the user and reset to a minimal context
4. THE Orchestrator SHALL not crash or disconnect the session due to context handling errors
5. WHEN recovering from an error, THE Orchestrator SHALL log the error details for debugging
