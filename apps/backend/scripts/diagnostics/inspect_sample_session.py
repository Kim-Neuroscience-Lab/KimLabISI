"""Inspect sample_session analysis results."""

import h5py
import numpy as np

h5_path = "data/sessions/sample_session/analysis_results/analysis_results.h5"

print("=" * 80)
print(f"INSPECTING: {h5_path}")
print("=" * 80)

with h5py.File(h5_path, 'r') as f:
    print("\nAvailable datasets:")
    for key in f.keys():
        item = f[key]
        if isinstance(item, h5py.Group):
            print(f"  [GROUP] {key}/")
            for subkey in item.keys():
                print(f"    - {subkey}: shape={item[subkey].shape}")
        elif isinstance(item, h5py.Dataset):
            print(f"  [DATASET] {key}: shape={item.shape}, dtype={item.dtype}")

    # Check for statistical VFS
    print("\n" + "=" * 80)
    if 'statistical_vfs_map' in f:
        vfs_stat = f['statistical_vfs_map'][:]
        print("✓ Found statistical_vfs_map!")
        print(f"  Range: [{np.nanmin(vfs_stat):.3f}, {np.nanmax(vfs_stat):.3f}]")
        print(f"  Non-zero: {np.sum(vfs_stat != 0)} ({100*np.sum(vfs_stat != 0)/vfs_stat.size:.1f}%)")
    else:
        print("✗ No statistical_vfs_map found!")

    if 'raw_vfs_map' in f:
        vfs_raw = f['raw_vfs_map'][:]
        print("\n✓ Found raw_vfs_map!")
        print(f"  Range: [{np.nanmin(vfs_raw):.3f}, {np.nanmax(vfs_raw):.3f}]")
        print(f"  Non-zero: {np.sum(vfs_raw != 0)} ({100*np.sum(vfs_raw != 0)/vfs_raw.size:.1f}%)")

print("=" * 80)
