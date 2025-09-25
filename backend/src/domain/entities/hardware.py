"""
Hardware Entity Domain Objects for ISI Macroscope System

Hardware entities represent the physical components of the ISI macroscope
system with status tracking and capability definitions.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
import json
import logging
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class HardwareStatus(Enum):
    """Hardware component status states"""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    BUSY = "busy"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class HardwareType(Enum):
    """Types of hardware components in the ISI system"""

    CAMERA = "camera"
    ILLUMINATION = "illumination"
    DISPLAY = "display"
    STAGE = "stage"
    FILTER_WHEEL = "filter_wheel"
    STORAGE = "storage"
    COMPUTE = "compute"


class CameraModel(Enum):
    """Supported camera models"""

    PCO_PANDA = "pco_panda"
    PCO_EDGE = "pco_edge"
    XIMEA_XISPEC = "ximea_xispec"
    BASLER_ACE = "basler_ace"
    GENERIC = "generic"


class DisplayType(Enum):
    """Display system types"""

    LCD_MONITOR = "lcd_monitor"
    LED_ARRAY = "led_array"
    PROJECTOR = "projector"
    OLED_DISPLAY = "oled_display"


class HardwareCapabilities(BaseModel):
    """Hardware capabilities and specifications"""

    max_resolution: tuple[int, int] = (0, 0)
    bit_depth: int = 16
    max_frame_rate: float = 30.0
    wavelength_range: tuple[float, float] = (400.0, 700.0)  # nm
    custom_properties: Dict[str, Any] = Field(default_factory=dict)

    def supports_resolution(self, width: int, height: int) -> bool:
        """Check if hardware supports specific resolution"""
        return width <= self.max_resolution[0] and height <= self.max_resolution[1]

    def supports_frame_rate(self, fps: float) -> bool:
        """Check if hardware supports frame rate"""
        return fps <= self.max_frame_rate


class HardwareConfiguration(BaseModel):
    """Hardware configuration settings"""

    exposure_time_ms: Optional[float] = None
    gain: Optional[float] = None
    binning: tuple[int, int] = (1, 1)
    roi: Optional[tuple[int, int, int, int]] = None  # x, y, width, height
    temperature_setpoint: Optional[float] = None
    custom_settings: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "exposure_time_ms": self.exposure_time_ms,
            "gain": self.gain,
            "binning": self.binning,
            "roi": self.roi,
            "temperature_setpoint": self.temperature_setpoint,
            "custom_settings": self.custom_settings,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> HardwareConfiguration:
        """Create from dictionary"""
        return cls(
            exposure_time_ms=data.get("exposure_time_ms"),
            gain=data.get("gain"),
            binning=tuple(data.get("binning", [1, 1])),
            roi=tuple(data["roi"]) if data.get("roi") else None,
            temperature_setpoint=data.get("temperature_setpoint"),
            custom_settings=data.get("custom_settings", {}),
        )


class HardwareMetrics(BaseModel):
    """Hardware performance and health metrics"""

    temperature: Optional[float] = None
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    disk_usage: Optional[float] = None
    network_latency: Optional[float] = None
    error_count: int = 0
    uptime_seconds: float = 0.0
    last_calibration: Optional[datetime] = None
    custom_metrics: Dict[str, float] = Field(default_factory=dict)

    def is_healthy(self) -> bool:
        """Check if hardware metrics indicate healthy operation"""
        if self.temperature and self.temperature > 80.0:
            return False
        if self.cpu_usage and self.cpu_usage > 95.0:
            return False
        if self.memory_usage and self.memory_usage > 95.0:
            return False
        if self.error_count > 10:
            return False
        return True


class HardwareComponent:
    """Base hardware component entity"""

    def __init__(
        self,
        hardware_id: str,
        name: str,
        hardware_type: HardwareType,
        model: str = "unknown",
        serial_number: Optional[str] = None,
    ):
        self.hardware_id = hardware_id
        self.name = name
        self.hardware_type = hardware_type
        self.model = model
        self.serial_number = serial_number

        self._status = HardwareStatus.UNKNOWN
        self._capabilities = HardwareCapabilities()
        self._configuration = HardwareConfiguration()
        self._metrics = HardwareMetrics()
        self._last_status_update = datetime.now()
        self._status_history: List[tuple[datetime, HardwareStatus]] = []
        self._error_messages: List[str] = []

        logger.debug(f"Created hardware component: {self.hardware_id} ({self.name})")

    @property
    def status(self) -> HardwareStatus:
        """Current hardware status"""
        return self._status

    @status.setter
    def status(self, new_status: HardwareStatus):
        """Update hardware status with history tracking"""
        if new_status != self._status:
            self._status_history.append((self._last_status_update, self._status))
            self._status = new_status
            self._last_status_update = datetime.now()
            logger.info(f"Hardware {self.hardware_id} status changed to {new_status.value}")

    @property
    def capabilities(self) -> HardwareCapabilities:
        """Hardware capabilities"""
        return self._capabilities

    @capabilities.setter
    def capabilities(self, capabilities: HardwareCapabilities):
        """Set hardware capabilities"""
        self._capabilities = capabilities
        logger.debug(f"Updated capabilities for {self.hardware_id}")

    @property
    def configuration(self) -> HardwareConfiguration:
        """Current hardware configuration"""
        return self._configuration

    @configuration.setter
    def configuration(self, config: HardwareConfiguration):
        """Set hardware configuration"""
        self._configuration = config
        logger.debug(f"Updated configuration for {self.hardware_id}")

    @property
    def metrics(self) -> HardwareMetrics:
        """Current hardware metrics"""
        return self._metrics

    @metrics.setter
    def metrics(self, metrics: HardwareMetrics):
        """Update hardware metrics"""
        self._metrics = metrics

    def is_available(self) -> bool:
        """Check if hardware is available for use"""
        return self._status == HardwareStatus.AVAILABLE

    def is_operational(self) -> bool:
        """Check if hardware is operational (available or busy)"""
        return self._status in [HardwareStatus.AVAILABLE, HardwareStatus.BUSY]

    def add_error_message(self, message: str):
        """Add error message to history"""
        self._error_messages.append(f"{datetime.now().isoformat()}: {message}")
        if len(self._error_messages) > 100:  # Keep last 100 errors
            self._error_messages.pop(0)
        self._metrics.error_count += 1

    def get_recent_errors(self, hours: int = 24) -> List[str]:
        """Get error messages from last N hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_errors = []

        for error_msg in self._error_messages:
            try:
                timestamp_str = error_msg.split(": ", 1)[0]
                timestamp = datetime.fromisoformat(timestamp_str)
                if timestamp >= cutoff_time:
                    recent_errors.append(error_msg)
            except (ValueError, IndexError):
                continue

        return recent_errors

    def get_status_history(self, hours: int = 24) -> List[tuple[datetime, HardwareStatus]]:
        """Get status change history for last N hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            (timestamp, status)
            for timestamp, status in self._status_history
            if timestamp >= cutoff_time
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "hardware_id": self.hardware_id,
            "name": self.name,
            "hardware_type": self.hardware_type.value,
            "model": self.model,
            "serial_number": self.serial_number,
            "status": self._status.value,
            "last_status_update": self._last_status_update.isoformat(),
            "capabilities": {
                "max_resolution": self._capabilities.max_resolution,
                "bit_depth": self._capabilities.bit_depth,
                "max_frame_rate": self._capabilities.max_frame_rate,
                "wavelength_range": self._capabilities.wavelength_range,
                "custom_properties": self._capabilities.custom_properties,
            },
            "configuration": self._configuration.to_dict(),
            "metrics": {
                "temperature": self._metrics.temperature,
                "cpu_usage": self._metrics.cpu_usage,
                "memory_usage": self._metrics.memory_usage,
                "disk_usage": self._metrics.disk_usage,
                "network_latency": self._metrics.network_latency,
                "error_count": self._metrics.error_count,
                "uptime_seconds": self._metrics.uptime_seconds,
                "last_calibration": (
                    self._metrics.last_calibration.isoformat()
                    if self._metrics.last_calibration
                    else None
                ),
                "custom_metrics": self._metrics.custom_metrics,
            },
            "recent_errors": self.get_recent_errors(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> HardwareComponent:
        """Create from dictionary"""
        component = cls(
            hardware_id=data["hardware_id"],
            name=data["name"],
            hardware_type=HardwareType(data["hardware_type"]),
            model=data.get("model", "unknown"),
            serial_number=data.get("serial_number"),
        )

        component._status = HardwareStatus(data["status"])
        component._last_status_update = datetime.fromisoformat(data["last_status_update"])

        # Restore capabilities
        cap_data = data.get("capabilities", {})
        component._capabilities = HardwareCapabilities(
            max_resolution=tuple(cap_data.get("max_resolution", [0, 0])),
            bit_depth=cap_data.get("bit_depth", 16),
            max_frame_rate=cap_data.get("max_frame_rate", 30.0),
            wavelength_range=tuple(cap_data.get("wavelength_range", [400.0, 700.0])),
            custom_properties=cap_data.get("custom_properties", {}),
        )

        # Restore configuration
        config_data = data.get("configuration", {})
        component._configuration = HardwareConfiguration.from_dict(config_data)

        # Restore metrics
        metrics_data = data.get("metrics", {})
        component._metrics = HardwareMetrics(
            temperature=metrics_data.get("temperature"),
            cpu_usage=metrics_data.get("cpu_usage"),
            memory_usage=metrics_data.get("memory_usage"),
            disk_usage=metrics_data.get("disk_usage"),
            network_latency=metrics_data.get("network_latency"),
            error_count=metrics_data.get("error_count", 0),
            uptime_seconds=metrics_data.get("uptime_seconds", 0.0),
            last_calibration=(
                datetime.fromisoformat(metrics_data["last_calibration"])
                if metrics_data.get("last_calibration")
                else None
            ),
            custom_metrics=metrics_data.get("custom_metrics", {}),
        )

        # Restore error messages
        component._error_messages = data.get("recent_errors", [])

        return component


class Camera(HardwareComponent):
    """Camera hardware component with imaging-specific capabilities"""

    def __init__(
        self,
        camera_id: str,
        name: str,
        model: CameraModel = CameraModel.GENERIC,
        serial_number: Optional[str] = None,
    ):
        super().__init__(camera_id, name, HardwareType.CAMERA, model.value, serial_number)
        self.camera_model = model
        self._cooling_enabled = False
        self._target_temperature = -10.0

    @property
    def is_cooling_enabled(self) -> bool:
        """Check if camera cooling is enabled"""
        return self._cooling_enabled

    def enable_cooling(self, target_temperature: float = -10.0):
        """Enable camera cooling to target temperature"""
        self._cooling_enabled = True
        self._target_temperature = target_temperature
        self._configuration.temperature_setpoint = target_temperature
        logger.info(f"Enabled cooling for camera {self.hardware_id} to {target_temperature}�C")

    def disable_cooling(self):
        """Disable camera cooling"""
        self._cooling_enabled = False
        self._configuration.temperature_setpoint = None
        logger.info(f"Disabled cooling for camera {self.hardware_id}")

    def set_exposure(self, exposure_ms: float):
        """Set camera exposure time"""
        self._configuration.exposure_time_ms = exposure_ms
        logger.debug(f"Set exposure to {exposure_ms}ms for camera {self.hardware_id}")

    def set_binning(self, x_bin: int, y_bin: int):
        """Set camera pixel binning"""
        self._configuration.binning = (x_bin, y_bin)
        logger.debug(f"Set binning to {x_bin}x{y_bin} for camera {self.hardware_id}")

    def is_temperature_stable(self, tolerance: float = 2.0) -> bool:
        """Check if camera temperature is stable within tolerance"""
        if not self._cooling_enabled or not self._metrics.temperature:
            return True
        return abs(self._metrics.temperature - self._target_temperature) <= tolerance


class Display(HardwareComponent):
    """Display hardware component for stimulus presentation"""

    def __init__(
        self,
        display_id: str,
        name: str,
        display_type: DisplayType = DisplayType.LCD_MONITOR,
        serial_number: Optional[str] = None,
    ):
        super().__init__(display_id, name, HardwareType.DISPLAY, display_type.value, serial_number)
        self.display_type = display_type
        self._brightness = 50.0
        self._contrast = 50.0
        self._gamma = 1.0

    @property
    def brightness(self) -> float:
        """Current display brightness (0-100)"""
        return self._brightness

    @brightness.setter
    def brightness(self, value: float):
        """Set display brightness"""
        self._brightness = max(0.0, min(100.0, value))
        self._configuration.custom_settings["brightness"] = self._brightness

    @property
    def contrast(self) -> float:
        """Current display contrast (0-100)"""
        return self._contrast

    @contrast.setter
    def contrast(self, value: float):
        """Set display contrast"""
        self._contrast = max(0.0, min(100.0, value))
        self._configuration.custom_settings["contrast"] = self._contrast

    @property
    def gamma(self) -> float:
        """Current display gamma correction"""
        return self._gamma

    @gamma.setter
    def gamma(self, value: float):
        """Set display gamma correction"""
        self._gamma = max(0.1, min(5.0, value))
        self._configuration.custom_settings["gamma"] = self._gamma


class HardwareSystem:
    """System-level hardware management entity"""

    def __init__(self, system_id: str = "isi_macroscope_system"):
        self.system_id = system_id
        self._components: Dict[str, HardwareComponent] = {}
        self._last_system_check = datetime.now()
        self._system_health_score = 0.0

        logger.info(f"Initialized hardware system: {system_id}")

    def add_component(self, component: HardwareComponent):
        """Add hardware component to system"""
        self._components[component.hardware_id] = component
        logger.info(f"Added component {component.hardware_id} to system {self.system_id}")

    def remove_component(self, hardware_id: str) -> bool:
        """Remove hardware component from system"""
        if hardware_id in self._components:
            del self._components[hardware_id]
            logger.info(f"Removed component {hardware_id} from system {self.system_id}")
            return True
        return False

    def get_component(self, hardware_id: str) -> Optional[HardwareComponent]:
        """Get hardware component by ID"""
        return self._components.get(hardware_id)

    def get_components_by_type(self, hardware_type: HardwareType) -> List[HardwareComponent]:
        """Get all components of specific type"""
        return [comp for comp in self._components.values() if comp.hardware_type == hardware_type]

    def get_available_components(self) -> List[HardwareComponent]:
        """Get all available components"""
        return [comp for comp in self._components.values() if comp.is_available()]

    def get_operational_components(self) -> List[HardwareComponent]:
        """Get all operational components"""
        return [comp for comp in self._components.values() if comp.is_operational()]

    def get_cameras(self) -> List[Camera]:
        """Get all camera components"""
        return [comp for comp in self._components.values() if isinstance(comp, Camera)]

    def get_displays(self) -> List[Display]:
        """Get all display components"""
        return [comp for comp in self._components.values() if isinstance(comp, Display)]

    def calculate_system_health(self) -> float:
        """Calculate overall system health score (0-1)"""
        if not self._components:
            return 0.0

        total_health = 0.0
        for component in self._components.values():
            component_health = 1.0 if component.is_operational() else 0.0
            if component.metrics.is_healthy():
                component_health *= 1.0
            else:
                component_health *= 0.5  # Reduce for unhealthy metrics
            total_health += component_health

        self._system_health_score = total_health / len(self._components)
        return self._system_health_score

    def is_system_ready_for_acquisition(self) -> tuple[bool, List[str]]:
        """Check if system is ready for data acquisition"""
        issues = []

        # Check for required components
        cameras = self.get_cameras()
        displays = self.get_displays()

        if not cameras:
            issues.append("No cameras available")
        elif not any(cam.is_available() for cam in cameras):
            issues.append("No cameras in available state")

        if not displays:
            issues.append("No display systems available")
        elif not any(disp.is_available() for disp in displays):
            issues.append("No display systems in available state")

        # Check camera readiness
        for camera in cameras:
            if camera.is_available():
                if hasattr(camera, "_cooling_enabled") and camera._cooling_enabled:
                    if not camera.is_temperature_stable():
                        issues.append(f"Camera {camera.hardware_id} temperature not stable")

        # Check system health
        health_score = self.calculate_system_health()
        if health_score < 0.7:
            issues.append(f"System health score too low: {health_score:.2f}")

        return len(issues) == 0, issues

    def get_system_status_summary(self) -> Dict[str, Any]:
        """Get comprehensive system status summary"""
        component_status = {}
        for comp_id, comp in self._components.items():
            component_status[comp_id] = {
                "name": comp.name,
                "type": comp.hardware_type.value,
                "status": comp.status.value,
                "operational": comp.is_operational(),
                "healthy": comp.metrics.is_healthy(),
                "error_count": comp.metrics.error_count,
            }

        ready, issues = self.is_system_ready_for_acquisition()

        return {
            "system_id": self.system_id,
            "last_check": self._last_system_check.isoformat(),
            "health_score": self.calculate_system_health(),
            "ready_for_acquisition": ready,
            "acquisition_issues": issues,
            "component_count": len(self._components),
            "operational_components": len(self.get_operational_components()),
            "available_components": len(self.get_available_components()),
            "components": component_status,
        }

    def save_to_file(self, file_path: Path):
        """Save hardware system state to JSON file"""
        system_data = {
            "system_id": self.system_id,
            "last_system_check": self._last_system_check.isoformat(),
            "components": {comp_id: comp.to_dict() for comp_id, comp in self._components.items()},
        }

        with open(file_path, "w") as f:
            json.dump(system_data, f, indent=2)

        logger.info(f"Saved hardware system state to {file_path}")

    @classmethod
    def load_from_file(cls, file_path: Path) -> HardwareSystem:
        """Load hardware system state from JSON file"""
        with open(file_path, "r") as f:
            data = json.load(f)

        system = cls(data["system_id"])
        system._last_system_check = datetime.fromisoformat(data["last_system_check"])

        for comp_id, comp_data in data["components"].items():
            # Determine component type and create appropriate instance
            hardware_type = HardwareType(comp_data["hardware_type"])

            if hardware_type == HardwareType.CAMERA:
                component = Camera(
                    comp_data["hardware_id"],
                    comp_data["name"],
                    (
                        CameraModel(comp_data["model"])
                        if comp_data["model"] in [m.value for m in CameraModel]
                        else CameraModel.GENERIC
                    ),
                    comp_data.get("serial_number"),
                )
            elif hardware_type == HardwareType.DISPLAY:
                component = Display(
                    comp_data["hardware_id"],
                    comp_data["name"],
                    (
                        DisplayType(comp_data["model"])
                        if comp_data["model"] in [d.value for d in DisplayType]
                        else DisplayType.LCD_MONITOR
                    ),
                    comp_data.get("serial_number"),
                )
            else:
                component = HardwareComponent.from_dict(comp_data)

            system.add_component(component)

        logger.info(f"Loaded hardware system from {file_path}")
        return system
