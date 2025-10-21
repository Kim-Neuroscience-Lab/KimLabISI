"""Visualize retinotopy maps to diagnose discontinuities."""

import sys
sys.path.insert(0, 'src')

import h5py
import numpy as np
import cv2
from config import AppConfig
from analysis.pipeline import AnalysisPipeline
from analysis.renderer import AnalysisRenderer
from ipc.shared_memory import SharedMemoryService

def visualize_sample_session():
    """Visualize sample session retinotopy maps and save as PNG."""
    print("=" * 70)
    print("Retinotopy Visualization - Sample Session")
    print("=" * 70)

    # Load sample session data
    session_path = 'data/sessions/sample_session'
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

        # Load old azimuth/elevation for comparison
        old_azimuth = f['azimuth_map'][:]
        old_elevation = f['elevation_map'][:]

    # Compute min coherence
    min_coherence = np.minimum.reduce([coherence_LR, coherence_RL, coherence_TB, coherence_BT])

    print(f"\nCoherence statistics:")
    print(f"  Range: [{np.nanmin(min_coherence):.3f}, {np.nanmax(min_coherence):.3f}]")
    print(f"  Mean: {np.nanmean(min_coherence):.3f}")
    print(f"  Median: {np.nanmedian(min_coherence):.3f}")

    # Load config and create pipeline
    cfg = AppConfig.from_file('config/isi_parameters.json')

    # Create analysis pipeline with current config
    pipeline = AnalysisPipeline(cfg.analysis)

    print("\n" + "=" * 70)
    print("Reprocessing with Current Unwrapping Method")
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
    print("Rendering Visualizations")
    print("=" * 70)

    print("\n[1/6] Rendering raw azimuth map...")
    azimuth_rgba = renderer.render_retinotopic_map(new_azimuth, map_type='azimuth')
    azimuth_rgb = azimuth_rgba[:, :, :3]
    cv2.imwrite('azimuth_raw.png', cv2.cvtColor(azimuth_rgb, cv2.COLOR_RGB2BGR))
    print("  Saved: azimuth_raw.png")

    print("\n[2/6] Rendering raw elevation map...")
    elevation_rgba = renderer.render_retinotopic_map(new_elevation, map_type='elevation')
    elevation_rgb = elevation_rgba[:, :, :3]
    cv2.imwrite('elevation_raw.png', cv2.cvtColor(elevation_rgb, cv2.COLOR_RGB2BGR))
    print("  Saved: elevation_raw.png")

    # Apply coherence thresholding
    print("\n[3/6] Applying coherence threshold...")
    # Use a reasonable threshold based on the data
    threshold = min(0.15, np.nanpercentile(min_coherence, 90))
    print(f"  Using threshold: {threshold:.3f}")
    print(f"  Pixels kept: {100*np.sum(min_coherence >= threshold)/min_coherence.size:.1f}%")

    azimuth_thresholded = new_azimuth.copy()
    azimuth_thresholded[min_coherence < threshold] = np.nan

    elevation_thresholded = new_elevation.copy()
    elevation_thresholded[min_coherence < threshold] = np.nan

    print("\n[4/6] Rendering thresholded azimuth...")
    azimuth_thresh_rgba = renderer.render_retinotopic_map(azimuth_thresholded, map_type='azimuth')
    azimuth_thresh_rgb = azimuth_thresh_rgba[:, :, :3]
    # Convert transparent pixels to white for visibility
    alpha = azimuth_thresh_rgba[:, :, 3]
    white_bg = np.ones_like(azimuth_thresh_rgb) * 255
    azimuth_thresh_rgb = (azimuth_thresh_rgb * (alpha[:, :, None] / 255.0) +
                          white_bg * (1 - alpha[:, :, None] / 255.0)).astype(np.uint8)
    cv2.imwrite('azimuth_thresholded.png', cv2.cvtColor(azimuth_thresh_rgb, cv2.COLOR_RGB2BGR))
    print("  Saved: azimuth_thresholded.png")

    print("\n[5/6] Rendering thresholded elevation...")
    elevation_thresh_rgba = renderer.render_retinotopic_map(elevation_thresholded, map_type='elevation')
    elevation_thresh_rgb = elevation_thresh_rgba[:, :, :3]
    alpha = elevation_thresh_rgba[:, :, 3]
    white_bg = np.ones_like(elevation_thresh_rgb) * 255
    elevation_thresh_rgb = (elevation_thresh_rgb * (alpha[:, :, None] / 255.0) +
                            white_bg * (1 - alpha[:, :, None] / 255.0)).astype(np.uint8)
    cv2.imwrite('elevation_thresholded.png', cv2.cvtColor(elevation_thresh_rgb, cv2.COLOR_RGB2BGR))
    print("  Saved: elevation_thresholded.png")

    # Render coherence map for reference
    print("\n[6/9] Rendering coherence map...")
    coherence_normalized = (min_coherence / np.nanmax(min_coherence) * 255).astype(np.uint8)
    coherence_colored = cv2.applyColorMap(coherence_normalized, cv2.COLORMAP_JET)
    cv2.imwrite('coherence_map.png', coherence_colored)
    print("  Saved: coherence_map.png")

    # Compute and render Visual Field Sign (VFS)
    print("\n[7/9] Computing Visual Field Sign...")
    gradients = pipeline.compute_spatial_gradients(new_azimuth, new_elevation)
    vfs_map = pipeline.calculate_visual_field_sign(gradients)

    print("\n[8/9] Rendering raw VFS map...")
    vfs_rgba = renderer.render_sign_map(vfs_map)
    vfs_rgb = vfs_rgba[:, :, :3]
    cv2.imwrite('vfs_raw.png', cv2.cvtColor(vfs_rgb, cv2.COLOR_RGB2BGR))
    print("  Saved: vfs_raw.png")

    # Apply coherence thresholding to VFS
    print("\n[9/9] Rendering thresholded VFS map...")
    vfs_thresholded = vfs_map.copy()
    vfs_thresholded[min_coherence < threshold] = 0
    vfs_thresh_rgba = renderer.render_sign_map(vfs_thresholded)
    vfs_thresh_rgb = vfs_thresh_rgba[:, :, :3]
    # Convert transparent pixels to white for visibility
    alpha = vfs_thresh_rgba[:, :, 3]
    white_bg = np.ones_like(vfs_thresh_rgb) * 255
    vfs_thresh_rgb = (vfs_thresh_rgb * (alpha[:, :, None] / 255.0) +
                      white_bg * (1 - alpha[:, :, None] / 255.0)).astype(np.uint8)
    cv2.imwrite('vfs_thresholded.png', cv2.cvtColor(vfs_thresh_rgb, cv2.COLOR_RGB2BGR))
    print("  Saved: vfs_thresholded.png")

    # Check discontinuities
    print("\n" + "=" * 70)
    print("Discontinuity Analysis")
    print("=" * 70)

    az_dx = np.abs(np.diff(new_azimuth, axis=1))
    az_dy = np.abs(np.diff(new_azimuth, axis=0))

    print("\nAzimuth Map (Raw):")
    print(f"  Max horizontal jump: {np.nanmax(az_dx):.2f}°")
    print(f"  Max vertical jump: {np.nanmax(az_dy):.2f}°")
    print(f"  Pixels with >30° horizontal jump: {np.sum(az_dx > 30)}")

    # Check in thresholded region
    mask_dx = (min_coherence[:, :-1] >= threshold) & (min_coherence[:, 1:] >= threshold)
    jumps_in_good = np.sum((az_dx > 30) & mask_dx)
    print(f"\nAzimuth Map (High Coherence Only):")
    print(f"  Pixels with >30° jumps: {jumps_in_good} / {np.sum(mask_dx)}")

    print("\n" + "=" * 70)
    print("✅ Visualization Complete!")
    print("=" * 70)
    print("\nGenerated files:")
    print("  • azimuth_raw.png           - Full azimuth map")
    print("  • azimuth_thresholded.png   - Coherence-thresholded azimuth")
    print("  • elevation_raw.png         - Full elevation map")
    print("  • elevation_thresholded.png - Coherence-thresholded elevation")
    print("  • vfs_raw.png               - Visual field sign (red=non-mirror, blue=mirror)")
    print("  • vfs_thresholded.png       - Coherence-thresholded VFS")
    print("  • coherence_map.png         - Signal quality map")

if __name__ == "__main__":
    try:
        visualize_sample_session()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
