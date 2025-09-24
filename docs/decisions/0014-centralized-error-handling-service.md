# 14. Centralized Error Handling Service

Date: 2025-01-14

## Status

Accepted

## Context

The ISI Macroscope system had significant architectural violations in error handling that created maintenance debt and violated Clean Architecture principles:

**Critical Issues Identified:**
- **17+ scattered custom exception classes** across different modules (ISIAnalysisError, DatasetError, RepositoryError, etc.)
- **Massive DRY violations** with duplicated try/catch/log/raise patterns in every service
- **Infrastructure contamination** in domain layer with direct logging calls and external library imports
- **Inconsistent error handling patterns** across services leading to different error formats and recovery behaviors
- **Poor error categorization** making it impossible to implement appropriate recovery strategies
- **No centralized error tracking** or metrics collection capabilities

**Clean Architecture Violations:**
- Domain services contained logging.getLogger() calls (infrastructure dependency)
- Domain entities imported numpy/scipy directly (computational library dependency)
- Exception handling was scattered with no consistent patterns
- Error recovery logic was embedded in business logic instead of being orchestrated

These violations made the system difficult to maintain, test, and extend while compromising the architectural integrity required for scientific applications.

## Decision

Implement a **centralized error handling architecture** with two complementary services that enforce Clean Architecture separation:

**1. Domain Error Service** (`domain/services/error_handler.py`):
- Pure domain service with zero external dependencies
- Centralized definitions for all system error types with consistent categorization
- Recovery strategy specification (retry, fallback, user intervention, system restart)
- Single `ISIDomainError` class to replace all scattered custom exceptions
- Protocol-based design for dependency injection

**2. Application Error Orchestrator** (`application/services/error_orchestrator.py`):
- Infrastructure-aware error handling implementing logging, metrics, and alerting
- Implements `ErrorLogger` protocol for integration with domain services
- Coordinates error recovery strategy execution
- Provides error history tracking and analysis capabilities
- Manages alert callbacks for critical error notifications

**3. Architecture Compliance Enforcement**:
- Domain layer: Only pure error definitions and business rules (no infrastructure concerns)
- Application layer: Error orchestration, logging, metrics, recovery coordination
- Infrastructure layer: Platform-specific error reporting and alerting systems

## Consequences

### Positive

- **DRY Compliance**: Eliminated 17+ duplicated exception classes and countless scattered error handling patterns
- **Clean Architecture Enforcement**: Perfect separation of concerns with domain layer purity maintained
- **Consistent Error Handling**: Unified error format, categorization, and recovery strategy across all system components
- **Enhanced Maintainability**: Single point of truth for error definitions and handling logic
- **Improved Testing**: Centralized error handling enables comprehensive error scenario testing
- **Better Observability**: Centralized metrics and tracking provide system-wide error visibility
- **Flexible Recovery**: Pluggable recovery strategies enable sophisticated error handling
- **Domain Purity**: Zero infrastructure dependencies in domain layer enables pure unit testing

### Negative

- **Initial Migration Effort**: Required systematic refactoring of existing error handling patterns
- **Learning Curve**: Team must understand dependency injection and protocol-based design patterns
- **Slightly More Complex Setup**: Services require proper dependency injection configuration

### Risks

- **Performance Impact**: Centralized error handling could introduce latency (mitigated by efficient implementation)
- **Single Point of Failure**: Error handling service becomes critical dependency (mitigated by comprehensive testing)
- **Over-Engineering Risk**: Could become too complex for simple error cases (mitigated by simple API design)

## Alternatives Considered

- **Option A - Keep Scattered Exceptions**: Maintain status quo with scattered custom exceptions
  - **Rejected**: Violates DRY principle and makes maintenance increasingly difficult
  - **Problems**: Inconsistent error handling, duplicated code, architectural violations

- **Option B - Simple Exception Consolidation**: Just replace custom exceptions with standard Python exceptions
  - **Rejected**: Doesn't address architectural violations or provide error categorization
  - **Problems**: Still requires scattered error handling logic, no recovery strategy support

- **Option C - Third-Party Error Handling Library**: Use external error handling framework
  - **Rejected**: Introduces external dependency and may not fit Clean Architecture requirements
  - **Problems**: Less control over error handling patterns, potential architectural violations

## Related Decisions

- **ADR-0002**: Adopt Clean Architecture - This decision directly supports Clean Architecture enforcement
- **ADR-0011**: Error Recovery and Graceful Degradation - This decision provides the implementation foundation for sophisticated recovery strategies
- **ADR-0012**: Fundamental Architectural Principles - This decision enforces SOLID and DRY principles

## Notes

**Implementation Details:**
- All domain services inject `ErrorHandlingService` through constructor dependency injection
- Application layer uses `ErrorOrchestrator` for infrastructure-aware error handling
- Global convenience functions provided for common error patterns while maintaining proper injection
- Comprehensive error categorization supports appropriate recovery strategies
- Protocol-based design enables testability and flexibility

**Migration Strategy:**
1. Create centralized error handling services
2. Update domain services to inject ErrorHandlingService
3. Replace scattered exceptions with ISIDomainError
4. Remove infrastructure dependencies from domain layer
5. Update application layer to use ErrorOrchestrator
6. Comprehensive testing of error scenarios

This decision represents a significant architectural improvement that eliminates technical debt while enforcing proper Clean Architecture patterns essential for maintainable scientific software.