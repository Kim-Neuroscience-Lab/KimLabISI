# Literature-Based Default Parameters

## Reference Papers:
1. **Kalatsky & Stryker 2003** - Fourier-based retinotopic mapping
2. **Juavinett et al. 2017** - Automated analysis pipelines
3. **MATLAB ISI-master** - Reference implementation

---

## Recommended Defaults:

### 1. **phase_filter_sigma** = 0.0
- **Literature**: MATLAB ISI-master does **complex-domain** smoothing, not phase-domain
- When processing from phase maps (not complex FFT), this should be **disabled (0.0)**
- Juavinett 2017 mentions smoothing but doesn't specify this exact parameter
- **Rationale**: Match MATLAB behavior - smoothing happens on degree maps instead

### 2. **smoothing_sigma** = 3.0
- **Literature**: MATLAB getMagFactors.m line 4: `fspecial('gaussian',size(kmap_hor),3)`
- **Direct match** to MATLAB implementation
- Applied AFTER degree conversion, BEFORE gradients
- **Keep as is**: ✓ Already correct

### 3. **coherence_threshold** = 0.3
- **Literature**: Kalatsky & Stryker 2003 - typical range 0.2-0.35
- Used for thresholding VFS maps by signal reliability
- 0.3 is middle of recommended range
- **Update**: Current value (0.75) is too high

### 4. **magnitude_threshold** = 0.3
- **Literature**: Juavinett et al. 2017 - per-direction magnitude filtering
- Typical values around 0.3 for normalized magnitude
- **Update**: Current value (0.76) is too high

### 5. **response_threshold_percent** = 20
- **Literature**: Juavinett et al. 2017 - percentile-based thresholding
- 20th percentile = keep top 80% of responsive pixels
- **Keep as is**: ✓ Reasonable default

### 6. **vfs_threshold_sd** = 2.0
- **Literature**: Standard statistical significance threshold
- 2 SD = ~95% confidence (assuming normal distribution)
- **Update**: Current value (3.0) is more conservative than typical

### 7. **area_min_size_mm2** = 0.1
- **Literature**: Depends on spatial resolution and cortical magnification
- 0.1 mm² is reasonable for rodent V1 (~0.3x0.3 mm minimum area)
- **Keep as is**: ✓ Reasonable default

### 8. **gradient_window_size** = 3 (UNUSED)
- **Note**: Now unused since we switched to `np.gradient()` (central differences)
- Was for Sobel operator kernel size
- **Keep**: For backwards compatibility

### 9. **ring_size_mm** = Keep current value (6.75)
- **User request**: Don't change
- This is specific to the imaging setup

---

## Summary of Changes:

| Parameter | Current | Literature Default | Change |
|-----------|---------|-------------------|--------|
| phase_filter_sigma | 2.0 | **0.0** | Disable (match MATLAB) |
| smoothing_sigma | 3.0 | **3.0** | ✓ Keep |
| coherence_threshold | 0.75 | **0.3** | Reduce (Kalatsky 2003) |
| magnitude_threshold | 0.76 | **0.3** | Reduce (Juavinett 2017) |
| response_threshold_percent | 20 | **20** | ✓ Keep |
| vfs_threshold_sd | 3.0 | **2.0** | Reduce (2 SD standard) |
| area_min_size_mm2 | 0.1 | **0.1** | ✓ Keep |
| gradient_window_size | 3 | **3** | ✓ Keep (unused) |
| ring_size_mm | 6.75 | **6.75** | ✓ Keep (user request) |
