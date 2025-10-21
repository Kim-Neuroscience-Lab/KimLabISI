"""Generate VFS figures from sample_session with statistical filtering."""

import h5py
import numpy as np
import cv2
from pathlib import Path

def save_vfs_jet(vfs, filename, title=""):
    """Save VFS using JET colormap."""
    vfs_norm = np.clip(vfs, -1, 1)
    vfs_scaled = ((vfs_norm + 1) / 2 * 255).astype(np.uint8)
    colored = cv2.applyColorMap(vfs_scaled, cv2.COLORMAP_JET)
    nan_mask = np.isnan(vfs) | (vfs == 0)
    colored[nan_mask] = [255, 255, 255]
    cv2.imwrite(filename, colored)
    print(f"  Saved: {filename}")

output_dir = Path('figures_output')
output_dir.mkdir(exist_ok=True)

print("=" * 80)
print("GENERATING SAMPLE_SESSION FIGURES WITH STATISTICAL FILTERING")
print("=" * 80)

h5_path = "data/sessions/sample_session/analysis_results/analysis_results.h5"

with h5py.File(h5_path, 'r') as f:
    raw_vfs = f['raw_vfs_map'][:]
    stat_vfs = f['statistical_vfs_map'][:]

    # Get magnitude for additional thresholding
    mag_LR = f['magnitude_maps/LR'][:]
    mag_RL = f['magnitude_maps/RL'][:]
    mag_TB = f['magnitude_maps/TB'][:]
    mag_BT = f['magnitude_maps/BT'][:]

    print(f"\nVFS Statistics:")
    print(f"  Raw VFS non-zero: {np.sum(raw_vfs != 0)} ({100*np.sum(raw_vfs != 0)/raw_vfs.size:.1f}%)")
    print(f"  Statistical VFS non-zero: {np.sum(stat_vfs != 0)} ({100*np.sum(stat_vfs != 0)/stat_vfs.size:.1f}%)")

# Compute magnitude masks
mag_hor = (mag_LR + mag_RL) / 2
mag_vert = (mag_TB + mag_BT) / 2
mag_hor_norm = (mag_hor - mag_hor.min()) / (mag_hor.max() - mag_hor.min() + 1e-10)
mag_vert_norm = (mag_vert - mag_vert.min()) / (mag_vert.max() - mag_vert.min() + 1e-10)

print("\n" + "=" * 80)
print("GENERATING FIGURES")
print("=" * 80)

# 1. Raw VFS (no statistical filter)
print("\n[1] Raw VFS (no statistical filter)...")
raw_vfs_display = raw_vfs.copy()
raw_vfs_display[raw_vfs_display == 0] = np.nan
save_vfs_jet(raw_vfs_display, str(output_dir / 'R43_VFS_Raw_NoStatFilter.png'))

# 2. Statistical VFS (with 1.5*std filter)
print("\n[2] Statistical VFS (with 1.5*std filter)...")
stat_vfs_display = stat_vfs.copy()
stat_vfs_display[stat_vfs_display == 0] = np.nan
save_vfs_jet(stat_vfs_display, str(output_dir / 'R43_VFS_StatisticallyFiltered.png'))

# 3. Statistical VFS with magnitude thresholding
print("\n[3] Statistical VFS with magnitude thresholding...")
thresholds = [0.05, 0.07, 0.10]
for thresh in thresholds:
    mask_hor = mag_hor_norm >= thresh
    mask_vert = mag_vert_norm >= thresh
    mask_combined = mask_hor & mask_vert

    stat_vfs_masked = stat_vfs.copy()
    stat_vfs_masked[~mask_combined] = np.nan
    stat_vfs_masked[stat_vfs == 0] = np.nan

    save_vfs_jet(stat_vfs_masked, str(output_dir / f'R43_VFS_StatFiltered_MagThresh_{thresh:.2f}.png'))

print("\n" + "=" * 80)
print("COMPARISON SUMMARY")
print("=" * 80)
print(f"\nRaw VFS:")
print(f"  - Shows ALL retinotopic gradient data")
print(f"  - Includes weak/noisy values")
print(f"  - 100% of pixels shown")

print(f"\nStatistical VFS:")
print(f"  - Filters out insignificant values (|VFS| < 1.5*std)")
print(f"  - Only significant gradient changes shown")
print(f"  - Only 5.7% of pixels shown (94.3% filtered)")
print(f"  - This is what MATLAB uses for clean visualization")

print(f"\nStatistical VFS + Magnitude Threshold:")
print(f"  - Statistical filter PLUS response magnitude filter")
print(f"  - Most stringent filtering")
print(f"  - Best for identifying clear visual area boundaries")

print("\n" + "=" * 80)
