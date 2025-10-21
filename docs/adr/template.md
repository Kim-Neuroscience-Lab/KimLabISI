# ADR-NNN: [Decision Title]

**Date**: YYYY-MM-DD
**Status**: Proposed | Accepted | Deprecated | Superseded by ADR-XXX
**Deciders**: @username, @team
**Technical Story**: [Link to GitHub issue or investigation]

---

## Context and Problem Statement

[Describe the context and problem that led to this decision. Include background information that helps understand why this decision was necessary.]

## Decision Drivers

- [Driver 1: e.g., "Performance requirements for real-time acquisition at 60 fps"]
- [Driver 2: e.g., "MATLAB compatibility for scientific validation"]
- [Driver 3: e.g., "Maintainability and code clarity"]
- [Driver 4: e.g., "Hardware limitations (camera bandwidth)"]

## Considered Options

### Option 1: [Name of Option 1]

**Description**: [Brief description of this approach]

**Pros**:
- [Positive aspect 1]
- [Positive aspect 2]

**Cons**:
- [Negative aspect 1]
- [Negative aspect 2]

**Implementation Effort**: Low | Medium | High

### Option 2: [Name of Option 2]

**Description**: [Brief description of this approach]

**Pros**:
- [Positive aspect 1]
- [Positive aspect 2]

**Cons**:
- [Negative aspect 1]
- [Negative aspect 2]

**Implementation Effort**: Low | Medium | High

### Option 3: [Name of Option 3]

[Repeat structure above]

## Decision Outcome

**Chosen option**: Option X - [Name]

**Rationale**:
[Explain why this option was chosen over the alternatives. Include specific decision drivers that were most influential.]

**Positive Consequences**:
- [Expected benefit 1]
- [Expected benefit 2]
- [Expected benefit 3]

**Negative Consequences**:
- [Tradeoff 1]
- [Tradeoff 2]

**Accepted Risks**:
- [Risk 1 and mitigation strategy]
- [Risk 2 and mitigation strategy]

## Implementation

**Files Changed**:
- `path/to/file1.py:100-250` - [What changed]
- `path/to/file2.ts:50-120` - [What changed]
- `path/to/file3.py` - [New file created]

**Key Code Example**:
```python
# Example showing the decision in action
def example_implementation():
    """Shows how the decision manifests in code."""
    pass
```

**Data Structures**:
[If applicable, show new data structures or schemas]

**Migration Guide**:
[If this changes existing APIs or workflows, provide migration steps]

```python
# Before
old_api_call(param1, param2)

# After
new_api_call(structured_params={'param1': value, 'param2': value})
```

## Validation

**Testing**:
- [How was this decision validated?]
- [What tests were added?]
- [What manual testing was performed?]

**Performance Impact**:
- [Measured performance changes, if applicable]

**Verification**:
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Documentation updated
- [ ] Performance benchmarks run

**References**:
- [Scientific paper: Author et al. (Year)]
- [External documentation URL]
- [Related GitHub issue]

## Follow-up

**TODO**:
- [ ] Update component documentation in `docs/components/`
- [ ] Add integration tests for new behavior
- [ ] Update troubleshooting guide if needed
- [ ] Update getting started guide if user-facing
- [ ] Consider deprecation timeline for old approach

**Related ADRs**:
- Supersedes: [ADR-XXX: Old Decision]
- Related to: [ADR-YYY: Related Decision]
- Influences: [ADR-ZZZ: Future Decision]

**Future Considerations**:
- [Potential future improvements]
- [Known limitations to address later]

---

**Review History**:
- 2025-XX-XX: Initial proposal
- 2025-XX-XX: Accepted after team review
- 2025-XX-XX: Updated based on implementation learnings
