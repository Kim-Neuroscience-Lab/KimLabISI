# Application Startup

## Overview

This document defines the system initialization procedures for the ISI Macroscope Control System, covering hardware detection, driver validation, performance baselines, and application state recovery. The startup process establishes a reliable foundation for all workflow operations while providing development-friendly bypass options.

## Startup Sequence

### Phase 1: System Health and Hardware Detection

**Hardware Enumeration:**
- **PCO Panda 4.2 USB**: Detect camera via USB 3.1 Gen 1 interface
- **RTX 4070 GPU**: Verify graphics hardware and driver availability
- **Samsung 990 PRO Storage**: Check NVMe storage accessibility and mount status
- **System Resources**: Validate 32 GB RAM availability and Intel 13700K cores

**Basic Connectivity Tests:**
- **Camera Communication**: PCO SDK initialization and basic status query
- **Display Hardware**: DirectX 12 context creation and display enumeration
- **Storage Access**: Write/read test to verify Samsung 990 PRO functionality
- **Memory Allocation**: Test allocation of component memory budgets

**Health Check Results:**
```
Hardware Status Dashboard:
✅ PCO Panda 4.2     [Connected, SDK v2.1.3]
✅ RTX 4070          [Driver 545.92, DirectX 12 Ready]
✅ Samsung 990 PRO   [2TB Available, 6.9GB/s Capable]
✅ System Memory     [32 GB Available, Allocation Ready]
✅ Intel 13700K      [16 Cores Available, Thermal Normal]
```

### Phase 2: Driver and Software Validation

**Driver Compatibility:**
- **PCO SDK**: Version compatibility check and initialization
- **CUDA Runtime**: RTX 4070 CUDA 12.x driver validation
- **DirectX 12**: Display driver and API feature support verification
- **Storage Drivers**: NVMe driver optimization status

**Software Component Initialization:**
- **Electron Frontend**: Renderer process startup and IPC establishment
- **Backend Services**: Python/C++ backend initialization
- **Communication Channels**: IPC/WebSocket connectivity validation
- **Memory Management**: Component memory pool allocation

**Cross-Platform Considerations:**
- **Development (macOS)**: Metal backend initialization and compatibility
- **Production (Windows)**: DirectX/CUDA backend optimization
- **Driver Abstraction**: Platform-specific optimizations while maintaining consistency

### Phase 3: Performance Baselines and Calibration

**Hardware Performance Benchmarking:**
- **Display Timing**: RTX 4070 timer query precision validation (<1μs)
- **Storage Throughput**: Samsung 990 PRO sustained write test (125+ MB/sec)
- **Memory Bandwidth**: System RAM allocation and access pattern testing
- **USB Performance**: PCO Panda bandwidth capability verification

**One-Time Calibrations:**
- **Display Calibration**: Gamma curves and color accuracy (persistent storage)
- **Timing Synchronization**: Cross-hardware timestamp calibration
- **Performance Profiles**: Hardware capability profiles for optimization
- **Platform Baselines**: Development vs production performance comparison

**Calibration Persistence:**
```json
{
  "calibration_data": {
    "display": {
      "gamma_curve": [...],
      "color_profile": "sRGB",
      "last_calibrated": "2024-03-15T14:30:45Z"
    },
    "timing": {
      "rtx4070_precision": "0.8μs",
      "pco_panda_precision": "1.0μs",
      "sync_offset": "0.2μs"
    },
    "performance": {
      "storage_write_speed": "6.8GB/s",
      "memory_bandwidth": "45GB/s",
      "usb_throughput": "480MB/s"
    }
  }
}
```

### Phase 4: Application State Recovery

**Previous Session Recovery:**
- **Workspace Restoration**: Load last spatial configuration and UI state
- **Configuration Validation**: Verify saved configurations are still valid
- **Error Log Review**: Check for previous session issues requiring attention
- **Data Integrity**: Verify any interrupted sessions or partial data

**Default Initialization:**
- **Spatial Configuration**: Load default Setup phase parameters (Marshel 2011 references)
- **UI Preferences**: Restore user interface settings and layout
- **Memory Allocation**: Establish initial memory budgets per [PERFORMANCE_SPECIFICATIONS.md](./PERFORMANCE_SPECIFICATIONS.md)
- **Workflow State**: Initialize to Setup phase (ready for spatial configuration)

