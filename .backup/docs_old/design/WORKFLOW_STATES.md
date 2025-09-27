# Workflow States

## Overview

This document defines the state machine and workflow control for the ISI Macroscope Control System. The state machine manages the scientific workflow while providing robust error handling, user navigation flexibility, and session persistence. The design supports both linear workflow progression and non-linear user navigation for experimental iteration.

## State Machine Architecture

### Core Design Principles

**Non-Linear Navigation:**
- Users can return to previous workflow phases at any time
- State transitions support both forward progression and backward navigation
- Configuration changes trigger appropriate downstream invalidation

**State Persistence:**
- All workflow state persists across application restarts
- Incomplete work is preserved and resumable
- Parameter settings survive between sessions

**Hardware Integration:**
- State transitions validate hardware requirements
- Graceful degradation when hardware is unavailable
- Error states provide recovery paths with full transparency

## State Definitions

### STARTUP
**Purpose:** System initialization and hardware validation
**Entry Conditions:** Application launch
**Hardware Requirements:** All production hardware or dev-mode bypass

**Operations:**
- Hardware detection and driver validation
- Performance baseline establishment
- Calibration data verification
- Development mode activation
- Previous session state restoration

**UI Elements:**
- Hardware status dashboard
- Development mode toggle
- Calibration status indicators
- Progress indicators for initialization phases

**Exit Conditions:**
- Hardware validation complete → SETUP_READY
- Dev-mode activated → SETUP_READY
- Hardware failure → ERROR
- User cancellation → Application exit

### SETUP_READY
**Purpose:** System validated and ready for spatial configuration
**Entry Conditions:** Successful startup or return from other phases
**Hardware Requirements:** Display hardware (RTX 4070 or dev-mode)

**Operations:**
- Load previous spatial configurations
- Access configuration management
- Navigate to other workflow phases (if data available)
- System health monitoring

**UI Elements:**
- Workflow navigation controls
- Configuration load/save options
- Hardware status monitoring
- Phase transition buttons (when appropriate)

**Exit Conditions:**
- User starts spatial configuration → SETUP
- User navigates to other phases → corresponding states
- Hardware failure → ERROR

### SETUP
**Purpose:** Interactive 3D spatial configuration of experimental geometry
**Entry Conditions:** User initiates spatial configuration
**Hardware Requirements:** Display hardware for 3D visualization

**Operations:**
- 3D monitor positioning interface (Three.js)
- Real-time parameter adjustment
- Visual field coverage validation
- Spherical coordinate system definition
- Configuration save/load management

**UI Elements:**
- 3D visualization scene with orbital controls
- Parameter sliders and numeric inputs
- Coverage preview and validation
- Configuration management interface
- Reference value information (Marshel 2011)

**Exit Conditions:**
- Configuration confirmed → GENERATION_READY
- User navigates away → SETUP_READY
- Hardware failure → ERROR

### GENERATION_READY
**Purpose:** Spatial configuration complete, ready for stimulus generation
**Entry Conditions:** Setup configuration confirmed or stimulus files exist
**Hardware Requirements:** GPU for stimulus generation (RTX 4070 or dev-mode)

**Operations:**
- **Dataset Discovery**: Automatic scan of existing stimulus datasets with parameter comparison
- **Compatibility Check**: Exact parameter matching against current spatial configuration
- **Dataset Management**: List, preview, validate, and delete existing stimulus datasets
- **Parameter Reuse**: Load spatial configuration from existing datasets (returns to SETUP)
- **Duplicate Prevention**: Block regeneration of existing valid datasets
- **Integrity Validation**: HDF5 file structure and hash verification on load

**UI Elements:**
- **Available Datasets List**: All discovered datasets with compatibility status
- **Parameter Comparison**: Detailed diff view of current vs. existing parameters
- **Dataset Actions**: Load, preview, delete, or regenerate options
- **Compatibility Indicators**: Clear visual indication of parameter match/mismatch
- **Integrity Status**: File validation results and corruption warnings
- **Generation Controls**: Access to stimulus generation with duplicate warnings

