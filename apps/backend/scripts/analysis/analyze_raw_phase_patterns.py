"""Analyze raw phase patterns to determine stimulus directions."""

import sys
sys.path.insert(0, 'src')

import numpy as np
import cv2
import scipy.io as sio

def load_and_analyze():
    """Load and analyze raw phase patterns."""
    # Load data
    file1 = sio.loadmat('../../sample_data/R43_000_004.mat')
    file2 = sio.loadmat('../../sample_data/R43_000_005.mat')

    maps = {
        'R43_004_[0,0]': file1['f1m'][0, 0],
        'R43_004_[0,1]': file1['f1m'][0, 1],
        'R43_005_[0,0]': file2['f1m'][0, 0],
        'R43_005_[0,1]': file2['f1m'][0, 1],
    }

    print("=" * 80)
    print("RAW PHASE PATTERN ANALYSIS")
    print("=" * 80)
    print("\nAnalyzing spatial structure of phase maps WITHOUT unwrapping")
    print("to avoid artifacts from the unwrapping process.\n")

    results = {}

    for name, complex_data in maps.items():
        phase = np.angle(complex_data)
        magnitude = np.abs(complex_data)

        print(f"\n{name}:")
        print("-" * 40)

        # Basic statistics
        print(f"  Phase: mean={np.mean(phase):.3f}, std={np.std(phase):.3f}")
        print(f"  Magnitude: mean={np.mean(magnitude):.3f}, std={np.std(magnitude):.3f}")

        # Analyze phase gradients (on wrapped phase)
        dy, dx = np.gradient(phase)
        print(f"\n  Wrapped phase gradients:")
        print(f"    dx: mean(abs)={np.mean(np.abs(dx)):.4f}, std={np.std(dx):.4f}")
        print(f"    dy: mean(abs)={np.mean(np.abs(dy)):.4f}, std={np.std(dy):.4f}")
        print(f"    Ratio dx/dy: {np.mean(np.abs(dx)) / np.mean(np.abs(dy)):.3f}")

        # Analyze spatial frequency content
        # Look at the dominant direction of variation

        # Sample profiles along horizontal and vertical lines
        mid_y, mid_x = phase.shape[0] // 2, phase.shape[1] // 2

        # Horizontal profile (varies along x-axis)
        h_profile = phase[mid_y, :]
        h_diff = np.diff(h_profile)
        h_wraps = np.sum(np.abs(h_diff) > np.pi)

        # Vertical profile (varies along y-axis)
        v_profile = phase[:, mid_x]
        v_diff = np.diff(v_profile)
        v_wraps = np.sum(np.abs(v_diff) > np.pi)

        print(f"\n  Phase wrapping analysis:")
        print(f"    Horizontal (x-axis): {h_wraps} wraps")
        print(f"    Vertical (y-axis): {v_wraps} wraps")

        if h_wraps > v_wraps * 1.5:
            orientation = "HORIZONTAL variation (vertical bar stimulus)"
        elif v_wraps > h_wraps * 1.5:
            orientation = "VERTICAL variation (horizontal bar stimulus)"
        else:
            orientation = "UNCLEAR"

        print(f"    → {orientation}")

        results[name] = {
            'phase': phase,
            'magnitude': magnitude,
            'h_wraps': h_wraps,
            'v_wraps': v_wraps,
            'orientation': orientation,
            'dx_mean': np.mean(np.abs(dx)),
            'dy_mean': np.mean(np.abs(dy)),
        }

    # Create visualization
    print("\n" + "=" * 80)
    print("CREATING VISUALIZATIONS")
    print("=" * 80)

    for name, data in results.items():
        phase = data['phase']
        magnitude = data['magnitude']
        height, width = phase.shape

        # Raw phase as HSV
        phase_hue = ((phase + np.pi) / (2 * np.pi) * 179).astype(np.uint8)
        phase_hsv = np.zeros((height, width, 3), dtype=np.uint8)
        phase_hsv[:, :, 0] = phase_hue
        phase_hsv[:, :, 1] = 255

        # Use magnitude as value
        mag_norm = np.clip(magnitude / np.percentile(magnitude, 99) * 255, 0, 255).astype(np.uint8)
        phase_hsv[:, :, 2] = mag_norm

        phase_rgb = cv2.cvtColor(phase_hsv, cv2.COLOR_HSV2BGR)

        # Also create a uniform brightness version
        phase_hsv_bright = phase_hsv.copy()
        phase_hsv_bright[:, :, 2] = 255
        phase_rgb_bright = cv2.cvtColor(phase_hsv_bright, cv2.COLOR_HSV2BGR)

        # Magnitude map
        mag_colored = cv2.applyColorMap(mag_norm, cv2.COLORMAP_HOT)

        # Combine
        combined = np.hstack([phase_rgb, phase_rgb_bright, mag_colored])

        # Save
        safe_name = name.replace('[', '_').replace(']', '_').replace(',', '')
        filename = f'raw_phase_{safe_name}.png'
        cv2.imwrite(filename, combined)
        print(f"  Saved: {filename}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    # Group by presumed orientation
    horizontal_var = []
    vertical_var = []
    unclear = []

    for name, data in results.items():
        if "HORIZONTAL variation" in data['orientation']:
            horizontal_var.append(name)
        elif "VERTICAL variation" in data['orientation']:
            vertical_var.append(name)
        else:
            unclear.append(name)

    print(f"\nMaps with HORIZONTAL variation (vertical bar moving L-R or R-L):")
    for name in horizontal_var:
        print(f"  - {name}")

    print(f"\nMaps with VERTICAL variation (horizontal bar moving T-B or B-T):")
    for name in vertical_var:
        print(f"  - {name}")

    if unclear:
        print(f"\nUnclear:")
        for name in unclear:
            print(f"  - {name}")

    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)

    if len(horizontal_var) == 2 and len(vertical_var) == 2:
        print("\n✓ Found 2 horizontal and 2 vertical - this is correct!")
        print("\nMapping:")
        print(f"  Azimuth (horizontal, L-R/R-L): {horizontal_var}")
        print(f"  Altitude (vertical, T-B/B-T): {vertical_var}")

        # Check file assignment
        print("\nFile assignment check:")
        h_files = set([n.split('_')[1] for n in horizontal_var])
        v_files = set([n.split('_')[1] for n in vertical_var])

        if '004' in h_files and '005' in v_files:
            print("  ✓ R43_000_004.mat contains horizontal (azimuth)")
            print("  ✓ R43_000_005.mat contains vertical (altitude)")
            print("  → Conversion script labels are CORRECT")
        elif '005' in h_files and '004' in v_files:
            print("  ✗ R43_000_004.mat contains VERTICAL (not horizontal!)")
            print("  ✗ R43_000_005.mat contains HORIZONTAL (not vertical!)")
            print("  → Conversion script labels are SWAPPED")
        else:
            print("  ⚠ Maps are mixed across files")
    else:
        print("\n⚠ Did not find expected 2+2 distribution")
        print("  This suggests the data may be organized differently than expected")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    try:
        load_and_analyze()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