**Recovery Scenarios:**
- **Clean Startup**: Fresh application start with default configurations
- **Session Resume**: Continue from interrupted workflow state
- **Error Recovery**: Restore from application crash or system failure
- **Configuration Migration**: Handle updates to configuration file formats

## Development Mode Bypass

### Dev-Mode Activation

**Access Method:**
- **Startup Dialog**: "Development Mode" checkbox during startup
- **Command Line**: `--dev-mode` flag for automated/CI usage
- **Environment Variable**: `ISI_DEV_MODE=true` for persistent development
- **Keyboard Shortcut**: Ctrl+Shift+D during startup screen

**Dev-Mode Warning System:**
```
⚠️ DEVELOPMENT MODE ACTIVE ⚠️

Hardware verification bypassed. System may not function as intended.

Bypassed Components:
❌ PCO Panda 4.2 Camera    [Mock camera active]
❌ RTX 4070 Display        [Software rendering active]
❌ Samsung 990 PRO Storage [Memory storage active]
❌ Performance Validation  [Timing checks disabled]

Production readiness: NOT VERIFIED

[Run Full System Check] [Continue in Dev Mode] [Exit]
```

### Selective Hardware Bypass

**Component-Specific Bypassing:**
- **Camera Only**: Skip PCO Panda, use mock 16-bit frame generation
- **Display Only**: Skip RTX 4070, use software rendering with timing simulation
- **Storage Only**: Skip Samsung 990 PRO, use in-memory or alternative storage
- **All Hardware**: Complete mock mode for pure software development

**Mock Component Behavior:**
- **Mock Camera**: Generate realistic 2048×2048 16-bit frames at 30 FPS
- **Mock Display**: Software rendering with simulated 60 FPS timing
- **Mock Storage**: In-memory file system or development directory
- **Mock Timing**: Simulated hardware timestamps with realistic precision

### Development Workflow Support

**Cross-Platform Development:**
- **macOS Development**: Bypass Windows-specific hardware requirements
- **Partial Hardware**: Continue with subset of available components
- **CI/CD Integration**: Automated testing without physical hardware
- **Algorithm Development**: Focus on software logic without hardware dependencies

**Mock Data Generation:**
- **Realistic Camera Data**: Generate ISI-appropriate 16-bit frame sequences
- **Stimulus Correlation**: Mock stimulus-camera correlation for analysis testing
- **Error Simulation**: Inject realistic error conditions for error recovery testing
- **Performance Simulation**: Simulate various hardware performance scenarios

### Dev-Mode Limitations and Warnings

**Persistent Warning Display:**
- **Status Bar Indicator**: Constant "DEV MODE" indicator in application
- **Performance Warnings**: Alert when mock components affect testing validity
- **Data Validity**: Mark all data generated in dev-mode as non-production
- **Export Restrictions**: Prevent accidental use of dev-mode data for real analysis

**Production Prevention:**
- **Build Flags**: Disable dev-mode in production builds
- **Hardware Validation**: Force full validation before real acquisition
- **Data Marking**: Tag all dev-mode data with clear identifiers
- **User Confirmation**: Require explicit confirmation for production transition

## Startup Success Criteria

### Production Mode Success

**Required Validations:**
- **All Hardware Detected**: PCO Panda, RTX 4070, Samsung 990 PRO operational
- **Performance Thresholds**: All timing and throughput benchmarks pass
- **Calibration Current**: All calibrations within validity period
- **System Resources**: 32 GB RAM and CPU cores available per allocation plan

**Ready State Indicators:**
- **Green Status**: All systems operational and validated
- **Performance Confirmed**: Real-time capabilities verified
- **Workflow Available**: All phases (Setup → Generation → Acquisition → Analysis) accessible
- **Error Recovery**: Error handling systems active and monitored

### Development Mode Success

**Minimum Requirements:**
- **Software Components**: Electron frontend and backend services operational
- **Mock Systems**: Appropriate mock components initialized for missing hardware
- **Development Tools**: Debug interfaces and development aids available
- **Warning Systems**: Clear indication of dev-mode status and limitations