**Exit Conditions:**
- User starts stimulus generation → GENERATION (with duplicate prevention check)
- User loads different parameters → SETUP (with loaded spatial configuration)
- User selects compatible dataset → ACQUISITION_READY (dataset loaded)
- User modifies setup → SETUP (invalidates existing dataset compatibility)
- Hardware failure → ERROR

### GENERATION
**Purpose:** Creating and optimizing visual stimulus datasets
**Entry Conditions:** User initiates stimulus generation
**Hardware Requirements:** GPU with CUDA support (RTX 4070 or dev-mode)

**Operations:**
- HDF5 stimulus file creation (LR, RL, TB, BT directions)
- CUDA-accelerated pattern generation
- Real-time preview rendering
- Memory optimization and caching
- Progress monitoring and quality validation

**UI Elements:**
- Generation progress indicators
- Real-time stimulus preview
- Memory usage monitoring
- Parameter adjustment controls
- Quality validation feedback

**Exit Conditions:**
- Generation complete → ACQUISITION_READY
- User cancels → GENERATION_READY
- User modifies parameters → Continue in GENERATION
- Hardware failure → ERROR

### ACQUISITION_READY
**Purpose:** Stimuli prepared, system ready for data acquisition
**Entry Conditions:** Stimulus generation complete or existing data available
**Hardware Requirements:** All hardware (camera, display, storage) or dev-mode

**Operations:**
- Acquisition protocol configuration
- Hardware status validation
- Filter state management (manual green/red switching)
- Session metadata definition
- Preview acquisition setup

**UI Elements:**
- Acquisition protocol controls
- Hardware readiness indicators
- Filter state display
- Session configuration interface
- Live hardware monitoring

**Exit Conditions:**
- User starts acquisition → ACQUISITION
- User modifies stimuli → GENERATION_READY
- User modifies setup → SETUP
- Hardware failure → ERROR

### ACQUISITION
**Purpose:** Real-time synchronized data capture
**Entry Conditions:** User initiates data acquisition
**Hardware Requirements:** All production hardware (PCO Panda 4.2, RTX 4070, storage)

**Operations:**
- 60 FPS stimulus presentation to mouse monitor
- 30 FPS camera capture with timestamp correlation
- Real-time data streaming to Samsung 990 PRO
- Live monitoring feed to frontend (downsampled)
- Protocol execution across all directions (LR, RL, TB, BT)

**UI Elements:**
- Real-time performance monitoring
- Acquisition progress indicators
- Live preview feeds (downsampled)
- Hardware status dashboard
- Emergency stop controls

**Exit Conditions:**
- Acquisition complete → ANALYSIS_READY
- User stops acquisition → ACQUISITION_READY
- Hardware failure → ERROR (with data preservation)
- Critical error → RECOVERY (attempt automatic recovery)

### ANALYSIS_READY
**Purpose:** Data captured, system ready for post-acquisition processing
**Entry Conditions:** Acquisition complete or existing data available
**Hardware Requirements:** GPU for analysis acceleration (RTX 4070 or dev-mode)

**Operations:**
- Analysis protocol configuration
- Data integrity validation
- Previous analysis results access
- Re-analysis capability
- Export preparation

**UI Elements:**
- Analysis parameter controls
- Data integrity indicators
- Results management interface
- Export options
- Hardware status monitoring

**Exit Conditions:**
- User starts analysis → ANALYSIS
- User repeats acquisition → ACQUISITION_READY
- User modifies setup → SETUP (invalidates downstream)
- Hardware failure → ERROR

### ANALYSIS
**Purpose:** ISI data processing and retinotopic map generation
**Entry Conditions:** User initiates analysis
**Hardware Requirements:** GPU with CUDA support (RTX 4070 or dev-mode)

**Operations:**
- CUDA-accelerated frame correlation
- ISI temporal averaging and filtering
- Retinotopic coordinate calculation
- Statistical aggregation and validation
- Interactive visualization rendering

