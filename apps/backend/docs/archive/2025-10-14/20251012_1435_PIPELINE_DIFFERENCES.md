# Pipeline Differences: Current vs Old Implementation

## Key Differences Found

### 1. **PRE-SMOOTHING of Retinotopic Maps**

**Old Implementation** (line 105-116):
```python
# PRE-SMOOTH retinotopic maps BEFORE gradient computation
if kmap_smooth_sigma > 0:
    kmap_h_smooth = self._apply_gaussian_smoothing(kmap_horizontal, kmap_smooth_sigma)
    kmap_v_smooth = self._apply_gaussian_smoothing(kmap_vertical, kmap_smooth_sigma)
else:
    kmap_h_smooth = kmap_horizontal
    kmap_v_smooth = kmap_vertical

# Then compute gradients on smoothed maps
grad_h_x, grad_h_y = np.gradient(kmap_h_smooth)
```

**Current Implementation** (line 444-455):
```python
# Smooth maps before computing gradients
sigma = self.config.smoothing_sigma
azimuth_smooth = ndimage.gaussian_filter(azimuth_map, sigma=sigma)
elevation_smooth = ndimage.gaussian_filter(elevation_map, sigma=sigma)

# Then compute gradients
d_azimuth_dy, d_azimuth_dx = np.gradient(azimuth_smooth)
```

**Issue**: Both do pre-smoothing, but:
- Old uses **FFT-based smoothing** (frequency domain)
- Current uses **scipy.ndimage.gaussian_filter** (spatial domain)
- Different smoothing methods can produce slightly different results

### 2. **Parameter Naming and Scaling**

**Old Implementation**:
- `kmap_smooth_sigma` - for retinotopic map smoothing (default σ=2, auto-scaled by pixels_per_mm)
- `vfs_smooth_sigma` - for VFS post-smoothing (default σ=3, auto-scaled by pixels_per_mm)
- Auto-scaling: `sigma * (39.0 / pixels_per_mm)`

**Current Implementation**:
- `smoothing_sigma` - for retinotopic map smoothing (fixed value from config)
- `vfs_smooth_sigma` - for VFS post-smoothing (fixed σ=3)
- No auto-scaling based on spatial resolution

### 3. **Smoothing Method**

**Old Implementation**:
```python
def _apply_gaussian_smoothing(self, data, sigma):
    h = self._create_gaussian_kernel(data.shape, sigma)
    h = h / np.sum(h)
    smoothed = np.real(np.fft.ifft2(np.fft.fft2(data) * np.abs(np.fft.fft2(h))))
    return smoothed
```

**Current Implementation**:
```python
azimuth_smooth = ndimage.gaussian_filter(azimuth_map, sigma=sigma)
```

**Impact**: FFT-based vs spatial-domain filtering can produce different edge behaviors

### 4. **VFS Gradient Method**

Both now use the same gradient angle method ✅

## Required Changes

To match old_implementation EXACTLY:

1. Use **FFT-based smoothing** for kmap pre-smoothing (not scipy.ndimage.gaussian_filter)
2. Add **auto-scaling** of smoothing parameters based on pixels_per_mm
3. Rename `smoothing_sigma` to `kmap_smooth_sigma` for clarity
4. Make smoothing parameters consistent with old_implementation defaults
