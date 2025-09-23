# 6. Twelve-State Workflow State Machine

Date: 2025-01-14

## Status

Accepted

## Context

The ISI Macroscope Control System manages a complex scientific workflow with multiple phases:

- System initialization and hardware validation
- Interactive spatial configuration with 3D visualization
- Visual stimulus generation with GPU acceleration
- Real-time data acquisition with precise timing
- Post-acquisition ISI analysis and visualization

The workflow must support:
- Linear progression through phases
- Non-linear navigation (users returning to previous phases)
- Hardware failure recovery at any point
- Session persistence across application restarts
- Clear state validation and transition guards
- Error handling with graceful degradation

Simple linear workflows would be too restrictive, while ad-hoc state management would be unreliable for scientific applications requiring reproducibility.

## Decision

We will implement a **12-state finite state machine** for workflow management:

### Primary Workflow States
1. **STARTUP**: System initialization and hardware validation
2. **SETUP_READY**: System validated, ready for spatial configuration
3. **SETUP**: Interactive 3D spatial configuration
4. **GENERATION_READY**: Spatial config complete, ready for stimulus generation
5. **GENERATION**: Creating and optimizing visual stimulus datasets
6. **ACQUISITION_READY**: Stimuli prepared, ready for data acquisition
7. **ACQUISITION**: Real-time synchronized data capture
8. **ANALYSIS_READY**: Data captured, ready for post-acquisition processing
9. **ANALYSIS**: ISI data processing and retinotopic map generation

### Error Handling States
10. **ERROR**: Hardware failures and system errors with transparency
11. **RECOVERY**: Automatic or guided recovery from error conditions
12. **DEGRADED**: Continue operation with reduced hardware capability

### State Management Features
- **Non-linear navigation**: Users can return to previous phases
- **State persistence**: Complete workflow state survives restarts
- **Transition guards**: Hardware/data validation before transitions
- **Error recovery**: Comprehensive failure handling with data preservation

## Consequences

### Positive

- **Scientific Reliability**: Explicit state management prevents undefined workflow conditions
- **User Flexibility**: Non-linear navigation supports experimental iteration
- **Error Resilience**: Dedicated error states provide predictable failure handling
- **Session Continuity**: State persistence enables resuming interrupted work
- **Validation Clarity**: Clear transition guards prevent invalid operations
- **Development Clarity**: Explicit states make system behavior predictable and testable

### Negative

- **Implementation Complexity**: State machine requires more code than simple linear workflow
- **State Explosion**: 12 states with transitions creates complex interaction matrix
- **Debug Complexity**: State-dependent bugs may be harder to reproduce
- **User Confusion**: Complex state model may overwhelm users if poorly presented

### Risks

- **State Corruption**: Invalid transitions could leave system in undefined state
- **Performance Overhead**: State validation and persistence could impact real-time operations
- **Transition Logic Bugs**: Complex guard conditions may have edge cases

## Alternatives Considered

- **Linear Workflow**: Rejected due to inflexibility for scientific iteration
- **Ad-hoc State Management**: Rejected due to unreliability for critical scientific applications
- **Simpler State Model (6-8 states)**: Rejected as insufficient for proper error handling
- **No State Management**: Rejected as inappropriate for complex scientific workflow
- **External State Machine Library**: Rejected due to Python/JavaScript integration complexity

## Related Decisions

- Depends on: ADR-0003 (Thin Client Architecture)
- Depends on: ADR-0005 (IPC/WebSocket Communication)
- Enables: Future ADRs on state persistence, error recovery, session management

## Notes

The 12-state model balances workflow flexibility with scientific reliability. Each state has:
- Clear entry/exit conditions
- Defined operations and UI elements
- Explicit transition guards
- Error handling procedures

State machine implementation should use:
- Enum-based state definitions for type safety
- Guard functions for transition validation
- Event-driven state changes
- Comprehensive logging for debugging

The design prioritizes scientific workflow requirements over simplicity, recognizing that research applications require more sophisticated state management than typical business applications.