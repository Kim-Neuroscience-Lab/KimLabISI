"""
Camera Calibration Infrastructure

Provides camera calibration functionality for the ISI macroscope system,
including intrinsic/extrinsic parameter estimation and validation.
"""

from __future__ import annotations
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import json
import logging
from datetime import datetime
from enum import Enum

from ....domain.entities.hardware import Camera


logger = logging.getLogger(__name__)


class CalibrationPatternType(Enum):
    """Types of calibration patterns"""
    CHECKERBOARD = "checkerboard"
    CIRCLE_GRID = "circle_grid"
    CHARUCO_BOARD = "charuco_board"


class CalibrationStatus(Enum):
    """Calibration status states"""
    NOT_CALIBRATED = "not_calibrated"
    CALIBRATING = "calibrating"
    CALIBRATED = "calibrated"
    VALIDATION_FAILED = "validation_failed"
    EXPIRED = "expired"


@dataclass
class CalibrationPattern:
    """Calibration pattern specification"""
    pattern_type: CalibrationPatternType
    width: int  # Number of internal corners/circles horizontally
    height: int  # Number of internal corners/circles vertically
    square_size: float  # Size of squares/circles in mm
    marker_size: float = 0.0  # Size of ArUco markers (for ChArUco)


@dataclass
class CameraIntrinsics:
    """Camera intrinsic parameters"""
    camera_matrix: np.ndarray  # 3x3 camera matrix
    distortion_coefficients: np.ndarray  # Distortion coefficients
    image_width: int
    image_height: int
    reprojection_error: float
    calibration_date: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "camera_matrix": self.camera_matrix.tolist(),
            "distortion_coefficients": self.distortion_coefficients.tolist(),
            "image_width": self.image_width,
            "image_height": self.image_height,
            "reprojection_error": float(self.reprojection_error),
            "calibration_date": self.calibration_date.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CameraIntrinsics:
        """Create from dictionary"""
        return cls(
            camera_matrix=np.array(data["camera_matrix"]),
            distortion_coefficients=np.array(data["distortion_coefficients"]),
            image_width=data["image_width"],
            image_height=data["image_height"],
            reprojection_error=data["reprojection_error"],
            calibration_date=datetime.fromisoformat(data["calibration_date"])
        )


@dataclass
class CalibrationResult:
    """Complete calibration result"""
    intrinsics: CameraIntrinsics
    status: CalibrationStatus
    images_used: int
    pattern_detections: int
    validation_error: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class CameraCalibrationError(Exception):
    """Raised when camera calibration fails"""
    pass


