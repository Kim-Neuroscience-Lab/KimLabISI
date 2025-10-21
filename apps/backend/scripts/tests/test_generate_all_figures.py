"""Generate all figures matching MATLAB generatekret.m output."""

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
    # Handle NaNs
    data_clean = data.copy()
    nan_mask = np.isnan(data_clean)
    data_clean[nan_mask] = 0

    # Apply mask if provided
    if mask is not None:
        data_clean[~mask] = np.nan

    # Normalize
    if vmin is None:
        vmin = np.nanmin(data_clean)
    if vmax is None:
        vmax = np.nanmax(data_clean)

    if vmax > vmin:
        normalized = np.clip((data_clean - vmin) / (vmax - vmin) * 255, 0, 255).astype(np.uint8)
    else:
        normalized = np.zeros_like(data_clean, dtype=np.uint8)

    # Apply colormap
    colored = cv2.applyColorMap(normalized, colormap)

    # Set NaN pixels to white
    if mask is not None:
        colored[~mask] = [255, 255, 255]
    colored[nan_mask] = [255, 255, 255]

    cv2.imwrite(filename, colored)
    print(f"  Saved: {filename}")

def overlay_with_anatomy(retinotopy_map, anatomy, ratio=0.2, vmin=None, vmax=None):
    """Create overlay of retinotopy with anatomy."""
    # Normalize anatomy to [0, 1]
    anatomy_norm = (anatomy - anatomy.min()) / (anatomy.max() - anatomy.min() + 1e-10)

    # Normalize retinotopy to [0, 1]
    if vmin is None:
        vmin = np.nanmin(retinotopy_map)
    if vmax is None:
        vmax = np.nanmax(retinotopy_map)

    ret_norm = np.clip((retinotopy_map - vmin) / (vmax - vmin + 1e-10), 0, 1)

    # Convert to HSV for retinotopy (using hue for phase)
    ret_hue = (ret_norm * 179).astype(np.uint8)
    ret_hsv = np.zeros((*retinotopy_map.shape, 3), dtype=np.uint8)
    ret_hsv[:, :, 0] = ret_hue
    ret_hsv[:, :, 1] = 255
    ret_hsv[:, :, 2] = 255
    ret_rgb = cv2.cvtColor(ret_hsv, cv2.COLOR_HSV2RGB).astype(np.float32) / 255.0

    # Convert anatomy to grayscale RGB
    anatomy_rgb = np.stack([anatomy_norm] * 3, axis=2)

    # Blend
    overlay = ratio * ret_rgb + (1 - ratio) * anatomy_rgb
    overlay = np.clip(overlay * 255, 0, 255).astype(np.uint8)

    return overlay

