"""Analyze phase map characteristics to determine stimulus directions."""

import sys
sys.path.insert(0, 'src')

import numpy as np
import cv2
import scipy.io as sio
from pathlib import Path

def load_matlab_data():
    """Load raw MATLAB data."""
    file1 = sio.loadmat('../../sample_data/R43_000_004.mat')
    file2 = sio.loadmat('../../sample_data/R43_000_005.mat')

    # Extract complex arrays
    f1 = file1['f1m']
    f2 = file2['f1m']

    # Get phase maps
    maps = {
        'R43_004_[0,0]': np.angle(f1[0, 0]),
        'R43_004_[0,1]': np.angle(f1[0, 1]),
        'R43_005_[0,0]': np.angle(f2[0, 0]),
        'R43_005_[0,1]': np.angle(f2[0, 1]),
    }

    return maps

def analyze_gradient_direction(phase_map):
    """Compute gradient characteristics to determine sweep direction."""
    # Compute gradients
    dy, dx = np.gradient(phase_map)

    # Unwrap phases for better gradient computation
    phase_unwrapped = np.unwrap(np.unwrap(phase_map, axis=0), axis=1)
    dy_unwrapped, dx_unwrapped = np.gradient(phase_unwrapped)

    # Compute gradient magnitudes and angles
    grad_mag = np.sqrt(dx**2 + dy**2)
    grad_mag_unwrapped = np.sqrt(dx_unwrapped**2 + dy_unwrapped**2)
    grad_angle = np.arctan2(dy, dx)
    grad_angle_unwrapped = np.arctan2(dy_unwrapped, dx_unwrapped)

    # Statistics
    stats = {
        'dx_mean': np.mean(np.abs(dx)),
        'dy_mean': np.mean(np.abs(dy)),
        'dx_std': np.std(dx),
        'dy_std': np.std(dy),
        'dx_unwrapped_mean': np.mean(np.abs(dx_unwrapped)),
        'dy_unwrapped_mean': np.mean(np.abs(dy_unwrapped)),
        'grad_mag_mean': np.mean(grad_mag),
        'grad_mag_unwrapped_mean': np.mean(grad_mag_unwrapped),
        'grad_angle_mean': np.mean(grad_angle),
        'horizontal_dominant': np.mean(np.abs(dx)) > np.mean(np.abs(dy)),
        'vertical_dominant': np.mean(np.abs(dy)) > np.mean(np.abs(dx)),
    }

    return stats, (dx, dy, dx_unwrapped, dy_unwrapped, grad_angle)

def analyze_phase_range(phase_map):
    """Analyze the phase value distribution."""
    return {
        'min': np.min(phase_map),
        'max': np.max(phase_map),
        'mean': np.mean(phase_map),
        'std': np.std(phase_map),
        'range': np.max(phase_map) - np.min(phase_map),
    }

def visualize_all_maps(maps):
    """Create comprehensive visualization of all phase maps."""
    # Create individual images for each map and its analysis
    for idx, (name, phase_map) in enumerate(maps.items()):
        height, width = phase_map.shape

        # Raw phase (HSV colormap)
        phase_normalized = ((phase_map + np.pi) / (2 * np.pi) * 179).astype(np.uint8)
        raw_hsv = np.zeros((height, width, 3), dtype=np.uint8)
        raw_hsv[:, :, 0] = phase_normalized
        raw_hsv[:, :, 1] = 255
        raw_hsv[:, :, 2] = 255
        raw_rgb = cv2.cvtColor(raw_hsv, cv2.COLOR_HSV2BGR)

        # Unwrapped phase
        phase_unwrapped = np.unwrap(np.unwrap(phase_map, axis=0), axis=1)
        unwrap_norm = ((phase_unwrapped - np.min(phase_unwrapped)) /
                      (np.max(phase_unwrapped) - np.min(phase_unwrapped)) * 255).astype(np.uint8)
        unwrap_colored = cv2.applyColorMap(unwrap_norm, cv2.COLORMAP_JET)

        # Gradients
        dy, dx = np.gradient(phase_unwrapped)

        # Normalize gradients to [-1, 1] then to [0, 255]
        dx_norm = np.clip((dx + 0.1) / 0.2, 0, 1)
        dx_colored = (dx_norm * 255).astype(np.uint8)
        dx_colored = cv2.applyColorMap(dx_colored, cv2.COLORMAP_JET)

        dy_norm = np.clip((dy + 0.1) / 0.2, 0, 1)
        dy_colored = (dy_norm * 255).astype(np.uint8)
        dy_colored = cv2.applyColorMap(dy_colored, cv2.COLORMAP_JET)

        # Stack images horizontally
        combined = np.hstack([raw_rgb, unwrap_colored, dx_colored, dy_colored])

        # Save
        safe_name = name.replace('[', '_').replace(']', '_').replace(',', '')
        filename = f'phase_analysis_{safe_name}.png'
        cv2.imwrite(filename, combined)
        print(f"  Saved: {filename}")

