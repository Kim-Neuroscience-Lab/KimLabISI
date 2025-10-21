"""Diagnose phase wrapping vs real discontinuities in retinotopy maps."""

import sys
sys.path.insert(0, 'src')

import h5py
import numpy as np
import cv2
from config import AppConfig
from analysis.pipeline import AnalysisPipeline

def diagnose_phase_wraps():
    """Analyze phase wraps and discontinuities in detail."""
    print("=" * 70)
    print("Phase Wrapping Diagnostic")
    print("=" * 70)

    # Load sample session data
    h5_path = 'data/sessions/sample_session/analysis_results/analysis_results.h5'

    with h5py.File(h5_path, 'r') as f:
        phase_LR = f['phase_maps/LR'][:]
        phase_RL = f['phase_maps/RL'][:]
        phase_TB = f['phase_maps/TB'][:]
        phase_BT = f['phase_maps/BT'][:]
        coherence_LR = f['coherence_maps/LR'][:]

    print(f"\nInput Phase Map Statistics:")
    print(f"  LR phase range: [{np.nanmin(phase_LR):.3f}, {np.nanmax(phase_LR):.3f}] rad")
    print(f"  RL phase range: [{np.nanmin(phase_RL):.3f}, {np.nanmax(phase_RL):.3f}] rad")
    print(f"  TB phase range: [{np.nanmin(phase_TB):.3f}, {np.nanmax(phase_TB):.3f}] rad")
    print(f"  BT phase range: [{np.nanmin(phase_BT):.3f}, {np.nanmax(phase_BT):.3f}] rad")
    print(f"  Coherence range: [{np.nanmin(coherence_LR):.3f}, {np.nanmax(coherence_LR):.3f}]")

    # Load config and create pipeline
    cfg = AppConfig.from_file('config/isi_parameters.json')
    pipeline = AnalysisPipeline(cfg.analysis)

    # Generate retinotopy maps
    azimuth = pipeline.generate_azimuth_map(phase_LR, phase_RL)
    elevation = pipeline.generate_elevation_map(phase_TB, phase_BT)

    print(f"\nOutput Retinotopy Statistics:")
    print(f"  Azimuth range: [{np.nanmin(azimuth):.2f}°, {np.nanmax(azimuth):.2f}°]")
    print(f"  Elevation range: [{np.nanmin(elevation):.2f}°, {np.nanmax(elevation):.2f}°]")

    # Analyze discontinuities
    print("\n" + "=" * 70)
    print("Discontinuity Analysis")
    print("=" * 70)

    # Compute gradients (rate of change)
    az_dx = np.diff(azimuth, axis=1)  # Horizontal gradient
    az_dy = np.diff(azimuth, axis=0)  # Vertical gradient
    el_dx = np.diff(elevation, axis=1)
    el_dy = np.diff(elevation, axis=0)

    print("\nAzimuth Map:")
    print(f"  Max horizontal gradient: {np.nanmax(np.abs(az_dx)):.2f}°")
    print(f"  Max vertical gradient: {np.nanmax(np.abs(az_dy)):.2f}°")
    print(f"  Gradients >30°: {np.sum(np.abs(az_dx) > 30)} horizontal, {np.sum(np.abs(az_dy) > 30)} vertical")

    # Find locations of large jumps
    large_jumps_h = np.abs(az_dx) > 30
    large_jumps_v = np.abs(az_dy) > 30

    if np.any(large_jumps_h):
        jump_locs = np.where(large_jumps_h)
        print(f"  Example large horizontal jump at row {jump_locs[0][0]}, col {jump_locs[1][0]}:")
        r, c = jump_locs[0][0], jump_locs[1][0]
        print(f"    Value at [{r},{c}]: {azimuth[r,c]:.2f}°")
        print(f"    Value at [{r},{c+1}]: {azimuth[r,c+1]:.2f}°")
        print(f"    Jump: {az_dx[r,c]:.2f}°")

    print("\nElevation Map:")
    print(f"  Max horizontal gradient: {np.nanmax(np.abs(el_dx)):.2f}°")
    print(f"  Max vertical gradient: {np.nanmax(np.abs(el_dy)):.2f}°")
    print(f"  Gradients >30°: {np.sum(np.abs(el_dx) > 30)} horizontal, {np.sum(np.abs(el_dy) > 30)} vertical")

    # Check if jumps correlate with phase wraps in input data
    print("\n" + "=" * 70)
    print("Phase Wrapping in Input Data")
    print("=" * 70)

    # Check for phase wraps in input phase maps
    LR_dx = np.abs(np.diff(phase_LR, axis=1))
    LR_wraps = np.sum(LR_dx > np.pi)
    RL_dx = np.abs(np.diff(phase_RL, axis=1))
    RL_wraps = np.sum(RL_dx > np.pi)

    print(f"\nLR phase map: {LR_wraps} phase wraps (jumps > π)")
    print(f"RL phase map: {RL_wraps} phase wraps (jumps > π)")

    TB_dy = np.abs(np.diff(phase_TB, axis=0))
    TB_wraps = np.sum(TB_dy > np.pi)
    BT_dy = np.abs(np.diff(phase_BT, axis=0))
    BT_wraps = np.sum(BT_dy > np.pi)

    print(f"TB phase map: {TB_wraps} phase wraps (jumps > π)")
    print(f"BT phase map: {BT_wraps} phase wraps (jumps > π)")

    # Create visualization showing jump locations
    print("\n" + "=" * 70)
    print("Creating Jump Location Visualizations")
    print("=" * 70)

    # Create a map showing where large gradients occur
    jump_map_azimuth = np.zeros_like(azimuth)
    jump_map_azimuth[:, :-1] += (np.abs(az_dx) > 30).astype(float)
    jump_map_azimuth[:-1, :] += (np.abs(az_dy) > 30).astype(float)

    jump_viz = (jump_map_azimuth * 255).astype(np.uint8)
    jump_colored = cv2.applyColorMap(jump_viz, cv2.COLORMAP_HOT)
    cv2.imwrite('azimuth_jumps.png', jump_colored)
    print("  Saved: azimuth_jumps.png (bright = large gradient)")

    # Show histogram of gradient magnitudes
    print("\n" + "=" * 70)
    print("Gradient Distribution")
    print("=" * 70)

    az_grad_mag = np.sqrt(az_dx[:-1, :]**2 + az_dy[:, :-1]**2)
    percentiles = [50, 75, 90, 95, 99, 100]
    print("\nAzimuth gradient magnitude percentiles:")
    for p in percentiles:
        val = np.nanpercentile(az_grad_mag, p)
        print(f"  {p}th percentile: {val:.2f}°")

    print("\n" + "=" * 70)
    print("✅ Diagnostic Complete!")
    print("=" * 70)

if __name__ == "__main__":
    try:
        diagnose_phase_wraps()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