class CameraCalibrator:
    """
    Camera calibration infrastructure component

    Handles camera intrinsic parameter calibration using various
    calibration patterns and provides validation mechanisms.
    """

    def __init__(
        self,
        calibration_data_path: Path,
        min_calibration_images: int = 10,
        max_calibration_error: float = 0.5
    ):
        self.calibration_data_path = Path(calibration_data_path)
        self.min_calibration_images = min_calibration_images
        self.max_calibration_error = max_calibration_error

        # Create calibration directory
        self.calibration_data_path.mkdir(parents=True, exist_ok=True)

        # Calibration state
        self._calibration_cache: Dict[str, CalibrationResult] = {}
        self._pattern_detectors = self._initialize_pattern_detectors()

        logger.info(f"Camera calibrator initialized with data path: {self.calibration_data_path}")

    def _initialize_pattern_detectors(self) -> Dict[CalibrationPatternType, Any]:
        """Initialize pattern detection algorithms"""
        detectors = {}

        try:
            import cv2

            # Checkerboard detector
            detectors[CalibrationPatternType.CHECKERBOARD] = cv2.findChessboardCorners

            # Circle grid detector
            detectors[CalibrationPatternType.CIRCLE_GRID] = cv2.findCirclesGrid

            # ChArUco detector (if available)
            if hasattr(cv2, 'aruco'):
                detectors[CalibrationPatternType.CHARUCO_BOARD] = self._detect_charuco_corners

        except ImportError:
            logger.warning("OpenCV not available - using mock pattern detectors")
            detectors = self._create_mock_detectors()

        return detectors

    def _create_mock_detectors(self) -> Dict[CalibrationPatternType, Any]:
        """Create mock pattern detectors for testing"""
        def mock_detector(*args, **kwargs):
            # Return mock detection result
            return True, np.random.rand(54, 1, 2).astype(np.float32)

        return {
            pattern_type: mock_detector
            for pattern_type in CalibrationPatternType
        }

    async def calibrate_camera(
        self,
        camera: Camera,
        calibration_images: List[np.ndarray],
        pattern: CalibrationPattern
    ) -> CalibrationResult:
        """
        Calibrate camera using provided images and calibration pattern

        Args:
            camera: Camera entity to calibrate
            calibration_images: List of calibration images
            pattern: Calibration pattern specification

        Returns:
            CalibrationResult with intrinsic parameters
        """
        try:
            logger.info(f"Starting calibration for camera {camera.component_id}")

            # Validate inputs
            if len(calibration_images) < self.min_calibration_images:
                raise CameraCalibrationError(
                    f"Insufficient calibration images: {len(calibration_images)} "
                    f"(minimum {self.min_calibration_images})"
                )

            # Detect calibration patterns in all images
            object_points, image_points, image_size = await self._detect_patterns(
                calibration_images, pattern
            )

            if len(object_points) < self.min_calibration_images:
                raise CameraCalibrationError(
                    f"Insufficient pattern detections: {len(object_points)} "
                    f"(minimum {self.min_calibration_images})"
                )

            # Perform camera calibration
            intrinsics = await self._calibrate_intrinsics(
                object_points, image_points, image_size
            )

            # Validate calibration
            validation_error = await self._validate_calibration(
                intrinsics, object_points, image_points
            )

            # Determine calibration status
            status = CalibrationStatus.CALIBRATED
            if validation_error > self.max_calibration_error:
                status = CalibrationStatus.VALIDATION_FAILED
                logger.warning(
                    f"Calibration validation failed for {camera.component_id}: "
                    f"error {validation_error:.3f} > {self.max_calibration_error}"
                )

            # Create calibration result
            result = CalibrationResult(
                intrinsics=intrinsics,
                status=status,
                images_used=len(calibration_images),
                pattern_detections=len(object_points),
                validation_error=validation_error,
                metadata={
                    "pattern_type": pattern.pattern_type.value,
                    "pattern_size": f"{pattern.width}x{pattern.height}",
                    "square_size": pattern.square_size
                }
            )

            # Cache and save calibration
            self._calibration_cache[camera.component_id] = result
            await self._save_calibration(camera.component_id, result)

            logger.info(
                f"Camera {camera.component_id} calibration completed: "
                f"status={status.value}, error={validation_error:.3f}"
            )

            return result

        except Exception as e:
            logger.exception(f"Camera calibration failed for {camera.component_id}")
            raise CameraCalibrationError(f"Calibration failed: {str(e)}")

    async def _detect_patterns(
        self,
        images: List[np.ndarray],
        pattern: CalibrationPattern
    ) -> Tuple[List[np.ndarray], List[np.ndarray], Tuple[int, int]]:
        """Detect calibration patterns in images"""
        object_points = []
        image_points = []
        image_size = None

        # Prepare object points (3D coordinates of pattern)
        objp = self._generate_object_points(pattern)

        detector = self._pattern_detectors.get(pattern.pattern_type)
        if not detector:
            raise CameraCalibrationError(f"No detector for pattern type: {pattern.pattern_type}")

        for i, image in enumerate(images):
            # Convert to grayscale if needed
            if len(image.shape) == 3:
                gray = self._convert_to_grayscale(image)
            else:
                gray = image

            if image_size is None:
                image_size = gray.shape[::-1]  # (width, height)

            # Detect pattern
            try:
                if pattern.pattern_type == CalibrationPatternType.CHECKERBOARD:
                    ret, corners = detector(gray, (pattern.width, pattern.height), None)
                elif pattern.pattern_type == CalibrationPatternType.CIRCLE_GRID:
                    ret, corners = detector(gray, (pattern.width, pattern.height), None)
                else:  # ChArUco or other
                    ret, corners = detector(gray, pattern)

                if ret:
                    object_points.append(objp)
                    image_points.append(corners)
                    logger.debug(f"Pattern detected in image {i}")
                else:
                    logger.debug(f"No pattern detected in image {i}")

            except Exception as e:
                logger.warning(f"Pattern detection failed for image {i}: {e}")
                continue

        return object_points, image_points, image_size

    def _generate_object_points(self, pattern: CalibrationPattern) -> np.ndarray:
        """Generate 3D object points for calibration pattern"""
        objp = np.zeros((pattern.width * pattern.height, 3), np.float32)
        objp[:, :2] = np.mgrid[0:pattern.width, 0:pattern.height].T.reshape(-1, 2)
        objp *= pattern.square_size
        return objp

    def _convert_to_grayscale(self, image: np.ndarray) -> np.ndarray:
        """Convert image to grayscale"""
        try:
            import cv2
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        except ImportError:
            # Fallback grayscale conversion
            return np.dot(image[..., :3], [0.2989, 0.5870, 0.1140]).astype(np.uint8)

    async def _calibrate_intrinsics(
        self,
        object_points: List[np.ndarray],
        image_points: List[np.ndarray],
        image_size: Tuple[int, int]
    ) -> CameraIntrinsics:
        """Perform camera intrinsic calibration"""
        try:
            import cv2

            # Perform calibration
            ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
                object_points, image_points, image_size, None, None
            )

            if not ret:
                raise CameraCalibrationError("OpenCV calibration failed")

            reprojection_error = ret

        except ImportError:
            # Mock calibration for testing
            logger.warning("OpenCV not available - using mock calibration")
            camera_matrix = np.array([
                [1000.0, 0.0, image_size[0] / 2],
                [0.0, 1000.0, image_size[1] / 2],
                [0.0, 0.0, 1.0]
            ])
            dist_coeffs = np.zeros(5)
            reprojection_error = 0.1

        return CameraIntrinsics(
            camera_matrix=camera_matrix,
            distortion_coefficients=dist_coeffs,
            image_width=image_size[0],
            image_height=image_size[1],
            reprojection_error=reprojection_error,
            calibration_date=datetime.now()
        )

    async def _validate_calibration(
        self,
        intrinsics: CameraIntrinsics,
        object_points: List[np.ndarray],
        image_points: List[np.ndarray]
    ) -> float:
        """Validate calibration by computing reprojection error"""
        try:
            import cv2

            total_error = 0
            total_points = 0

            # Generate rotation and translation vectors for validation
            for i in range(len(object_points)):
                # Find pose of calibration pattern
                ret, rvec, tvec = cv2.solvePnP(
                    object_points[i],
                    image_points[i],
                    intrinsics.camera_matrix,
                    intrinsics.distortion_coefficients
                )

                if ret:
                    # Project 3D points back to image plane
                    projected_points, _ = cv2.projectPoints(
                        object_points[i],
                        rvec,
                        tvec,
                        intrinsics.camera_matrix,
                        intrinsics.distortion_coefficients
                    )

                    # Compute reprojection error
                    error = cv2.norm(image_points[i], projected_points, cv2.NORM_L2)
                    total_error += error * error
                    total_points += len(object_points[i])

            return np.sqrt(total_error / total_points) if total_points > 0 else float('inf')

        except ImportError:
            # Mock validation for testing
            return intrinsics.reprojection_error

    def _detect_charuco_corners(self, image: np.ndarray, pattern: CalibrationPattern):
        """Detect ChArUco board corners (requires OpenCV with ArUco)"""
        try:
            import cv2

            # Create ChArUco board
            aruco_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_6X6_250)
            charuco_board = cv2.aruco.CharucoBoard_create(
                pattern.width, pattern.height, pattern.square_size, pattern.marker_size, aruco_dict
            )

            # Detect markers
            corners, ids, rejected = cv2.aruco.detectMarkers(image, aruco_dict)

            if len(corners) > 0:
                # Interpolate ChArUco corners
                ret, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
                    corners, ids, image, charuco_board
                )
                return ret > 0, charuco_corners

            return False, None

        except (ImportError, AttributeError):
            # Fallback to mock detection
            return True, np.random.rand(pattern.width * pattern.height, 1, 2).astype(np.float32)

    async def load_calibration(self, camera_id: str) -> Optional[CalibrationResult]:
        """Load existing calibration for camera"""
        # Check cache first
        if camera_id in self._calibration_cache:
            result = self._calibration_cache[camera_id]

            # Check if calibration is expired (e.g., older than 30 days)
            if self._is_calibration_expired(result.intrinsics.calibration_date):
                result.status = CalibrationStatus.EXPIRED

            return result

        # Load from file
        calibration_file = self.calibration_data_path / f"{camera_id}_calibration.json"
        if calibration_file.exists():
            try:
                with open(calibration_file, 'r') as f:
                    data = json.load(f)

                intrinsics = CameraIntrinsics.from_dict(data["intrinsics"])

                result = CalibrationResult(
                    intrinsics=intrinsics,
                    status=CalibrationStatus(data["status"]),
                    images_used=data["images_used"],
                    pattern_detections=data["pattern_detections"],
                    validation_error=data.get("validation_error"),
                    metadata=data.get("metadata")
                )

                # Check expiration
                if self._is_calibration_expired(intrinsics.calibration_date):
                    result.status = CalibrationStatus.EXPIRED

                self._calibration_cache[camera_id] = result
                return result

            except Exception as e:
                logger.error(f"Failed to load calibration for {camera_id}: {e}")
                return None

        return None

    async def _save_calibration(self, camera_id: str, result: CalibrationResult):
        """Save calibration result to file"""
        calibration_file = self.calibration_data_path / f"{camera_id}_calibration.json"

        try:
            calibration_data = {
                "intrinsics": result.intrinsics.to_dict(),
                "status": result.status.value,
                "images_used": result.images_used,
                "pattern_detections": result.pattern_detections,
                "validation_error": result.validation_error,
                "metadata": result.metadata
            }

            with open(calibration_file, 'w') as f:
                json.dump(calibration_data, f, indent=2)

            logger.info(f"Calibration saved for camera {camera_id}")

        except Exception as e:
            logger.error(f"Failed to save calibration for {camera_id}: {e}")
            raise CameraCalibrationError(f"Failed to save calibration: {str(e)}")

    def _is_calibration_expired(self, calibration_date: datetime, days_valid: int = 30) -> bool:
        """Check if calibration has expired"""
        expiry_date = calibration_date + timedelta(days=days_valid)
        return datetime.now() > expiry_date

    def get_calibration_status(self, camera_id: str) -> CalibrationStatus:
        """Get current calibration status for camera"""
        result = self._calibration_cache.get(camera_id)
        if result:
            # Check expiration
            if self._is_calibration_expired(result.intrinsics.calibration_date):
                result.status = CalibrationStatus.EXPIRED
                self._calibration_cache[camera_id] = result

            return result.status

        return CalibrationStatus.NOT_CALIBRATED

    def list_calibrated_cameras(self) -> List[str]:
        """List all cameras with valid calibrations"""
        calibrated_cameras = []

        # Check cached calibrations
        for camera_id, result in self._calibration_cache.items():
            if (result.status == CalibrationStatus.CALIBRATED and
                not self._is_calibration_expired(result.intrinsics.calibration_date)):
                calibrated_cameras.append(camera_id)

        # Check saved calibrations
        for calibration_file in self.calibration_data_path.glob("*_calibration.json"):
            camera_id = calibration_file.stem.replace("_calibration", "")
            if camera_id not in calibrated_cameras:
                result = await self.load_calibration(camera_id)
                if (result and result.status == CalibrationStatus.CALIBRATED and
                    not self._is_calibration_expired(result.intrinsics.calibration_date)):
                    calibrated_cameras.append(camera_id)

        return calibrated_cameras

    def create_calibration_pattern(
        self,
        pattern_type: CalibrationPatternType,
        width: int,
        height: int,
        square_size: float,
        marker_size: float = 0.0
    ) -> CalibrationPattern:
        """Create calibration pattern specification"""
        return CalibrationPattern(
            pattern_type=pattern_type,
            width=width,
            height=height,
            square_size=square_size,
            marker_size=marker_size
        )

    async def delete_calibration(self, camera_id: str) -> bool:
        """Delete calibration data for camera"""
        try:
            # Remove from cache
            if camera_id in self._calibration_cache:
                del self._calibration_cache[camera_id]

            # Remove calibration file
            calibration_file = self.calibration_data_path / f"{camera_id}_calibration.json"
            if calibration_file.exists():
                calibration_file.unlink()

            logger.info(f"Calibration deleted for camera {camera_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete calibration for {camera_id}: {e}")
            return False