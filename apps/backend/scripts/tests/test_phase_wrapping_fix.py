"""Test the phase wrapping fix by reprocessing existing phase maps."""

import sys
sys.path.insert(0, 'src')

import h5py
import numpy as np
from config import AppConfig
from analysis.pipeline import AnalysisPipeline

def test_phase_wrapping_fix():
    """Test that phase wrapping fix eliminates discontinuities."""
    print("=" * 70)
    print("Testing Phase Wrapping Fix")
    print("=" * 70)

    # Load existing phase maps
    session_path = 'data/sessions/names n stuff'
    h5_path = f'{session_path}/analysis_results/analysis_results.h5'

    print(f"\nLoading phase maps from: {h5_path}")

    with h5py.File(h5_path, 'r') as f:
        # Load raw phase maps
        phase_LR = f['phase_maps/LR'][:]
        phase_RL = f['phase_maps/RL'][:]
        phase_TB = f['phase_maps/TB'][:]
        phase_BT = f['phase_maps/BT'][:]

        print(f"  LR phase range: [{np.nanmin(phase_LR):.3f}, {np.nanmax(phase_LR):.3f}] rad")
        print(f"  RL phase range: [{np.nanmin(phase_RL):.3f}, {np.nanmax(phase_RL):.3f}] rad")
        print(f"  TB phase range: [{np.nanmin(phase_TB):.3f}, {np.nanmax(phase_TB):.3f}] rad")
        print(f"  BT phase range: [{np.nanmin(phase_BT):.3f}, {np.nanmax(phase_BT):.3f}] rad")

    # Load config and create pipeline
    cfg = AppConfig.from_file('config/isi_parameters.json')
    pipeline = AnalysisPipeline(cfg.analysis)

    print("\n" + "=" * 70)
    print("Reprocessing with Fixed Bidirectional Analysis")
    print("=" * 70)

    # Regenerate azimuth and elevation maps
    azimuth_map = pipeline.generate_azimuth_map(phase_LR, phase_RL)
    elevation_map = pipeline.generate_elevation_map(phase_TB, phase_BT)

    print(f"\nAzimuth map range: [{np.nanmin(azimuth_map):.2f}°, {np.nanmax(azimuth_map):.2f}°]")
    print(f"Elevation map range: [{np.nanmin(elevation_map):.2f}°, {np.nanmax(elevation_map):.2f}°]")

    # Check for discontinuities
    print("\n" + "=" * 70)
    print("Discontinuity Analysis")
    print("=" * 70)

    az_dx = np.abs(np.diff(azimuth_map, axis=1))
    az_dy = np.abs(np.diff(azimuth_map, axis=0))
    el_dx = np.abs(np.diff(elevation_map, axis=1))
    el_dy = np.abs(np.diff(elevation_map, axis=0))

    print("\nAzimuth Map:")
    print(f"  Max horizontal jump: {np.nanmax(az_dx):.2f}°")
    print(f"  Max vertical jump: {np.nanmax(az_dy):.2f}°")
    print(f"  Pixels with >30° horizontal jump: {np.sum(az_dx > 30)}")
    print(f"  Pixels with >30° vertical jump: {np.sum(az_dy > 30)}")
    print(f"  Mean gradient: {np.nanmean(az_dx):.2f}°")

    print("\nElevation Map:")
    print(f"  Max horizontal jump: {np.nanmax(el_dx):.2f}°")
    print(f"  Max vertical jump: {np.nanmax(el_dy):.2f}°")
    print(f"  Pixels with >15° horizontal jump: {np.sum(el_dx > 15)}")
    print(f"  Pixels with >15° vertical jump: {np.sum(el_dy > 15)}")
    print(f"  Mean gradient: {np.nanmean(el_dx):.2f}°")

    # Verdict
    print("\n" + "=" * 70)
    if np.nanmax(az_dx) < 30 and np.nanmax(el_dx) < 15:
        print("✅ SUCCESS: Discontinuities eliminated!")
        print("=" * 70)
        return True
    else:
        print("⚠️  PARTIAL: Discontinuities reduced but not eliminated")
        print(f"   Azimuth: {np.sum(az_dx > 30)} pixels with >30° jumps")
        print(f"   Elevation: {np.sum(el_dx > 15)} pixels with >15° jumps")
        print("=" * 70)
        return False

if __name__ == "__main__":
    success = test_phase_wrapping_fix()
    sys.exit(0 if success else 1)
