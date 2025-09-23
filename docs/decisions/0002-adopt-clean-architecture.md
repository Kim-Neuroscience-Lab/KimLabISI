# 2. Adopt Clean Architecture

Date: 2025-10-22

## Status

Accepted

## Context

The current codebase has become difficult to understand and maintain:

- Business logic is scattered across UI components and message handlers
- Database concerns leak into business rules
- Testing is difficult due to tight coupling
- Framework changes would require massive refactoring
- WebSocket message handling is intertwined with business logic

## Decision

We will adopt Clean Architecture principles with clear layer separation:

- Domain layer: Pure business logic, zero dependencies
- Application layer: Use cases orchestrating domain logic, message handlers
- Infrastructure layer: WebSocket server, database, external services
- Presentation layer: Message protocol handlers, serialization

## Consequences

### Positive

- Business logic becomes framework-agnostic
- Improved testability (can test domain without mocks)
- Clear dependency rules prevent coupling
- Easier to understand system boundaries

### Negative

- More initial boilerplate code
- Learning curve for team members
- May feel over-engineered for simple CRUD operations

### Risks

- Team might bypass architecture for "quick fixes"
- Anemic domain models if not carefully implemented

## Alternatives Considered

- MVC: Too simplistic for our complexity
- Microservices: Premature optimization, adds operational complexity
- Keep current structure: Technical debt too high
