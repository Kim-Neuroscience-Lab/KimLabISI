"""
Display Calibration Infrastructure

Provides display calibration functionality for the ISI macroscope system,
including gamma correction, color calibration, and spatial mapping.
"""

from __future__ import annotations
from typing import Dict, List, Tuple, Optional, Any, Union
from pydantic import BaseModel, Field
from pathlib import Path
import numpy as np
import json
import logging
from datetime import datetime, timedelta
from enum import Enum

from ....domain.entities.hardware import Display


logger = logging.getLogger(__name__)


class DisplayCalibrationMode(Enum):
    """Display calibration modes"""
    GAMMA_CORRECTION = "gamma_correction"
    COLOR_PROFILE = "color_profile"
    SPATIAL_MAPPING = "spatial_mapping"
    UNIFORMITY_CORRECTION = "uniformity_correction"


class ColorSpace(Enum):
    """Color space specifications"""
    SRGB = "sRGB"
    ADOBE_RGB = "AdobeRGB"
    REC2020 = "Rec2020"
    DCI_P3 = "DCI-P3"


class GammaCorrection(BaseModel):
    """Gamma correction parameters"""
    red_gamma: float
    green_gamma: float
    blue_gamma: float
    luminance_curve: np.ndarray
    measurement_date: datetime
    target_gamma: float = 2.2

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "red_gamma": float(self.red_gamma),
            "green_gamma": float(self.green_gamma),
            "blue_gamma": float(self.blue_gamma),
            "luminance_curve": self.luminance_curve.tolist(),
            "measurement_date": self.measurement_date.isoformat(),
            "target_gamma": float(self.target_gamma)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GammaCorrection:
        """Create from dictionary"""
        return cls(
            red_gamma=data["red_gamma"],
            green_gamma=data["green_gamma"],
            blue_gamma=data["blue_gamma"],
            luminance_curve=np.array(data["luminance_curve"]),
            measurement_date=datetime.fromisoformat(data["measurement_date"]),
            target_gamma=data.get("target_gamma", 2.2)
        )


class ColorProfile(BaseModel):
    """Color profile calibration"""
    color_space: ColorSpace
    white_point: Tuple[float, float]  # CIE xy coordinates
    primaries: np.ndarray  # RGB primary coordinates (3x2)
    color_matrix: np.ndarray  # 3x3 transformation matrix
    max_luminance: float  # cd/m�
    measurement_date: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "color_space": self.color_space.value,
            "white_point": list(self.white_point),
            "primaries": self.primaries.tolist(),
            "color_matrix": self.color_matrix.tolist(),
            "max_luminance": float(self.max_luminance),
            "measurement_date": self.measurement_date.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ColorProfile:
        """Create from dictionary"""
        return cls(
            color_space=ColorSpace(data["color_space"]),
            white_point=tuple(data["white_point"]),
            primaries=np.array(data["primaries"]),
            color_matrix=np.array(data["color_matrix"]),
            max_luminance=data["max_luminance"],
            measurement_date=datetime.fromisoformat(data["measurement_date"])
        )


class SpatialMapping(BaseModel):
    """Spatial calibration mapping"""
    display_corners: np.ndarray  # 4x2 array of corner coordinates
    mapping_matrix: np.ndarray  # Perspective transformation matrix
    distortion_coefficients: Optional[np.ndarray] = None
    pixel_pitch: Tuple[float, float] = (0.0, 0.0)  # �m per pixel
    measurement_date: Optional[datetime] = None

    def __post_init__(self):
        if self.measurement_date is None:
            self.measurement_date = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "display_corners": self.display_corners.tolist(),
            "mapping_matrix": self.mapping_matrix.tolist(),
            "distortion_coefficients": self.distortion_coefficients.tolist() if self.distortion_coefficients is not None else None,
            "pixel_pitch": list(self.pixel_pitch),
            "measurement_date": self.measurement_date.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SpatialMapping:
        """Create from dictionary"""
        return cls(
            display_corners=np.array(data["display_corners"]),
            mapping_matrix=np.array(data["mapping_matrix"]),
            distortion_coefficients=np.array(data["distortion_coefficients"]) if data.get("distortion_coefficients") else None,
            pixel_pitch=tuple(data["pixel_pitch"]),
            measurement_date=datetime.fromisoformat(data["measurement_date"])
        )


