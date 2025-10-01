"""IPC message schemas."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, ConfigDict

__all__ = [
    "BaseMessage",
    "ControlMessage",
    "SyncMessagePayload",
    "HealthMessagePayload",
]


class BaseMessage(BaseModel):
    type: str
    model_config = ConfigDict(extra="allow")


class ControlMessage(BaseMessage):
    messageId: Optional[str] = None
    success: Optional[bool] = None
    error: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class SyncMessagePayload(BaseMessage):
    state: Optional[str] = None
    display_text: Optional[str] = None
    is_ready: Optional[bool] = None
    is_error: Optional[bool] = None
    timestamp: float
    details: Optional[Dict[str, Any]] = None
    error_detail: Optional[str] = Field(None, alias="error")
    parameters: Optional[Dict[str, Any]] = None
    parameter_config: Optional[Dict[str, Any]] = None


class HealthMessagePayload(BaseModel):
    timestamp_us: int
    backend_fps: float
    frame_buffer_usage_percent: float
    memory_usage_mb: float
    cpu_usage_percent: float
    active_threads: int
    stimulus_active: bool
    camera_active: bool
