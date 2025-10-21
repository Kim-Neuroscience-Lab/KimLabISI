# Visual Field Sign Processing Comparison

## Complete Line-by-Line Comparison: Old vs Current Implementation

Based on comprehensive analysis of:
- `/Users/Adam/KimLabISI/old_implementation/core/visual_field_sign.py` (working MATLAB-like implementation)
- `/Users/Adam/KimLabISI/apps/backend/src/analysis/pipeline.py` (current implementation)

---

## ⚠️ CRITICAL DIFFERENCES FOUND

### 1. **MISSING: VFS Post-Smoothing (σ=3 using FFT)**
**Impact: HIGH - This is likely the main cause of visual differences**

**Old Implementation** (lines 139-146):
```python
# POST-SMOOTH VFS AFTER computing (σ=3 using FFT)
if vfs_smooth_sigma > 0:
    h = self._create_gaussian_kernel(vfs.shape, vfs_smooth_sigma)
    h = h / np.sum(h)
    vfs_smooth = np.real(
        np.fft.ifft2(np.fft.fft2(vfs) * np.abs(np.fft.fft2(h)))
    )
else:
    vfs_smooth = vfs
```

**Current Implementation** (pipeline.py:451):
```python
# Returns raw Jacobian WITHOUT any post-smoothing
return jacobian_det.astype(np.float32)  # ← MISSING POST-SMOOTHING!
```

**Status: ❌ NOT IMPLEMENTED**

---

### 2. **VFS Computation Method Difference**
**Impact: MEDIUM - Both methods are theoretically equivalent but may differ numerically**

**Old Implementation** (lines 125-131) - Sereno Method:
```python
# Compute gradient directions
graddir_horizontal = np.arctan2(grad_h_y, grad_h_x)
graddir_vertical = np.arctan2(grad_v_y, grad_v_x)

# Compute VFS using complex exponentials
vdiff = np.exp(1j * graddir_horizontal) * np.exp(-1j * graddir_vertical)
vfs = np.sin(np.angle(vdiff))
```

**Current Implementation** (lines 443-445) - Jacobian Determinant:
```python
# Direct Jacobian determinant
jacobian_det = d_azimuth_dx * d_elevation_dy - d_azimuth_dy * d_elevation_dx
```

**Mathematical Relationship:**
- Sereno: `VFS = sin(angle(∇H × ∇V))`
- Jacobian: `VFS = |∇H × ∇V|` (determinant)

These are **NOT identical** - the Sereno method includes `sin()` normalization!

**Status: ⚠️ DIFFERENT METHODS**

---

### 3. **Gaussian Filtering Method Difference**
**Impact: MEDIUM - FFT vs spatial domain may produce different results**

**Old Implementation** (lines 164-179) - FFT-Based:
```python
def _apply_gaussian_smoothing(self, data: np.ndarray, sigma: float) -> np.ndarray:
    """Apply Gaussian smoothing using frequency domain approach."""
    h = self._create_gaussian_kernel(data.shape, sigma)
    h = h / np.sum(h)
    # FFT-based convolution
    smoothed = np.real(np.fft.ifft2(np.fft.fft2(data) * np.abs(np.fft.fft2(h))))
    return smoothed

def _create_gaussian_kernel(self, shape: Tuple[int, int], sigma: float) -> np.ndarray:
    """Create Gaussian kernel centered on image."""
    y, x = np.ogrid[: shape[0], : shape[1]]
    center_y, center_x = shape[0] // 2, shape[1] // 2
    kernel = np.exp(-((x - center_x) ** 2 + (y - center_y) ** 2) / (2 * sigma**2))
    return kernel
```

**Current Implementation** (pipeline.py:391) - Spatial Domain:
```python
# Uses scipy's gaussian_filter (spatial-domain convolution)
azimuth_smooth = ndimage.gaussian_filter(azimuth_map, sigma=sigma)
```

**Key Differences:**
- FFT method: Global operation, wraps at boundaries, full-image kernel
- Spatial method: Local operation, different boundary handling, truncated kernel

**Status: ⚠️ DIFFERENT IMPLEMENTATION**

---

### 4. **Pixel Density Auto-Scaling**
**Impact: MEDIUM - Ensures sigma values scale with imaging resolution**

**Old Implementation** (lines 82-93):
```python
# Auto-scale parameters based on pixel density
# MATLAB baseline: 39 pixels/mm
matlab_baseline_pixmm = 39.0
scale_factor = matlab_baseline_pixmm / self.pixels_per_mm

if kmap_smooth_sigma is None:
    # Scale kmap smoothing: original σ=2 at 39px/mm
    kmap_smooth_sigma = 2.0 * scale_factor

if vfs_smooth_sigma is None:
    # Scale VFS smoothing: original σ=3 at 39px/mm
    vfs_smooth_sigma = 3.0 * scale_factor
```

**Current Implementation**:
```python
# Uses fixed smoothing_sigma from config (no auto-scaling)
sigma = self.config.smoothing_sigma  # ← NOT auto-scaled by pixel density!
```

**Status: ❌ AUTO-SCALING NOT IMPLEMENTED**

---

### 5. **Default Parameter Values**
**Impact: HIGH if parameters don't match**

