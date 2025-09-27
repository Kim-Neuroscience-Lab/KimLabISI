# 7. Parameter Separation: Generation vs Acquisition

Date: 2025-01-14

## Status

Accepted

## Context

The ISI retinotopic mapping workflow involves two distinct phases with different parameter requirements:

- **Stimulus Generation**: Creating visual patterns (bar width, drift speed, checkerboard size, spherical correction)
- **Acquisition Protocol**: Data capture execution (repetitions, frame rates, timing intervals, session naming)

Initial design conflated these parameters, leading to confusion about:
- When parameters are set and validated
- Which parameters affect stimulus dataset reuse
- What changes invalidate existing generated stimuli
- How to maintain scientific reproducibility

Mixed parameters would create issues with:
- Dataset compatibility checking (generation params mixed with protocol params)
- Parameter reuse workflows (loading incompatible parameter sets)
- Scientific reproducibility (unclear which params affect stimulus content vs execution)

## Decision

We will **strictly separate generation-time and acquisition-time parameters**:

### Generation-Time Parameters (Stimulus Characteristics)
- **Spatial Configuration**: Monitor distance, angle, screen dimensions
- **Stimulus Properties**: Bar width, drift speed, pattern type, checkerboard size, flicker frequency
- **Mathematical Properties**: Spherical transform, coordinate correction
- **Quality Settings**: Resolution, compression, geometric validation

### Acquisition-Time Parameters (Protocol Execution)
- **Protocol Control**: Repetitions per direction, trial sequencing, inter-trial timing
- **Session Management**: Session naming, metadata, export formats
- **Hardware Settings**: Frame rates, exposure times, trigger modes
- **Real-Time Control**: Buffer management, error handling preferences

### Implementation Rules
- **Generation Phase**: Only accepts generation-time parameters
- **Acquisition Phase**: Only accepts acquisition-time parameters
- **Dataset Reuse**: Based exclusively on generation-time parameter matching
- **State Transitions**: Parameter type determines which workflow phase is affected

## Consequences

### Positive

- **Scientific Clarity**: Clear distinction between stimulus content and experimental execution
- **Dataset Reuse Reliability**: Exact parameter matching prevents invalid stimulus reuse
- **Parameter Independence**: Acquisition changes don't invalidate generated stimuli
- **Reproducibility**: Stimulus datasets contain only parameters that affect visual content
- **Development Clarity**: Clear boundaries for parameter validation and UI design
- **Storage Efficiency**: Generated stimuli can be reused across different acquisition protocols

### Negative

- **User Interface Complexity**: Parameters must be set at appropriate workflow phases
- **Validation Complexity**: Different parameter sets require different validation rules
- **Documentation Overhead**: Must clearly specify which parameters belong to which phase
- **Migration Complexity**: Existing configurations must be split correctly

### Risks

- **User Confusion**: Users may expect to set all parameters at once
- **Parameter Dependencies**: Some parameters may have cross-phase relationships
- **Validation Gaps**: Parameters may not be validated at appropriate times

## Alternatives Considered

- **Unified Parameter Set**: Rejected due to confusion about dataset reuse and scientific reproducibility
- **Phase-Agnostic Parameters**: Rejected as it obscures when parameters affect stimulus content
- **Runtime Parameter Classification**: Rejected due to complexity and potential for errors
- **Hierarchical Parameters**: Rejected as over-engineered for the specific requirements

## Related Decisions

- Depends on: ADR-0006 (Twelve-State Workflow State Machine)
- Enables: Future ADRs on dataset reuse, HDF5 metadata schemas, parameter validation

## Notes

This separation aligns with scientific best practices where:
- Stimulus characteristics are fixed properties of visual patterns
- Experimental protocols are methodological choices independent of stimulus content

Parameter separation enables:
- Stimulus datasets to be shared across different experimental protocols
- Clear understanding of what parameters affect scientific reproducibility
- Efficient storage and reuse of computationally expensive stimulus generation

Implementation should enforce separation through:
- Type-safe parameter schemas (Pydantic models)
- Phase-specific UI components
- Clear documentation and error messages
- Validation at appropriate workflow transitions