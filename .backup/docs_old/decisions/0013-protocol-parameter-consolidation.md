# ADR-0013: Protocol Parameter System Consolidation

**Status:** Accepted
**Date:** 2024-09-23
**Deciders:** System Architecture Team

## Context

During implementation of the domain value objects, a duplicate protocol parameter system was created (`protocol.py`) that overlapped with the existing parameter system (`parameters.py`). This created inconsistency in the codebase:

### Existing System (`parameters.py`)
- **`AcquisitionProtocolParams`**: Handles acquisition-time protocol parameters
- **Consistent patterns**: Literature-based defaults, validation ranges, frozen models
- **Integrated persistence**: JSON storage via `FileBasedParameterStore`
- **Session integration**: Part of `CombinedParameters` used throughout the system
- **Parameter management**: Handled by `ParameterManager` with validation

### Duplicate System (`protocol.py`)
- **`AcquisitionProtocol`**: Attempted to handle similar functionality
- **Inconsistent patterns**: No defaults, optional parameters, unfrozen
- **No persistence**: Not integrated with existing storage system
- **Separate from sessions**: Would require separate management

## Decision

**Consolidate all protocol parameters into the existing parameter system** rather than maintaining two separate systems.

### Specific Actions:

1. **Remove `protocol.py`** - Delete the duplicate protocol system
2. **Enhance `AcquisitionProtocolParams`** - Add any missing functionality to the existing system
3. **Maintain consistency** - Follow established patterns for defaults, validation, and persistence

## Consequences

### Positive
- **Single source of truth** for protocol parameters
- **Consistent patterns** across all parameter systems
- **Integrated persistence** and session management
- **Reduced complexity** and maintenance burden
- **Better user experience** with unified parameter management

### Negative
- **Temporary development effort** to consolidate systems
- **Need to update references** to the removed protocol system

## Implementation Plan

### Phase 1: Analysis
- Compare functionality between `AcquisitionProtocolParams` and `AcquisitionProtocol`
- Identify missing features that need to be added to the existing system

### Phase 2: Enhancement
- Add missing protocol features to `AcquisitionProtocolParams`:
  - Direction sequencing options (sequential, interleaved, randomized, custom)
  - Baseline recording strategies (pre-session, pre-direction, pre-cycle, interleaved)
  - Advanced timing controls (inter-direction, inter-cycle intervals)
  - Protocol repetition controls

### Phase 3: Migration
- Update any code references from `AcquisitionProtocol` to `AcquisitionProtocolParams`
- Remove `protocol.py` file
- Update imports and dependencies

### Phase 4: Testing
- Ensure parameter persistence works correctly
- Verify session integration continues to function
- Test parameter validation and defaults

## Architecture Alignment

This decision aligns with our architectural principles:

- **ADR-0007**: Maintains clear separation between generation and acquisition parameters
- **Clean Architecture**: Keeps domain value objects consistent and focused
- **Parameter System Design**: Follows established patterns for defaults, validation, and persistence

## Updated Parameter vs Configuration System Structure

### Scientific Parameters (`parameters.py`)
```
parameters.py (Value Objects)
├── SpatialConfiguration (generation-time, frozen, literature defaults)
├── StimulusGenerationParams (generation-time, frozen, literature defaults)
└── AcquisitionProtocolParams (acquisition-time, frozen, literature defaults)
    ├── Basic controls: num_cycles, repetitions_per_direction
    ├── Timing: frame_rate, intervals, baseline durations
    ├── Direction sequencing: sequential, interleaved, randomized, custom
    ├── Baseline strategies: pre-session, pre-direction, pre-cycle, interleaved
    └── Session management: naming, export formats, error recovery

entities/parameters.py (Business Logic)
├── ParameterStore (abstract interface)
├── FileBasedParameterStore (JSON persistence)
├── DefaultParameterFactory (literature-based defaults)
└── ParameterManager (high-level management)
```

### Technical Configuration (`stream_config.py`)
```
stream_config.py (Value Objects)
├── StreamConfiguration (base streaming settings)
├── CameraStreamConfig (camera data streaming)
├── DisplayStreamConfig (display/stimulus streaming)
├── StatusStreamConfig (status and telemetry streaming)
└── StreamingProfile (complete streaming configuration)
```

## References

- **ADR-0007**: Parameter Separation: Generation vs Acquisition
- **Marshel et al. 2011**: Literature defaults for retinotopy protocols
- **Clean Architecture**: Domain value object consistency principles