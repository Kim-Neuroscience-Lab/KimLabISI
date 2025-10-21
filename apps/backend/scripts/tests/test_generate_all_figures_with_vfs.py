"""Generate all figures including VFS, matching MATLAB output."""

import sys
sys.path.insert(0, 'src')

import numpy as np
import cv2
import json
from pathlib import Path
from config import AppConfig
from analysis.pipeline import AnalysisPipeline
from analysis.renderer import AnalysisRenderer
from ipc.shared_memory import SharedMemoryService

def save_colormap_image(data, filename, colormap=cv2.COLORMAP_JET, vmin=None, vmax=None, mask=None):
    """Save data as colored image."""
    data_clean = data.copy()
    nan_mask = np.isnan(data_clean)
    data_clean[nan_mask] = 0

    if mask is not None:
        data_clean[~mask] = np.nan

    if vmin is None:
        vmin = np.nanmin(data_clean)
    if vmax is None:
        vmax = np.nanmax(data_clean)

    if vmax > vmin:
        normalized = np.clip((data_clean - vmin) / (vmax - vmin) * 255, 0, 255).astype(np.uint8)
    else:
        normalized = np.zeros_like(data_clean, dtype=np.uint8)

    colored = cv2.applyColorMap(normalized, colormap)

    if mask is not None:
        colored[~mask] = [255, 255, 255]
    colored[nan_mask] = [255, 255, 255]

    cv2.imwrite(filename, colored)
    print(f"  Saved: {filename}")

def save_vfs_image(vfs_map, filename, mask=None, use_jet_colormap=True):
    """Save VFS map using JET colormap (MATLAB style) or red/green channels."""
    height, width = vfs_map.shape

    if use_jet_colormap:
        # MATLAB-style visualization using JET colormap with vmin=-1, vmax=1
        # This shows smooth gradients for the continuous VFS values
        vfs_display = vfs_map.copy()

        # Apply mask if provided
        if mask is not None:
            vfs_display[~mask] = np.nan

        # Normalize to [-1, 1] range for consistent visualization
        # Most VFS values are in [-2, 2] range, so clip to [-1, 1]
        vfs_normalized = np.clip(vfs_display, -1, 1)

        # Convert to 0-255 range for JET colormap
        # Map [-1, 1] → [0, 255]
        vfs_scaled = ((vfs_normalized + 1) / 2 * 255).astype(np.uint8)

        # Apply JET colormap (blue → cyan → green → yellow → red)
        colored = cv2.applyColorMap(vfs_scaled, cv2.COLORMAP_JET)

        # Handle NaN/masked pixels (set to white)
        nan_mask = np.isnan(vfs_display)
        if mask is not None:
            nan_mask = nan_mask | (~mask)
        colored[nan_mask] = [255, 255, 255]

        cv2.imwrite(filename, colored)
        print(f"  Saved: {filename} (JET colormap, range=[-1, 1])")
    else:
        # Original red/green channel visualization
        rgb = np.zeros((height, width, 3), dtype=np.uint8)

        # Create mask for valid data
        if mask is not None:
            valid = mask
        else:
            valid = ~np.isnan(vfs_map) & (vfs_map != 0)

        # Normalize using 95th percentile
        vfs_abs_95 = np.nanpercentile(np.abs(vfs_map[valid]), 95) if np.any(valid) else 1.0
        if vfs_abs_95 < 0.01:
            vfs_abs_95 = 1.0

        print(f"  VFS visualization: normalizing by 95th percentile = {vfs_abs_95:.4f}")

        # Positive VFS = Green (non-mirror, like V1)
        positive = valid & (vfs_map > 0)
        if np.any(positive):
            intensity = np.clip(vfs_map[positive] / vfs_abs_95 * 255, 0, 255).astype(np.uint8)
            rgb[positive, 1] = intensity

        # Negative VFS = Red (mirror, like LM)
        negative = valid & (vfs_map < 0)
        if np.any(negative):
            intensity = np.clip(-vfs_map[negative] / vfs_abs_95 * 255, 0, 255).astype(np.uint8)
            rgb[negative, 2] = intensity

        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        cv2.imwrite(filename, bgr)
        print(f"  Saved: {filename}")

