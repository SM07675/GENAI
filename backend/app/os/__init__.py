"""Genie OS kernel primitives.

These modules are intentionally small and dependency-light. They provide the
task/event backbone that the current assistant can route through while the
larger Genie OS migration happens module by module.
"""
from .events import EventEnvelope
from .kernel import GenieOSKernel, get_kernel
from .permissions import PermissionRequest, PermissionStatus, SideEffectLevel
from .tasks import TaskRecord, TaskRegistry, TaskStatus

__all__ = [
    "EventEnvelope",
    "GenieOSKernel",
    "PermissionRequest",
    "PermissionStatus",
    "SideEffectLevel",
    "TaskRecord",
    "TaskRegistry",
    "TaskStatus",
    "get_kernel",
]