class UniformityCorrection(BaseModel):
    """Display uniformity correction"""
    correction_map: np.ndarray  # Spatial correction factors
    vignetting_correction: np.ndarray  # Radial correction
    measurement_points: np.ndarray  # Grid points where measurements were taken
    uniformity_score: float  # 0-1, higher is more uniform
    measurement_date: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "correction_map": self.correction_map.tolist(),
            "vignetting_correction": self.vignetting_correction.tolist(),
            "measurement_points": self.measurement_points.tolist(),
            "uniformity_score": float(self.uniformity_score),
            "measurement_date": self.measurement_date.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> UniformityCorrection:
        """Create from dictionary"""
        return cls(
            correction_map=np.array(data["correction_map"]),
            vignetting_correction=np.array(data["vignetting_correction"]),
            measurement_points=np.array(data["measurement_points"]),
            uniformity_score=data["uniformity_score"],
            measurement_date=datetime.fromisoformat(data["measurement_date"])
        )


class DisplayCalibrationResult(BaseModel):
    """Complete display calibration result"""
    display_id: str
    gamma_correction: Optional[GammaCorrection] = None
    color_profile: Optional[ColorProfile] = None
    spatial_mapping: Optional[SpatialMapping] = None
    uniformity_correction: Optional[UniformityCorrection] = None
    calibration_date: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.calibration_date is None:
            self.calibration_date = datetime.now()


class DisplayCalibrationError(Exception):
    """Raised when display calibration fails"""
    pass


