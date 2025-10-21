"""Simple test for VFS post-smoothing fix (no visualization)."""

import numpy as np
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import AnalysisConfig
from analysis.pipeline import AnalysisPipeline

def test_vfs_smoothing():
    """Test VFS smoothing with synthetic gradient data."""
    print("=" * 70)
    print("Testing VFS Post-Smoothing Fix")
    print("=" * 70)

    # Create synthetic gradient data with noise
    np.random.seed(42)
    size = 128

    # Create smooth gradient fields with noise
    noise_level = 0.1
    d_azimuth_dx = np.ones((size, size)) + noise_level * np.random.randn(size, size)
    d_azimuth_dy = noise_level * np.random.randn(size, size)
    d_elevation_dx = noise_level * np.random.randn(size, size)
    d_elevation_dy = np.ones((size, size)) + noise_level * np.random.randn(size, size)

    # Create pipeline
    config = AnalysisConfig(
        coherence_threshold=0.3,
        ring_size_mm=2.0,
        phase_filter_sigma=2.0,
        smoothing_sigma=3.0,
        gradient_window_size=3,
        magnitude_threshold=0.3,
        response_threshold_percent=20,
        vfs_threshold_sd=2.0,
        area_min_size_mm2=0.1
    )

    pipeline = AnalysisPipeline(config)

    # Test 1: VFS without smoothing (sigma=0)
    print("\n[Test 1] Computing VFS without post-smoothing...")
    gradients = {
        'd_azimuth_dx': d_azimuth_dx,
        'd_azimuth_dy': d_azimuth_dy,
        'd_elevation_dx': d_elevation_dx,
        'd_elevation_dy': d_elevation_dy
    }

    vfs_raw = pipeline.calculate_visual_field_sign(gradients, vfs_smooth_sigma=0)

    # Test 2: VFS with smoothing (sigma=3)
    print("\n[Test 2] Computing VFS with post-smoothing (sigma=3)...")
    vfs_smoothed = pipeline.calculate_visual_field_sign(gradients, vfs_smooth_sigma=3.0)

    # Test 3: VFS with default smoothing (should be sigma=3)
    print("\n[Test 3] Computing VFS with default post-smoothing...")
    vfs_default = pipeline.calculate_visual_field_sign(gradients)

    # Verify smoothing was applied
    print("\n" + "=" * 70)
    print("Verification Results:")
    print("=" * 70)

    # Check that smoothed version has less variance (smoother)
    raw_std = np.std(vfs_raw)
    smoothed_std = np.std(vfs_smoothed)
    default_std = np.std(vfs_default)

    print(f"\nStandard deviation comparison:")
    print(f"  Raw (sigma=0):       {raw_std:.4f}")
    print(f"  Smoothed (sigma=3):  {smoothed_std:.4f}")
    print(f"  Default:             {default_std:.4f}")

    passed = 0
    failed = 0

    if smoothed_std < raw_std:
        print("✅ PASS: Smoothed VFS has lower variance (smoother)")
        passed += 1
    else:
        print("❌ FAIL: Smoothed VFS should have lower variance")
        failed += 1

    # Check that default matches smoothed
    if np.allclose(vfs_default, vfs_smoothed):
        print("✅ PASS: Default smoothing matches sigma=3")
        passed += 1
    else:
        print("⚠️  WARNING: Default smoothing doesn't match sigma=3")
        failed += 1

    # Test FFT-based smoothing helpers
    print("\n" + "=" * 70)
    print("Testing FFT-based Gaussian smoothing helpers:")
    print("=" * 70)

    # Create test data
    test_data = np.random.randn(64, 64)

    # Test kernel creation
    kernel = pipeline._create_gaussian_kernel(test_data.shape, sigma=3.0)
    print(f"\nGaussian kernel created: shape={kernel.shape}")
    print(f"  Kernel center value: {kernel[32, 32]:.6f}")
    print(f"  Kernel corner value: {kernel[0, 0]:.6f}")
    print(f"  Kernel sum: {np.sum(kernel):.6f}")

    if kernel[32, 32] > kernel[0, 0]:
        print("✅ PASS: Kernel has maximum at center")
        passed += 1
    else:
        print("❌ FAIL: Kernel should have maximum at center")
        failed += 1

    # Test smoothing
    smoothed_test = pipeline._apply_fft_gaussian_smoothing(test_data, sigma=3.0)
    print(f"\nFFT smoothing applied:")
    print(f"  Input std:  {np.std(test_data):.6f}")
    print(f"  Output std: {np.std(smoothed_test):.6f}")

    if np.std(smoothed_test) < np.std(test_data):
        print("✅ PASS: FFT smoothing reduces variance")
        passed += 1
    else:
        print("❌ FAIL: FFT smoothing should reduce variance")
        failed += 1

    # Print summary
    print("\n" + "=" * 70)
    print("Test Summary:")
    print("=" * 70)
    print(f"  Passed: {passed}/4")
    print(f"  Failed: {failed}/4")

    if failed == 0:
        print("\n✅ All tests PASSED! VFS post-smoothing is working correctly.")
    else:
        print(f"\n❌ {failed} test(s) FAILED!")

    print("=" * 70)

    return passed == 4

if __name__ == "__main__":
    success = test_vfs_smoothing()
    sys.exit(0 if success else 1)
