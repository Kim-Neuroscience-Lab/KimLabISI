"""Check if statistical VFS filtering is applied."""

import h5py
import numpy as np
import cv2
from pathlib import Path

def save_vfs_jet(vfs, filename):
    """Quick JET colormap save."""
    vfs_norm = np.clip(vfs, -1, 1)
    vfs_scaled = ((vfs_norm + 1) / 2 * 255).astype(np.uint8)
    colored = cv2.applyColorMap(vfs_scaled, cv2.COLORMAP_JET)
    nan_mask = np.isnan(vfs)
    colored[nan_mask] = [255, 255, 255]
    cv2.imwrite(filename, colored)
    print(f"  Saved: {filename}")

h5_path = "data/sessions/names n stuff/analysis_results/analysis_results.h5"

print("=" * 80)
print("CHECKING STATISTICAL VFS FILTERING")
print("=" * 80)

with h5py.File(h5_path, 'r') as f:
    raw_vfs = f['raw_vfs_map'][:]
    stat_vfs = f['statistical_vfs_map'][:]

    print(f"\n[1] Raw VFS (no statistical filtering):")
    print(f"  Range: [{np.nanmin(raw_vfs):.3f}, {np.nanmax(raw_vfs):.3f}]")
    print(f"  Mean: {np.nanmean(raw_vfs):.3f}")
    print(f"  Std: {np.nanstd(raw_vfs):.3f}")
    print(f"  Non-zero pixels: {np.sum(raw_vfs != 0)} ({100*np.sum(raw_vfs != 0)/raw_vfs.size:.1f}%)")

    print(f"\n[2] Statistical VFS (with 1.5*std filtering):")
    print(f"  Range: [{np.nanmin(stat_vfs):.3f}, {np.nanmax(stat_vfs):.3f}]")
    print(f"  Mean: {np.nanmean(stat_vfs):.3f}")
    print(f"  Std: {np.nanstd(stat_vfs):.3f}")
    print(f"  Non-zero pixels: {np.sum(stat_vfs != 0)} ({100*np.sum(stat_vfs != 0)/stat_vfs.size:.1f}%)")
    print(f"  Zeroed pixels: {np.sum(stat_vfs == 0)} ({100*np.sum(stat_vfs == 0)/stat_vfs.size:.1f}%)")

    # Calculate the threshold
    vfs_std = np.std(raw_vfs)
    stat_threshold = 1.5 * vfs_std
    print(f"\n[3] Statistical Threshold:")
    print(f"  VFS std: {vfs_std:.3f}")
    print(f"  Threshold (1.5 * std): {stat_threshold:.3f}")
    print(f"  Pixels above threshold: {np.sum(np.abs(raw_vfs) >= stat_threshold/2)} ({100*np.sum(np.abs(raw_vfs) >= stat_threshold/2)/raw_vfs.size:.1f}%)")

# Generate side-by-side comparison figures
output_dir = Path('figures_output_names_n_stuff')
output_dir.mkdir(exist_ok=True)
print(f"\n" + "=" * 80)
print(f"GENERATING COMPARISON FIGURES")
print(f"=" * 80)

with h5py.File(h5_path, 'r') as f:
    raw_vfs = f['raw_vfs_map'][:]
    stat_vfs = f['statistical_vfs_map'][:]

    # Get magnitude for thresholding
    mag_LR = f['magnitude_maps/LR'][:]
    mag_RL = f['magnitude_maps/RL'][:]
    mag_TB = f['magnitude_maps/TB'][:]
    mag_BT = f['magnitude_maps/BT'][:]

    mag_hor = (mag_LR + mag_RL) / 2
    mag_vert = (mag_TB + mag_BT) / 2
    mag_hor_norm = (mag_hor - mag_hor.min()) / (mag_hor.max() - mag_hor.min() + 1e-10)
    mag_vert_norm = (mag_vert - mag_vert.min()) / (mag_vert.max() - mag_vert.min() + 1e-10)

    # Apply magnitude threshold
    mask_combined = (mag_hor_norm >= 0.07) & (mag_vert_norm >= 0.07)

    # Raw VFS with magnitude threshold
    raw_vfs_masked = raw_vfs.copy()
    raw_vfs_masked[~mask_combined] = np.nan

    # Statistical VFS with magnitude threshold
    stat_vfs_masked = stat_vfs.copy()
    stat_vfs_masked[~mask_combined] = np.nan

    print(f"\n[4] Saving comparison figures...")
    save_vfs_jet(raw_vfs_masked, str(output_dir / 'VFS_Raw_NoStatFilter.png'))
    save_vfs_jet(stat_vfs_masked, str(output_dir / 'VFS_StatisticallyFiltered.png'))

print(f"\n" + "=" * 80)
print(f"CONCLUSION:")
print(f"=" * 80)
print(f"Statistical filtering zeros out weak/noisy VFS values.")
print(f"This is what MATLAB does to clean up the VFS visualization.")
print(f"We should use the statistical_vfs_map for final visualization!")
print(f"=" * 80)
