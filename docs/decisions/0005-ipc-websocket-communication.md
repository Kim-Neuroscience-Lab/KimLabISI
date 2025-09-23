# 5. IPC/WebSocket Communication (No Internal APIs)

Date: 2025-01-14

## Status

Accepted

## Context

The thin client architecture requires communication between Electron frontend and Python backend for:

- Real-time monitoring data (downsampled camera previews, hardware status)
- User commands (start acquisition, change parameters, navigate workflow)
- State synchronization (workflow phase, progress updates, error notifications)
- Configuration management (spatial parameters, stimulus settings)

Communication mechanisms must support:
- Real-time data streaming for monitoring
- Bidirectional command/response patterns
- Type-safe message protocols
- Cross-process error handling
- Development and debugging workflows

## Decision

We will use **IPC/WebSocket communication exclusively** with no internal APIs:

- **Electron IPC**: Native inter-process communication for local desktop application
- **WebSocket Fallback**: WebSocket server for development flexibility and potential remote monitoring
- **Structured Messages**: Pydantic V2-validated message schemas for type safety
- **No Internal APIs**: Explicitly avoid REST/HTTP APIs for internal component communication
- **Shared Protocols**: Common TypeScript/Python message definitions in `/shared/protocols/`

## Consequences

### Positive

- **Native Performance**: Electron IPC provides optimal performance for desktop applications
- **Type Safety**: Shared message schemas prevent communication errors
- **Real-Time Capable**: Both IPC and WebSocket support streaming data efficiently
- **Development Flexibility**: WebSocket enables browser-based development/debugging tools
- **Cross-Platform**: Works consistently across macOS development and Windows production
- **No HTTP Overhead**: Avoids unnecessary REST/JSON serialization for internal communication
- **Security**: No exposed HTTP endpoints that could be accessed externally

### Negative

- **Protocol Maintenance**: Must maintain shared message schemas across TypeScript and Python
- **Debugging Complexity**: IPC debugging requires specialized tools compared to HTTP
- **Development Setup**: Requires both processes running for full functionality testing
- **Message Versioning**: Schema evolution requires careful backward compatibility

### Risks

- **Communication Failures**: Process crashes could break communication channels
- **Message Schema Drift**: TypeScript and Python definitions could diverge without proper tooling
- **Performance Bottlenecks**: Large message volumes could saturate IPC channels

## Alternatives Considered

- **REST/HTTP APIs**: Rejected as inappropriate for internal desktop application communication
- **Direct File System Communication**: Rejected due to complexity and poor real-time characteristics
- **Named Pipes**: Rejected due to platform-specific limitations and complexity
- **TCP Sockets**: Rejected as WebSocket provides better abstraction with same underlying transport
- **gRPC**: Rejected as over-engineered for internal desktop communication

## Related Decisions

- Depends on: ADR-0003 (Thin Client Architecture)
- Depends on: ADR-0004 (Modern Technology Stack - Pydantic V2 for validation)
- Enables: Future ADRs on message protocols, error handling, monitoring

## Notes

This decision explicitly rejects internal APIs to maintain clear architectural boundaries. The system is designed as a cohesive desktop application, not a distributed system requiring API-based integration.

IPC/WebSocket choice supports both local development (IPC) and potential remote monitoring scenarios (WebSocket) while maintaining type safety through shared Pydantic schemas that generate both Python and TypeScript definitions.

Message protocol design should prioritize:
- Clear request/response patterns
- Event streaming for real-time updates
- Comprehensive error handling
- Schema versioning and evolution