**Development Capabilities:**
- **UI Development**: Frontend development with mock backend data
- **Algorithm Testing**: Analysis algorithm development with simulated data
- **Workflow Testing**: State machine and workflow logic validation
- **Performance Profiling**: Software performance analysis independent of hardware

## Integration with Workflow Phases

### Transition to Setup Phase

**Successful Startup → Setup Entry:**
- **Spatial Configuration**: Ready for 3D monitor positioning interface
- **Hardware Baseline**: Display and GPU capabilities confirmed for 3D rendering
- **Configuration Loading**: Previous spatial configurations available for loading
- **Parameter Defaults**: Literature reference values (Marshel 2011) loaded as defaults

### Error Conditions and Recovery

**Startup Failure Handling:**
- **Hardware Missing**: Offer dev-mode bypass or configuration assistance
- **Driver Issues**: Provide specific guidance for driver updates/fixes
- **Calibration Expired**: Option to use previous calibration or recalibrate
- **Configuration Corruption**: Reset to defaults with user confirmation

**Integration with [ERROR_RECOVERY.md](./ERROR_RECOVERY.md):**
- **Health Monitoring**: Startup establishes baseline for ongoing health monitoring
- **Recovery Procedures**: Startup failure recovery feeds into general error recovery
- **Performance Tracking**: Startup benchmarks provide baseline for degradation detection

## Configuration and Preferences

### Startup Configuration File

**Configuration Storage:**
```json
{
  "startup_config": {
    "version": "1.0",
    "hardware_validation": {
      "camera_required": true,
      "display_required": true,
      "storage_required": true,
      "performance_validation": true
    },
    "dev_mode": {
      "allowed": true,
      "default_bypasses": ["camera"],
      "warning_level": "persistent"
    },
    "calibration": {
      "auto_check": true,
      "validity_period_days": 30,
      "auto_recalibrate": false
    },
    "recovery": {
      "auto_restore_session": true,
      "backup_configurations": true,
      "error_log_retention_days": 7
    }
  }
}
```

### User Preferences

**Startup Behavior:**
- **Auto-Recovery**: Automatically restore previous session vs clean start
- **Hardware Validation**: Full validation vs quick check vs dev-mode
- **Calibration Policy**: Auto-check, manual-only, or skip (dev-mode)
- **Warning Levels**: Verbose, normal, or minimal startup feedback

**Development Preferences:**
- **Default Dev-Mode**: Remember dev-mode state between sessions
- **Mock Component Selection**: Default mock components for development
- **Performance Simulation**: Simulate various hardware performance levels
- **Debug Interfaces**: Enable additional development and debugging tools

## Logging and Diagnostics

### Startup Logging

**Log Categories:**
- **Hardware Detection**: Detailed hardware enumeration and capability detection
- **Driver Validation**: Driver version, compatibility, and feature support
- **Performance Benchmarking**: Timing precision, throughput measurements
- **Configuration Loading**: Spatial configurations, calibrations, preferences

**Log Format:**
```
[2024-03-15 14:30:45.123] [STARTUP] [INFO] PCO Panda 4.2 detected: USB3.1, Serial AB123456
[2024-03-15 14:30:45.145] [STARTUP] [INFO] RTX 4070 initialized: Driver 545.92, CUDA 12.1
[2024-03-15 14:30:45.167] [STARTUP] [WARN] Samsung 990 PRO: Performance below optimal (5.2GB/s)
[2024-03-15 14:30:45.189] [STARTUP] [INFO] Memory allocation successful: 32GB available
```

### Diagnostic Information

**System Report Generation:**
- **Hardware Configuration**: Complete system specification report
- **Performance Profile**: Benchmark results and capability assessment
- **Software Versions**: Driver versions, SDK versions, application version
- **Configuration Status**: Calibration status, configuration validity

**Troubleshooting Support:**
- **Issue Detection**: Common startup problems and suggested solutions
- **Hardware Compatibility**: Version compatibility matrix and requirements
- **Performance Guidance**: Optimization suggestions based on benchmark results
- **Support Information**: Diagnostic data formatted for technical support

The Application Startup phase establishes the reliable foundation necessary for all subsequent workflow operations while maintaining development efficiency through intelligent bypass mechanisms and comprehensive error handling.