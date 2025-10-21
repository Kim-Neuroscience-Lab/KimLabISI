"""Test with real experimental session to verify coherence computation."""

import sys
sys.path.insert(0, 'src')

import h5py
import numpy as np
import cv2
from config import AppConfig
from analysis.pipeline import AnalysisPipeline
from analysis.renderer import AnalysisRenderer
from ipc.shared_memory import SharedMemoryService

def test_real_session():
    """Test with real experimental data."""
    print("=" * 70)
    print("Testing Real Experimental Session: 'names n stuff'")
    print("=" * 70)

    # Load real session data
    session_path = 'data/sessions/names n stuff'
    h5_path = f'{session_path}/analysis_results/analysis_results.h5'

    print(f"\nLoading data from: {h5_path}")

    with h5py.File(h5_path, 'r') as f:
        # Load phase and coherence maps
        phase_LR = f['phase_maps/LR'][:]
        phase_RL = f['phase_maps/RL'][:]
        phase_TB = f['phase_maps/TB'][:]
        phase_BT = f['phase_maps/BT'][:]

        coherence_LR = f['coherence_maps/LR'][:]
        coherence_RL = f['coherence_maps/RL'][:]
        coherence_TB = f['coherence_maps/TB'][:]
        coherence_BT = f['coherence_maps/BT'][:]

    # Compute min coherence
    min_coherence = np.minimum.reduce([coherence_LR, coherence_RL, coherence_TB, coherence_BT])

    print(f"\n" + "=" * 70)
    print("COHERENCE ANALYSIS (Real Experimental Data)")
    print("=" * 70)
    print(f"\nCoherence statistics:")
    print(f"  Range: [{np.nanmin(min_coherence):.3f}, {np.nanmax(min_coherence):.3f}]")
    print(f"  Mean: {np.nanmean(min_coherence):.3f}")
    print(f"  Median: {np.nanmedian(min_coherence):.3f}")
    print(f"  25th percentile: {np.nanpercentile(min_coherence, 25):.3f}")
    print(f"  75th percentile: {np.nanpercentile(min_coherence, 75):.3f}")

    # Check individual directions
    print(f"\nPer-direction coherence:")
    print(f"  LR: mean={np.nanmean(coherence_LR):.3f}, range=[{np.nanmin(coherence_LR):.3f}, {np.nanmax(coherence_LR):.3f}]")
    print(f"  RL: mean={np.nanmean(coherence_RL):.3f}, range=[{np.nanmin(coherence_RL):.3f}, {np.nanmax(coherence_RL):.3f}]")
    print(f"  TB: mean={np.nanmean(coherence_TB):.3f}, range=[{np.nanmin(coherence_TB):.3f}, {np.nanmax(coherence_TB):.3f}]")
    print(f"  BT: mean={np.nanmean(coherence_BT):.3f}, range=[{np.nanmin(coherence_BT):.3f}, {np.nanmax(coherence_BT):.3f}]")

    # Load config and create pipeline
    cfg = AppConfig.from_file('config/isi_parameters.json')

    print(f"\nUsing coherence_threshold = {cfg.analysis.coherence_threshold}")
    pixels_above = np.sum(min_coherence >= cfg.analysis.coherence_threshold)
    total_pixels = min_coherence.size
    print(f"  Pixels above threshold: {pixels_above}/{total_pixels} ({100*pixels_above/total_pixels:.1f}%)")

    # Create pipeline
    pipeline = AnalysisPipeline(cfg.analysis)

    print("\n" + "=" * 70)
    print("Reprocessing Retinotopy Maps")
    print("=" * 70)

    # Regenerate maps
    new_azimuth = pipeline.generate_azimuth_map(phase_LR, phase_RL)
    new_elevation = pipeline.generate_elevation_map(phase_TB, phase_BT)

    print(f"\nAzimuth range: [{np.nanmin(new_azimuth):.2f}°, {np.nanmax(new_azimuth):.2f}°]")
    print(f"Elevation range: [{np.nanmin(new_elevation):.2f}°, {np.nanmax(new_elevation):.2f}°]")

    # Create renderer
    shared_mem = SharedMemoryService()
    renderer = AnalysisRenderer(cfg.analysis, shared_mem)

    # Render maps
    print("\n" + "=" * 70)
    print("Rendering Real Session Data")
    print("=" * 70)

    print("\n[1/3] Rendering coherence map...")
    coherence_normalized = (min_coherence / np.nanmax(min_coherence) * 255).astype(np.uint8)
    coherence_colored = cv2.applyColorMap(coherence_normalized, cv2.COLORMAP_JET)
    cv2.imwrite('real_coherence_map.png', coherence_colored)
    print("  Saved: real_coherence_map.png")

    # Apply coherence threshold
    print(f"\n[2/3] Applying coherence threshold ({cfg.analysis.coherence_threshold})...")
    azimuth_thresholded = new_azimuth.copy()
    azimuth_thresholded[min_coherence < cfg.analysis.coherence_threshold] = np.nan

    azimuth_thresh_rgba = renderer.render_retinotopic_map(azimuth_thresholded, map_type='azimuth')
    azimuth_thresh_rgb = azimuth_thresh_rgba[:, :, :3]
    # Convert transparent pixels to white for visibility
    alpha = azimuth_thresh_rgba[:, :, 3]
    white_bg = np.ones_like(azimuth_thresh_rgb) * 255
    azimuth_thresh_rgb = (azimuth_thresh_rgb * (alpha[:, :, None] / 255.0) +
                          white_bg * (1 - alpha[:, :, None] / 255.0)).astype(np.uint8)
    cv2.imwrite('real_azimuth_thresholded.png', cv2.cvtColor(azimuth_thresh_rgb, cv2.COLOR_RGB2BGR))
    print("  Saved: real_azimuth_thresholded.png")

    print("\n[3/3] Rendering raw azimuth for comparison...")
    azimuth_rgba = renderer.render_retinotopic_map(new_azimuth, map_type='azimuth')
    azimuth_rgb = azimuth_rgba[:, :, :3]
    cv2.imwrite('real_azimuth_raw.png', cv2.cvtColor(azimuth_rgb, cv2.COLOR_RGB2BGR))
    print("  Saved: real_azimuth_raw.png")

    print("\n" + "=" * 70)
    print("✅ Real Session Analysis Complete!")
    print("=" * 70)
    print("\nGenerated files:")
    print("  • real_coherence_map.png          - Signal quality (SHOULD show variation!)")
    print("  • real_azimuth_raw.png            - Full azimuth map")
    print("  • real_azimuth_thresholded.png    - Coherence-filtered azimuth")
    print("\nIf coherence map still shows all red, there's a data generation issue.")

if __name__ == "__main__":
    try:
        test_real_session()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
