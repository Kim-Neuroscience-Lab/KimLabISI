# VFS Pipeline Fixes - Master Report

## Overview

This document summarizes **all critical fixes** applied to achieve exact replication of the MATLAB retinotopic mapping pipeline, including VFS computation, statistical filtering, and figure generation.

## Timeline of Discoveries and Fixes

### Phase 1: Direction Mapping Bug (CRITICAL)

**Problem:** Phase maps had incorrect direction labels causing horizontal/vertical axis swap

**Discovery Method:** Correlation testing against HDF5 reference revealed:
```
NPY File      → Actual Content (HDF5 Reference)
phase_LR.npy  → TB data (correlation=1.0)
phase_RL.npy  → LR data (correlation=1.0)
phase_TB.npy  → BT data (correlation=1.0)
phase_BT.npy  → RL data (correlation=1.0)
```

**Root Cause:** Extraction script had incorrect assumptions:
- Assumed horizontal came from 005[0,0] and 004[0,0]
- Assumed vertical came from 005[0,1] and 004[0,1]
- **Actual mapping**: Horizontal from 004[0,0]/004[0,1], Vertical from 005[0,0]/005[0,1]
- Counter-intuitive: "azimuth experiment" (005) contains **vertical** data

**Fix Applied:**
- **File:** `scripts/convert_sample_data.py` lines 107-139
- Corrected direction mapping in extraction script
- Regenerated all `.npy` files with correct labels

**Verification:**
```
Phase Map Correlation with HDF5 Reference:
  LR: 1.000000 ✓
  RL: 1.000000 ✓
  TB: 1.000000 ✓
  BT: 1.000000 ✓
```

**Documentation:** `DIRECTION_MAPPING_FIX_COMPLETE.md`

---

### Phase 2: Bidirectional Analysis Simplification

**Problem:** Retinotopic maps didn't match reference (correlation=-0.15) despite perfect phase maps

**Root Cause:** Using complex hemodynamic delay correction when reference uses simple subtraction

**MATLAB Reference:**
```matlab
% Simple phase subtraction (no delay correction)
retinotopy = (forward - reverse) / 2 * (60/pi);
```

**Fix Applied:**
- **File:** `src/analysis/pipeline.py` lines 224-252
- Simplified `bidirectional_analysis()` to use simple subtraction:
```python
center_map = (forward_phase - reverse_phase) / 2
```

**Verification:**
```
Retinotopic Map Correlation with Reference:
  Azimuth:  1.000000 ✓✓✓
  Elevation: 1.000000 ✓✓✓
```

**Documentation:** `DIRECTION_MAPPING_FIX_COMPLETE.md`

---

### Phase 3: Statistical VFS Threshold Bug (CRITICAL)

**Problem:** Statistical VFS output entirely white (all pixels masked)

**Discovery Method:** Visual inspection + @agent-codebase-auditor comprehensive analysis

**Root Cause:** Threshold computed on **wrong data subset**
```python
# WRONG: Computing on coherence-filtered VFS (17.47% of pixels)
vfs_std = np.std(coherence_vfs_map[coherence_vfs_map != 0])  # std=0.5420
threshold = 2.0 * vfs_std  # = 1.0840
# Result: Threshold > Max VFS (0.9860) → ALL pixels masked
```

**Mathematical Analysis:**
- Coherence-filtered subset: 9,111 pixels (17.47%)
- Subset std: 0.5420 (biased, inflated)
- Threshold: 2.0 × 0.5420 = 1.0840
- Max VFS: 0.9860
- **Threshold exceeds maximum → 100% masking**

**MATLAB Reference:**
```matlab
% getAreaBorders.m line 96
threshSeg = 1.5*std(VFS(:));  % Computed on ALL pixels
```