**Old Implementation Defaults:**
- `kmap_smooth_sigma`: 2.0 (scaled by pixel density)
- `vfs_smooth_sigma`: 3.0 (scaled by pixel density)
- `pixels_per_mm`: 39.0 (MATLAB baseline)

**Current Implementation Defaults** (from config):
- `smoothing_sigma`: ??? (need to check config file)
- `phase_filter_sigma`: ??? (applied BEFORE, not same as kmap smoothing)

**Status: ⚠️ NEEDS VERIFICATION**

---

## 📋 COMPLETE PROCESSING PIPELINE COMPARISON

### Old Implementation Flow (visual_field_sign.py):

1. **Input**: Raw retinotopic maps (azimuth, elevation)
2. **Pre-smooth retinotopic maps** (σ=2, auto-scaled, FFT-based)
3. **Compute gradients** using `np.gradient()` (central differences)
4. **Compute gradient directions** using `arctan2()`
5. **Compute VFS** using Sereno method: `sin(angle(exp(iθ_h) × exp(-iθ_v)))`
6. **Handle NaN values**: Set `vfs[isnan(vfs)] = 0`
7. **Post-smooth VFS** (σ=3, auto-scaled, FFT-based) ← **CRITICAL MISSING STEP**
8. **Output**: Smoothed VFS map

### Current Implementation Flow (pipeline.py):

1. **Input**: Raw retinotopic maps (azimuth, elevation)
2. **Pre-smooth retinotopic maps** (configurable σ, spatial-domain)
3. **Compute gradients** using `np.gradient()` (central differences) ✅ MATCHES
4. **Skip gradient directions** (not computed)
5. **Compute VFS** using Jacobian determinant directly ⚠️ DIFFERENT METHOD
6. **No NaN handling** (maps should not have NaN)
7. **NO POST-SMOOTHING** ❌ MISSING!
8. **Output**: Raw Jacobian determinant

---

## 🔍 ADDITIONAL OBSERVATIONS

### Matching Features ✅
- Both use `np.gradient()` for central differences (correct!)
- Both apply pre-smoothing to retinotopic maps
- Both handle 2D arrays correctly

### Missing Features ❌
1. VFS post-smoothing (σ=3, FFT-based)
2. Pixel density auto-scaling for sigma values
3. Sereno method VFS computation (using sin + angle)
4. FFT-based Gaussian filtering implementation

### Different Features ⚠️
1. VFS computation: Sereno vs Jacobian
2. Gaussian filtering: FFT-based vs spatial-domain
3. Parameter scaling: Auto-scaled vs fixed

---

## 🎯 RECOMMENDED FIXES (Priority Order)

### Priority 1: CRITICAL
1. **Add VFS post-smoothing** (σ=3 using FFT)
   - This is likely the PRIMARY cause of visual differences
   - Implement FFT-based Gaussian filter helper
   - Apply after Jacobian computation

### Priority 2: HIGH
2. **Implement pixel density auto-scaling**
   - Add pixels_per_mm parameter to config
   - Auto-scale smoothing parameters based on resolution
   - Default baseline: 39 px/mm (MATLAB standard)

3. **Implement FFT-based Gaussian filtering**
   - Add helper functions: `_create_gaussian_kernel()` and `_apply_gaussian_smoothing()`
   - Use for both pre-smoothing and post-smoothing
   - Matches MATLAB's frequency-domain filtering exactly

### Priority 3: MEDIUM
4. **Consider switching to Sereno VFS method**
   - Both methods should work, but Sereno is literature-standard
   - Test if this improves results
   - May need gradient direction computation

### Priority 4: LOW
5. **Parameter verification** ✅ VERIFIED
   - Current config.py defaults (lines 338-339):
     - `phase_filter_sigma`: 2.0 (applied BEFORE phase-to-position conversion)
     - `smoothing_sigma`: 3.0 (applied AFTER phase-to-position conversion TO POSITION MAPS)
   - **CRITICAL ISSUE**: `smoothing_sigma=3.0` is being applied to POSITION MAPS, NOT to VFS!
   - Old implementation: σ=3 post-smoothing is applied to VFS MAP, not position maps
   - **This confirms the missing VFS post-smoothing is the PRIMARY issue**

---

## 📊 VERIFICATION PLAN

Once fixes are implemented:
1. Run both implementations on sample data
2. Compare VFS maps pixel-by-pixel
3. Check that output visually matches MATLAB figures
4. Verify numerical values are within tolerance (< 1% difference)

---

## 🔬 TECHNICAL NOTES

### Why FFT-based Gaussian matters:
- FFT method creates full-image kernel (wraps at boundaries)
- Spatial method truncates kernel at boundaries
- For periodic/circular structures (retinotopy), FFT is preferred
- MATLAB's `fspecial('gaussian')` + FFT convolution = FFT-based method

### Why VFS post-smoothing matters:
- VFS is computed from gradients (inherently noisy)
- Post-smoothing reduces high-frequency noise in VFS
- Makes area boundaries clearer and more stable
- Standard practice in all MATLAB implementations

### Why pixel density scaling matters:
- Different imaging setups have different spatial resolution
- Sigma values should scale with pixels/mm
- Without scaling: over/under-smoothing at different resolutions
- MATLAB baseline: 39 px/mm (Garrett et al. 2014)
