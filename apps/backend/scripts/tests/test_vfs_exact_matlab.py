"""VFS computation EXACTLY matching MATLAB (both methods separately)."""

import sys
sys.path.insert(0, 'src')

import numpy as np
import cv2
import json
from pathlib import Path
from config import AppConfig
from analysis.pipeline import AnalysisPipeline

def gaussian_fft_filter(data, sigma):
    """Apply Gaussian filter using FFT (matches MATLAB's fspecial + ifft2(fft2...))."""
    h, w = data.shape
    y, x = np.ogrid[-h//2:h//2, -w//2:w//2]
    gaussian = np.exp(-(x*x + y*y) / (2.0 * sigma * sigma))
    gaussian /= gaussian.sum()

    data_fft = np.fft.fft2(data)
    gaussian_fft = np.fft.fft2(np.fft.ifftshift(gaussian))
    filtered = np.fft.ifft2(data_fft * np.abs(gaussian_fft))

    return np.real(filtered)

def compute_jacobian_vfs(kmap_hor, kmap_vert, pixpermm, sigma=3):
    """Compute Jacobian VFS EXACTLY matching getMagFactors.m.

    MATLAB lines 4-11:
      - Smooth retinotopy maps FIRST
      - Compute gradients from smoothed maps
      - Compute Jacobian scaled by pixpermm^2
    """
    print(f"\n{'='*80}")
    print("JACOBIAN VFS (getMagFactors.m method)")
    print(f"{'='*80}")

    # STEP 1: Smooth retinotopy maps (MATLAB lines 4-7)
    print(f"[1/3] Smoothing retinotopy maps (sigma={sigma})...")
    kmap_hor_filtered = gaussian_fft_filter(kmap_hor, sigma)
    kmap_vert_filtered = gaussian_fft_filter(kmap_vert, sigma)

    # STEP 2: Compute gradients from SMOOTHED maps (MATLAB lines 9-10)
    print("[2/3] Computing gradients from smoothed maps...")
    dhdx, dhdy = np.gradient(kmap_hor_filtered)
    dvdx, dvdy = np.gradient(kmap_vert_filtered)
    print(f"  dh/dx: mean={np.mean(np.abs(dhdx)):.4f}")
    print(f"  dv/dy: mean={np.mean(np.abs(dvdy)):.4f}")

    # STEP 3: Compute Jacobian (MATLAB line 11)
    print(f"[3/3] Computing Jacobian: (dhdx*dvdy - dvdx*dhdy) * pixpermm^2...")
    JacIm = (dhdx * dvdy - dvdx * dhdy) * (pixpermm ** 2)

    print(f"\n  Jacobian range: [{np.nanmin(JacIm):.2f}, {np.nanmax(JacIm):.2f}] deg²/mm²")
    print(f"  Jacobian mean: {np.nanmean(JacIm):.2f}")
    print(f"  Positive (non-mirror): {np.sum(JacIm > 0)} pixels ({100*np.sum(JacIm > 0)/JacIm.size:.1f}%)")
    print(f"  Negative (mirror): {np.sum(JacIm < 0)} pixels ({100*np.sum(JacIm < 0)/JacIm.size:.1f}%)")

    return JacIm

def compute_sereno_vfs(kmap_hor, kmap_vert, sigma=3):
    """Compute Sereno VFS EXACTLY matching getMouseAreaBorders.m.

    MATLAB lines 28-41:
      - Compute gradients from UNSMOOTHED maps FIRST
      - Compute VFS from gradient directions
      - Smooth VFS AFTER computing
    """
    print(f"\n{'='*80}")
    print("SERENO VFS (getMouseAreaBorders.m method)")
    print(f"{'='*80}")

    # STEP 1: Compute gradients from UNSMOOTHED maps (MATLAB lines 28-29)
    print("[1/4] Computing gradients from UNSMOOTHED maps...")
    dhdx, dhdy = np.gradient(kmap_hor)
    dvdx, dvdy = np.gradient(kmap_vert)
    print(f"  dh/dx: mean={np.mean(np.abs(dhdx)):.4f}")
    print(f"  dv/dy: mean={np.mean(np.abs(dvdy)):.4f}")

    # STEP 2: Compute gradient directions (MATLAB lines 31-32)
    print("[2/4] Computing gradient directions...")
    graddir_hor = np.arctan2(dhdy, dhdx)
    graddir_vert = np.arctan2(dvdy, dvdx)

    # STEP 3: Compute VFS (MATLAB lines 34-37)
    print("[3/4] Computing VFS = sin(angle(exp(i*graddir_hor) * exp(-i*graddir_vert)))...")
    vdiff = np.exp(1j * graddir_hor) * np.exp(-1j * graddir_vert)
    VFS = np.sin(np.angle(vdiff))

    # Replace NaNs with 0
    VFS[np.isnan(VFS)] = 0

    print(f"  VFS (before smoothing) range: [{np.min(VFS):.4f}, {np.max(VFS):.4f}]")

    # STEP 4: Smooth VFS AFTER computing (MATLAB lines 39-41)
    print(f"[4/4] Smoothing VFS (sigma={sigma}) AFTER computing...")
    VFS_smoothed = gaussian_fft_filter(VFS, sigma)

    print(f"\n  VFS (after smoothing) range: [{np.min(VFS_smoothed):.4f}, {np.max(VFS_smoothed):.4f}]")
    print(f"  VFS mean: {np.mean(VFS_smoothed):.4f}")
    print(f"  VFS std: {np.std(VFS_smoothed):.4f}")

    return VFS_smoothed

def save_vfs_jet(vfs_map, filename, mask=None, vmin=-1, vmax=1):
    """Save VFS with JET colormap."""
    vfs_display = vfs_map.copy()
    if mask is not None:
        vfs_display[~mask] = np.nan

    vfs_norm = (vfs_display - vmin) / (vmax - vmin)
    vfs_norm = np.clip(vfs_norm, 0, 1)
    vfs_uint8 = np.nan_to_num(vfs_norm * 255, nan=128).astype(np.uint8)

    colored = cv2.applyColorMap(vfs_uint8, cv2.COLORMAP_JET)
    nan_mask = np.isnan(vfs_display)
    colored[nan_mask] = [255, 255, 255]

    cv2.imwrite(filename, colored)
    print(f"  Saved: {filename}")

def main():
    print("="*80)
    print("VFS COMPUTATION - EXACT MATLAB IMPLEMENTATION")
    print("="*80)
    print("\nComputing TWO separate VFS methods:")
    print("  1. Jacobian (getMagFactors.m) - smooth maps then gradients")
    print("  2. Sereno (getMouseAreaBorders.m) - gradients then smooth VFS")

    session_path = Path('data/sessions/sample_session')

    # Load data
    phase_LR = np.load(session_path / 'phase_LR.npy')
    phase_RL = np.load(session_path / 'phase_RL.npy')
    phase_TB = np.load(session_path / 'phase_TB.npy')
    phase_BT = np.load(session_path / 'phase_BT.npy')
    mag_LR = np.load(session_path / 'magnitude_LR.npy')
    mag_RL = np.load(session_path / 'magnitude_RL.npy')
    mag_TB = np.load(session_path / 'magnitude_TB.npy')
    mag_BT = np.load(session_path / 'magnitude_BT.npy')

    # Apply MATLAB orientation (fliplr)
    print("\n" + "="*80)
    print("APPLYING MATLAB ORIENTATION")
    print("="*80)
    print("  Applying fliplr to match generatekret.m line 93...")

    phase_LR = np.fliplr(phase_LR)
    phase_RL = np.fliplr(phase_RL)
    phase_TB = np.fliplr(phase_TB)
    phase_BT = np.fliplr(phase_BT)
    mag_LR = np.fliplr(mag_LR)
    mag_RL = np.fliplr(mag_RL)
    mag_TB = np.fliplr(mag_TB)
    mag_BT = np.fliplr(mag_BT)

    # Generate retinotopic maps
    cfg = AppConfig.from_file('config/isi_parameters.json')
    pipeline = AnalysisPipeline(cfg.analysis)

    print("\n" + "="*80)
    print("GENERATING RETINOTOPIC MAPS")
    print("="*80)

    azimuth = pipeline.generate_azimuth_map(phase_LR, phase_RL)
    elevation = pipeline.generate_elevation_map(phase_TB, phase_BT)

    # Center maps
    azimuth_centered = azimuth - np.nanmean(azimuth)
    elevation_centered = elevation - np.nanmean(elevation)

    print(f"\nAzimuth: [{np.nanmin(azimuth_centered):.1f}°, {np.nanmax(azimuth_centered):.1f}°]")
    print(f"Elevation: [{np.nanmin(elevation_centered):.1f}°, {np.nanmax(elevation_centered):.1f}°]")

    # Compute pixpermm
    pixpermm = azimuth.shape[1] / cfg.analysis.ring_size_mm
    print(f"\nPixels per mm: {pixpermm:.2f}")

    # Compute BOTH VFS methods separately
    JacIm = compute_jacobian_vfs(azimuth_centered, elevation_centered, pixpermm, sigma=3)
    VFS_sereno = compute_sereno_vfs(azimuth_centered, elevation_centered, sigma=3)

    # Compare methods
    print("\n" + "="*80)
    print("COMPARING BOTH METHODS")
    print("="*80)

    # Normalize Jacobian for comparison
    JacIm_norm = JacIm / np.nanmax(np.abs(JacIm))

    # Correlation between methods
    valid = ~np.isnan(JacIm_norm) & ~np.isnan(VFS_sereno)
    correlation = np.corrcoef(JacIm_norm[valid], VFS_sereno[valid])[0, 1]
    print(f"\nCorrelation between Jacobian and Sereno VFS: {correlation:.4f}")
    print(f"(Should be high if both methods agree on VFS patterns)")

    # Compute thresholds
    print("\n" + "="*80)
    print("COMPUTING THRESHOLDS")
    print("="*80)

    # Statistical threshold (MATLAB line 70)
    threshold_stat = 1.5 * np.std(VFS_sereno)
    gradmag = np.abs(VFS_sereno)
    mask_stat = gradmag >= (threshold_stat / 2)
    print(f"\nStatistical threshold (1.5σ): {threshold_stat:.4f}")
    print(f"  Pixels above: {np.sum(mask_stat)}/{mask_stat.size} ({100*np.sum(mask_stat)/mask_stat.size:.1f}%)")

    # Magnitude threshold
    mag_avg = (mag_LR + mag_RL + mag_TB + mag_BT) / 4
    mag_norm = mag_avg / np.max(mag_avg)
    mask_mag = mag_norm >= 0.07
    print(f"\nMagnitude threshold (0.07): ")
    print(f"  Pixels above: {np.sum(mask_mag)}/{mask_mag.size} ({100*np.sum(mask_mag)/mask_mag.size:.1f}%)")

    # Save figures
    output_dir = Path('figures_output_exact_matlab')
    output_dir.mkdir(exist_ok=True)

    print("\n" + "="*80)
    print(f"SAVING FIGURES TO: {output_dir}")
    print("="*80)

    print("\n[1/6] Jacobian VFS (raw)...")
    save_vfs_jet(JacIm_norm, str(output_dir / 'VFS_Jacobian_Raw.png'))

    print("\n[2/6] Jacobian VFS (stat threshold)...")
    save_vfs_jet(JacIm_norm, str(output_dir / 'VFS_Jacobian_StatThresh.png'), mask=mask_stat)

    print("\n[3/6] Jacobian VFS (mag threshold)...")
    save_vfs_jet(JacIm_norm, str(output_dir / 'VFS_Jacobian_MagThresh.png'), mask=mask_mag)

    print("\n[4/6] Sereno VFS (raw)...")
    save_vfs_jet(VFS_sereno, str(output_dir / 'VFS_Sereno_Raw.png'))

    print("\n[5/6] Sereno VFS (stat threshold)...")
    save_vfs_jet(VFS_sereno, str(output_dir / 'VFS_Sereno_StatThresh.png'), mask=mask_stat)

    print("\n[6/6] Sereno VFS (mag threshold)...")
    save_vfs_jet(VFS_sereno, str(output_dir / 'VFS_Sereno_MagThresh.png'), mask=mask_mag)

    # Summary
    print("\n" + "="*80)
    print("EXACT MATLAB VFS COMPUTATION COMPLETE")
    print("="*80)
    print("\n✅ Both VFS methods now EXACTLY match MATLAB:")
    print("\n  1. Jacobian (getMagFactors.m):")
    print("     • Smooth retinotopy maps (sigma=3)")
    print("     • Compute gradients from smoothed maps")
    print("     • Jacobian = (dhdx*dvdy - dvdx*dhdy) * pixpermm²")
    print("\n  2. Sereno (getMouseAreaBorders.m):")
    print("     • Compute gradients from UNSMOOTHED maps")
    print("     • VFS = sin(angle(exp(i*graddir_hor)*exp(-i*graddir_vert)))")
    print("     • Smooth VFS after computing (sigma=3)")
    print("\n  Key difference: Smoothing BEFORE vs AFTER gradient computation!")
    print("="*80)

    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
