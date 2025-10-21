"""Inspect all MATLAB files in sample_data."""

import scipy.io as sio
import numpy as np
from pathlib import Path

def inspect_mat_file(filepath):
    """Inspect a single MAT file."""
    print(f"\n{'=' * 80}")
    print(f"FILE: {filepath.name}")
    print('=' * 80)

    try:
        data = sio.loadmat(filepath)

        # List all keys
        print("\nKeys in file:")
        for key in data.keys():
            if not key.startswith('__'):
                print(f"  - {key}")

        # Examine non-metadata keys
        print("\nData structures:")
        for key, value in data.items():
            if not key.startswith('__'):
                print(f"\n  {key}:")
                print(f"    Type: {type(value)}")
                if isinstance(value, np.ndarray):
                    print(f"    Shape: {value.shape}")
                    print(f"    Dtype: {value.dtype}")

                    # If it's a cell array or object array, dig deeper
                    if value.dtype == object:
                        print(f"    Contents (object array):")
                        for i in range(min(value.size, 10)):
                            idx = np.unravel_index(i, value.shape)
                            item = value[idx]
                            print(f"      [{idx}]: type={type(item)}, shape={getattr(item, 'shape', 'N/A')}, dtype={getattr(item, 'dtype', 'N/A')}")

                    # If it contains complex data, show statistics
                    elif np.iscomplexobj(value):
                        phase = np.angle(value)
                        magnitude = np.abs(value)
                        print(f"    Phase range: [{np.min(phase):.3f}, {np.max(phase):.3f}] rad")
                        print(f"    Magnitude range: [{np.min(magnitude):.3f}, {np.max(magnitude):.3f}]")

                    # If numeric, show range
                    elif np.issubdtype(value.dtype, np.number):
                        print(f"    Value range: [{np.min(value):.3f}, {np.max(value):.3f}]")

    except Exception as e:
        print(f"  ERROR loading file: {e}")
        import traceback
        traceback.print_exc()

def main():
    sample_dir = Path('../../sample_data')

    print("=" * 80)
    print("MATLAB FILE INSPECTION")
    print("=" * 80)
    print(f"\nSearching in: {sample_dir.absolute()}")

    mat_files = sorted(sample_dir.glob('*.mat'))
    print(f"Found {len(mat_files)} .mat files")

    for mat_file in mat_files:
        inspect_mat_file(mat_file)

    print("\n" + "=" * 80)
    print("INSPECTION COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
