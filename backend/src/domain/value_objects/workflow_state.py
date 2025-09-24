"""
Workflow State Value Objects

This module contains immutable value objects for the ISI Macroscope Control System's
workflow state management, following Clean Architecture principles.

Value Objects:
- WorkflowState: Enum of possible workflow states
- HardwareRequirement: Enum of hardware capability requirements
- WorkflowTransition: Immutable record of state transitions
"""

from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class WorkflowState(Enum):
    """12-state workflow states for ISI Macroscope Control System"""

    # Primary Workflow States (9 states)
    STARTUP = "startup"
    SETUP_READY = "setup_ready"
    SETUP = "setup"
    GENERATION_READY = "generation_ready"
    GENERATION = "generation"
    ACQUISITION_READY = "acquisition_ready"
    ACQUISITION = "acquisition"
    ANALYSIS_READY = "analysis_ready"
    ANALYSIS = "analysis"

    # Error Handling States (3 states)
    ERROR = "error"
    RECOVERY = "recovery"
    DEGRADED = "degraded"


class HardwareRequirement(Enum):
    """Hardware requirements for workflow states"""
    MINIMAL = "minimal"  # Display only for error reporting
    DISPLAY = "display"  # Display hardware (RTX 4070 or dev-mode)
    GPU = "gpu"  # GPU with CUDA support
    CAMERA = "camera"  # PCO Panda 4.2 camera
    STORAGE = "storage"  # High-speed storage (Samsung 990 PRO)
    ALL_HARDWARE = "all_hardware"  # Complete production hardware
    DEV_MODE_BYPASS = "dev_mode_bypass"  # Development mode allows bypass


class WorkflowTransition(BaseModel):
    """Immutable workflow state transition record using Pydantic V2"""
    from_state: WorkflowState
    to_state: WorkflowState
    timestamp: datetime = Field(description="Timestamp when transition occurred")
    user_initiated: bool = Field(description="Whether transition was user-initiated")
    validation_passed: bool = Field(description="Whether transition validation passed")
    hardware_available: bool = Field(description="Whether required hardware was available")
    error_message: Optional[str] = Field(None, description="Error message if transition failed")

    model_config = {"frozen": True, "use_enum_values": True}