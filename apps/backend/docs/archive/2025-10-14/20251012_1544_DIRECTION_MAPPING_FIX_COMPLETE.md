# Direction Mapping Fix - Complete

## Problem Discovered

The phase maps extracted from MATLAB sample data had **incorrect direction labels**. Testing revealed:

```
NPY File      → Actual Content (HDF5 Reference)
phase_LR.npy  → TB data (vertical, not horizontal)
phase_RL.npy  → LR data (horizontal, not vertical)
phase_TB.npy  → BT data (vertical opposite)
phase_BT.npy  → RL data (horizontal opposite)
```

This caused the pipeline to compute retinotopic maps with swapped horizontal/vertical axes.

## Root Cause

The extraction script (`scripts/convert_sample_data.py`) had the file-to-direction mapping backwards:
- Assumed horizontal (LR/RL) came from 005[0,0] and 004[0,0]
- Assumed vertical (TB/BT) came from 005[0,1] and 004[0,1]

But the actual mapping was:
- Horizontal (LR/RL) comes from 004[0,0] and 004[0,1]
- Vertical (TB/BT) comes from 005[0,0] and 005[0,1]

Counter-intuitively:
- "azimuth experiment" (005) contains **vertical** retinotopy data
- "altitude experiment" (004) contains **horizontal** retinotopy data

## Fixes Applied

### 1. Fixed Extraction Script
**File:** `scripts/convert_sample_data.py`

**Changes:**
```python
# OLD (WRONG):
LR ← 005[0,0], RL ← 004[0,0]  # horizontal
TB ← 005[0,1], BT ← 004[0,1]  # vertical

# NEW (CORRECT):
LR ← 004[0,0], RL ← 004[0,1]  # horizontal
TB ← 005[0,0], BT ← 005[0,1]  # vertical
```

### 2. Regenerated Sample Data
Ran the corrected extraction script to regenerate all `.npy` files with proper direction labels.

**Verification:**
```
Phase Map Correlation with HDF5 Reference:
  LR: 1.000000 ✓
  RL: 1.000000 ✓
  TB: 1.000000 ✓
  BT: 1.000000 ✓
```

### 3. Simplified Bidirectional Analysis
**File:** `src/analysis/pipeline.py`

The reference implementation uses **simple phase subtraction** without hemodynamic delay correction:

```python
# OLD (complex delay correction):
delay = angle(exp(i*forward) + exp(i*reverse))
forward_corrected = forward - delay
reverse_corrected = reverse - delay
center = (wrap(forward_corrected) - wrap(reverse_corrected)) / 2

# NEW (simple subtraction - matches reference):
center = (forward - reverse) / 2
```

**Verification:**
```
Retinotopic Map Correlation with Reference:
  Azimuth:  1.000000 ✓✓✓
  Elevation: 1.000000 ✓✓✓
```

## Pipeline Status

### ✅ Working Correctly
1. **Phase extraction** - Direction labels now correct
2. **Bidirectional analysis** - Simple subtraction matches reference
3. **Retinotopic maps** - Perfect correlation (1.0) with reference
4. **VFS computation** - Gradient angle method with FFT smoothing
5. **Statistical filtering** - Coherence → statistical threshold pipeline

### 📊 Current Configuration
```python
smoothing_sigma = 3.0          # FFT-based Gaussian for retinotopy
vfs_threshold_sd = 2.0         # Statistical VFS threshold (2 SD)
coherence_threshold = 0.3      # Signal reliability cutoff
phase_filter_sigma = 0.0       # Disabled (matches MATLAB)
```

## Files Modified

1. `scripts/convert_sample_data.py` - Fixed direction mapping
2. `src/analysis/pipeline.py` - Simplified bidirectional_analysis()
3. `data/sessions/sample_session/*.npy` - Regenerated with correct labels

## Verification

All phase maps now match reference with correlation=1.0:
- ✓ Phase_LR.npy matches HDF5 LR
- ✓ Phase_RL.npy matches HDF5 RL
- ✓ Phase_TB.npy matches HDF5 TB
- ✓ Phase_BT.npy matches HDF5 BT

Retinotopic maps computed from corrected phases:
- ✓ Azimuth correlation: 1.000000
- ✓ Elevation correlation: 1.000000

## Output

Successfully generated 36 figures including:
- Centered horizontal/vertical retinotopy
- VFS maps (raw, coherence-thresh, statistical, magnitude-thresh)
- VFS with boundary overlays
- Composite response magnitude figures

All figures now use data with correct direction mappings.

---

**Date:** 2025-10-12
**Status:** ✅ COMPLETE - Direction mapping fixed, data regenerated, pipeline verified
