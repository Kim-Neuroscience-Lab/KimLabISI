"""Stimulus control interface for acquisition orchestration.

⚠️  WARNING: PREVIEW MODE ONLY - NOT FOR RECORD MODE

This module uses async/real-time stimulus generation and is ONLY suitable for preview mode.
For scientifically valid data recording, use CameraTriggeredStimulusController instead.

Record mode REQUIRES camera-triggered synchronous stimulus generation for perfect 1:1
frame correspondence between camera captures and stimulus frames.
"""

from typing import Dict, Any

from .logging_utils import get_logger

logger = get_logger(__name__)


class StimulusController:
    """
    Controls stimulus lifecycle for PREVIEW MODE ONLY.

    ⚠️  WARNING: DO NOT USE FOR RECORD MODE

    This class uses async stimulus generation (RealtimeFrameProducer) which is NOT
    scientifically valid for data recording. Record mode must use
    CameraTriggeredStimulusController for camera-triggered synchronous generation.

    Use Cases:
    - Preview mode: Testing stimulus appearance
    - Preview mode: Verifying stimulus parameters
    - Preview mode: Visual debugging

    NOT for:
    - Record mode (data acquisition)
    - Scientific experiments requiring timestamp accuracy
    - Any use case requiring camera-stimulus synchronization

    Provides a clean interface for starting/stopping stimuli without
    requiring direct imports of stimulus_manager IPC handlers.
    """

    def start_stimulus(
        self,
        direction: str,
        show_bar_mask: bool = True,
        fps: float = 60.0,
    ) -> Dict[str, Any]:
        """
        Start stimulus presentation.

        Args:
            direction: Stimulus direction (LR, RL, TB, BT)
            show_bar_mask: Whether to show the bar mask
            fps: Frame rate for stimulus presentation

        Returns:
            Dictionary with success status and message
        """
        # Import here to avoid circular dependency
        from .stimulus_manager import handle_start_stimulus

        try:
            result = handle_start_stimulus({
                "direction": direction,
                "show_bar_mask": show_bar_mask,
                "fps": fps,
            })

            if result.get("success"):
                logger.debug(f"Stimulus started: direction={direction}")
            else:
                logger.error(f"Failed to start stimulus: {result.get('error')}")

            return result

        except Exception as exc:
            logger.error(f"Exception starting stimulus: {exc}", exc_info=True)
            return {
                "success": False,
                "error": f"Exception starting stimulus: {exc}"
            }

    def stop_stimulus(self) -> Dict[str, Any]:
        """
        Stop stimulus presentation.

        Returns:
            Dictionary with success status and message
        """
        # Import here to avoid circular dependency
        from .stimulus_manager import handle_stop_stimulus

        try:
            result = handle_stop_stimulus({})

            if result.get("success"):
                logger.debug("Stimulus stopped")
            else:
                logger.error(f"Failed to stop stimulus: {result.get('error')}")

            return result

        except Exception as exc:
            logger.error(f"Exception stopping stimulus: {exc}", exc_info=True)
            return {
                "success": False,
                "error": f"Exception stopping stimulus: {exc}"
            }

    def is_presenting(self) -> bool:
        """
        Check if stimulus is currently presenting.

        Returns:
            True if stimulus is active
        """
        from .service_locator import get_services

        services = get_services()
        if hasattr(services, 'acquisition_state') and services.acquisition_state:
            return services.acquisition_state.stimulus_active

        return False
