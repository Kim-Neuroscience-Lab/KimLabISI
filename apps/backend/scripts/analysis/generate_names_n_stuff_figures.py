"""Generate VFS figures from 'names n stuff' session (corrected data)."""

import sys
import h5py
import numpy as np
import cv2
from pathlib import Path

def save_vfs_image_jet(vfs_map, filename, mask=None):
    """Save VFS map using JET colormap."""
    vfs_display = vfs_map.copy()

    if mask is not None:
        vfs_display[~mask] = np.nan

    # Normalize to [-1, 1] range
    vfs_normalized = np.clip(vfs_display, -1, 1)

    # Convert to 0-255 range for JET colormap
    vfs_scaled = ((vfs_normalized + 1) / 2 * 255).astype(np.uint8)

    # Apply JET colormap
    colored = cv2.applyColorMap(vfs_scaled, cv2.COLORMAP_JET)

    # Handle NaN/masked pixels (white)
    nan_mask = np.isnan(vfs_display)
    if mask is not None:
        nan_mask = nan_mask | (~mask)
    colored[nan_mask] = [255, 255, 255]

    cv2.imwrite(filename, colored)
    print(f"  Saved: {filename}")

# Create output directory
output_dir = Path('figures_output_names_n_stuff')
output_dir.mkdir(exist_ok=True)

print("=" * 80)
print("GENERATING FIGURES FROM 'names n stuff' SESSION")
print("=" * 80)

# Load analysis results
h5_path = "data/sessions/names n stuff/analysis_results/analysis_results.h5"
print(f"\nLoading: {h5_path}")

with h5py.File(h5_path, 'r') as f:
    vfs = f['raw_vfs_map'][:]
    azimuth = f['azimuth_map'][:]
    elevation = f['elevation_map'][:]
    boundary = f['boundary_map'][:]

    # Get magnitude maps for thresholding
    mag_LR = f['magnitude_maps/LR'][:]
    mag_RL = f['magnitude_maps/RL'][:]
    mag_TB = f['magnitude_maps/TB'][:]
    mag_BT = f['magnitude_maps/BT'][:]

    print(f"  Loaded VFS: shape={vfs.shape}, range=[{np.nanmin(vfs):.3f}, {np.nanmax(vfs):.3f}]")

# Compute average magnitude for thresholding
mag_hor = (mag_LR + mag_RL) / 2
mag_vert = (mag_TB + mag_BT) / 2
mag_hor_norm = (mag_hor - mag_hor.min()) / (mag_hor.max() - mag_hor.min() + 1e-10)
mag_vert_norm = (mag_vert - mag_vert.min()) / (mag_vert.max() - mag_vert.min() + 1e-10)

print("\n" + "=" * 80)
print("GENERATING VFS FIGURES")
print("=" * 80)

# 1. Raw VFS (no thresholding)
print("\n[1] Raw VFS...")
save_vfs_image_jet(vfs, str(output_dir / 'VFS_Raw.png'))

# 2. Magnitude-thresholded VFS at different levels
thresholds = [0.05, 0.07, 0.10]
print("\n[2] Magnitude-thresholded VFS...")
for thresh in thresholds:
    mask_hor = mag_hor_norm >= thresh
    mask_vert = mag_vert_norm >= thresh
    mask_combined = mask_hor & mask_vert

    vfs_thresh = vfs.copy()
    vfs_thresh[~mask_combined] = np.nan

    save_vfs_image_jet(vfs_thresh, str(output_dir / f'VFS_MagThresh_{thresh:.2f}.png'), mask=mask_combined)

# 3. VFS with boundaries
print("\n[3] VFS with boundaries...")
mask_combined = (mag_hor_norm >= 0.07) & (mag_vert_norm >= 0.07)
vfs_thresh = vfs.copy()
vfs_thresh[~mask_combined] = np.nan

# Use JET colormap for VFS
vfs_normalized = np.clip(vfs_thresh, -1, 1)
vfs_scaled = ((vfs_normalized + 1) / 2 * 255).astype(np.uint8)
vfs_with_boundaries = cv2.applyColorMap(vfs_scaled, cv2.COLORMAP_JET)

# Handle NaN pixels
nan_mask = np.isnan(vfs_thresh)
vfs_with_boundaries[nan_mask] = [255, 255, 255]

# Overlay boundaries in white
vfs_with_boundaries[boundary > 0] = [255, 255, 255]

cv2.imwrite(str(output_dir / 'VFS_with_Boundaries.png'), vfs_with_boundaries)
print(f"  Saved: {output_dir / 'VFS_with_Boundaries.png'}")

# 4. Boundary map alone
print("\n[4] Boundary map...")
boundary_colored = np.zeros((*boundary.shape, 3), dtype=np.uint8)
boundary_colored[boundary > 0] = [255, 255, 255]
cv2.imwrite(str(output_dir / 'Boundaries.png'), boundary_colored)
print(f"  Saved: {output_dir / 'Boundaries.png'}")

print("\n" + "=" * 80)
print("FIGURE GENERATION COMPLETE")
print("=" * 80)
print(f"\n✅ Generated VFS figures in {output_dir}/")
print("\nFigures show:")
print("  • Raw VFS with gradient angle method (range [-1, 1])")
print("  • Magnitude-thresholded VFS at 5%, 7%, and 10%")
print("  • VFS with detected area boundaries")
print("  • Visual area boundaries alone")
print("\n" + "=" * 80)