**UI Elements:**
- Analysis progress monitoring
- Real-time result previews
- Parameter adjustment controls
- Quality metrics display
- Export controls

**Exit Conditions:**
- Analysis complete → ANALYSIS_READY
- User modifies parameters → Continue in ANALYSIS
- User exports results → Continue in ANALYSIS
- Hardware failure → ERROR (preserve partial results)

## Error and Recovery States

### ERROR
**Purpose:** Handle hardware failures and system errors with full transparency
**Entry Conditions:** Hardware failure, software error, or data corruption detected
**Hardware Requirements:** Minimal (display for error reporting)

**Operations:**
- Error diagnosis and reporting
- Data preservation and integrity validation
- Recovery option presentation
- Manual intervention guidance
- System health assessment

**UI Elements:**
- Detailed error information
- Recovery action recommendations
- Data status indicators
- Manual intervention instructions
- Contact information for support

**Exit Conditions:**
- Automatic recovery successful → RECOVERY
- User chooses manual recovery → RECOVERY
- User restarts application → STARTUP
- Unrecoverable error → Application exit (with data preservation)

### RECOVERY
**Purpose:** Attempt automatic or guided recovery from error conditions
**Entry Conditions:** Error state with recovery options available
**Hardware Requirements:** Varies by recovery type

**Operations:**
- Automatic hardware reinitialization
- Data integrity verification
- State restoration procedures
- Progressive recovery attempts
- Fallback to degraded operation

**UI Elements:**
- Recovery progress indicators
- Step-by-step recovery status
- User confirmation prompts
- Fallback option presentation
- Success/failure feedback

**Exit Conditions:**
- Recovery successful → Previous state or appropriate ready state
- Recovery failed → ERROR (with updated information)
- User chooses degraded mode → DEGRADED
- User cancels recovery → ERROR

### DEGRADED
**Purpose:** Continue operation with reduced hardware capability
**Entry Conditions:** Partial hardware failure with graceful degradation possible
**Hardware Requirements:** Subset of full hardware requirements

**Operations:**
- Limited functionality operation
- Clear capability indication
- Data quality warnings
- Alternative operation modes
- Upgrade to full operation when hardware restored

**UI Elements:**
- Degraded mode indicators
- Capability limitation warnings
- Alternative operation controls
- Hardware restoration monitoring
- Data quality notifications

**Exit Conditions:**
- Hardware restored → Previous operational state
- User accepts limitations → Continue in current phase
- Critical hardware fails → ERROR
- User chooses full restart → STARTUP

## State Transition Matrix

### Forward Progression (Normal Workflow)
```
STARTUP → SETUP_READY → SETUP → GENERATION_READY → GENERATION →
ACQUISITION_READY → ACQUISITION → ANALYSIS_READY → ANALYSIS
```

### Backward Navigation (User-Initiated)
```
Any State → Previous States (with appropriate validations)
ANALYSIS → ACQUISITION_READY (re-acquire data)
ACQUISITION_READY → GENERATION_READY (regenerate stimuli)
GENERATION_READY → SETUP (reconfigure geometry)
SETUP → SETUP_READY (abandon changes)
```

### Error Handling (System-Initiated)
```
Any Operational State → ERROR (on failure)
ERROR → RECOVERY (when recovery possible)
RECOVERY → Original State or DEGRADED (on success)
RECOVERY → ERROR (on failure)
```

## Transition Guards and Validations

### Hardware Validation Guards
- **STARTUP → SETUP_READY**: All hardware validated or dev-mode active
- **SETUP_READY → SETUP**: Display hardware available for 3D rendering
- **GENERATION_READY → GENERATION**: GPU with CUDA support available
- **ACQUISITION_READY → ACQUISITION**: Camera, display, and storage all operational
- **ANALYSIS_READY → ANALYSIS**: GPU with sufficient VRAM available

