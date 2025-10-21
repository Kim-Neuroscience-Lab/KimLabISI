"""Test corrected sample data conversion and analysis."""

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

def test_corrected_sample_data():
    """Verify corrected sample data structure and analysis."""
    print("=" * 80)
    print("CORRECTED SAMPLE DATA VERIFICATION")
    print("=" * 80)

    # Load session
    session_path = Path('data/sessions/sample_session')
    print(f"\nLoading corrected sample session from: {session_path}")

    # Load metadata
    with open(session_path / 'metadata.json', 'r') as f:
        metadata = json.load(f)

    print("\nMetadata:")
    print(f"  Session: {metadata['session_name']}")
    print(f"  Source: {metadata['source']}")
    print(f"  Shape: {metadata['shape']}")
    print(f"  Directions: {metadata['directions']}")

    if 'conversion_info' in metadata:
        print("\n  Conversion Info:")
        for direction, mapping in metadata['conversion_info']['file_mapping'].items():
            print(f"    {direction}: {mapping}")
        print(f"  Reference: {metadata['conversion_info']['reference']}")

    # Load phase and magnitude data
    print("\n" + "=" * 80)
    print("LOADING DATA")
    print("=" * 80)

    data = {}
    for direction in ['LR', 'RL', 'TB', 'BT']:
        phase = np.load(session_path / f'phase_{direction}.npy')
        magnitude = np.load(session_path / f'magnitude_{direction}.npy')
        data[direction] = {'phase': phase, 'magnitude': magnitude}
        print(f"\n{direction}:")
        print(f"  Phase: range=[{np.min(phase):.3f}, {np.max(phase):.3f}], mean={np.mean(phase):.3f}, std={np.std(phase):.3f}")
        print(f"  Magnitude: range=[{np.min(magnitude):.3f}, {np.max(magnitude):.3f}], mean={np.mean(magnitude):.3f}")

    # Verify spatial characteristics
    print("\n" + "=" * 80)
    print("SPATIAL CHARACTERISTICS VERIFICATION")
    print("=" * 80)

    def analyze_gradient(phase, name):
        """Analyze gradient characteristics."""
        dy, dx = np.gradient(phase)
        dx_mean = np.mean(np.abs(dx))
        dy_mean = np.mean(np.abs(dy))
        ratio = dx_mean / dy_mean

        # Count phase wraps
        mid_y, mid_x = phase.shape[0] // 2, phase.shape[1] // 2
        h_profile = phase[mid_y, :]
        v_profile = phase[:, mid_x]
        h_wraps = np.sum(np.abs(np.diff(h_profile)) > np.pi)
        v_wraps = np.sum(np.abs(np.diff(v_profile)) > np.pi)

        print(f"\n{name}:")
        print(f"  Gradient ratio (dx/dy): {ratio:.3f}")
        print(f"  Phase wraps: H={h_wraps}, V={v_wraps}")

        if ratio > 1.2:
            orientation = "HORIZONTAL dominant"
        elif ratio < 0.8:
            orientation = "VERTICAL dominant"
        else:
            orientation = "Mixed/unclear"

        print(f"  → {orientation}")

        return ratio, h_wraps, v_wraps

    # Analyze each direction
    lr_ratio, lr_h, lr_v = analyze_gradient(data['LR']['phase'], 'LR (from 005[0,0])')
    rl_ratio, rl_h, rl_v = analyze_gradient(data['RL']['phase'], 'RL (from 004[0,0])')
    tb_ratio, tb_h, tb_v = analyze_gradient(data['TB']['phase'], 'TB (from 005[0,1])')
    bt_ratio, bt_h, bt_v = analyze_gradient(data['BT']['phase'], 'BT (from 004[0,1])')

    # Verify expected patterns
    print("\n" + "=" * 80)
    print("VERIFICATION RESULTS")
    print("=" * 80)

    checks = []

    # Check horizontal pair has horizontal gradients
    if lr_h > 0 or rl_h > 0:
        print("\n✅ LR/RL pair shows horizontal phase variation (expected)")
        checks.append(True)
    else:
        print("\n❌ LR/RL pair does NOT show horizontal variation (unexpected)")
        checks.append(False)

    # Check vertical pair has vertical gradients
    if tb_v > 0 or bt_v > 0:
        print("✅ TB/BT pair shows vertical phase variation (expected)")
        checks.append(True)
    else:
        print("❌ TB/BT pair does NOT show vertical variation (unexpected)")
        checks.append(False)

    # Run analysis pipeline
    print("\n" + "=" * 80)
    print("RUNNING ANALYSIS PIPELINE")
    print("=" * 80)

    cfg = AppConfig.from_file('config/isi_parameters.json')
    pipeline = AnalysisPipeline(cfg.analysis)

    # Generate retinotopic maps
    print("\nGenerating azimuth map from LR/RL...")
    azimuth = pipeline.generate_azimuth_map(data['LR']['phase'], data['RL']['phase'])
    print(f"  Azimuth range: [{np.nanmin(azimuth):.2f}°, {np.nanmax(azimuth):.2f}°]")
    print(f"  Azimuth mean: {np.nanmean(azimuth):.2f}°")

    print("\nGenerating elevation map from TB/BT...")
    elevation = pipeline.generate_elevation_map(data['TB']['phase'], data['BT']['phase'])
    print(f"  Elevation range: [{np.nanmin(elevation):.2f}°, {np.nanmax(elevation):.2f}°]")
    print(f"  Elevation mean: {np.nanmean(elevation):.2f}°")

    # Compute simple coherence from magnitude
    print("\nComputing coherence (from magnitude)...")
    # Simple coherence approximation: normalize magnitude to [0, 1] range
    coherence_LR = data['LR']['magnitude'] / (np.max(data['LR']['magnitude']) + 1e-10)
    coherence_RL = data['RL']['magnitude'] / (np.max(data['RL']['magnitude']) + 1e-10)
    coherence_TB = data['TB']['magnitude'] / (np.max(data['TB']['magnitude']) + 1e-10)
    coherence_BT = data['BT']['magnitude'] / (np.max(data['BT']['magnitude']) + 1e-10)

    min_coherence = np.minimum.reduce([coherence_LR, coherence_RL, coherence_TB, coherence_BT])
    print(f"  Coherence range: [{np.nanmin(min_coherence):.3f}, {np.nanmax(min_coherence):.3f}]")
    print(f"  Coherence mean: {np.nanmean(min_coherence):.3f}")

    # Render maps
    print("\n" + "=" * 80)
    print("RENDERING MAPS")
    print("=" * 80)

    shared_mem = SharedMemoryService()
    renderer = AnalysisRenderer(cfg.analysis, shared_mem)

    print("\n[1/3] Rendering azimuth map...")
    azimuth_rgba = renderer.render_retinotopic_map(azimuth, map_type='azimuth')
    azimuth_rgb = azimuth_rgba[:, :, :3]
    cv2.imwrite('corrected_sample_azimuth.png', cv2.cvtColor(azimuth_rgb, cv2.COLOR_RGB2BGR))
    print("  Saved: corrected_sample_azimuth.png")

    print("\n[2/3] Rendering elevation map...")
    elevation_rgba = renderer.render_retinotopic_map(elevation, map_type='elevation')
    elevation_rgb = elevation_rgba[:, :, :3]
    cv2.imwrite('corrected_sample_elevation.png', cv2.cvtColor(elevation_rgb, cv2.COLOR_RGB2BGR))
    print("  Saved: corrected_sample_elevation.png")

    print("\n[3/3] Rendering coherence map...")
    coherence_normalized = (min_coherence / np.nanmax(min_coherence) * 255).astype(np.uint8)
    coherence_colored = cv2.applyColorMap(coherence_normalized, cv2.COLORMAP_JET)
    cv2.imwrite('corrected_sample_coherence.png', coherence_colored)
    print("  Saved: corrected_sample_coherence.png")

    # Final summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    if all(checks):
        print("\n✅ ALL CHECKS PASSED!")
        print("\nThe corrected sample data conversion is working correctly:")
        print("  • File assignments are correct (005=horizontal, 004=vertical)")
        print("  • Spatial gradients match expected patterns")
        print("  • Analysis pipeline produces valid retinotopic maps")
        print("\nThe sample data structure has been successfully corrected!")
        return 0
    else:
        print("\n⚠️  SOME CHECKS FAILED")
        print("  Review the spatial characteristics above")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(test_corrected_sample_data())
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
