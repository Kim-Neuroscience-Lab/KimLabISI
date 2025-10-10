# Phase 7 API Reference

Quick reference for the supporting services modules.

## health.py

### Classes

**HealthMonitor**
```python
class HealthMonitor:
    def __init__(
        self,
        ipc: MultiChannelIPC,
        check_interval: float = 5.0,
        cpu_warning_threshold: float = 80.0,
        memory_warning_threshold: float = 85.0,
        disk_warning_threshold: float = 90.0,
    )

    def start_monitoring(self) -> None
    def stop_monitoring(self) -> None
    def get_health_report(self) -> HealthReport

    @property
    def is_monitoring(self) -> bool
```

**HealthReport**
```python
@dataclass
class HealthReport:
    status: HealthStatus
    timestamp: float
    metrics: SystemMetrics
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> Dict[str, Any]
```

**SystemMetrics**
```python
@dataclass
class SystemMetrics:
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    disk_free_gb: float
    thread_count: int
    process_count: int
    uptime_seconds: float
    gpu_available: bool
    gpu_memory_used_mb: Optional[float]
    gpu_memory_total_mb: Optional[float]
    gpu_utilization_percent: Optional[float]

    def to_dict(self) -> Dict[str, Any]
```

**HealthStatus**
```python
class HealthStatus(Enum):
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    ERROR = "error"
    UNKNOWN = "unknown"
```

### Usage Example

```python
from health import HealthMonitor
from ipc.channels import build_multi_channel_ipc

ipc = build_multi_channel_ipc()
health = HealthMonitor(ipc=ipc, check_interval=5.0)

# Get single report
report = health.get_health_report()
print(f"Status: {report.status.value}")
print(f"CPU: {report.metrics.cpu_percent}%")

# Start continuous monitoring
health.start_monitoring()

# Stop monitoring
health.stop_monitoring()
```

---

## startup.py

### Classes

**StartupCoordinator**
```python
class StartupCoordinator:
    def __init__(self)

    @staticmethod
    def validate_system_requirements(
        requirements: Optional[SystemRequirements] = None
    ) -> ValidationResult

    @staticmethod
    def check_hardware_availability() -> Dict[str, Any]

    @staticmethod
    def validate_config_file(config_path: str | Path) -> ValidationResult

    def run_all_validations(
        self, config_path: Optional[str | Path] = None
    ) -> ValidationResult
```

**ValidationResult**
```python
@dataclass
class ValidationResult:
    success: bool
    message: str
    details: Optional[Dict[str, Any]]
```

**SystemRequirements**
```python
@dataclass
class SystemRequirements:
    min_python_version: Tuple[int, int, int] = (3, 10, 0)
    min_memory_mb: int = 2048
    min_disk_space_gb: int = 1
    required_packages: list[str] = [
        "numpy", "opencv-python", "torch", "psutil", "zmq"
    ]
```

### Functions

```python
def validate_system_requirements() -> Tuple[bool, list[str]]
def check_hardware_availability() -> Dict[str, Any]
```

### Usage Example

```python
from startup import StartupCoordinator, validate_system_requirements, check_hardware_availability

# Simple API
success, errors = validate_system_requirements()
if not success:
    for error in errors:
        print(f"Error: {error}")

hardware = check_hardware_availability()
print(f"Cameras: {hardware['cameras']}")
print(f"GPU: {hardware['gpu']}")

# Full coordinator
coordinator = StartupCoordinator()
result = coordinator.run_all_validations("config/isi_parameters.json")
if result.success:
    print("All validations passed")
```

---

## display.py

### Classes

**DisplayInfo**
```python
@dataclass
class DisplayInfo:
    name: str
    identifier: str
    width: int
    height: int
    refresh_rate: float
    is_primary: bool
    position_x: int = 0
    position_y: int = 0
    scale_factor: float = 1.0

    def to_dict(self) -> Dict[str, Any]
```

### Functions

**Detection**
```python
def detect_displays() -> List[DisplayInfo]
def get_primary_display() -> Optional[DisplayInfo]
```

**Lookup**
```python
def get_display_by_identifier(identifier: str) -> Optional[DisplayInfo]
def get_display_by_name(name: str) -> Optional[DisplayInfo]
```

**Validation**
```python
def validate_display_config(
    required_width: int,
    required_height: int,
    required_refresh_rate: Optional[float] = None,
) -> Tuple[bool, str]
```

### Usage Example

```python
from display import detect_displays, get_primary_display, validate_display_config

# Detect all displays
displays = detect_displays()
for display in displays:
    print(f"{display.name}: {display.width}x{display.height} @ {display.refresh_rate}Hz")

# Get primary display
primary = get_primary_display()
if primary:
    print(f"Primary: {primary.name}")

# Validate requirements
is_valid, message = validate_display_config(1920, 1080, 60.0)
if not is_valid:
    print(f"Validation failed: {message}")
```

---

## Integration Patterns

### Early Startup Validation

```python
def main():
    # Validate before creating services
    success, errors = validate_system_requirements()
    if not success:
        sys.exit(1)

    # Check hardware
    hardware = check_hardware_availability()
    logger.info(f"Hardware: {hardware}")

    # Create services
    config = AppConfig.from_file("config/isi_parameters.json")
    services = create_services(config)

    # Start monitoring
    services["health_monitor"].start_monitoring()
```

### Composition Root

```python
def create_services(config: AppConfig) -> dict:
    # Infrastructure
    ipc = build_multi_channel_ipc(...)

    # Supporting services
    health_monitor = HealthMonitor(
        ipc=ipc,
        check_interval=5.0,
    )

    return {
        "ipc": ipc,
        "health_monitor": health_monitor,
        # ... other services
    }
```

### IPC Handlers

```python
def create_handlers(services: dict) -> dict:
    health = services["health_monitor"]

    return {
        "get_health": lambda cmd: health.get_health_report().to_dict(),
        "check_hardware": lambda cmd: check_hardware_availability(),
        "detect_displays": lambda cmd: {
            "displays": [d.to_dict() for d in detect_displays()],
        },
    }
```

---

## Architecture Principles

1. **Constructor Injection Only** - All dependencies passed to `__init__()`
2. **NO Service Locator** - Zero imports from `service_locator`
3. **Pure Functions** - Utilities like `detect_displays()` have no state
4. **Explicit Dependencies** - Everything visible at composition root
5. **Cross-Platform** - Works on macOS, Linux, Windows

## Testing

```python
# Run all Phase 7 tests
cd /Users/Adam/KimLabISI/apps/backend
.venv/bin/python src/test_phase7.py
```

All tests verify:
- NO service_locator imports
- Constructor injection works
- Services start/stop correctly
- Hardware detection works
- Display detection works
- Validation functions work

---

**Phase 7 Complete** - Ready for integration into main.py!