### Data Dependency Guards
- **→ GENERATION_READY**: Valid spatial configuration exists
- **→ ACQUISITION_READY**: Valid stimulus datasets exist
- **→ ANALYSIS_READY**: Valid acquisition data exists
- **SETUP → GENERATION_READY**: Configuration changes invalidate downstream data

### User Confirmation Guards
- **SETUP → GENERATION_READY**: User explicitly confirms spatial configuration
- **GENERATION → ACQUISITION_READY**: Generation process completed successfully
- **ACQUISITION → ANALYSIS_READY**: Acquisition process completed successfully

## State Operations and UI Availability

### Global UI Elements (Available in All States)
- Workflow phase indicators showing current state
- Navigation breadcrumbs with enabled/disabled phases
- Hardware status monitoring dashboard
- Error notification system
- Application menu and settings

### State-Specific UI Elements

**STARTUP State:**
- Hardware detection progress
- Calibration status indicators
- Development mode controls
- Session recovery options

**SETUP States:**
- 3D visualization scene (Three.js)
- Parameter adjustment controls
- Configuration management
- Reference value displays

**GENERATION States:**
- Stimulus preview rendering
- Generation progress monitoring
- Memory usage indicators
- Parameter modification controls

**ACQUISITION States:**
- Real-time performance metrics
- Live camera feed (downsampled)
- Protocol execution status
- Emergency controls

**ANALYSIS States:**
- Result visualization
- Parameter adjustment
- Export controls
- Quality metrics

### Disabled Operations by State
- **SETUP**: Cannot access acquisition controls until stimuli generated
- **GENERATION**: Cannot modify spatial parameters during generation
- **ACQUISITION**: Cannot modify upstream parameters during active acquisition
- **ANALYSIS**: Cannot modify acquisition parameters during analysis

## Session Persistence Strategy

### Persistent State Information
```json
{
  "session_state": {
    "current_phase": "ACQUISITION_READY",
    "last_active": "2024-03-15T14:30:45Z",
    "workflow_progress": {
      "setup_completed": true,
      "setup_config_hash": "abc123...",
      "generation_completed": true,
      "generation_timestamp": "2024-03-15T14:25:30Z",
      "acquisition_completed": false,
      "analysis_completed": false
    },
    "hardware_state": {
      "last_validation": "2024-03-15T14:20:15Z",
      "dev_mode_active": false,
      "degraded_components": []
    },
    "user_preferences": {
      "auto_resume": true,
      "default_configurations": {...}
    }
  }
}
```

### Recovery Scenarios

**Clean Application Restart:**
- Restore to last active state if recent (< 1 hour)
- Validate hardware state before resuming
- Offer user choice to resume or restart workflow

**Interrupted Acquisition:**
- Preserve partial acquisition data
- Mark session as incomplete
- Offer resume from interruption point or restart acquisition

**Hardware State Changes:**
- Detect hardware configuration changes
- Invalidate dependent workflow stages
- Guide user through re-validation process

**Configuration Updates:**
- Track configuration file version changes
- Migrate saved state to new formats
- Preserve user data through updates

## Integration with Other Systems

### APPLICATION_STARTUP.md Integration
- STARTUP state implementation details
- Hardware validation procedures
- Development mode bypass mechanisms
- Session recovery procedures

### ERROR_RECOVERY.md Integration
- ERROR and RECOVERY state implementation
- Hardware failure detection and response
- Data preservation during failures
- Graceful degradation strategies

### STATE_PERSISTENCE.md Integration (Future)
- Detailed persistence mechanisms
- Session data storage formats
- Recovery procedures and validation
- Cross-session state synchronization

### Hardware Integration
- Real-time hardware monitoring across all states
- Hardware-specific state transition requirements
- Performance validation during state transitions
- Resource allocation per operational state

### Data Flow Integration
- State-aware data pipeline management
- Data validation during state transitions
- Cleanup procedures when states invalidate data
- Data integrity maintenance across workflow phases

This state machine provides robust workflow management while maintaining the flexibility and error handling required for reliable scientific data acquisition and analysis.