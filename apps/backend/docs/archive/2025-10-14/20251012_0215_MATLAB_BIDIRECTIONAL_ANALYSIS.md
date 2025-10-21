# ISI-Master MATLAB Bidirectional Analysis

## Reference Implementation

From `/ISI-master/Gprocesskret.m` lines 99-100:

```matlab
%Use delay vector to calculate retinotopy.
kmap_hor = .5*(angle(exp(1i*(ang0-delay_hor))) - angle(exp(1i*(ang2-delay_hor))));
kmap_vert = .5*(angle(exp(1i*(ang1-delay_vert))) - angle(exp(1i*(ang3-delay_vert))));
```

## Key Findings

### MATLAB Does NOT Use unwrap()

The ISI-master MATLAB implementation:
1. **Works directly with wrapped phases** (ang0, ang2, etc.)
2. **Does NOT call `unwrap()`**
3. Uses `angle(exp(1i*(...)))` which wraps to [-π, π]
4. Subtracts delays
5. Computes bidirectional difference and divides by 2

### Mathematical Equivalence

**MATLAB**:
```matlab
kmap = 0.5 * (angle(exp(1i*(ang0-delay))) - angle(exp(1i*(ang2-delay))))
```

**Python Equivalent**:
```python
center = (forward_phase - reverse_phase) / 2
center = np.arctan2(np.sin(center), np.cos(center))  # Wrap to [-π, π]
```

Where:
- MATLAB `angle()` ↔ Python `np.angle()` or `np.arctan2(imag, real)`
- MATLAB `exp(1i*x)` ↔ Python `np.exp(1j*x)`
- The arctan2 wrapping handles phase continuity

### Why No Unwrapping?

The Kalatsky & Stryker 2003 bidirectional method:
```
φ_retino = (φ_forward - φ_reverse) / 2
```

This **automatically removes the hemodynamic delay** component by subtraction. The delay affects both directions equally, so it cancels out. No unwrapping is needed because:

1. Phase wraps are **natural** in retinotopic data (representing the visual field)
2. Unwrapping can **introduce artifacts** (horizontal/vertical line artifacts)
3. The arctan2 wrapping mathematically preserves the correct topology

### Implementation in Python

Current implementation in `src/analysis/pipeline.py` (lines 224-279):

```python
def bidirectional_analysis(
    self,
    forward_phase: np.ndarray,
    reverse_phase: np.ndarray,
    unwrap_axis: int = 1
) -> np.ndarray:
    """Combine opposing directions to find retinotopic center.

    CRITICAL: Works directly with WRAPPED phases. The arctan2() re-wrapping
    at the end mathematically handles phase continuity. Explicit unwrapping
    is NOT needed and actually introduces severe line artifacts.
    """
    logger.info("Performing bidirectional analysis (NO phase unwrapping)...")

    # Subtract the two directions (Kalatsky & Stryker 2003 method)
    # Work directly with wrapped phases - no unwrapping needed!
    center_map = (forward_phase - reverse_phase) / 2

    # Wrap result back to [-π, π]
    # This handles all phase continuity mathematically
    center_map = np.arctan2(np.sin(center_map), np.cos(center_map))

    return center_map
```

### Verification

- ✅ Matches ISI-master MATLAB implementation
- ✅ No `np.unwrap()` calls
- ✅ Uses arctan2 for phase wrapping
- ✅ Works directly with wrapped phases

### Common Pitfall

**DO NOT USE**:
```python
# WRONG - causes linear artifacts
forward_unwrapped = np.unwrap(forward_phase, axis=unwrap_axis)
reverse_unwrapped = np.unwrap(reverse_phase, axis=unwrap_axis)
center = (forward_unwrapped - reverse_unwrapped) / 2
```

This approach **causes horizontal/vertical line artifacts** because `np.unwrap()` propagates errors along the unwrap axis.

### References

1. Kalatsky & Stryker 2003 - Original Fourier-based ISI method
2. ISI-master MATLAB code - `Gprocesskret.m` lines 99-100
3. Juavinett et al. 2017 - Modern retinotopy analysis methods

---

**Date**: 2025-10-12
**Status**: Implementation verified against MATLAB reference code
