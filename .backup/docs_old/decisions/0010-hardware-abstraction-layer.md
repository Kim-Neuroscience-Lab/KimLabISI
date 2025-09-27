# 10. Hardware Abstraction Layer

Date: 2025-01-14

## Status

Accepted

## Context

The ISI Macroscope Control System must interface with platform-specific hardware across different environments:

- **Production Hardware**: PCO Panda 4.2 cameras, RTX 4070 GPU with DirectX 12, CUDA acceleration
- **Development Environment**: macOS systems without production hardware access
- **Cross-Platform Requirements**: Identical application behavior across platforms
- **Real-Time Constraints**: Microsecond-precise timing for scientific data acquisition
- **Hardware Failure Scenarios**: Graceful degradation when hardware is unavailable or malfunctioning

Direct hardware integration would either:
1. Prevent development on macOS due to Windows-specific hardware dependencies
2. Require separate codebases for different platforms
3. Make testing impossible without expensive production hardware
4. Create fragile coupling between application logic and hardware specifics

## Decision

We will implement a **comprehensive hardware abstraction layer** with platform-specific backends:

### Abstraction Architecture
- **Common Interfaces**: Abstract base classes defining hardware operations (ICameraControl, IGPUAcceleration, ITriggerSystem)
- **Platform Implementations**: Windows (DirectX, PCO SDK, CUDA) and macOS (Mock, Metal, Simulation)
- **Capability Detection**: Runtime hardware discovery and feature availability reporting
- **Configuration Management**: Platform-specific settings and performance parameters

### Hardware Interface Categories

#### Camera Control Interface
- Hardware initialization and configuration management
- Acquisition parameter setup and validation
- Real-time frame capture and streaming
- Status monitoring and error reporting

#### GPU Acceleration Interface
- Compute context initialization and management
- Memory buffer allocation and transfer operations
- Kernel execution for stimulus generation and image processing
- Cross-platform acceleration (DirectX 12 on Windows, Metal on macOS)

#### Timing Synchronization Interface
- High-precision timing configuration and control
- Hardware trigger synchronization and coordination
- Real-time event scheduling and execution
- Microsecond-precision timing validation

### Platform-Specific Implementations

#### Windows Production Backend
- **Camera**: PCO SDK integration using validated pybind11 bindings
- **GPU**: DirectX 12 acceleration leveraging existing Microsoft APIs and CUDA libraries
- **Timing**: Windows high-resolution performance counters and proven hardware trigger libraries
- **Threading**: Windows real-time thread priority APIs and optimized scheduling

#### macOS Development Backend
- **Camera**: Mock implementation using established testing frameworks and simulation libraries
- **GPU**: Metal acceleration through Apple's validated Metal Performance Shaders framework
- **Timing**: macOS timing APIs with configurable simulation parameters
- **Threading**: Grand Central Dispatch using Apple's optimized concurrency frameworks

### External Package Strategy
- **Validated Libraries**: Leverage proven external packages for hardware abstraction (pybind11, Metal Performance Shaders, DirectX APIs)
- **Testing Frameworks**: Use established mocking and simulation libraries rather than custom implementations
- **Cross-Platform APIs**: Utilize existing cross-platform libraries where available (OpenCV, CuPy, NumPy)
- **Hardware SDKs**: Integrate manufacturer-provided SDKs and APIs directly rather than creating custom wrappers

## Consequences

### Positive

- **Development Flexibility**: Full development capability on macOS without production hardware
- **Platform Independence**: Application logic decoupled from hardware specifics
- **Testing Capability**: Comprehensive testing without expensive hardware dependencies
- **Risk Mitigation**: Hardware failures don't prevent software development or testing
- **Code Maintainability**: Clear separation between business logic and hardware integration
- **Performance Optimization**: Platform-specific optimizations without sacrificing portability

### Negative

- **Implementation Complexity**: Multiple platform backends require significant development effort
- **Mock Accuracy**: Mock hardware may not perfectly replicate all production characteristics
- **Maintenance Overhead**: Platform-specific code paths require separate maintenance and testing
- **Performance Overhead**: Abstraction layer may introduce minimal performance costs
- **Testing Complexity**: Must validate behavior across multiple platform implementations

### Risks

- **Platform Divergence**: Different behavior between platforms could emerge over time
- **Mock Hardware Gaps**: Subtle production hardware behaviors may not be captured in mocks
- **Performance Differences**: Optimization differences between DirectX and Metal could affect results
- **Hardware Integration Bugs**: Platform-specific bugs may only surface in production environment

## Alternatives Considered

- **Platform-Specific Applications**: Rejected due to code duplication and maintenance burden
- **Hardware-Agnostic Only**: Rejected due to performance requirements for real-time scientific applications
- **Container-Based Abstraction**: Rejected due to direct hardware access requirements
- **Virtual Hardware Layer**: Rejected due to complexity and potential performance overhead
- **Runtime Platform Detection**: Rejected as insufficient for development environment support

## Related Decisions

- Depends on: ADR-0008 (Cross-Platform Development Strategy)
- Depends on: ADR-0004 (Modern Technology Stack - pybind11, Metal, DirectX)
- Depends on: ADR-0003 (Thin Client Architecture)
- Enables: Future ADRs on testing strategy, mock hardware implementation, performance optimization

## Notes

The hardware abstraction layer enables the cross-platform development strategy while maintaining optimal production performance. Key implementation principles:

- **Interface Consistency**: Identical application behavior regardless of underlying platform
- **Performance Transparency**: Abstraction overhead must not impact real-time requirements
- **Error Handling**: Unified error reporting across all platform implementations
- **Configuration Management**: Platform capabilities exposed through common configuration interface

The design prioritizes scientific application requirements where hardware control precision is critical, while enabling modern development practices through comprehensive hardware simulation.

Implementation requires:
- Rigorous interface specification and documentation
- Comprehensive mock hardware validation against production systems
- Platform-specific performance optimization and testing
- Clear hardware capability reporting and graceful degradation strategies