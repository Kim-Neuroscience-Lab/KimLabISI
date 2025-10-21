# Architecture Decision Records (ADRs)

**Last Updated**: 2025-10-15 01:48

> Documented architectural decisions with rationale, alternatives considered, and implementation details.

## ⚠️ CRITICAL COMPLIANCE ALERT

**Status**: ❌ WIDESPREAD VIOLATIONS DETECTED (2025-10-15 01:10 Audit)

ADR-004 "Parameter Manager SSoT + NO Hardcoded Defaults" is being **systematically violated** across the codebase:
- **23+ instances** of hardcoded parameter defaults found
- Analysis Manager, Main.py, Parameter Manager itself all violate specification
- Only Acquisition Manager follows correct pattern
- **Production readiness**: REJECTED until remediated

See: `docs/audits/2025-10-15_0110_comprehensive_audit.md` and `docs/TODO.md` for details.

---

## What is an ADR?

An **Architecture Decision Record** documents an important architectural decision made along with its context and consequences. ADRs help:

- Understand why past decisions were made
- Evaluate whether decisions should be revisited
- Onboard new team members quickly
- Avoid repeating past mistakes
- Provide context for future decisions

---

## ADR Index

| ID | Title | Status | Date | Priority |
|----|-------|--------|------|----------|
| [006](006-unified-logging.md) | Unified Logging Architecture | ✅ Accepted | 2025-10-15 | High |
| [005](005-no-legacy-code-policy.md) | No Legacy Code Policy | Accepted | 2025-10-15 | Critical |
| [004](004-parameter-manager-refactor.md) | Parameter Manager SSoT + NO Hardcoded Defaults | Accepted | 2025-10-11 (Updated 2025-10-15) | **CRITICAL** |
| [003](003-backend-analysis-rendering.md) | Backend Analysis Rendering | Accepted | 2025-10-09 | High |
| [002](002-unified-stimulus-controller.md) | Unified Stimulus Controller | Accepted | 2025-10-14 | High |
| [001](001-backend-modular-architecture.md) | Backend Modular Architecture | Accepted | 2025-10-10 | High |

---

## Status Definitions

- **Proposed**: Under discussion, not yet implemented
- **Accepted**: Decision made and implemented
- **Deprecated**: No longer recommended, superseded by better approach
- **Superseded**: Replaced by another ADR

---

## Creating a New ADR

1. Copy the [ADR template](template.md)
2. Name it `NNN-short-title.md` (increment number)
3. Fill in all sections thoroughly
4. Get team review
5. Update this index
6. Link to it from related component docs

---

## Guidelines

### When to Create an ADR

Create an ADR when:
- Making a significant architectural decision
- Choosing between multiple viable approaches
- Making a decision with long-term implications
- Changing a fundamental system design
- Introducing new patterns or paradigms

### When NOT to Create an ADR

Don't create an ADR for:
- Bug fixes (use changelog instead)
- Minor refactoring (use component docs)
- Obvious decisions with no alternatives
- Implementation details (use code comments)

---

## Related Documentation

- [Changelog](../CHANGELOG.md) - Recent changes
- [Components](../components/README.md) - Component details
- [Investigations](../investigations/active/README.md) - Active research

---

**ADR Index Version**: 1.2
**Next ADR Number**: 007
**Last Updated**: 2025-10-15
