# 3. Thin Client Architecture with Scientific Data Isolation

Date: 2025-01-14

## Status

Accepted

## Context

The ISI Macroscope Control System requires precise control over scientific hardware (RTX 4070 display, PCO Panda 4.2 camera, Samsung 990 PRO storage) while providing a user-friendly interface for researchers. Critical constraints include:

- Frame-perfect stimulus presentation (60 FPS ±10μs)
- Zero-drop camera capture (30 FPS at 16-bit, 2048×2048)
- Microsecond-precision timestamp correlation
- Scientific data integrity requirements
- Real-time hardware control with deterministic timing
- Cross-platform development (macOS) vs production (Windows) workflow

Traditional web-based or thick client architectures would introduce timing uncertainties and potential data corruption paths through the UI layer.

## Decision

We will implement a **thin client architecture** with strict scientific data isolation:

- **Electron Frontend**: Monitoring and configuration only, receives downsampled previews
- **Python Backend**: Exclusive scientific control, hardware management, data processing
- **Critical Principle**: Full-resolution scientific data (stimulus + camera) NEVER passes through Electron frontend
- **Communication**: IPC/WebSocket for control and monitoring (no internal APIs)
- **Hardware Control**: Backend maintains direct, exclusive hardware access

## Consequences

### Positive

- **Scientific Integrity**: Eliminates UI-induced timing variations and data corruption risks
- **Performance Isolation**: Real-time hardware control unaffected by UI rendering or JavaScript garbage collection
- **Deterministic Timing**: Backend can dedicate CPU cores exclusively to hardware timing
- **Data Safety**: Impossible to accidentally route scientific data through UI layer
- **Development Flexibility**: UI can be developed/debugged without affecting scientific operations
- **Resource Allocation**: Clear separation allows optimal memory/CPU allocation per subsystem

### Negative

- **Increased Complexity**: Two separate applications with communication overhead
- **Development Overhead**: Must maintain IPC protocols and shared data structures
- **Debugging Complexity**: Cross-process debugging more difficult than monolithic application
- **Deployment Complexity**: Must package and deploy both frontend and backend components

### Risks

- **Communication Failures**: IPC/WebSocket interruptions could break UI monitoring
- **State Synchronization**: Frontend and backend state could diverge during failures
- **Development Workflow**: Developers must run both processes for full system testing

## Alternatives Considered

- **Monolithic Electron Application**: Rejected due to JavaScript timing unpredictability and memory management issues
- **Web-Based Interface**: Rejected due to browser security restrictions on hardware access and timing precision
- **Native Desktop Application**: Rejected due to development complexity and cross-platform constraints
- **Command-Line Only**: Rejected due to user experience requirements for spatial configuration and real-time monitoring

## Related Decisions

- Depends on: ADR-0002 (Clean Architecture)
- Enables: Future ADRs on IPC communication, hardware interfaces, state management

## Notes

This architecture is inspired by professional scientific instrumentation software where UI and control systems are always separated for reliability and precision. The thin client pattern is well-established in neuroscience research tools where data integrity is paramount.

Implementation requires careful design of the IPC protocol to provide responsive UI feedback while maintaining the strict separation of concerns.