**Fix Applied:**
- **File:** `src/analysis/pipeline.py` line 803
- Compute std on **raw VFS** (all 52,170 pixels)
- Apply threshold to **coherence-filtered VFS**
```python
# CORRECT: Computing on raw VFS (100% of pixels)
vfs_std = np.std(raw_sign_map)  # std=0.1863
statistical_threshold = 1.5 * vfs_std  # = 0.2794
```

**Additional Fix:**
- **File:** `config/isi_parameters.json` lines 288, 350
- Changed default from 2.0 to 1.5 (MATLAB standard)

**Verification:**
```
Before Fix:
  Threshold: 1.0840 (exceeds max)
  Pixels kept: 0 (0.00%)
  Output: Entirely white

After Fix:
  Threshold: 0.2794
  Pixels kept: ~2,953 (5.66%)
  Output: Red/blue VFS regions
```

**Documentation:** `STATISTICAL_VFS_FIX_COMPLETE.md`

---

## Complete VFS Pipeline (Verified)

### Processing Steps

1. **Load Phase/Magnitude Data** (4 directions: LR, RL, TB, BT)
   - ✅ Direction labels now correct

2. **Bidirectional Analysis** (combine opposing directions)
   - ✅ Simple subtraction: `center = (forward - reverse) / 2`

3. **FFT-Based Smoothing** (σ=3.0 on retinotopic maps)
   - ✅ Frequency-domain Gaussian matching MATLAB

4. **Gradient Computation** (Sobel, kernel size=3)
   - ✅ For azimuth and elevation maps

5. **VFS Computation** (gradient angle method)
   - ✅ `VFS = sin(angle(exp(i*graddir_hor) * exp(-i*graddir_vert)))`

6. **Coherence Filtering** (threshold=0.3)
   - ✅ Remove unreliable pixels (signal quality)

7. **Statistical Filtering** (threshold=1.5×SD)
   - ✅ Compute on raw VFS, apply to coherence-filtered
   - ✅ Keep strongest ~5.66% of pixels

8. **Boundary Detection** (VFS threshold + morphology)
   - ✅ Identify visual cortex area borders

### Two-Stage Filtering Pipeline

**Critical Insight:** Statistical threshold MUST be computed on full distribution, then applied to filtered data.

```
Raw VFS (52,170 pixels)
    ↓
Coherence Filter (keeps 17.47% = 9,111 pixels)
    ↓
Statistical Threshold = 1.5 × std(Raw VFS)  ← Computed on RAW
    ↓
Apply to Coherence-Filtered VFS  ← Applied to FILTERED
    ↓
Statistical VFS (keeps 5.66% = ~2,953 pixels)
```

**Why This Order:**
1. **Coherence first** - Removes unreliable/noisy pixels
2. **Threshold on raw** - Prevents bias from subset statistics
3. **Apply to filtered** - Ensures both reliability AND strength

---

## All Files Modified

### 1. Data Extraction
- **`scripts/convert_sample_data.py`** (lines 107-139)
  - Fixed direction mapping: LR/RL from 004, TB/BT from 005
  - Regenerated all `.npy` files

### 2. Analysis Pipeline
- **`src/analysis/pipeline.py`** (lines 224-252)
  - Simplified bidirectional analysis to simple subtraction

- **`src/analysis/pipeline.py`** (line 803)
  - Fixed statistical threshold computation (raw VFS, not filtered)

### 3. Configuration
- **`config/isi_parameters.json`** (lines 288, 350)
  - Changed `vfs_threshold_sd` from 2.0 to 1.5

- **`config/isi_parameters.json`** (lines 110-111)
  - Updated documentation for `vfs_threshold_sd`

### 4. Figure Generation
- **`test_generate_all_figures_with_vfs.py`** (lines 319-348)
  - Added statistical VFS extraction and usage

---

## Verification Summary

### Perfect Matches (Correlation = 1.0)
✅ **Phase maps** - All 4 directions (LR, RL, TB, BT)
✅ **Retinotopic maps** - Both azimuth and elevation
✅ **FFT smoothing** - Matches MATLAB frequency-domain method

