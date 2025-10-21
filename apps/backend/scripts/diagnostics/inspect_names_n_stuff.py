"""Inspect the 'names n stuff' session analysis results."""

import h5py
import numpy as np

h5_path = "data/sessions/names n stuff/analysis_results/analysis_results.h5"

print("=" * 80)
print(f"INSPECTING: {h5_path}")
print("=" * 80)

with h5py.File(h5_path, 'r') as f:
    print("\nTop-level groups/datasets:")
    for key in f.keys():
        item = f[key]
        if isinstance(item, h5py.Group):
            print(f"  [GROUP] {key}/")
            for subkey in item.keys():
                subitem = item[subkey]
                if isinstance(subitem, h5py.Dataset):
                    print(f"    [DATASET] {subkey}: shape={subitem.shape}, dtype={subitem.dtype}")
                elif isinstance(subitem, h5py.Group):
                    print(f"    [GROUP] {subkey}/")
        elif isinstance(item, h5py.Dataset):
            print(f"  [DATASET] {key}: shape={item.shape}, dtype={item.dtype}")

    # Check if VFS data exists
    print("\n" + "=" * 80)
    print("CHECKING FOR VFS DATA:")
    print("=" * 80)

    if 'visual_field_sign' in f:
        vfs = f['visual_field_sign'][:]
        print(f"\n✓ Found VFS map!")
        print(f"  Shape: {vfs.shape}")
        print(f"  Range: [{np.nanmin(vfs):.3f}, {np.nanmax(vfs):.3f}]")
        print(f"  Mean: {np.nanmean(vfs):.3f}")
        print(f"  Std: {np.nanstd(vfs):.3f}")
    else:
        print("\n✗ No VFS map found at 'visual_field_sign'")

    # Check for retinotopic maps
    if 'azimuth_map' in f:
        print(f"\n✓ Found azimuth_map: shape={f['azimuth_map'].shape}")
    if 'elevation_map' in f:
        print(f"✓ Found elevation_map: shape={f['elevation_map'].shape}")

    # Check for phase/magnitude
    phase_keys = [k for k in f.keys() if 'phase' in k.lower()]
    mag_keys = [k for k in f.keys() if 'mag' in k.lower()]

    if phase_keys:
        print(f"\n✓ Found {len(phase_keys)} phase datasets:")
        for k in phase_keys:
            print(f"  - {k}: shape={f[k].shape}")

    if mag_keys:
        print(f"\n✓ Found {len(mag_keys)} magnitude datasets:")
        for k in mag_keys:
            print(f"  - {k}: shape={f[k].shape}")

print("\n" + "=" * 80)