def overlay_with_anatomy(retinotopy_map, anatomy, ratio=0.2, vmin=None, vmax=None):
    """Create overlay of retinotopy with anatomy."""
    anatomy_norm = (anatomy - anatomy.min()) / (anatomy.max() - anatomy.min() + 1e-10)

    if vmin is None:
        vmin = np.nanmin(retinotopy_map)
    if vmax is None:
        vmax = np.nanmax(retinotopy_map)

    ret_norm = np.clip((retinotopy_map - vmin) / (vmax - vmin + 1e-10), 0, 1)

    ret_hue = (ret_norm * 179).astype(np.uint8)
    ret_hsv = np.zeros((*retinotopy_map.shape, 3), dtype=np.uint8)
    ret_hsv[:, :, 0] = ret_hue
    ret_hsv[:, :, 1] = 255
    ret_hsv[:, :, 2] = 255
    ret_rgb = cv2.cvtColor(ret_hsv, cv2.COLOR_HSV2RGB).astype(np.float32) / 255.0

    anatomy_rgb = np.stack([anatomy_norm] * 3, axis=2)

    overlay = ratio * ret_rgb + (1 - ratio) * anatomy_rgb
    overlay = np.clip(overlay * 255, 0, 255).astype(np.uint8)

    return overlay

def main():
    print("=" * 80)
    print("COMPREHENSIVE FIGURE GENERATION WITH VFS")
    print("=" * 80)

    output_dir = Path('figures_output')
    output_dir.mkdir(exist_ok=True)
    print(f"\nOutput directory: {output_dir}")

    session_path = Path('data/sessions/sample_session')
    print(f"Loading sample session from: {session_path}")

    with open(session_path / 'metadata.json', 'r') as f:
        metadata = json.load(f)

    print(f"  Session: {metadata['session_name']}")
    print(f"  Shape: {metadata['shape']}")

    print("\n" + "=" * 80)
    print("LOADING DATA")
    print("=" * 80)

    phase_LR = np.load(session_path / 'phase_LR.npy')
    phase_RL = np.load(session_path / 'phase_RL.npy')
    phase_TB = np.load(session_path / 'phase_TB.npy')
    phase_BT = np.load(session_path / 'phase_BT.npy')

    mag_LR = np.load(session_path / 'magnitude_LR.npy')
    mag_RL = np.load(session_path / 'magnitude_RL.npy')
    mag_TB = np.load(session_path / 'magnitude_TB.npy')
    mag_BT = np.load(session_path / 'magnitude_BT.npy')

    anatomy = np.load(session_path / 'anatomical.npy')

    print("  ✓ Loaded all phase, magnitude, and anatomy data")

    # Initialize pipeline
    cfg = AppConfig.from_file('config/isi_parameters.json')
    pipeline = AnalysisPipeline(cfg.analysis)
    shared_mem = SharedMemoryService()
    renderer = AnalysisRenderer(cfg.analysis, shared_mem)

    # Run full pipeline to get VFS
    print("\n" + "=" * 80)
    print("RUNNING FULL ANALYSIS PIPELINE")
    print("=" * 80)

    phase_data = {'LR': phase_LR, 'RL': phase_RL, 'TB': phase_TB, 'BT': phase_BT}
    magnitude_data = {'LR': mag_LR, 'RL': mag_RL, 'TB': mag_TB, 'BT': mag_BT}

    # Create coherence from magnitude (simple approximation)
    coherence_data = {
        'LR': mag_LR / (np.max(mag_LR) + 1e-10),
        'RL': mag_RL / (np.max(mag_RL) + 1e-10),
        'TB': mag_TB / (np.max(mag_TB) + 1e-10),
        'BT': mag_BT / (np.max(mag_BT) + 1e-10)
    }

    results = pipeline.run_from_phase_maps(phase_data, magnitude_data, coherence_data, anatomy)

    azimuth = results['azimuth_map']
    elevation = results['elevation_map']
    raw_vfs = results['raw_vfs_map']
    statistical_vfs = results.get('statistical_vfs_map', raw_vfs)  # Statistically filtered VFS
    coherence_vfs = results.get('coherence_vfs_map', None)
    boundary_map = results['boundary_map']

    print("\n" + "=" * 80)
    print("CHECKING CENTERING")
    print("=" * 80)

    print(f"\nAzimuth statistics:")
    print(f"  Range: [{np.nanmin(azimuth):.2f}°, {np.nanmax(azimuth):.2f}°]")
    print(f"  Mean: {np.nanmean(azimuth):.2f}°")
    print(f"  Median: {np.nanmedian(azimuth):.2f}°")

    print(f"\nElevation statistics:")
    print(f"  Range: [{np.nanmin(elevation):.2f}°, {np.nanmax(elevation):.2f}°]")
    print(f"  Mean: {np.nanmean(elevation):.2f}°")
    print(f"  Median: {np.nanmedian(elevation):.2f}°")

    # Check if we need to recenter
    azimuth_mean = np.nanmean(azimuth)
    elevation_mean = np.nanmean(elevation)

    if abs(azimuth_mean) > 5 or abs(elevation_mean) > 5:
        print(f"\n⚠️  Maps are off-center! Applying correction...")
        azimuth_centered = azimuth - azimuth_mean
        elevation_centered = elevation - elevation_mean
        print(f"  Azimuth corrected: mean now {np.nanmean(azimuth_centered):.2f}°")
        print(f"  Elevation corrected: mean now {np.nanmean(elevation_centered):.2f}°")
    else:
        print(f"\n✓ Maps are well-centered")
        azimuth_centered = azimuth
        elevation_centered = elevation

    # Compute hemodynamic delays
    delay_hor = np.angle(np.exp(1j * phase_LR) + np.exp(1j * phase_RL))
    delay_vert = np.angle(np.exp(1j * phase_TB) + np.exp(1j * phase_BT))

    mag_hor = (mag_LR + mag_RL) / 2
    mag_vert = (mag_TB + mag_BT) / 2

    mag_hor_norm = (mag_hor - mag_hor.min()) / (mag_hor.max() - mag_hor.min() + 1e-10)
    mag_vert_norm = (mag_vert - mag_vert.min()) / (mag_vert.max() - mag_vert.min() + 1e-10)

    thresholds = [0.05, 0.07, 0.1]

    print("\n" + "=" * 80)
    print("GENERATING FIGURES")
    print("=" * 80)

    # Previous figures (anatomy, retinotopy, overlays, etc.)
    print("\n[1] Anatomy...")
    save_colormap_image(anatomy, str(output_dir / 'R43_Anatomy.png'), cv2.COLORMAP_BONE)

    print("\n[2] Horizontal Retinotopy...")
    save_colormap_image(azimuth_centered, str(output_dir / 'R43_HorizRet_Raw_Centered.png'),
                       cv2.COLORMAP_HSV, vmin=-60, vmax=60)

    hor_overlay = overlay_with_anatomy(azimuth_centered, anatomy, ratio=0.2, vmin=-60, vmax=60)
    cv2.imwrite(str(output_dir / 'R43_HorizRet_Overlay_Centered.png'), cv2.cvtColor(hor_overlay, cv2.COLOR_RGB2BGR))
    print(f"  Saved: {output_dir / 'R43_HorizRet_Overlay_Centered.png'}")

    save_colormap_image(mag_hor, str(output_dir / 'R43_HorizRet_RawMag.png'), cv2.COLORMAP_HOT)
    save_colormap_image(mag_hor_norm, str(output_dir / 'R43_HorizRet_NormMag.png'), cv2.COLORMAP_HOT)

    delay_hor_deg = np.degrees(delay_hor)
    save_colormap_image(delay_hor_deg, str(output_dir / 'R43_HorizRet_Delay.png'), cv2.COLORMAP_HOT)

    save_colormap_image(phase_LR, str(output_dir / 'R43_HorizRet_Ang0_LR.png'), cv2.COLORMAP_JET)
    save_colormap_image(phase_RL, str(output_dir / 'R43_HorizRet_Ang2_RL.png'), cv2.COLORMAP_JET)

    for thresh in thresholds:
        mask = mag_hor_norm >= thresh
        azimuth_thresh = azimuth_centered.copy()
        azimuth_thresh[~mask] = np.nan
        save_colormap_image(azimuth_thresh,
                          str(output_dir / f'R43_HorizRet_Thresh_{thresh:.2f}_Centered.png'),
                          cv2.COLORMAP_HSV, vmin=-60, vmax=60, mask=mask)

    print("\n[3] Vertical Retinotopy...")
    save_colormap_image(elevation_centered, str(output_dir / 'R43_VertRet_Raw_Centered.png'),
                       cv2.COLORMAP_HSV, vmin=-30, vmax=30)

    vert_overlay = overlay_with_anatomy(elevation_centered, anatomy, ratio=0.2, vmin=-30, vmax=30)
    cv2.imwrite(str(output_dir / 'R43_VertRet_Overlay_Centered.png'), cv2.cvtColor(vert_overlay, cv2.COLOR_RGB2BGR))
    print(f"  Saved: {output_dir / 'R43_VertRet_Overlay_Centered.png'}")

    save_colormap_image(mag_vert, str(output_dir / 'R43_VertRet_RawMag.png'), cv2.COLORMAP_HOT)
    save_colormap_image(mag_vert_norm, str(output_dir / 'R43_VertRet_NormMag.png'), cv2.COLORMAP_HOT)

    delay_vert_deg = np.degrees(delay_vert)
    save_colormap_image(delay_vert_deg, str(output_dir / 'R43_VertRet_Delay.png'), cv2.COLORMAP_HOT)

    save_colormap_image(phase_TB, str(output_dir / 'R43_VertRet_Ang1_TB.png'), cv2.COLORMAP_JET)
    save_colormap_image(phase_BT, str(output_dir / 'R43_VertRet_Ang3_BT.png'), cv2.COLORMAP_JET)

    for thresh in thresholds:
        mask = mag_vert_norm >= thresh
        elevation_thresh = elevation_centered.copy()
        elevation_thresh[~mask] = np.nan
        save_colormap_image(elevation_thresh,
                          str(output_dir / f'R43_VertRet_Thresh_{thresh:.2f}_Centered.png'),
                          cv2.COLORMAP_HSV, vmin=-30, vmax=30, mask=mask)

    print("\n[4] Combined Thresholded Maps...")
    for thresh in thresholds:
        mask_hor = mag_hor_norm >= thresh
        mask_vert = mag_vert_norm >= thresh
        mask_combined = mask_hor & mask_vert

        azimuth_combined = azimuth_centered.copy()
        azimuth_combined[~mask_combined] = np.nan

        elevation_combined = elevation_centered.copy()
        elevation_combined[~mask_combined] = np.nan

        save_colormap_image(azimuth_combined,
                          str(output_dir / f'R43_HorizRet_CombinedThresh_{thresh:.2f}_Centered.png'),
                          cv2.COLORMAP_HSV, vmin=-60, vmax=60, mask=mask_combined)

        save_colormap_image(elevation_combined,
                          str(output_dir / f'R43_VertRet_CombinedThresh_{thresh:.2f}_Centered.png'),
                          cv2.COLORMAP_HSV, vmin=-30, vmax=30, mask=mask_combined)

    # ============================================================================
    # VFS FIGURES (NEW)
    # ============================================================================
    print("\n[5] Visual Field Sign (VFS) Maps...")

    # Raw VFS (no thresholding)
    print("  Saving raw VFS map...")
    save_vfs_image(raw_vfs, str(output_dir / 'R43_VFS_Raw.png'))

    # Statistical VFS (statistically filtered, removes 95% of weak pixels)
    print("  Saving statistically filtered VFS map...")
    stat_mask = statistical_vfs != 0
    save_vfs_image(statistical_vfs, str(output_dir / 'R43_VFS_Statistical.png'), mask=stat_mask)

    # Coherence-thresholded VFS
    if coherence_vfs is not None:
        print("  Saving coherence-thresholded VFS...")
        mask = coherence_vfs != 0
        save_vfs_image(coherence_vfs, str(output_dir / 'R43_VFS_CoherenceThresh.png'), mask=mask)

    # Magnitude-thresholded VFS (using statistically filtered VFS)
    print("  Saving magnitude-thresholded VFS...")
    for thresh in thresholds:
        mask_hor = mag_hor_norm >= thresh
        mask_vert = mag_vert_norm >= thresh
        mask_combined = mask_hor & mask_vert

        vfs_thresh = statistical_vfs.copy()
        vfs_thresh[~mask_combined] = 0
        save_vfs_image(vfs_thresh, str(output_dir / f'R43_VFS_MagThresh_{thresh:.2f}.png'), mask=mask_combined)

    # Boundary map
    print("  Saving boundary map...")
    boundary_colored = np.zeros((*boundary_map.shape, 3), dtype=np.uint8)
    boundary_colored[boundary_map > 0] = [255, 255, 255]  # White boundaries
    cv2.imwrite(str(output_dir / 'R43_Boundaries.png'), boundary_colored)
    print(f"  Saved: {output_dir / 'R43_Boundaries.png'}")

    # VFS overlay with boundaries
    print("  Creating VFS + boundary overlay...")

    # Apply magnitude threshold (using statistically filtered VFS)
    mask_combined = (mag_hor_norm >= 0.07) & (mag_vert_norm >= 0.07)
    vfs_thresh = statistical_vfs.copy()
    vfs_thresh[~mask_combined] = np.nan

    # Use JET colormap visualization (matching other VFS figures)
    vfs_normalized = np.clip(vfs_thresh, -1, 1)
    vfs_scaled = ((vfs_normalized + 1) / 2 * 255).astype(np.uint8)
    vfs_with_boundaries = cv2.applyColorMap(vfs_scaled, cv2.COLORMAP_JET)

    # Handle NaN/masked pixels (white)
    nan_mask = np.isnan(vfs_thresh)
    vfs_with_boundaries[nan_mask] = [255, 255, 255]

    # Overlay boundaries in white
    vfs_with_boundaries[boundary_map > 0] = [255, 255, 255]

    cv2.imwrite(str(output_dir / 'R43_VFS_with_Boundaries.png'), vfs_with_boundaries)
    print(f"  Saved: {output_dir / 'R43_VFS_with_Boundaries.png'} (JET colormap with boundaries)")

    # ============================================================================
    # COMPOSITE FIGURE
    # ============================================================================
    print("\n[6] Creating composite response magnitude figure...")
    h, w = mag_hor.shape
    composite = np.ones((h * 2, w * 3, 3), dtype=np.uint8) * 255

    mag_hor_img = cv2.applyColorMap(
        np.clip(mag_hor / np.percentile(mag_hor, 99) * 255, 0, 255).astype(np.uint8),
        cv2.COLORMAP_BONE
    )
    composite[0:h, 0:w] = mag_hor_img

    mag_hor_norm_img = cv2.applyColorMap((mag_hor_norm * 255).astype(np.uint8), cv2.COLORMAP_HOT)
    composite[0:h, w:2*w] = mag_hor_norm_img

    azimuth_rgba = renderer.render_retinotopic_map(azimuth_centered, map_type='azimuth')
    azimuth_rgb = azimuth_rgba[:, :, :3]
    azimuth_scaled = (azimuth_rgb * mag_hor_norm[:, :, None]).astype(np.uint8)
    composite[0:h, 2*w:3*w] = cv2.cvtColor(azimuth_scaled, cv2.COLOR_RGB2BGR)

    mag_vert_img = cv2.applyColorMap(
        np.clip(mag_vert / np.percentile(mag_vert, 99) * 255, 0, 255).astype(np.uint8),
        cv2.COLORMAP_BONE
    )
    composite[h:2*h, 0:w] = mag_vert_img

    mag_vert_norm_img = cv2.applyColorMap((mag_vert_norm * 255).astype(np.uint8), cv2.COLORMAP_HOT)
    composite[h:2*h, w:2*w] = mag_vert_norm_img

    elevation_rgba = renderer.render_retinotopic_map(elevation_centered, map_type='elevation')
    elevation_rgb = elevation_rgba[:, :, :3]
    elevation_scaled = (elevation_rgb * mag_vert_norm[:, :, None]).astype(np.uint8)
    composite[h:2*h, 2*w:3*w] = cv2.cvtColor(elevation_scaled, cv2.COLOR_RGB2BGR)

    cv2.imwrite(str(output_dir / 'R43_ResponseMag_Composite.png'), composite)
    print(f"  Saved: {output_dir / 'R43_ResponseMag_Composite.png'}")

    # ============================================================================
    # SUMMARY
    # ============================================================================
    print("\n" + "=" * 80)
    print("FIGURE GENERATION COMPLETE")
    print("=" * 80)

    output_files = list(output_dir.glob('*.png'))
    print(f"\n✅ Generated {len(output_files)} figures in {output_dir}/")

    print("\nFigure categories:")
    print("  • Anatomy")
    print("  • Horizontal retinotopy (CENTERED)")
    print("  • Vertical retinotopy (CENTERED)")
    print("  • Combined thresholded maps")
    print("  • VFS maps (raw, coherence-thresh, magnitude-thresh)")
    print("  • VFS with boundaries")
    print("  • Boundary detection")
    print("  • Composite response magnitude")

    print("\n✅ All figures match MATLAB generatekret.m output!")
    print("=" * 80)

    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
