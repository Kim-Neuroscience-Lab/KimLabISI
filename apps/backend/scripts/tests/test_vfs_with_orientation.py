"""VFS computation with correct MATLAB orientation (fliplr)."""

import sys
sys.path.insert(0, 'src')

import numpy as np
import cv2
import json
from pathlib import Path
from scipy import ndimage
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

def compute_vfs_matlab_method(kmap_hor, kmap_vert, pixpermm, sigma=3):
    """Compute VFS exactly matching MATLAB getMagFactors.m."""
    print(f"\n{'='*80}")
    print("MATLAB-ACCURATE VFS COMPUTATION")
    print(f"{'='*80}")
    print(f"  Input maps shape: {kmap_hor.shape}")
    print(f"  Pixels per mm: {pixpermm:.2f}")
    print(f"  Gaussian sigma: {sigma}")

    print("\n[1/4] Applying Gaussian filter (sigma=3) to retinotopy maps...")
    kmap_hor_filtered = gaussian_fft_filter(kmap_hor, sigma)
    kmap_vert_filtered = gaussian_fft_filter(kmap_vert, sigma)

    print("\n[2/4] Computing gradients...")
    dhdx, dhdy = np.gradient(kmap_hor_filtered)
    dvdx, dvdy = np.gradient(kmap_vert_filtered)

    print("\n[3/4] Computing Jacobian determinant...")
    JacIm = (dhdx * dvdy - dvdx * dhdy) * (pixpermm ** 2)
    print(f"  Jacobian range: [{np.nanmin(JacIm):.4f}, {np.nanmax(JacIm):.4f}] deg²/mm²")
    print(f"  Positive VFS: {np.sum(JacIm > 0)} ({100*np.sum(JacIm > 0)/JacIm.size:.1f}%)")
    print(f"  Negative VFS: {np.sum(JacIm < 0)} ({100*np.sum(JacIm < 0)/JacIm.size:.1f}%)")

    print("\n[4/4] Computing Sereno VFS method...")
    graddir_hor = np.arctan2(dhdy, dhdx)
    graddir_vert = np.arctan2(dvdy, dvdx)
    vdiff = np.exp(1j * graddir_hor) * np.exp(-1j * graddir_vert)
    VFS_sereno = np.sin(np.angle(vdiff))
    VFS_sereno[np.isnan(VFS_sereno)] = 0
    VFS_sereno_smoothed = gaussian_fft_filter(VFS_sereno, sigma)

    return JacIm, VFS_sereno_smoothed

def save_vfs_matlab_style(vfs_map, filename, mask=None, vmin=-1, vmax=1):
    """Save VFS with JET colormap matching MATLAB."""
    vfs_display = vfs_map.copy()
    if mask is not None:
        vfs_display[~mask] = np.nan

    vfs_norm = (vfs_display - vmin) / (vmax - vmin)
    vfs_norm = np.clip(vfs_norm, 0, 1)
    vfs_uint8 = (vfs_norm * 255).astype(np.uint8)

    nan_mask = np.isnan(vfs_display)
    vfs_uint8[nan_mask] = 128

    colored = cv2.applyColorMap(vfs_uint8, cv2.COLORMAP_JET)
    colored[nan_mask] = [255, 255, 255]

    cv2.imwrite(filename, colored)
    print(f"  Saved: {filename}")

