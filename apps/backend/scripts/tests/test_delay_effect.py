"""Test the effect of delay correction on retinotopy range."""

import sys
sys.path.insert(0, 'src')

import h5py
import numpy as np

def test_delay_effect():
    """Compare retinotopy with and without delay correction."""
    print("=" * 70)
    print("Testing Delay Correction Effect")
    print("=" * 70)

    # Load sample session data
    h5_path = 'data/sessions/sample_session/analysis_results/analysis_results.h5'

    with h5py.File(h5_path, 'r') as f:
        phase_LR = f['phase_maps/LR'][:]
        phase_RL = f['phase_maps/RL'][:]

    print(f"\nInput phases:")
    print(f"  LR: [{np.min(phase_LR):.3f}, {np.max(phase_LR):.3f}] rad")
    print(f"  RL: [{np.min(phase_RL):.3f}, {np.max(phase_RL):.3f}] rad")

    # Method 1: Simple subtraction (no delay correction)
    print("\n" + "=" * 70)
    print("Method 1: Simple Subtraction (No Delay)")
    print("=" * 70)
    center_simple = (phase_LR - phase_RL) / 2
    azimuth_simple = center_simple * (60.0 / np.pi)
    print(f"  Center phase range: [{np.min(center_simple):.3f}, {np.max(center_simple):.3f}] rad")
    print(f"  Azimuth range: [{np.min(azimuth_simple):.2f}, {np.max(azimuth_simple):.2f}]°")

    # Method 2: With delay correction
    print("\n" + "=" * 70)
    print("Method 2: With Delay Correction")
    print("=" * 70)

    # Compute delay
    forward_complex = np.exp(1j * phase_LR)
    reverse_complex = np.exp(1j * phase_RL)
    delay_complex = forward_complex + reverse_complex
    delay = np.angle(delay_complex)

    print(f"  Computed delay range: [{np.min(delay):.3f}, {np.max(delay):.3f}] rad")
    print(f"  Delay mean: {np.mean(delay):.3f}, std: {np.std(delay):.3f}")

    # Subtract delay and wrap
    forward_corrected = phase_LR - delay
    reverse_corrected = phase_RL - delay
    forward_wrapped = np.angle(np.exp(1j * forward_corrected))
    reverse_wrapped = np.angle(np.exp(1j * reverse_corrected))

    print(f"  After delay subtraction:")
    print(f"    Forward wrapped: [{np.min(forward_wrapped):.3f}, {np.max(forward_wrapped):.3f}] rad")
    print(f"    Reverse wrapped: [{np.min(reverse_wrapped):.3f}, {np.max(reverse_wrapped):.3f}] rad")

    center_delay = (forward_wrapped - reverse_wrapped) / 2
    azimuth_delay = center_delay * (60.0 / np.pi)

    print(f"  Center phase range: [{np.min(center_delay):.3f}, {np.max(center_delay):.3f}] rad")
    print(f"  Azimuth range: [{np.min(azimuth_delay):.2f}, {np.max(azimuth_delay):.2f}]°")

    # Check if phases are approximately opposite
    print("\n" + "=" * 70)
    print("Phase Relationship Analysis")
    print("=" * 70)

    # For retinotopy, forward and reverse should be approximately opposite
    # i.e., LR ≈ -RL (modulo 2π wrapping)
    phase_diff = phase_LR - phase_RL
    phase_sum = phase_LR + phase_RL

    print(f"  LR - RL range: [{np.min(phase_diff):.3f}, {np.max(phase_diff):.3f}] rad")
    print(f"  LR + RL range: [{np.min(phase_sum):.3f}, {np.max(phase_sum):.3f}] rad")
    print(f"  Mean LR + RL: {np.mean(phase_sum):.3f} (should be ~0 if opposite)")

    # Sample a few pixels to see the relationship
    print("\n  Sample pixels (center region):")
    h, w = phase_LR.shape
    for r in [h//4, h//2, 3*h//4]:
        for c in [w//4, w//2, 3*w//4]:
            lr = phase_LR[r, c]
            rl = phase_RL[r, c]
            print(f"    [{r},{c}]: LR={lr:6.3f}, RL={rl:6.3f}, sum={lr+rl:6.3f}, diff={lr-rl:6.3f}")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    test_delay_effect()
