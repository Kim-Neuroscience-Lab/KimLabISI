"""Verify phase relationships with corrected pairing."""

import sys
sys.path.insert(0, 'src')

import numpy as np
import cv2
import scipy.io as sio

def main():
    print("=" * 80)
    print("VERIFICATION: Corrected Direction Pairing")
    print("=" * 80)
    print("\nTesting hypothesis:")
    print("  - R43_004_[0,0] and R43_005_[0,0] are OPPOSING horizontals")
    print("  - R43_004_[0,1] and R43_005_[0,1] are OPPOSING verticals")
    print()

    # Load data
    file1 = sio.loadmat('../../sample_data/R43_000_004.mat')
    file2 = sio.loadmat('../../sample_data/R43_000_005.mat')

    # Extract complex data
    h1_complex = file1['f1m'][0, 0]  # First horizontal
    v1_complex = file1['f1m'][0, 1]  # First vertical
    h2_complex = file2['f1m'][0, 0]  # Second horizontal (opposing)
    v2_complex = file2['f1m'][0, 1]  # Second vertical (opposing)

    # Extract phases
    h1_phase = np.angle(h1_complex)
    v1_phase = np.angle(v1_complex)
    h2_phase = np.angle(h2_complex)
    v2_phase = np.angle(v2_complex)

    print("\n" + "=" * 80)
    print("PHASE RELATIONSHIP ANALYSIS")
    print("=" * 80)

    # Test horizontal pair
    print("\n[1/2] Horizontal Pair: R43_004_[0,0] vs R43_005_[0,0]")
    print("-" * 40)
    h_diff = np.angle(np.exp(1j * h1_phase) * np.exp(-1j * h2_phase))
    h_mean = np.mean(h_diff)
    h_std = np.std(h_diff)

    print(f"  Phase difference:")
    print(f"    Mean: {h_mean:.3f} rad ({np.degrees(h_mean):.1f}°)")
    print(f"    Std: {h_std:.3f} rad")
    print(f"    Expected for opposing: ~π rad (±180°)")

    if np.abs(np.abs(h_mean) - np.pi) < 0.3:
        print(f"  ✅ CONSISTENT with opposing directions!")
        h_opposing = True
    else:
        print(f"  ❌ NOT consistent with opposing directions")
        h_opposing = False

    # Test vertical pair
    print("\n[2/2] Vertical Pair: R43_004_[0,1] vs R43_005_[0,1]")
    print("-" * 40)
    v_diff = np.angle(np.exp(1j * v1_phase) * np.exp(-1j * v2_phase))
    v_mean = np.mean(v_diff)
    v_std = np.std(v_diff)

    print(f"  Phase difference:")
    print(f"    Mean: {v_mean:.3f} rad ({np.degrees(v_mean):.1f}°)")
    print(f"    Std: {v_std:.3f} rad")
    print(f"    Expected for opposing: ~π rad (±180°)")

    if np.abs(np.abs(v_mean) - np.pi) < 0.3:
        print(f"  ✅ CONSISTENT with opposing directions!")
        v_opposing = True
    else:
        print(f"  ❌ NOT consistent with opposing directions")
        v_opposing = False

    # Compare with OLD (wrong) pairing
    print("\n" + "=" * 80)
    print("COMPARISON WITH OLD (WRONG) PAIRING")
    print("=" * 80)

    print("\nOLD pairing assumed:")
    print("  - R43_004_[0,0] vs R43_004_[0,1] (horizontal pair - WRONG!)")
    print("  - R43_005_[0,0] vs R43_005_[0,1] (vertical pair - WRONG!)")

    # Test OLD horizontal "pair" (actually h1 vs v1)
    print("\n[OLD] R43_004_[0,0] vs R43_004_[0,1]:")
    old_h_diff = np.angle(np.exp(1j * h1_phase) * np.exp(-1j * v1_phase))
    old_h_mean = np.mean(old_h_diff)
    print(f"  Phase difference: {old_h_mean:.3f} rad ({np.degrees(old_h_mean):.1f}°)")
    print(f"  → These are orthogonal stimuli, NOT opposing!")

    # Test OLD vertical "pair" (actually h2 vs v2)
    print("\n[OLD] R43_005_[0,0] vs R43_005_[0,1]:")
    old_v_diff = np.angle(np.exp(1j * h2_phase) * np.exp(-1j * v2_phase))
    old_v_mean = np.mean(old_v_diff)
    print(f"  Phase difference: {old_v_mean:.3f} rad ({np.degrees(old_v_mean):.1f}°)")
    print(f"  → These are orthogonal stimuli, NOT opposing!")

    # Generate test retinotopic maps with CORRECT pairing
    print("\n" + "=" * 80)
    print("GENERATING RETINOTOPIC MAPS (Corrected Pairing)")
    print("=" * 80)

    # Compute hemodynamic delay for horizontal
    h_delay = np.angle(np.exp(1j * h1_phase) + np.exp(1j * h2_phase))
    print(f"\nHorizontal delay: mean={np.mean(h_delay):.3f} rad")

    # Compute azimuth (horizontal retinotopy)
    azimuth = 0.5 * (np.angle(np.exp(1j * (h1_phase - h_delay))) -
                     np.angle(np.exp(1j * (h2_phase - h_delay))))
    azimuth_deg = np.degrees(azimuth)

    print(f"  Azimuth range: [{np.min(azimuth_deg):.1f}°, {np.max(azimuth_deg):.1f}°]")
    print(f"  Azimuth mean: {np.mean(azimuth_deg):.1f}°")

    # Compute hemodynamic delay for vertical
    v_delay = np.angle(np.exp(1j * v1_phase) + np.exp(1j * v2_phase))
    print(f"\nVertical delay: mean={np.mean(v_delay):.3f} rad")

    # Compute elevation (vertical retinotopy)
    elevation = 0.5 * (np.angle(np.exp(1j * (v1_phase - v_delay))) -
                       np.angle(np.exp(1j * (v2_phase - v_delay))))
    elevation_deg = np.degrees(elevation)

    print(f"  Elevation range: [{np.min(elevation_deg):.1f}°, {np.max(elevation_deg):.1f}°]")
    print(f"  Elevation mean: {np.mean(elevation_deg):.1f}°")

    # Save visualizations
    print("\n" + "=" * 80)
    print("SAVING VISUALIZATIONS")
    print("=" * 80)

    # Azimuth map
    azimuth_norm = ((azimuth + np.pi) / (2 * np.pi) * 179).astype(np.uint8)
    azimuth_hsv = np.zeros((azimuth.shape[0], azimuth.shape[1], 3), dtype=np.uint8)
    azimuth_hsv[:, :, 0] = azimuth_norm
    azimuth_hsv[:, :, 1] = 255
    azimuth_hsv[:, :, 2] = 255
    azimuth_rgb = cv2.cvtColor(azimuth_hsv, cv2.COLOR_HSV2BGR)
    cv2.imwrite('corrected_azimuth_map.png', azimuth_rgb)
    print("  Saved: corrected_azimuth_map.png")

    # Elevation map
    elevation_norm = ((elevation + np.pi) / (2 * np.pi) * 179).astype(np.uint8)
    elevation_hsv = np.zeros((elevation.shape[0], elevation.shape[1], 3), dtype=np.uint8)
    elevation_hsv[:, :, 0] = elevation_norm
    elevation_hsv[:, :, 1] = 255
    elevation_hsv[:, :, 2] = 255
    elevation_rgb = cv2.cvtColor(elevation_hsv, cv2.COLOR_HSV2BGR)
    cv2.imwrite('corrected_elevation_map.png', elevation_rgb)
    print("  Saved: corrected_elevation_map.png")

    # Summary
    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)

    if h_opposing and v_opposing:
        print("\n✅ CORRECTED PAIRING IS CORRECT!")
        print("\nThe data organization is:")
        print("  R43_000_004.mat:")
        print("    [0,0] = Horizontal direction 1 (LR or RL)")
        print("    [0,1] = Vertical direction 1 (TB or BT)")
        print("  R43_000_005.mat:")
        print("    [0,0] = Horizontal direction 2 (RL or LR) - opposite of 004[0,0]")
        print("    [0,1] = Vertical direction 2 (BT or TB) - opposite of 004[0,1]")
        print("\n📝 The conversion script needs to be updated to reflect this!")
    else:
        print("\n⚠ Unexpected result - further investigation needed")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