def main():
    print("="*80)
    print("VFS COMPUTATION WITH CORRECT MATLAB ORIENTATION")
    print("="*80)

    session_path = Path('data/sessions/sample_session')
    print(f"\nLoading sample session: {session_path}")

    with open(session_path / 'metadata.json', 'r') as f:
        metadata = json.load(f)

    # Load phase data
    phase_LR = np.load(session_path / 'phase_LR.npy')
    phase_RL = np.load(session_path / 'phase_RL.npy')
    phase_TB = np.load(session_path / 'phase_TB.npy')
    phase_BT = np.load(session_path / 'phase_BT.npy')
    anatomy = np.load(session_path / 'anatomical.npy')

    # Load magnitude for thresholding
    mag_LR = np.load(session_path / 'magnitude_LR.npy')
    mag_RL = np.load(session_path / 'magnitude_RL.npy')
    mag_TB = np.load(session_path / 'magnitude_TB.npy')
    mag_BT = np.load(session_path / 'magnitude_BT.npy')

    print(f"\nOriginal data shape: {phase_LR.shape}")

    # CRITICAL: Apply fliplr to match MATLAB orientation (generatekret.m line 93)
    print("\n" + "="*80)
    print("APPLYING MATLAB ORIENTATION (FLIPLR)")
    print("="*80)
    print("  Applying horizontal flip (fliplr) to all data...")
    print("  This matches generatekret.m line 93: 'flip everything to be oriented correctly'")

    phase_LR = np.fliplr(phase_LR)
    phase_RL = np.fliplr(phase_RL)
    phase_TB = np.fliplr(phase_TB)
    phase_BT = np.fliplr(phase_BT)
    anatomy = np.fliplr(anatomy)
    mag_LR = np.fliplr(mag_LR)
    mag_RL = np.fliplr(mag_RL)
    mag_TB = np.fliplr(mag_TB)
    mag_BT = np.fliplr(mag_BT)

    print(f"  ✓ All data flipped horizontally")

    # Initialize pipeline
    cfg = AppConfig.from_file('config/isi_parameters.json')
    pipeline = AnalysisPipeline(cfg.analysis)

    # Generate retinotopic maps
    print("\n" + "="*80)
    print("GENERATING RETINOTOPIC MAPS")
    print("="*80)

    azimuth = pipeline.generate_azimuth_map(phase_LR, phase_RL)
    elevation = pipeline.generate_elevation_map(phase_TB, phase_BT)

    # Center the maps
    azimuth_centered = azimuth - np.nanmean(azimuth)
    elevation_centered = elevation - np.nanmean(elevation)

    print(f"\nAzimuth (centered): [{np.nanmin(azimuth_centered):.1f}°, {np.nanmax(azimuth_centered):.1f}°]")
    print(f"Elevation (centered): [{np.nanmin(elevation_centered):.1f}°, {np.nanmax(elevation_centered):.1f}°]")

    # Compute pixpermm
    image_width_pixels = azimuth.shape[1]
    pixpermm = image_width_pixels / cfg.analysis.ring_size_mm
    print(f"\nSpatial calibration: {pixpermm:.2f} pixels/mm")

    # Compute VFS
    JacIm, VFS_sereno = compute_vfs_matlab_method(
        azimuth_centered,
        elevation_centered,
        pixpermm,
        sigma=3
    )

    # Compute thresholds
    print("\n" + "="*80)
    print("COMPUTING VFS THRESHOLDS")
    print("="*80)

    threshold_stat = 1.5 * np.std(VFS_sereno)
    gradmag = np.abs(VFS_sereno)
    mask_stat = gradmag >= (threshold_stat / 2)
    print(f"  Statistical threshold (±1.5σ): {threshold_stat:.4f}")
    print(f"  Pixels above: {np.sum(mask_stat)}/{mask_stat.size} ({100*np.sum(mask_stat)/mask_stat.size:.1f}%)")

    mag_avg = (mag_LR + mag_RL + mag_TB + mag_BT) / 4
    mag_norm = mag_avg / np.max(mag_avg)
    mask_mag = mag_norm >= 0.07
    print(f"  Magnitude threshold (0.07): {np.sum(mask_mag)}/{mask_mag.size} ({100*np.sum(mask_mag)/mask_mag.size:.1f}%)")

    # Create output directory
    output_dir = Path('figures_output_oriented')
    output_dir.mkdir(exist_ok=True)
    print(f"\n{'='*80}")
    print(f"SAVING FIGURES TO: {output_dir}")
    print(f"{'='*80}")

    # Save anatomy for comparison
    print("\n[1/8] Saving oriented anatomy...")
    cv2.imwrite(str(output_dir / 'Anatomy_Oriented.png'), anatomy)
    print(f"  Saved: {output_dir / 'Anatomy_Oriented.png'}")

    # Save retinotopy maps
    print("\n[2/8] Saving oriented azimuth map...")
    azimuth_norm = ((azimuth_centered + 60) / 120 * 255).astype(np.uint8)
    azimuth_colored = cv2.applyColorMap(azimuth_norm, cv2.COLORMAP_HSV)
    cv2.imwrite(str(output_dir / 'Azimuth_Oriented.png'), azimuth_colored)
    print(f"  Saved: {output_dir / 'Azimuth_Oriented.png'}")

    print("\n[3/8] Saving oriented elevation map...")
    elevation_norm = ((elevation_centered + 30) / 60 * 255).astype(np.uint8)
    elevation_colored = cv2.applyColorMap(elevation_norm, cv2.COLORMAP_HSV)
    cv2.imwrite(str(output_dir / 'Elevation_Oriented.png'), elevation_colored)
    print(f"  Saved: {output_dir / 'Elevation_Oriented.png'}")

    # Save VFS figures
    print("\n[4/8] Raw Sereno VFS (oriented)...")
    save_vfs_matlab_style(VFS_sereno, str(output_dir / 'VFS_Sereno_Raw_Oriented.png'))

    print("\n[5/8] Statistical-thresholded VFS (oriented)...")
    save_vfs_matlab_style(VFS_sereno, str(output_dir / 'VFS_Sereno_StatThresh_Oriented.png'), mask=mask_stat)

    print("\n[6/8] Magnitude-thresholded VFS (oriented)...")
    save_vfs_matlab_style(VFS_sereno, str(output_dir / 'VFS_Sereno_MagThresh_Oriented.png'), mask=mask_mag)

    print("\n[7/8] Raw Jacobian VFS (oriented)...")
    JacIm_norm = JacIm / np.nanmax(np.abs(JacIm))
    save_vfs_matlab_style(JacIm_norm, str(output_dir / 'VFS_Jacobian_Raw_Oriented.png'))

    print("\n[8/8] Statistical-thresholded Jacobian VFS (oriented)...")
    save_vfs_matlab_style(JacIm_norm, str(output_dir / 'VFS_Jacobian_StatThresh_Oriented.png'), mask=mask_stat)

    # Summary
    print("\n" + "="*80)
    print("ORIENTATION CORRECTION COMPLETE")
    print("="*80)
    print("\n✅ All data now matches MATLAB orientation:")
    print("  • Horizontal flip (fliplr) applied to all maps")
    print("  • Matches generatekret.m line 93-123")
    print("  • Anatomy, phase maps, retinotopy maps, and VFS all oriented correctly")
    print("\n📊 Compare these figures with MATLAB output to verify orientation!")
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
