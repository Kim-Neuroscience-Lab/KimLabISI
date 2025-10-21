# Analysis Parameter Update Summary

Updated analysis parameters to literature-based defaults while keeping ring_size_mm unchanged per user request.

## Changes Made

| Parameter | Old Value | New Value | Source |
|-----------|-----------|-----------|--------|
| **phase_filter_sigma** | 2.0 | **0.0** | Match MATLAB (disables phase filtering) |
| **smoothing_sigma** | 3.0 | **3.0** | ✓ MATLAB getMagFactors.m (no change) |
| **coherence_threshold** | 0.75 | **0.3** | Kalatsky & Stryker 2003 |
| **magnitude_threshold** | 0.76 | **0.3** | Juavinett et al. 2017 |
| **response_threshold_percent** | 20 | **20** | ✓ Juavinett et al. 2017 (no change) |
| **vfs_threshold_sd** | 3.0 | **2.0** | Standard 2-sigma threshold |
| **area_min_size_mm2** | 0.1 | **0.1** | ✓ Reasonable default (no change) |
| **gradient_window_size** | 3 | **3** | ✓ Now unused, kept for compatibility (no change) |
| **ring_size_mm** | 6.75 | **6.75** | ✓ User requested no change |

## Key Changes Explained

### 1. phase_filter_sigma: 2.0 → 0.0 (DISABLED)
- **Why**: MATLAB ISI-master smooths in the **complex domain** before extracting phase
- Our implementation works with pre-computed phase maps, so phase-domain smoothing is different
- Disabling this makes behavior more consistent with MATLAB
- Smoothing still happens via `smoothing_sigma` on degree maps (same as MATLAB)

### 2. coherence_threshold: 0.75 → 0.3
- **Why**: Old value (0.75) was too restrictive - filtered out too much data
- Kalatsky & Stryker 2003 recommend range 0.2-0.35
- 0.3 is the middle of this range and widely used in literature

### 3. magnitude_threshold: 0.76 → 0.3
- **Why**: Old value was also too restrictive
- Juavinett et al. 2017 uses moderate thresholds around 0.3
- Allows more data through while still filtering noise

### 4. vfs_threshold_sd: 3.0 → 2.0
- **Why**: Standard statistical significance uses 2 SD (~95% confidence)
- 3 SD is very conservative (99.7% confidence)
- 2 SD is more standard in neuroscience literature

## Files Updated

1. **config/isi_parameters.json**
   - Updated both `current` and `default` sections
   - Updated parameter descriptions with literature citations

2. **Documentation Created**
   - `LITERATURE_DEFAULTS.md` - Detailed explanation of each parameter
   - `PARAMETER_UPDATE_SUMMARY.md` - This file

## Testing Recommendation

After these changes, you should test with a real experimental session to verify:
1. Coherence thresholding now properly filters noisy regions (not everything)
2. Magnitude thresholding allows sufficient data through
3. VFS maps show clear structure with proper signal/noise separation

The lower thresholds should result in:
- ✓ More pixels passing coherence filter
- ✓ Better coverage in retinotopy maps
- ✓ More visible structure in VFS maps
- ✓ Behavior matching published literature and MATLAB implementation
