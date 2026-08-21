# Genie AI OS — Architecture Specification

## Overview

Genie is an agentic, multimodal, autonomous AI operating system companion designed for continuous computer use, desktop productivity, research, coding, and context-aware assistance.

```text
                               ┌─────────────────────────┐
                               │       GENIE AI OS       │
                               └────────────┬────────────┘
                                            │
                               ┌────────────▼────────────┐
                               │    PERCEPTION LAYER     │
                               │  Voice • Screen • App   │
                               └────────────┬────────────┘
                                            │
                               ┌────────────▼────────────┐
                               │      GOAL ENGINE        │
                               │  Intent & Constraints   │
                               └────────────┬────────────┘
                                            │
                               ┌────────────▼────────────┐
                               │   AUTONOMOUS PLANNER    │
                               │  Execution Graph (DAG)  │
                               └────────────┬────────────┘
                                            │
                               ┌────────────▼────────────┐
                               │      AGENT ROUTER       │
                               └────────────┬────────────┘
                                            │
     ┌─────────────┬─────────────┬──────────┴───┬─────────────┬─────────────┐
     ↓             ↓             ↓              ↓             ↓             ↓
  Research      Coding         File          System        Browser        Data
   Agent         Agent         Agent          Agent         Agent        Agent
     └─────────────┴─────────────┼──────────────┴─────────────┴─────────────┘
                                 │
                               ┌─▼───────────────────────┐
                               │      TOOL EXECUTOR      │
                               │  Permission Boundaries  │
                               └─────────┬───────────────┘
                                         │
                               ┌─────────▼───────────────┐
                               │   OBSERVATION ENGINE    │
                               │  DOM • FS • Screenshot  │
                               └─────────┬───────────────┘
                                         │
                               ┌─────────▼───────────────┐
                               │   VERIFICATION ENGINE   │
                               └─────────┬───────────────┘
                                         │
                               ┌─────────▼───────────────┐
                               │     RECOVERY ENGINE     │
                               │  Retry • Replan • Alter │
                               └─────────┬───────────────┘
                                         │
                               ┌─────────▼───────────────┐
                               │     MEMORY SERVICE      │
                               │ Short • Working • Long  │
                               └─────────────────────────┘
```

---

## Key Subsystems

### 1. Agent Runtime (`backend/app/runtime/agent_runtime.py`)
- Central lifecycle coordinator for multi-step goals.
- Owns task graphs, execution loops, pause/resume/cancel controls, and real-time WebSocket event broadcasts.

### 2. Goal Engine (`backend/app/runtime/goal_engine.py`)
- Distinguishes simple fast queries (single-turn chat) from complex goals (multi-step planning).
- Extracts objectives, constraints, expected deliverables, and capability requirements.

### 3. Autonomous Planner (`backend/app/runtime/planner.py`)
- Formulates directed acyclic graphs (DAGs) of executable plan steps.
- Handles autonomous replanning when obstacles occur, preserving already completed milestones.

### 4. Task Graph (`backend/app/runtime/task_graph.py`)
- Executes plan steps with topological dependency resolution.
- Runs independent steps concurrently and manages step-level timeouts.

### 5. Specialized Agents (`backend/app/agents/`)
- **GeneralAgent**: General reasoning, conversation, and synthesis.
- **ResearchAgent**: Web searches, source comparisons, news briefings, fact extraction.
- **CodingAgent**: Code comprehension, debugging, test execution, refactoring.
- **FileAgent**: Filesystem traversal, creation, modification, conversion.
- **SystemAgent**: Application launches, window management, audio levels, screenshots.
- **MediaAgent**: YouTube and YouTube Music streaming controls.
- **BrowserAgent**: Web navigation, page interaction, extraction.
- **DataAgent**: Python script generation, execution, and data analysis.
- **DocumentAgent**: PDF, DOCX, PPTX structure generation.
- **ProductivityAgent**: Notes, reminders, and schedules.

### 6. Tool Executor & Permission Boundary (`backend/app/runtime/tool_executor.py`, `backend/app/runtime/autonomy.py`)
- Inspects side-effect levels (Read-Only, Local Change, External Network, Personal Data, Destructive, Account).
- Enforces user autonomy levels: **Manual**, **Assist**, **Balanced**, and **Autonomous**.

### 7. Observation & Verification (`backend/app/runtime/observation_engine.py`, `backend/app/runtime/verification_engine.py`)
- Collects concrete post-action evidence from filesystem, processes, exit codes, DOM, and tools.
- Asserts that actions actually succeeded before declaring steps complete.

### 8. Cognitive Memory Service (`backend/app/runtime/memory_service.py`)
- Short-term dialogue buffer
- Working memory for active task state
- Long-term persistent facts with semantic vector search
- Episodic history of past missions
- User preference memory and project context

### 9. Model Router (`backend/app/runtime/model_router.py`)
- Unified role-based model router (Fast, Reasoning, Coding, Vision, Embeddings).
- Prioritizes local GGUF models where viable, falling back to resilient cloud provider pools.

### 10. Desktop UI Shell (`frontend/src/`)
- Hero **Genie Core Orb** with real-time state visualization (idle, listening, thinking, planning, executing, verifying, speaking, success, error).
- **Task Workspace**: Live DAG plan progression, agent badges, execution timeline, and evidence inspector.
- **Global Command Bar**: Universal `Ctrl+K` launcher for autonomous goals and slash commands.
- **Missions View**: Historical and active task tracker.