class DisplayCalibrator:
    """
    Display calibration infrastructure component

    Handles display calibration including gamma correction, color profiles,
    spatial mapping, and uniformity correction for the macroscope system.
    """

    def __init__(
        self,
        calibration_data_path: Path,
        colorimeter_available: bool = False,
        photometer_available: bool = False
    ):
        self.calibration_data_path = Path(calibration_data_path)
        self.colorimeter_available = colorimeter_available
        self.photometer_available = photometer_available

        # Create calibration directory
        self.calibration_data_path.mkdir(parents=True, exist_ok=True)

        # Calibration cache
        self._calibration_cache: Dict[str, DisplayCalibrationResult] = {}

        # Standard color spaces
        self._standard_color_spaces = self._initialize_standard_color_spaces()

        logger.info(
            f"Display calibrator initialized with colorimeter={colorimeter_available}, "
            f"photometer={photometer_available}"
        )

    def _initialize_standard_color_spaces(self) -> Dict[ColorSpace, Dict[str, Any]]:
        """Initialize standard color space definitions"""
        return {
            ColorSpace.SRGB: {
                "white_point": (0.3127, 0.3290),  # D65
                "primaries": np.array([
                    [0.64, 0.33],   # Red
                    [0.30, 0.60],   # Green
                    [0.15, 0.06]    # Blue
                ]),
                "gamma": 2.2
            },
            ColorSpace.ADOBE_RGB: {
                "white_point": (0.3127, 0.3290),  # D65
                "primaries": np.array([
                    [0.64, 0.33],   # Red
                    [0.21, 0.71],   # Green
                    [0.15, 0.06]    # Blue
                ]),
                "gamma": 2.2
            },
            ColorSpace.REC2020: {
                "white_point": (0.3127, 0.3290),  # D65
                "primaries": np.array([
                    [0.708, 0.292],  # Red
                    [0.170, 0.797],  # Green
                    [0.131, 0.046]   # Blue
                ]),
                "gamma": 2.4
            }
        }

    async def calibrate_gamma(
        self,
        display: Display,
        measurement_function: Optional[callable] = None,
        target_gamma: float = 2.2
    ) -> GammaCorrection:
        """
        Calibrate gamma correction for display

        Args:
            display: Display entity to calibrate
            measurement_function: Function to measure luminance
            target_gamma: Target gamma value

        Returns:
            GammaCorrection result
        """
        try:
            logger.info(f"Starting gamma calibration for display {display.component_id}")

            # Generate test patterns (gray levels 0-255)
            test_levels = np.linspace(0, 255, 32).astype(int)

            # Measure luminance for each test level
            if measurement_function and self.photometer_available:
                luminance_values = await self._measure_luminance(
                    display, test_levels, measurement_function
                )
            else:
                # Use model-based estimation for testing
                luminance_values = self._estimate_luminance(test_levels, target_gamma)

            # Fit gamma curves for each channel
            red_gamma, green_gamma, blue_gamma = self._fit_gamma_curves(
                test_levels, luminance_values, target_gamma
            )

            # Create luminance curve
            full_levels = np.arange(256)
            luminance_curve = self._generate_luminance_curve(full_levels, target_gamma)

            result = GammaCorrection(
                red_gamma=red_gamma,
                green_gamma=green_gamma,
                blue_gamma=blue_gamma,
                luminance_curve=luminance_curve,
                measurement_date=datetime.now(),
                target_gamma=target_gamma
            )

            logger.info(
                f"Gamma calibration completed for {display.component_id}: "
                f"R={red_gamma:.3f}, G={green_gamma:.3f}, B={blue_gamma:.3f}"
            )

            return result

        except Exception as e:
            logger.exception(f"Gamma calibration failed for {display.component_id}")
            raise DisplayCalibrationError(f"Gamma calibration failed: {str(e)}")

    async def calibrate_color_profile(
        self,
        display: Display,
        target_color_space: ColorSpace,
        measurement_function: Optional[callable] = None
    ) -> ColorProfile:
        """
        Calibrate color profile for display

        Args:
            display: Display entity to calibrate
            target_color_space: Target color space
            measurement_function: Function to measure color coordinates

        Returns:
            ColorProfile result
        """
        try:
            logger.info(
                f"Starting color profile calibration for display {display.component_id} "
                f"to {target_color_space.value}"
            )

            # Get target color space parameters
            target_params = self._standard_color_spaces[target_color_space]

            if measurement_function and self.colorimeter_available:
                # Measure actual display primaries
                measured_primaries = await self._measure_primaries(display, measurement_function)
                measured_white_point = await self._measure_white_point(display, measurement_function)
                max_luminance = await self._measure_max_luminance(display, measurement_function)
            else:
                # Use target values for testing/simulation
                measured_primaries = target_params["primaries"]
                measured_white_point = target_params["white_point"]
                max_luminance = 100.0  # cd/m�

            # Calculate color transformation matrix
            color_matrix = self._calculate_color_matrix(
                measured_primaries, measured_white_point, target_params
            )

            result = ColorProfile(
                color_space=target_color_space,
                white_point=measured_white_point,
                primaries=measured_primaries,
                color_matrix=color_matrix,
                max_luminance=max_luminance,
                measurement_date=datetime.now()
            )

            logger.info(f"Color profile calibration completed for {display.component_id}")
            return result

        except Exception as e:
            logger.exception(f"Color profile calibration failed for {display.component_id}")
            raise DisplayCalibrationError(f"Color profile calibration failed: {str(e)}")

    async def calibrate_spatial_mapping(
        self,
        display: Display,
        reference_points: np.ndarray,
        measured_points: np.ndarray
    ) -> SpatialMapping:
        """
        Calibrate spatial mapping between logical and physical coordinates

        Args:
            display: Display entity to calibrate
            reference_points: Reference coordinates (Nx2)
            measured_points: Measured coordinates (Nx2)

        Returns:
            SpatialMapping result
        """
        try:
            logger.info(f"Starting spatial mapping calibration for display {display.component_id}")

            # Calculate perspective transformation matrix
            mapping_matrix = self._calculate_perspective_transform(
                reference_points, measured_points
            )

            # Determine display corners (for full display area)
            display_corners = self._calculate_display_corners(mapping_matrix, display)

            # Calculate pixel pitch if possible
            pixel_pitch = self._calculate_pixel_pitch(reference_points, measured_points)

            # Calculate distortion coefficients (if significant distortion detected)
            distortion_coefficients = self._calculate_distortion(
                reference_points, measured_points, mapping_matrix
            )

            result = SpatialMapping(
                display_corners=display_corners,
                mapping_matrix=mapping_matrix,
                distortion_coefficients=distortion_coefficients,
                pixel_pitch=pixel_pitch,
                measurement_date=datetime.now()
            )

            logger.info(f"Spatial mapping calibration completed for {display.component_id}")
            return result

        except Exception as e:
            logger.exception(f"Spatial mapping calibration failed for {display.component_id}")
            raise DisplayCalibrationError(f"Spatial mapping calibration failed: {str(e)}")

    async def calibrate_uniformity(
        self,
        display: Display,
        measurement_function: Optional[callable] = None,
        grid_size: Tuple[int, int] = (9, 9)
    ) -> UniformityCorrection:
        """
        Calibrate display uniformity correction

        Args:
            display: Display entity to calibrate
            measurement_function: Function to measure luminance at points
            grid_size: Grid size for uniformity measurements

        Returns:
            UniformityCorrection result
        """
        try:
            logger.info(f"Starting uniformity calibration for display {display.component_id}")

            # Generate measurement grid
            measurement_points = self._generate_measurement_grid(grid_size)

            if measurement_function and self.photometer_available:
                # Measure luminance at each grid point
                luminance_map = await self._measure_uniformity_grid(
                    display, measurement_points, measurement_function
                )
            else:
                # Generate simulated uniformity map
                luminance_map = self._simulate_uniformity_map(measurement_points)

            # Calculate uniformity score
            uniformity_score = self._calculate_uniformity_score(luminance_map)

            # Generate correction maps
            correction_map = self._generate_correction_map(luminance_map)
            vignetting_correction = self._generate_vignetting_correction(
                measurement_points, luminance_map
            )

            result = UniformityCorrection(
                correction_map=correction_map,
                vignetting_correction=vignetting_correction,
                measurement_points=measurement_points,
                uniformity_score=uniformity_score,
                measurement_date=datetime.now()
            )

            logger.info(
                f"Uniformity calibration completed for {display.component_id}: "
                f"uniformity_score={uniformity_score:.3f}"
            )

            return result

        except Exception as e:
            logger.exception(f"Uniformity calibration failed for {display.component_id}")
            raise DisplayCalibrationError(f"Uniformity calibration failed: {str(e)}")

    # Helper methods for measurements and calculations
    async def _measure_luminance(
        self, display: Display, test_levels: np.ndarray, measurement_func: callable
    ) -> np.ndarray:
        """Measure luminance values for test levels"""
        luminance_values = []
        for level in test_levels:
            # Display test pattern at given level
            luminance = await measurement_func(display, level)
            luminance_values.append(luminance)
        return np.array(luminance_values)

    def _estimate_luminance(self, test_levels: np.ndarray, gamma: float) -> np.ndarray:
        """Estimate luminance values using gamma model"""
        normalized_levels = test_levels / 255.0
        return np.power(normalized_levels, gamma) * 100.0  # Assume 100 cd/m� max

    def _fit_gamma_curves(
        self, test_levels: np.ndarray, luminance_values: np.ndarray, target_gamma: float
    ) -> Tuple[float, float, float]:
        """Fit gamma curves for RGB channels"""
        # For simplicity, assume similar gamma for all channels
        # In practice, would fit separate curves
        try:
            from scipy.optimize import curve_fit

            def gamma_function(x, gamma, scale):
                return scale * np.power(x / 255.0, gamma)

            popt, _ = curve_fit(gamma_function, test_levels, luminance_values)
            fitted_gamma = popt[0]

            return fitted_gamma, fitted_gamma, fitted_gamma

        except ImportError:
            # Fallback to target gamma
            return target_gamma, target_gamma, target_gamma

    def _generate_luminance_curve(self, levels: np.ndarray, gamma: float) -> np.ndarray:
        """Generate luminance curve for given gamma"""
        normalized_levels = levels / 255.0
        return np.power(normalized_levels, gamma)

    async def _measure_primaries(self, display: Display, measurement_func: callable) -> np.ndarray:
        """Measure RGB primary coordinates"""
        # Would display pure R, G, B and measure CIE xy coordinates
        # For now, return standard sRGB primaries
        return self._standard_color_spaces[ColorSpace.SRGB]["primaries"]

    async def _measure_white_point(self, display: Display, measurement_func: callable) -> Tuple[float, float]:
        """Measure white point coordinates"""
        # Would display white and measure CIE xy coordinates
        return self._standard_color_spaces[ColorSpace.SRGB]["white_point"]

    async def _measure_max_luminance(self, display: Display, measurement_func: callable) -> float:
        """Measure maximum display luminance"""
        # Would display white at maximum level and measure
        return 100.0  # cd/m�

    def _calculate_color_matrix(
        self,
        measured_primaries: np.ndarray,
        measured_white_point: Tuple[float, float],
        target_params: Dict[str, Any]
    ) -> np.ndarray:
        """Calculate color transformation matrix"""
        # Simplified color matrix calculation
        # In practice, would use proper colorimetric calculations
        return np.eye(3)

    def _calculate_perspective_transform(
        self, reference_points: np.ndarray, measured_points: np.ndarray
    ) -> np.ndarray:
        """Calculate perspective transformation matrix"""
        try:
            import cv2
            return cv2.getPerspectiveTransform(
                reference_points.astype(np.float32),
                measured_points.astype(np.float32)
            )
        except ImportError:
            # Return identity matrix as fallback
            return np.eye(3)

    def _calculate_display_corners(self, mapping_matrix: np.ndarray, display: Display) -> np.ndarray:
        """Calculate display corner coordinates"""
        # Assume display resolution from display entity
        width, height = 1920, 1080  # Default resolution
        corners = np.array([
            [0, 0],
            [width, 0],
            [width, height],
            [0, height]
        ], dtype=np.float32)
        return corners

    def _calculate_pixel_pitch(
        self, reference_points: np.ndarray, measured_points: np.ndarray
    ) -> Tuple[float, float]:
        """Calculate pixel pitch in micrometers"""
        # Simplified calculation
        return (25.4, 25.4)  # Assume ~25.4 �m/pixel (100 DPI)

    def _calculate_distortion(
        self,
        reference_points: np.ndarray,
        measured_points: np.ndarray,
        mapping_matrix: np.ndarray
    ) -> Optional[np.ndarray]:
        """Calculate distortion coefficients"""
        # Check if distortion is significant enough to warrant correction
        # For now, return None (no distortion correction)
        return None

    def _generate_measurement_grid(self, grid_size: Tuple[int, int]) -> np.ndarray:
        """Generate uniformity measurement grid points"""
        rows, cols = grid_size
        x = np.linspace(0.1, 0.9, cols)
        y = np.linspace(0.1, 0.9, rows)
        xx, yy = np.meshgrid(x, y)
        return np.column_stack([xx.ravel(), yy.ravel()])

    async def _measure_uniformity_grid(
        self,
        display: Display,
        measurement_points: np.ndarray,
        measurement_func: callable
    ) -> np.ndarray:
        """Measure luminance at grid points"""
        luminance_values = []
        for point in measurement_points:
            luminance = await measurement_func(display, point)
            luminance_values.append(luminance)
        return np.array(luminance_values)

    def _simulate_uniformity_map(self, measurement_points: np.ndarray) -> np.ndarray:
        """Generate simulated uniformity map for testing"""
        # Simulate typical LCD vignetting pattern
        center = np.array([0.5, 0.5])
        distances = np.linalg.norm(measurement_points - center, axis=1)
        # Luminance drops off toward edges
        luminance_map = 100.0 * (1.0 - 0.2 * distances)
        return luminance_map

    def _calculate_uniformity_score(self, luminance_map: np.ndarray) -> float:
        """Calculate uniformity score (0-1, higher is better)"""
        mean_luminance = np.mean(luminance_map)
        std_luminance = np.std(luminance_map)
        # Simple uniformity score based on coefficient of variation
        cv = std_luminance / mean_luminance if mean_luminance > 0 else 1.0
        uniformity_score = max(0.0, 1.0 - cv)
        return uniformity_score

    def _generate_correction_map(self, luminance_map: np.ndarray) -> np.ndarray:
        """Generate uniformity correction map"""
        max_luminance = np.max(luminance_map)
        correction_map = max_luminance / luminance_map
        # Clamp correction factors to reasonable range
        correction_map = np.clip(correction_map, 0.5, 2.0)
        return correction_map

    def _generate_vignetting_correction(
        self, measurement_points: np.ndarray, luminance_map: np.ndarray
    ) -> np.ndarray:
        """Generate radial vignetting correction"""
        center = np.array([0.5, 0.5])
        distances = np.linalg.norm(measurement_points - center, axis=1)

        # Fit polynomial to luminance vs distance
        coefficients = np.polyfit(distances, luminance_map, 2)

        return coefficients

    async def load_calibration(self, display_id: str) -> Optional[DisplayCalibrationResult]:
        """Load existing calibration for display"""
        if display_id in self._calibration_cache:
            return self._calibration_cache[display_id]

        calibration_file = self.calibration_data_path / f"{display_id}_display_calibration.json"
        if calibration_file.exists():
            try:
                with open(calibration_file, 'r') as f:
                    data = json.load(f)

                result = DisplayCalibrationResult(display_id=display_id)

                if "gamma_correction" in data:
                    result.gamma_correction = GammaCorrection.from_dict(data["gamma_correction"])

                if "color_profile" in data:
                    result.color_profile = ColorProfile.from_dict(data["color_profile"])

                if "spatial_mapping" in data:
                    result.spatial_mapping = SpatialMapping.from_dict(data["spatial_mapping"])

                if "uniformity_correction" in data:
                    result.uniformity_correction = UniformityCorrection.from_dict(data["uniformity_correction"])

                result.calibration_date = datetime.fromisoformat(data["calibration_date"])
                result.metadata = data.get("metadata")

                self._calibration_cache[display_id] = result
                return result

            except Exception as e:
                logger.error(f"Failed to load display calibration for {display_id}: {e}")
                return None

        return None

    async def _save_calibration(self, result: DisplayCalibrationResult):
        """Save calibration result to file"""
        calibration_file = self.calibration_data_path / f"{result.display_id}_display_calibration.json"

        try:
            calibration_data = {
                "display_id": result.display_id,
                "calibration_date": result.calibration_date.isoformat(),
                "metadata": result.metadata
            }

            if result.gamma_correction:
                calibration_data["gamma_correction"] = result.gamma_correction.to_dict()

            if result.color_profile:
                calibration_data["color_profile"] = result.color_profile.to_dict()

            if result.spatial_mapping:
                calibration_data["spatial_mapping"] = result.spatial_mapping.to_dict()

            if result.uniformity_correction:
                calibration_data["uniformity_correction"] = result.uniformity_correction.to_dict()

            with open(calibration_file, 'w') as f:
                json.dump(calibration_data, f, indent=2)

            logger.info(f"Display calibration saved for {result.display_id}")

        except Exception as e:
            logger.error(f"Failed to save display calibration for {result.display_id}: {e}")
            raise DisplayCalibrationError(f"Failed to save calibration: {str(e)}")

    def list_calibrated_displays(self) -> List[str]:
        """List all displays with valid calibrations"""
        calibrated_displays = []

        # Check cached calibrations
        for display_id in self._calibration_cache:
            calibrated_displays.append(display_id)

        # Check saved calibrations
        for calibration_file in self.calibration_data_path.glob("*_display_calibration.json"):
            display_id = calibration_file.stem.replace("_display_calibration", "")
            if display_id not in calibrated_displays:
                calibrated_displays.append(display_id)

        return calibrated_displays