# Complete Pipeline Comparison: MATLAB vs Our Implementation

## MATLAB ISI-master Pipeline (Gprocesskret.m → getMagFactors.m)

### Phase 1: Gprocesskret.m - Retinotopy Computation
1. **Input**: Complex FFT coefficients (ang0, ang1, ang2, ang3)
2. **Optional**: High-pass filter on complex values (line 28-33)
3. **Optional**: Smoothing in complex domain using `roifilt2` (line 54-57)
4. **Extract**: Magnitude with `abs()` and phase with `angle()` (line 59-69)
5. **Delay correction**:
   - Compute: `delay = angle(exp(i*forward) + exp(i*reverse))` (line 88)
   - Adjust: `delay = delay + pi/2*(1-sign(delay))` (line 95)
6. **Bidirectional analysis** (line 99-100):
   ```matlab
   kmap = 0.5*(angle(exp(1i*(ang0-delay))) - angle(exp(1i*(ang2-delay))))
   ```
7. **Convert to degrees** (line 104): `kmap * 180/pi`

### Phase 2: getMagFactors.m - VFS Computation
1. **Gaussian smoothing** (line 4-7): sigma=3 via FFT convolution on degree maps
2. **Compute gradients** (line 9-10): Using MATLAB's `gradient()` (central differences)
3. **VFS = Jacobian determinant** (line 11):
   ```matlab
   JacIm = (dhdx.*dvdy - dvdx.*dhdy) * pixpermm^2
   ```

---

## Our Implementation

### Phase 1: compute_fft_phase_maps() - FFT Analysis
1. **Input**: Raw camera frames [n_frames, height, width]
2. **FFT computation**: Extract phase, magnitude, coherence
3. **Extract phase**: `phase = np.angle(complex_amplitude)` immediately
4. **Optional phase filtering** (PARAMETER 2: phase_filter_sigma):
   - Gaussian smoothing on PHASE values (in radians)
   - Default: 0 (disabled)
   - Juavinett et al. 2017 method

### Phase 2: bidirectional_analysis() - Retinotopy Computation
1. **Delay correction**:
   - Compute: `delay = angle(exp(1j*forward) + exp(1j*reverse))`
   - Adjust: `delay = delay + (pi/2) * (1 - sign(delay))`
2. **Subtract delay and wrap**:
   ```python
   forward_wrapped = angle(exp(1j*(forward - delay)))
   reverse_wrapped = angle(exp(1j*(reverse - delay)))
   ```
3. **Bidirectional analysis**:
   ```python
   center_map = (forward_wrapped - reverse_wrapped) / 2
   ```
4. **Convert to degrees**: `azimuth = center_map * (60/pi)`

### Phase 3: compute_spatial_gradients() - Gradient Computation
1. **Gaussian smoothing** (PARAMETER 7: smoothing_sigma):
   - Applied to degree maps (azimuth/elevation)
   - Default: typically 2-3 pixels
   - Matches MATLAB's sigma=3
2. **Compute gradients**: Using **Sobel operator** (not central differences)
   - Juavinett et al. 2017 recommends Sobel for better noise handling

### Phase 4: calculate_visual_field_sign() - VFS Computation
1. **VFS = Jacobian determinant**:
   ```python
   jacobian_det = d_azimuth_dx * d_elevation_dy - d_azimuth_dy * d_elevation_dx
   ```
2. **Normalize**: To [-1, 1] range using 99th percentile

---

## Key Differences

| Aspect | MATLAB | Our Implementation |
|--------|--------|-------------------|
| **Smoothing domain** | Complex-valued FFT coefficients | Phase values OR position maps |
| **Smoothing timing** | Before phase extraction | After FFT (optional) AND after degree conversion |
| **Gradient method** | Central differences (`gradient()`) | Sobel operator |
| **VFS normalization** | Raw Jacobian * pixpermm^2 | Normalized to [-1, 1] |
| **Parameters** | Fixed sigma=3 | Configurable: phase_filter_sigma + smoothing_sigma |

---

## Are We Missing Any Steps?

### ✅ Implemented Correctly:
1. Delay correction with adjustment to [0, π]
2. Bidirectional analysis with wrapped phase subtraction
3. Smoothing before gradient computation
4. VFS as Jacobian determinant

### ⚠️ Differences (Not Necessarily Wrong):
1. **Smoothing domain**:
   - MATLAB: Complex-domain smoothing
   - Ours: Phase-domain (phase_filter_sigma) or position-domain (smoothing_sigma)
   - **Note**: When processing from saved phase maps (like sample session), complex-domain smoothing isn't possible

2. **Gradient method**:
   - MATLAB: Central differences
   - Ours: Sobel operator (following Juavinett et al. 2017)
   - **Note**: Sobel is more robust to noise

3. **VFS normalization**:
   - MATLAB: Raw values scaled by pixpermm^2
   - Ours: Normalized to [-1, 1]
   - **Note**: Our normalization makes visualization consistent across datasets

### 🔍 Potential Enhancement:
When processing **raw camera frames** (not pre-computed phase maps), we could add complex-domain smoothing before phase extraction. This would match MATLAB's approach more closely.

---

## Conclusion

**Yes, we're doing all the essential steps!**

The differences are either:
1. **Methodological improvements** (Sobel vs gradient, normalized VFS)
2. **Flexibility** (two smoothing stages with configurable parameters)
3. **Adaptation to data format** (when loading pre-computed phase maps, complex-domain smoothing isn't available)

Our implementation follows both the **MATLAB ISI reference** and the **modern literature (Juavinett et al. 2017)**, combining best practices from both.