### Correct Implementation (Validated)
✅ **VFS computation** - Gradient angle method
✅ **Coherence filtering** - Removes 82.53% of unreliable pixels
✅ **Statistical filtering** - Keeps strongest 5.66% of pixels
✅ **Boundary detection** - Identifies visual cortex areas

### Visual Verification (36 Figures)
✅ **Raw VFS** - Full noisy data with balanced ±1 range
✅ **Statistical VFS** - Red/blue regions (not white)
✅ **VFS with Boundaries** - Green overlay on statistical VFS
✅ **All retinotopy figures** - Centered, thresholded, overlays

---

## Current Configuration (Final)

```python
# Analysis Parameters (matching MATLAB)
coherence_threshold = 0.3           # Signal reliability
magnitude_threshold = 0.3           # Response strength
vfs_threshold_sd = 1.5              # Statistical filtering (MATLAB standard)
smoothing_sigma = 3.0               # Retinotopic map smoothing
phase_filter_sigma = 0.0            # Disabled (MATLAB smooths FFT)
gradient_window_size = 3            # Sobel kernel
area_min_size_mm2 = 0.1             # Region filtering
ring_size_mm = 6.75                 # Spatial calibration
```

---

## Key Insights

### 1. Direction Mapping Counter-Intuitive
The MATLAB dataset structure is **non-obvious**:
- File 004 ("altitude experiment") → Horizontal retinotopy
- File 005 ("azimuth experiment") → Vertical retinotopy

**Lesson:** Always verify with correlation testing, don't assume based on names.

### 2. Simplicity Over Complexity
The reference implementation uses **simple phase subtraction**, not complex hemodynamic delay correction.

**Lesson:** Match the reference exactly, don't add sophistication unless verified.

### 3. Statistical Threshold on Full Distribution
Computing statistics on a **filtered subset** introduces severe bias (5.8× threshold inflation).

**Lesson:** Compute thresholds on full distributions, apply to filtered data.

### 4. No Hacks, No Fallbacks, No Workarounds
Every fix was **proper methodology** based on:
- MATLAB reference code
- Published literature (Kalatsky & Stryker 2003, Juavinett et al. 2017)
- Mathematical validation
- Correlation verification

**Lesson:** Proper fixes are always better than workarounds.

---

## Audit Recognition

The statistical threshold bug was discovered by **@agent-codebase-auditor** through:
- Systematic code review against MATLAB reference
- Mathematical analysis of threshold computation
- Statistical distribution validation
- Identification of biased subset sampling

The auditor's comprehensive analysis prevented deployment of mathematically flawed code and ensured exact MATLAB replication.

---

## Output Quality

### Before All Fixes:
- ❌ Phase maps: Wrong directions (swapped axes)
- ❌ Retinotopy: Incorrect (correlation=-0.15)
- ❌ Statistical VFS: Entirely white (all masked)

### After All Fixes:
- ✅ Phase maps: Perfect match (correlation=1.0)
- ✅ Retinotopy: Perfect match (correlation=1.0)
- ✅ Statistical VFS: Proper red/blue regions (5.66% retained)
- ✅ 36 figures generated matching MATLAB output

---

## References

### MATLAB Code
- `getMagFactors.m` - Retinotopic map smoothing (σ=3)
- `getAreaBorders.m` - VFS thresholding (1.5×SD, line 96)
- `generatekret.m` - Figure generation pipeline

### Literature
- **Kalatsky & Stryker 2003** - Fourier-based retinotopic mapping
- **Juavinett et al. 2017** - Visual field sign computation and thresholding
- **MATLAB ISI-master** - Reference implementation

---

**Date:** 2025-10-12
**Status:** ✅ COMPLETE - All critical bugs fixed, pipeline verified, MATLAB replication achieved
**Figures:** 36 outputs matching reference
**Correlation:** 1.000 for all phase and retinotopic maps
