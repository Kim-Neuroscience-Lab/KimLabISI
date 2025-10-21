"""Test that linear artifacts are eliminated with the no-unwrap approach."""

import sys
sys.path.insert(0, 'src')

import numpy as np
from config import AppConfig
from analysis.pipeline import AnalysisPipeline

def test_bidirectional_no_artifacts():
    """Verify bidirectional analysis doesn't produce linear artifacts."""
    print("=" * 70)
    print("Testing Bidirectional Analysis - No Unwrap Approach")
    print("=" * 70)

    # Load config
    cfg = AppConfig.from_file('config/isi_parameters.json')
    pipeline = AnalysisPipeline(cfg.analysis)

    # Create synthetic phase maps with smooth progression
    height, width = 100, 100

    # Forward phase: smooth gradient from -π to π
    forward_phase = np.linspace(-np.pi, np.pi, width)
    forward_phase = np.tile(forward_phase, (height, 1)).astype(np.float32)

    # Reverse phase: opposite gradient
    reverse_phase = -forward_phase

    print(f"\nInput phase maps:")
    print(f"  Forward phase range: [{np.min(forward_phase):.2f}, {np.max(forward_phase):.2f}] rad")
    print(f"  Reverse phase range: [{np.min(reverse_phase):.2f}, {np.max(reverse_phase):.2f}] rad")

    # Run bidirectional analysis
    print(f"\nRunning bidirectional analysis...")
    center_map = pipeline.bidirectional_analysis(forward_phase, reverse_phase, unwrap_axis=1)

    print(f"\nOutput center map:")
    print(f"  Range: [{np.min(center_map):.2f}, {np.max(center_map):.2f}] rad")
    print(f"  Mean: {np.mean(center_map):.2f} rad")
    print(f"  Std: {np.std(center_map):.2f} rad")

    # Check for artifacts
    # Compute gradient to detect sharp transitions (artifacts show as large gradients)
    grad_x = np.diff(center_map, axis=1)
    grad_y = np.diff(center_map, axis=0)

    max_grad_x = np.max(np.abs(grad_x))
    max_grad_y = np.max(np.abs(grad_y))

    print(f"\nGradient analysis (artifact detection):")
    print(f"  Max horizontal gradient: {max_grad_x:.3f} rad/pixel")
    print(f"  Max vertical gradient: {max_grad_y:.3f} rad/pixel")

    # For smooth phase maps, gradients should be small
    # Large gradients (> 1.0) indicate artifacts
    artifact_threshold = 1.0

    if max_grad_x < artifact_threshold and max_grad_y < artifact_threshold:
        print(f"\n✅ NO LINEAR ARTIFACTS DETECTED")
        print(f"   Gradients are below threshold ({artifact_threshold} rad/pixel)")
        return True
    else:
        print(f"\n❌ LINEAR ARTIFACTS DETECTED")
        print(f"   Gradients exceed threshold ({artifact_threshold} rad/pixel)")
        return False

if __name__ == "__main__":
    try:
        success = test_bidirectional_no_artifacts()
        print("\n" + "=" * 70)
        if success:
            print("✅ TEST PASSED: Linear artifacts eliminated!")
        else:
            print("❌ TEST FAILED: Linear artifacts still present!")
        print("=" * 70)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
