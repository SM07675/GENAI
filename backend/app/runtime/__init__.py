"""Genie Agent Runtime — the agentic core of Genie AI OS.

This package implements the full agent lifecycle:
    Goal → Plan → TaskGraph → Agent → Tool → Observe → Verify → Recover → Memory

Submodules:
    schemas          — Shared data models (Goal, AgentState, Observation, etc.)
    goal_engine      — Intent extraction and goal decomposition
    planner          — Autonomous plan generation with LLM
    task_graph       — DAG-based task execution engine
    agent_router     — Routes plan steps to specialized agents
    tool_executor    — Permissioned tool execution with timeout
    observation_engine — Post-action evidence collection
    verification_engine — Result validation
    recovery_engine  — Intelligent failure handling and replanning
    agent_runtime    — Central runtime orchestrating the full lifecycle
    memory_service   — Unified memory interface
    context_service  — Continuous context engine
    model_router     — Unified model routing
    personality      — Personality layer
    interrupt_handler — User interrupt handling
    autonomy         — Progressive autonomy settings
"""
