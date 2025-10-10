"""
IPC Utilities - Shared patterns for IPC command handlers

This module provides reusable utilities to eliminate code duplication across
all IPC command handlers, ensuring consistent error handling, logging, and
response formatting.
"""

from __future__ import annotations

from typing import Dict, Any, Callable, TypeVar, ParamSpec
from functools import wraps

from .logging_utils import get_logger

logger = get_logger(__name__)

P = ParamSpec('P')
R = TypeVar('R', bound=Dict[str, Any])


def ipc_handler(command_type: str):
    """
    Decorator for IPC command handlers that provides standardized:
    - Error handling and logging
    - Response formatting
    - Type field injection
    - Exception catching

    Usage:
        @ipc_handler("detect_cameras")
        def handle_detect_cameras(command: Dict[str, Any]) -> Dict[str, Any]:
            cameras = camera_manager.detect_cameras()
            return {"success": True, "cameras": cameras}

    The decorator will automatically:
    - Add "type" field to response
    - Catch and format exceptions
    - Log errors
    - Ensure consistent response structure
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(command: Dict[str, Any], *args: P.args, **kwargs: P.kwargs) -> Dict[str, Any]:
            try:
                logger.debug(f"Processing IPC command: {command_type}")
                result = func(command, *args, **kwargs)

                # Ensure response has type field
                if "type" not in result:
                    result["type"] = command_type

                # Ensure success field is present
                if "success" not in result:
                    result["success"] = True

                logger.debug(f"IPC command {command_type} completed successfully")
                return result

            except Exception as e:
                logger.error(f"Error in IPC handler {command_type}: {e}", exc_info=True)
                return {
                    "success": False,
                    "type": command_type,
                    "error": str(e),
                }

        return wrapper
    return decorator


def format_success_response(
    command_type: str,
    message: str | None = None,
    **extra_fields: Any
) -> Dict[str, Any]:
    """
    Format a standardized success response for IPC commands.

    Args:
        command_type: The command type identifier
        message: Optional success message
        **extra_fields: Additional fields to include in response

    Returns:
        Standardized success response dictionary
    """
    response = {
        "success": True,
        "type": command_type,
    }

    if message:
        response["message"] = message

    response.update(extra_fields)
    return response


def format_error_response(
    command_type: str,
    error: str | Exception,
    **extra_fields: Any
) -> Dict[str, Any]:
    """
    Format a standardized error response for IPC commands.

    Args:
        command_type: The command type identifier
        error: Error message or exception
        **extra_fields: Additional fields to include in response

    Returns:
        Standardized error response dictionary
    """
    response = {
        "success": False,
        "type": command_type,
        "error": str(error),
    }

    response.update(extra_fields)
    return response


def validate_required_fields(
    command: Dict[str, Any],
    *required_fields: str
) -> Dict[str, Any] | None:
    """
    Validate that a command contains required fields.

    Args:
        command: The command dictionary to validate
        *required_fields: Names of required fields

    Returns:
        Error response dict if validation fails, None if valid
    """
    missing_fields = [
        field for field in required_fields
        if field not in command or command[field] is None
    ]

    if missing_fields:
        return {
            "success": False,
            "error": f"Missing required fields: {', '.join(missing_fields)}",
        }

    return None
