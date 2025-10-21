"""Check the VFS values in 'names n stuff' analysis results."""

import h5py
import numpy as np

h5_path = "data/sessions/names n stuff/analysis_results/analysis_results.h5"

print("=" * 80)
print("VFS ANALYSIS - 'names n stuff' Session")
print("=" * 80)

with h5py.File(h5_path, 'r') as f:
    vfs = f['raw_vfs_map'][:]

    print(f"\nVFS Statistics:")
    print(f"  Shape: {vfs.shape}")
    print(f"  Range: [{np.nanmin(vfs):.3f}, {np.nanmax(vfs):.3f}]")
    print(f"  Mean: {np.nanmean(vfs):.3f}")
    print(f"  Std: {np.nanstd(vfs):.3f}")
    print(f"  Positive pixels: {np.sum(vfs > 0)} ({100*np.sum(vfs > 0)/vfs.size:.1f}%)")
    print(f"  Negative pixels: {np.sum(vfs < 0)} ({100*np.sum(vfs < 0)/vfs.size:.1f}%)")
    print(f"  Zero pixels: {np.sum(vfs == 0)} ({100*np.sum(vfs == 0)/vfs.size:.1f}%)")

    # Check VFS range to determine method
    vfs_max_abs = np.nanmax(np.abs(vfs))
    print(f"\n✓ Method Detection:")
    if vfs_max_abs <= 1.1:  # Allow some tolerance
        print(f"  → Uses GRADIENT ANGLE method (range ≤ 1.0)")
        print(f"    Max absolute value: {vfs_max_abs:.3f}")
        print(f"    ✓ This is the CORRECT method matching MATLAB")
    else:
        print(f"  → Uses JACOBIAN DETERMINANT method (range > 1.0)")
        print(f"    Max absolute value: {vfs_max_abs:.3f}")
        print(f"    ✗ This is the INCORRECT method (not MATLAB-compatible)")

    # Check other datasets
    print(f"\n✓ Other Available Maps:")
    print(f"  - azimuth_map: {f['azimuth_map'].shape}")
    print(f"  - elevation_map: {f['elevation_map'].shape}")
    print(f"  - boundary_map: {f['boundary_map'].shape}")
    print(f"  - magnitude_vfs_map: {f['magnitude_vfs_map'].shape}")
    print(f"  - statistical_vfs_map: {f['statistical_vfs_map'].shape}")

print("\n" + "=" * 80)
print("CONCLUSION:")
print("=" * 80)
print("This session contains the analysis results from our current pipeline.")
print("We should generate new figures using this session data to verify the VFS fix.")
print("=" * 80)
