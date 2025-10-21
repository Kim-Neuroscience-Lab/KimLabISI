"""Compare current implementation with old_implementation to identify differences."""

import sys
sys.path.insert(0, 'src')

import numpy as np
from pathlib import Path

print("=" * 80)
print("IMPLEMENTATION COMPARISON")
print("=" * 80)

# Load sample data
session_path = Path('data/sessions/sample_session')
if not session_path.exists():
    print(f"Error: Session not found at {session_path}")
    sys.exit(1)

phase_LR = np.load(session_path / 'phase_LR.npy')
phase_RL = np.load(session_path / 'phase_RL.npy')
phase_TB = np.load(session_path / 'phase_TB.npy')
phase_BT = np.load(session_path / 'phase_BT.npy')

mag_LR = np.load(session_path / 'magnitude_LR.npy')
mag_RL = np.load(session_path / 'magnitude_RL.npy')
mag_TB = np.load(session_path / 'magnitude_TB.npy')
mag_BT = np.load(session_path / 'magnitude_BT.npy')

print(f"\nData loaded:")
print(f"  Phase maps shape: {phase_LR.shape}")
print(f"  Magnitude maps shape: {mag_LR.shape}")

# Test 1: Current implementation
print("\n" + "=" * 80)
print("CURRENT IMPLEMENTATION")
print("=" * 80)

from config import AppConfig
from analysis.pipeline import AnalysisPipeline

cfg = AppConfig.from_file('config/isi_parameters.json')
current_pipeline = AnalysisPipeline(cfg.analysis)

# Create coherence maps (normalize magnitudes)
coherence_data = {
    'LR': mag_LR / (np.max(mag_LR) + 1e-10),
    'RL': mag_RL / (np.max(mag_RL) + 1e-10),
    'TB': mag_TB / (np.max(mag_TB) + 1e-10),
    'BT': mag_BT / (np.max(mag_BT) + 1e-10)
}

current_results = current_pipeline.run_from_phase_maps(
    phase_data={'LR': phase_LR, 'RL': phase_RL, 'TB': phase_TB, 'BT': phase_BT},
    magnitude_data={'LR': mag_LR, 'RL': mag_RL, 'TB': mag_TB, 'BT': mag_BT},
    coherence_data=coherence_data
)

current_azimuth = current_results['azimuth_map']
current_elevation = current_results['elevation_map']
current_vfs = current_results['raw_vfs_map']

print(f"\nCurrent Results:")
print(f"  Azimuth range: [{np.nanmin(current_azimuth):.2f}, {np.nanmax(current_azimuth):.2f}]")
print(f"  Elevation range: [{np.nanmin(current_elevation):.2f}, {np.nanmax(current_elevation):.2f}]")
print(f"  VFS range: [{np.nanmin(current_vfs):.3f}, {np.nanmax(current_vfs):.3f}]")
print(f"  VFS mean: {np.nanmean(current_vfs):.3f}, std: {np.nanstd(current_vfs):.3f}")

# Test 2: Load reference data if available
print("\n" + "=" * 80)
print("REFERENCE DATA (if available)")
print("=" * 80)

try:
    # Check if we have reference HDF5 file from old implementation
    ref_file = session_path / 'reference_results.h5'
    if ref_file.exists():
        import h5py
        with h5py.File(ref_file, 'r') as f:
            if 'vfs' in f:
                old_vfs = f['vfs'][:]

                print(f"\nReference VFS found:")
                print(f"  VFS range: [{np.nanmin(old_vfs):.3f}, {np.nanmax(old_vfs):.3f}]")
                print(f"  VFS mean: {np.nanmean(old_vfs):.3f}, std: {np.nanstd(old_vfs):.3f}")

                # Compare
                print("\n" + "=" * 80)
                print("COMPARISON")
                print("=" * 80)

                vfs_correlation = np.corrcoef(current_vfs.flatten(), old_vfs.flatten())[0, 1]
                vfs_diff = np.nanmean(np.abs(current_vfs - old_vfs))

                print(f"\nVFS Correlation: {vfs_correlation:.6f}")
                print(f"VFS Mean Absolute Difference: {vfs_diff:.6f}")

                if vfs_correlation > 0.99:
                    print("✅ Implementations match (correlation > 0.99)")
                elif vfs_correlation > 0.95:
                    print("⚠️  Implementations similar but not identical (0.95 < correlation < 0.99)")
                else:
                    print("❌ Implementations differ significantly (correlation < 0.95)")
            else:
                print("No 'vfs' dataset in reference file")
    else:
        print(f"No reference file found at {ref_file}")
        print("Skipping comparison (this is okay if you haven't run old_implementation yet)")

except Exception as e:
    print(f"Could not load reference data: {e}")

print("\n" + "=" * 80)