def main():
    print("=" * 80)
    print("PHASE MAP DIRECTION ANALYSIS")
    print("=" * 80)
    print("\nGoal: Determine which phase map corresponds to which stimulus direction")
    print("by analyzing spatial gradient characteristics.\n")

    # Load data
    print("Loading MATLAB data...")
    maps = load_matlab_data()
    print(f"Loaded {len(maps)} phase maps\n")

    # Visualize all maps
    print("Creating comprehensive visualization...")
    visualize_all_maps(maps)

    # Analyze each map
    print("\n" + "=" * 80)
    print("GRADIENT ANALYSIS")
    print("=" * 80)

    results = {}
    for name, phase_map in maps.items():
        print(f"\n{name}:")
        print("-" * 40)

        # Phase range analysis
        phase_stats = analyze_phase_range(phase_map)
        print(f"  Phase range: [{phase_stats['min']:.3f}, {phase_stats['max']:.3f}] rad")
        print(f"  Phase std: {phase_stats['std']:.3f} rad")

        # Gradient analysis
        grad_stats, grad_data = analyze_gradient_direction(phase_map)
        print(f"\n  Wrapped gradients:")
        print(f"    |dx| mean: {grad_stats['dx_mean']:.6f}")
        print(f"    |dy| mean: {grad_stats['dy_mean']:.6f}")
        print(f"    Ratio dx/dy: {grad_stats['dx_mean'] / grad_stats['dy_mean']:.3f}")

        print(f"\n  Unwrapped gradients:")
        print(f"    |dx| mean: {grad_stats['dx_unwrapped_mean']:.6f}")
        print(f"    |dy| mean: {grad_stats['dy_unwrapped_mean']:.6f}")
        print(f"    Ratio dx/dy: {grad_stats['dx_unwrapped_mean'] / grad_stats['dy_unwrapped_mean']:.3f}")

        if grad_stats['horizontal_dominant']:
            print(f"  → HORIZONTAL gradient dominant (Left-Right or Right-Left)")
        else:
            print(f"  → VERTICAL gradient dominant (Top-Bottom or Bottom-Top)")

        results[name] = {
            'phase_stats': phase_stats,
            'grad_stats': grad_stats,
            'grad_data': grad_data
        }

    # Determine pairings
    print("\n" + "=" * 80)
    print("DIRECTION CLASSIFICATION")
    print("=" * 80)

    horizontal_maps = []
    vertical_maps = []

    for name, data in results.items():
        ratio = data['grad_stats']['dx_unwrapped_mean'] / data['grad_stats']['dy_unwrapped_mean']
        if ratio > 1.2:  # Significantly more horizontal gradient
            horizontal_maps.append(name)
            print(f"\n{name}: HORIZONTAL (azimuth) - dx/dy = {ratio:.2f}")
        elif ratio < 0.8:  # Significantly more vertical gradient
            vertical_maps.append(name)
            print(f"\n{name}: VERTICAL (altitude) - dx/dy = {ratio:.2f}")
        else:
            print(f"\n{name}: AMBIGUOUS - dx/dy = {ratio:.2f}")

    # Check for opposing directions
    print("\n" + "=" * 80)
    print("OPPOSING DIRECTION ANALYSIS")
    print("=" * 80)

    if len(horizontal_maps) == 2:
        print(f"\nHorizontal pair: {horizontal_maps[0]} & {horizontal_maps[1]}")
        map1 = maps[horizontal_maps[0]]
        map2 = maps[horizontal_maps[1]]

        # Check phase relationship
        phase_diff = np.angle(np.exp(1j * map1) * np.exp(-1j * map2))
        mean_diff = np.mean(phase_diff)
        print(f"  Mean phase difference: {mean_diff:.3f} rad ({np.degrees(mean_diff):.1f}°)")
        print(f"  Expected for opposing: ~π rad (180°)")

        if np.abs(np.abs(mean_diff) - np.pi) < 0.5:
            print(f"  ✓ Phase relationship consistent with opposing directions")
        else:
            print(f"  ⚠ Phase relationship NOT consistent with opposing directions")

    if len(vertical_maps) == 2:
        print(f"\nVertical pair: {vertical_maps[0]} & {vertical_maps[1]}")
        map1 = maps[vertical_maps[0]]
        map2 = maps[vertical_maps[1]]

        phase_diff = np.angle(np.exp(1j * map1) * np.exp(-1j * map2))
        mean_diff = np.mean(phase_diff)
        print(f"  Mean phase difference: {mean_diff:.3f} rad ({np.degrees(mean_diff):.1f}°)")
        print(f"  Expected for opposing: ~π rad (180°)")

        if np.abs(np.abs(mean_diff) - np.pi) < 0.5:
            print(f"  ✓ Phase relationship consistent with opposing directions")
        else:
            print(f"  ⚠ Phase relationship NOT consistent with opposing directions")

    # Summary
    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)

    if len(horizontal_maps) == 2 and len(vertical_maps) == 2:
        print("\n✓ Successfully classified all 4 maps into horizontal and vertical pairs")
        print(f"\nHorizontal (Azimuth): {horizontal_maps}")
        print(f"Vertical (Altitude): {vertical_maps}")
        print("\nTo determine specific direction (LR vs RL, TB vs BT):")
        print("  - Need anatomical reference or expected retinotopic organization")
        print("  - Or analyze sign of gradient (increasing vs decreasing)")
    else:
        print("\n⚠ Could not cleanly separate into horizontal and vertical pairs")
        print("  - Gradients may be too similar")
        print("  - Or maps may already be delay-corrected")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