def main():
    print("=" * 80)
    print("COMPREHENSIVE FIGURE GENERATION")
    print("Matching MATLAB generatekret.m output")
    print("=" * 80)

    # Create output directory
    output_dir = Path('figures_output')
    output_dir.mkdir(exist_ok=True)
    print(f"\nOutput directory: {output_dir}")

    # Load session
    session_path = Path('data/sessions/sample_session')
    print(f"\nLoading sample session from: {session_path}")

    # Load metadata
    with open(session_path / 'metadata.json', 'r') as f:
        metadata = json.load(f)

    print(f"  Session: {metadata['session_name']}")
    print(f"  Shape: {metadata['shape']}")

    # Load all data
    print("\n" + "=" * 80)
    print("LOADING DATA")
    print("=" * 80)

    # Load phase and magnitude
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

    # Generate retinotopic maps
    print("\n" + "=" * 80)
    print("GENERATING RETINOTOPIC MAPS")
    print("=" * 80)

    print("\n[1/2] Computing azimuth (horizontal) map...")
    azimuth = pipeline.generate_azimuth_map(phase_LR, phase_RL)
    print(f"  Range: [{np.nanmin(azimuth):.1f}°, {np.nanmax(azimuth):.1f}°]")

    print("\n[2/2] Computing elevation (vertical) map...")
    elevation = pipeline.generate_elevation_map(phase_TB, phase_BT)
    print(f"  Range: [{np.nanmin(elevation):.1f}°, {np.nanmax(elevation):.1f}°]")

    # Compute delays (hemodynamic delay correction)
    print("\n" + "=" * 80)
    print("COMPUTING HEMODYNAMIC DELAYS")
    print("=" * 80)

    delay_hor = np.angle(np.exp(1j * phase_LR) + np.exp(1j * phase_RL))
    delay_vert = np.angle(np.exp(1j * phase_TB) + np.exp(1j * phase_BT))

    print(f"  Horizontal delay: mean={np.degrees(np.mean(delay_hor)):.1f}°")
    print(f"  Vertical delay: mean={np.degrees(np.mean(delay_vert)):.1f}°")

    # Compute response magnitudes (average of opposing directions)
    mag_hor = (mag_LR + mag_RL) / 2
    mag_vert = (mag_TB + mag_BT) / 2

    # Normalize response magnitudes
    mag_hor_norm = (mag_hor - mag_hor.min()) / (mag_hor.max() - mag_hor.min() + 1e-10)
    mag_vert_norm = (mag_vert - mag_vert.min()) / (mag_vert.max() - mag_vert.min() + 1e-10)

    print(f"  Horizontal magnitude: mean={np.mean(mag_hor):.2f}")
    print(f"  Vertical magnitude: mean={np.mean(mag_vert):.2f}")

    # Create thresholds
    thresholds = [0.05, 0.07, 0.1]

    print("\n" + "=" * 80)
    print("GENERATING FIGURES")
    print("=" * 80)

    # ============================================================================
    # ANATOMY
    # ============================================================================
    print("\n[1] Anatomy...")
    save_colormap_image(anatomy, str(output_dir / 'R43_Anatomy.png'), cv2.COLORMAP_BONE)

    # ============================================================================
    # HORIZONTAL RETINOTOPY
    # ============================================================================
    print("\n[2] Horizontal Retinotopy...")

    # Raw horizontal retinotopy
    save_colormap_image(azimuth, str(output_dir / 'R43_HorizRet_Raw.png'),
                       cv2.COLORMAP_HSV, vmin=-60, vmax=60)

    # Horizontal overlay with anatomy
    print("  Creating horizontal overlay with anatomy...")
    hor_overlay = overlay_with_anatomy(azimuth, anatomy, ratio=0.2, vmin=-60, vmax=60)
    cv2.imwrite(str(output_dir / 'R43_HorizRet_Overlay.png'), cv2.cvtColor(hor_overlay, cv2.COLOR_RGB2BGR))
    print(f"  Saved: {output_dir / 'R43_HorizRet_Overlay.png'}")

    # Horizontal response magnitude
    save_colormap_image(mag_hor, str(output_dir / 'R43_HorizRet_RawMag.png'), cv2.COLORMAP_HOT)
    save_colormap_image(mag_hor_norm, str(output_dir / 'R43_HorizRet_NormMag.png'), cv2.COLORMAP_HOT)

    # Horizontal delay
    delay_hor_deg = np.degrees(delay_hor)
    save_colormap_image(delay_hor_deg, str(output_dir / 'R43_HorizRet_Delay.png'), cv2.COLORMAP_HOT)

    # Individual angle maps for horizontal
    print("  Creating individual angle maps (horizontal)...")
    save_colormap_image(phase_LR, str(output_dir / 'R43_HorizRet_Ang0_LR.png'), cv2.COLORMAP_JET)
    save_colormap_image(phase_RL, str(output_dir / 'R43_HorizRet_Ang2_RL.png'), cv2.COLORMAP_JET)

    # Thresholded horizontal maps
    print("  Creating thresholded horizontal maps...")
    for thresh in thresholds:
        mask = mag_hor_norm >= thresh
        azimuth_thresh = azimuth.copy()
        azimuth_thresh[~mask] = np.nan
        save_colormap_image(azimuth_thresh,
                          str(output_dir / f'R43_HorizRet_Thresh_{thresh:.2f}.png'),
                          cv2.COLORMAP_HSV, vmin=-60, vmax=60, mask=mask)

    # ============================================================================
    # VERTICAL RETINOTOPY
    # ============================================================================
    print("\n[3] Vertical Retinotopy...")

    # Raw vertical retinotopy
    save_colormap_image(elevation, str(output_dir / 'R43_VertRet_Raw.png'),
                       cv2.COLORMAP_HSV, vmin=-30, vmax=30)

    # Vertical overlay with anatomy
    print("  Creating vertical overlay with anatomy...")
    vert_overlay = overlay_with_anatomy(elevation, anatomy, ratio=0.2, vmin=-30, vmax=30)
    cv2.imwrite(str(output_dir / 'R43_VertRet_Overlay.png'), cv2.cvtColor(vert_overlay, cv2.COLOR_RGB2BGR))
    print(f"  Saved: {output_dir / 'R43_VertRet_Overlay.png'}")

    # Vertical response magnitude
    save_colormap_image(mag_vert, str(output_dir / 'R43_VertRet_RawMag.png'), cv2.COLORMAP_HOT)
    save_colormap_image(mag_vert_norm, str(output_dir / 'R43_VertRet_NormMag.png'), cv2.COLORMAP_HOT)

    # Vertical delay
    delay_vert_deg = np.degrees(delay_vert)
    save_colormap_image(delay_vert_deg, str(output_dir / 'R43_VertRet_Delay.png'), cv2.COLORMAP_HOT)

    # Individual angle maps for vertical
    print("  Creating individual angle maps (vertical)...")
    save_colormap_image(phase_TB, str(output_dir / 'R43_VertRet_Ang1_TB.png'), cv2.COLORMAP_JET)
    save_colormap_image(phase_BT, str(output_dir / 'R43_VertRet_Ang3_BT.png'), cv2.COLORMAP_JET)

    # Thresholded vertical maps
    print("  Creating thresholded vertical maps...")
    for thresh in thresholds:
        mask = mag_vert_norm >= thresh
        elevation_thresh = elevation.copy()
        elevation_thresh[~mask] = np.nan
        save_colormap_image(elevation_thresh,
                          str(output_dir / f'R43_VertRet_Thresh_{thresh:.2f}.png'),
                          cv2.COLORMAP_HSV, vmin=-30, vmax=30, mask=mask)

    # ============================================================================
    # COMBINED THRESHOLDED MAPS
    # ============================================================================
    print("\n[4] Combined Thresholded Maps...")

    for thresh in thresholds:
        # Combined mask (pixels above threshold in BOTH horizontal and vertical)
        mask_hor = mag_hor_norm >= thresh
        mask_vert = mag_vert_norm >= thresh
        mask_combined = mask_hor & mask_vert

        # Exclusive mask (pixels above threshold in both)
        azimuth_combined = azimuth.copy()
        azimuth_combined[~mask_combined] = np.nan

        elevation_combined = elevation.copy()
        elevation_combined[~mask_combined] = np.nan

        save_colormap_image(azimuth_combined,
                          str(output_dir / f'R43_HorizRet_CombinedThresh_{thresh:.2f}.png'),
                          cv2.COLORMAP_HSV, vmin=-60, vmax=60, mask=mask_combined)

        save_colormap_image(elevation_combined,
                          str(output_dir / f'R43_VertRet_CombinedThresh_{thresh:.2f}.png'),
                          cv2.COLORMAP_HSV, vmin=-30, vmax=30, mask=mask_combined)

    # ============================================================================
    # COMPOSITE RESPONSE MAGNITUDE FIGURE
    # ============================================================================
    print("\n[5] Creating composite response magnitude figure...")

    # Create 2x3 grid
    h, w = mag_hor.shape
    composite = np.ones((h * 2, w * 3, 3), dtype=np.uint8) * 255

    # Row 1: Horizontal
    # [0,0] Raw horizontal magnitude
    mag_hor_img = cv2.applyColorMap(
        np.clip(mag_hor / np.percentile(mag_hor, 99) * 255, 0, 255).astype(np.uint8),
        cv2.COLORMAP_BONE
    )
    composite[0:h, 0:w] = mag_hor_img

    # [0,1] Normalized horizontal magnitude
    mag_hor_norm_img = cv2.applyColorMap((mag_hor_norm * 255).astype(np.uint8), cv2.COLORMAP_HOT)
    composite[0:h, w:2*w] = mag_hor_norm_img

    # [0,2] Horizontal map scaled by magnitude
    azimuth_rgba = renderer.render_retinotopic_map(azimuth, map_type='azimuth')
    azimuth_rgb = azimuth_rgba[:, :, :3]
    # Apply magnitude as alpha
    azimuth_scaled = (azimuth_rgb * mag_hor_norm[:, :, None]).astype(np.uint8)
    composite[0:h, 2*w:3*w] = cv2.cvtColor(azimuth_scaled, cv2.COLOR_RGB2BGR)

    # Row 2: Vertical
    # [1,0] Raw vertical magnitude
    mag_vert_img = cv2.applyColorMap(
        np.clip(mag_vert / np.percentile(mag_vert, 99) * 255, 0, 255).astype(np.uint8),
        cv2.COLORMAP_BONE
    )
    composite[h:2*h, 0:w] = mag_vert_img

    # [1,1] Normalized vertical magnitude
    mag_vert_norm_img = cv2.applyColorMap((mag_vert_norm * 255).astype(np.uint8), cv2.COLORMAP_HOT)
    composite[h:2*h, w:2*w] = mag_vert_norm_img

    # [1,2] Vertical map scaled by magnitude
    elevation_rgba = renderer.render_retinotopic_map(elevation, map_type='elevation')
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

    # Count files
    output_files = list(output_dir.glob('*.png'))
    print(f"\n✅ Generated {len(output_files)} figures in {output_dir}/")

    print("\nFigure categories:")
    print("  • Anatomy (1 figure)")
    print("  • Horizontal retinotopy (raw, overlay, magnitude, delay, angles)")
    print(f"  • Horizontal thresholded ({len(thresholds)} thresholds)")
    print("  • Vertical retinotopy (raw, overlay, magnitude, delay, angles)")
    print(f"  • Vertical thresholded ({len(thresholds)} thresholds)")
    print(f"  • Combined thresholded ({len(thresholds)} thresholds, both axes)")
    print("  • Composite response magnitude figure")

    print("\nThese figures match the output from MATLAB generatekret.m!")
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
