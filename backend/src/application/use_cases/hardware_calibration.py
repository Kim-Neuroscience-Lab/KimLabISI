"""
Hardware Calibration Use Case

Orchestrates the complete hardware calibration workflow including camera calibration,
display calibration, and timing synchronization following Clean Architecture principles.
"""

from typing import Dict, Any, Optional
from datetime import datetime

from ...domain.services.error_handler import ErrorHandlingService, ISIDomainError
from ...infrastructure.hardware.factory import HardwareFactory
from ...infrastructure.hardware.calibration.camera_calibrator import CameraCalibrator
from ...infrastructure.hardware.calibration.display_calibrator import DisplayCalibrator


class HardwareCalibrationUseCase:
    """
    Use case for orchestrating hardware calibration procedures

    This use case coordinates the calibration of all hardware components
    required for ISI experiments, ensuring proper system setup.
    """

    def __init__(
        self,
        hardware_factory: HardwareFactory,
        camera_calibrator: CameraCalibrator,
        display_calibrator: DisplayCalibrator,
        error_handler: Optional[ErrorHandlingService] = None
    ):
        self.hardware_factory = hardware_factory
        self.camera_calibrator = camera_calibrator
        self.display_calibrator = display_calibrator
        self.error_handler = error_handler or ErrorHandlingService()

    async def calibrate_all_hardware(self) -> Dict[str, Any]:
        """
        Perform complete hardware calibration workflow

        Returns:
            Calibration results and status for all hardware components
        """
        try:
            calibration_results = {
                "calibration_timestamp": datetime.now().isoformat(),
                "camera_calibration": {},
                "display_calibration": {},
                "overall_status": "pending"
            }

            # Camera calibration
            camera_result = await self._calibrate_camera()
            calibration_results["camera_calibration"] = camera_result

            # Display calibration
            display_result = await self._calibrate_display()
            calibration_results["display_calibration"] = display_result

            # Determine overall status
            if camera_result["success"] and display_result["success"]:
                calibration_results["overall_status"] = "completed"
            else:
                calibration_results["overall_status"] = "failed"

            return calibration_results

        except Exception as e:
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="HARDWARE_CALIBRATION_ERROR",
                custom_message="Hardware calibration workflow failed",
                operation="calibrate_all_hardware"
            )
            raise ISIDomainError(domain_error)

    async def _calibrate_camera(self) -> Dict[str, Any]:
        """Calibrate camera system"""
        try:
            camera = self.hardware_factory.create_camera()

            # Perform camera calibration
            calibration_result = await self.camera_calibrator.calibrate_camera(camera)

            return {
                "success": True,
                "calibration_data": calibration_result,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def _calibrate_display(self) -> Dict[str, Any]:
        """Calibrate display system"""
        try:
            display = self.hardware_factory.create_display()

            # Perform display calibration
            calibration_result = await self.display_calibrator.calibrate_display(display)

            return {
                "success": True,
                "calibration_data": calibration_result,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def verify_calibration(self) -> Dict[str, Any]:
        """
        Verify that all hardware calibration is valid and current

        Returns:
            Verification results for all calibrated hardware
        """
        verification_results = {
            "camera_valid": False,
            "display_valid": False,
            "overall_valid": False,
            "verification_timestamp": datetime.now().isoformat()
        }

        try:
            # Verify camera calibration
            camera_valid = await self.camera_calibrator.verify_calibration()
            verification_results["camera_valid"] = camera_valid

            # Verify display calibration
            display_valid = await self.display_calibrator.verify_calibration()
            verification_results["display_valid"] = display_valid

            # Overall system valid if all components valid
            verification_results["overall_valid"] = camera_valid and display_valid

            return verification_results

        except Exception as e:
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="HARDWARE_CALIBRATION_ERROR",
                custom_message="Hardware calibration verification failed",
                operation="verify_calibration"
            )
            raise ISIDomainError(domain_error)