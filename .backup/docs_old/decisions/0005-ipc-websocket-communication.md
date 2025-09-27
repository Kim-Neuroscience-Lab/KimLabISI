# 5. Electron IPC Communication (No Internal APIs)

Date: 2025-01-14
Last Updated: 2025-01-15

## Status

Accepted (Updated)

## Context

The thin client architecture requires communication between Electron frontend and Python backend for:

- Real-time monitoring data (downsampled camera previews, hardware status)
- User commands (start acquisition, change parameters, navigate workflow)
- State synchronization (workflow phase, progress updates, error notifications)
- Configuration management (spatial parameters, stimulus settings)

Communication mechanisms must support:
- High-bandwidth real-time data streaming for scientific imaging
- Bidirectional command/response patterns
- Type-safe message protocols
- Cross-process error handling
- Desktop application performance requirements

## Decision

We will use **Electron IPC communication exclusively** with no internal APIs:

- **Electron IPC**: Native inter-process communication for all frontend-backend communication
- **Binary Protocols**: Efficient binary streaming for high-bandwidth scientific data
- **Structured Messages**: Pydantic V2-validated message schemas for type safety
- **No Internal APIs**: Explicitly avoid REST/HTTP APIs for internal component communication
- **No WebSocket**: Reject WebSocket complexity as unnecessary for desktop-only application
- **Shared Protocols**: Common TypeScript/Python message definitions in `/shared/protocols/`

## Consequences

### Positive

- **Optimal Performance**: Native IPC provides maximum performance for high-bandwidth scientific data
- **Lower Latency**: Direct process communication eliminates network stack overhead
- **Enhanced Security**: No network ports exposed, even locally
- **Simplified Architecture**: Single communication path reduces complexity by ~30%
- **Better Resource Utilization**: Direct memory sharing for large datasets
- **Type Safety**: Shared message schemas prevent communication errors
- **Cross-Platform**: Works consistently across macOS development and Windows production
- **Desktop Optimized**: Leverages Electron's native IPC mechanisms fully

### Negative

- **Development Debugging**: Requires Electron DevTools for IPC debugging (vs browser tools)
- **Protocol Maintenance**: Must maintain shared message schemas across TypeScript and Python
- **Development Setup**: Requires both processes running for full functionality testing
- **Message Versioning**: Schema evolution requires careful backward compatibility
- **No Remote Access**: Cannot support remote monitoring without additional implementation

### Risks

- **Communication Failures**: Process crashes could break communication channels
- **Message Schema Drift**: TypeScript and Python definitions could diverge without proper tooling
- **Performance Bottlenecks**: Large message volumes could saturate IPC channels
- **Debugging Complexity**: IPC debugging requires specialized tools compared to HTTP

## Alternatives Considered

- **REST/HTTP APIs**: Rejected as inappropriate for internal desktop application communication
- **WebSocket Communication**: Rejected after analysis - unnecessary complexity for desktop-only scientific application
- **Direct File System Communication**: Rejected due to complexity and poor real-time characteristics
- **Named Pipes**: Rejected due to platform-specific limitations and complexity
- **TCP Sockets**: Rejected as IPC provides better performance for local communication
- **gRPC**: Rejected as over-engineered for internal desktop communication

### WebSocket Rejection Rationale

WebSocket was initially considered for development flexibility and potential remote monitoring, but rejected because:

- **Performance**: WebSocket adds unnecessary serialization overhead for local high-bandwidth data
- **Security**: Scientific equipment should not expose network interfaces
- **Complexity**: Dual communication paths increase maintenance burden
- **YAGNI**: Remote monitoring was speculative, not an actual requirement
- **Desktop Focus**: Pure desktop application benefits more from native IPC optimization

## Related Decisions

- Depends on: ADR-0003 (Thin Client Architecture)
- Depends on: ADR-0004 (Modern Technology Stack - Pydantic V2 for validation)
- Enables: Future ADRs on message protocols, error handling, monitoring

## Notes

This decision explicitly rejects internal APIs and WebSocket fallbacks to maintain clear architectural boundaries and optimal performance. The system is designed as a cohesive desktop scientific application, not a distributed system requiring web-based communication.

Pure Electron IPC provides:
- Maximum performance for scientific imaging data streams
- Optimal security posture for laboratory equipment
- Simplified architecture with single communication path
- Better resource utilization for high-bandwidth applications

Message protocol design should prioritize:
- Clear request/response patterns optimized for IPC
- Efficient binary streaming for scientific data
- Comprehensive error handling for process communication
- Schema versioning and evolution for long-term maintainability

This architecture decision prioritizes scientific application performance and security over web development convenience.