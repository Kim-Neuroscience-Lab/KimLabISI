"""
Complete Stimulus Generation Test Suite

Single comprehensive test for stimulus generation with optional video output.
Tests the refactored stimulus calculator with proper Marshel et al. parameters.

Video Output (when enabled):
- LR_drifting_bar.mp4: Left-to-right bar movement
- RL_drifting_bar.mp4: Right-to-left bar movement
- TB_drifting_bar.mp4: Top-to-bottom bar movement
- BT_drifting_bar.mp4: Bottom-to-top bar movement
"""

import pytest
import numpy as np
from pathlib import Path
import logging
import argparse
import sys

from src.domain.services.stimulus_calculator import StimulusCalculator, StimulusDirection

# Configure logging for better test output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Video output settings
VIDEO_OUTPUT_DIR = Path("/Users/Adam/KimLabISI/backend/stimulus_test_videos")



def _video_generation_available() -> bool:
    """Check if video generation dependencies are available"""
    try:
        import cv2
        return True
    except ImportError:
        return False


def _should_generate_videos() -> bool:
    """Check if video generation was requested via command line"""
    return "--generate-videos" in sys.argv


class TestStimulusGenerationComplete:
    """Complete stimulus generation test suite"""

    @pytest.fixture
    def marshel_spatial_config(self):
        """Spatial configuration with correct screen dimensions and parameters"""
        return {
            "monitor_distance_cm": 10.0,  # Distance from mouse
            "monitor_angle_degrees": 20.0,  # Vertical angle
            "monitor_height_degrees": 30.0,  # Horizontal angle
            "monitor_roll_degrees": 0.0,
            "screen_width_cm": 60.96,   # Correct screen width
            "screen_height_cm": 36.195,  # Correct screen height
            "screen_width_pixels": 2560,  # Correct resolution width
            "screen_height_pixels": 1440,  # Correct resolution height
        }

    @pytest.fixture
    def marshel_stimulus_params(self):
        """Stimulus parameters with correct specifications"""
        return {
            "bar_width_degrees": 20.0,  # Bar width of 20 deg
            "drift_speed_degrees_per_sec": 9.0,  # Bar speed 9 deg per sec
            "checkerboard_size_degrees": 25.0,  # Checker size of 25 deg
            "flicker_frequency_hz": 6.0,  # Strobe rate 6 hz
            "frame_rate_fps": 60.0,  # 60 fps
            "contrast": 0.5,
            "background_luminance": 0.5,
        }

    @pytest.fixture
    def stimulus_calculator(self):
        """Create stimulus calculator instance"""
        return StimulusCalculator()

    def test_basic_pattern_generation(self, stimulus_calculator, marshel_spatial_config, marshel_stimulus_params):
        """Test basic pattern generation for all directions"""
        logger.info("Testing basic pattern generation for all directions...")

        directions = [
            StimulusDirection.LEFT_TO_RIGHT,
            StimulusDirection.RIGHT_TO_LEFT,
            StimulusDirection.TOP_TO_BOTTOM,
            StimulusDirection.BOTTOM_TO_TOP,
        ]

        for direction in directions:
            logger.info(f"Testing direction: {direction.value}")

            # Generate pattern at center position
            pattern = stimulus_calculator.generate_drifting_bar_pattern(
                bar_position_degrees=0.0,
                direction=direction,
                spatial_config=marshel_spatial_config,
                stimulus_params=marshel_stimulus_params,
                flicker_phase=0.0,
            )

            # Validate pattern properties - should match screen resolution
            expected_shape = (marshel_spatial_config["screen_height_pixels"], marshel_spatial_config["screen_width_pixels"])
            assert pattern.pattern.shape == expected_shape, f"Wrong shape: {pattern.pattern.shape}"
            assert 0.0 <= pattern.pattern.min() <= 1.0, f"Pattern values out of range: {pattern.pattern.min()}"
            assert 0.0 <= pattern.pattern.max() <= 1.0, f"Pattern values out of range: {pattern.pattern.max()}"
            assert pattern.bar_position == 0.0, f"Wrong bar position: {pattern.bar_position}"
            assert pattern.direction == direction, f"Wrong direction: {pattern.direction}"

            # Check that pattern contains bar (should not be all background)
            unique_values = np.unique(pattern.pattern)
            assert len(unique_values) > 1, f"Pattern should contain checkerboard values, got {unique_values}"

            logger.info(f"  ✓ Pattern shape: {pattern.pattern.shape}")
            logger.info(f"  ✓ Pattern range: {pattern.pattern.min():.3f} - {pattern.pattern.max():.3f}")
            logger.info(f"  ✓ Unique values: {len(unique_values)}")

        logger.info("✅ Basic pattern generation test passed")

    def test_counter_phase_flicker(self, stimulus_calculator, marshel_spatial_config, marshel_stimulus_params):
        """Test counter-phase checkerboard flicker"""
        logger.info("Testing counter-phase checkerboard flicker...")

        # Generate patterns with different flicker phases
        pattern_0 = stimulus_calculator.generate_drifting_bar_pattern(
            bar_position_degrees=0.0,
            direction=StimulusDirection.LEFT_TO_RIGHT,
            spatial_config=marshel_spatial_config,
            stimulus_params=marshel_stimulus_params,
            flicker_phase=0.0,
        )

        pattern_180 = stimulus_calculator.generate_drifting_bar_pattern(
            bar_position_degrees=0.0,
            direction=StimulusDirection.LEFT_TO_RIGHT,
            spatial_config=marshel_spatial_config,
            stimulus_params=marshel_stimulus_params,
            flicker_phase=0.6,  # > 0.5 should flip checkerboard
        )

        # Patterns should be different due to counter-phase
        assert not np.array_equal(pattern_0.pattern, pattern_180.pattern), \
            "Counter-phase patterns should be different"

        # Check that the difference is systematic (not just noise)
        difference_ratio = np.mean(pattern_0.pattern != pattern_180.pattern)
        assert difference_ratio > 0.05, f"Counter-phase should affect significant portion of pattern: {difference_ratio}"

        logger.info(f"  ✓ Phase 0.0 range: {pattern_0.pattern.min():.3f} - {pattern_0.pattern.max():.3f}")
        logger.info(f"  ✓ Phase 0.6 range: {pattern_180.pattern.min():.3f} - {pattern_180.pattern.max():.3f}")
        logger.info(f"  ✓ Difference ratio: {difference_ratio:.3f}")
        logger.info("✅ Counter-phase flicker test passed")

    def test_bar_position_sweep(self, stimulus_calculator, marshel_spatial_config):
        """Test bar position calculations for sweep"""
        logger.info("Testing bar position sweep calculations...")

        directions = list(StimulusDirection)

        for direction in directions:
            positions = stimulus_calculator.calculate_bar_positions_for_sweep(
                direction=direction,
                spatial_config=marshel_spatial_config,
                num_positions=20,
                bar_width_degrees=20.0,  # Use default bar width for testing
            )

            # Check positions are reasonable
            assert len(positions) == 20, f"Should get 20 positions, got {len(positions)}"
            assert positions[0] != positions[-1], "Start and end positions should be different"

            # Check field of view is reasonable for 52cm screen at 10cm distance
            # Range is extended by bar width (20°) so bar starts and ends off-screen
            fov_range = abs(positions[-1] - positions[0])
            expected_fov = 2 * np.degrees(np.arctan(52.0 / (2 * 10.0))) + 20.0  # ~158 degrees + bar width
            assert 140 < fov_range < 180, f"Extended range (with bar width) seems wrong: {fov_range}° (expected ~{expected_fov:.0f}°)"

            logger.info(f"  ✓ {direction.value}: {positions[0]:.1f}° to {positions[-1]:.1f}° ({fov_range:.1f}° range)")

        logger.info("✅ Bar position sweep test passed")

    def test_pattern_consistency(self, stimulus_calculator, marshel_spatial_config, marshel_stimulus_params):
        """Test that patterns are consistent across multiple generations"""
        logger.info("Testing pattern consistency...")

        # Generate same pattern multiple times
        patterns = []
        for i in range(3):
            pattern = stimulus_calculator.generate_drifting_bar_pattern(
                bar_position_degrees=10.0,
                direction=StimulusDirection.LEFT_TO_RIGHT,
                spatial_config=marshel_spatial_config,
                stimulus_params=marshel_stimulus_params,
                flicker_phase=0.25,
            )
            patterns.append(pattern.pattern)

        # All patterns should be identical
        for i in range(1, len(patterns)):
            assert np.array_equal(patterns[0], patterns[i]), \
                f"Pattern {i} differs from pattern 0 - patterns should be consistent"

        logger.info("  ✓ Multiple generations produce identical patterns")
        logger.info("✅ Pattern consistency test passed")

    @pytest.mark.parametrize("direction", list(StimulusDirection))
    def test_individual_directions(self, direction, stimulus_calculator, marshel_spatial_config, marshel_stimulus_params):
        """Test each direction individually"""
        logger.info(f"Testing individual direction: {direction.value}")

        # Test multiple positions for this direction
        positions = [-20.0, -10.0, 0.0, 10.0, 20.0]

        patterns = []
        for pos in positions:
            pattern = stimulus_calculator.generate_drifting_bar_pattern(
                bar_position_degrees=pos,
                direction=direction,
                spatial_config=marshel_spatial_config,
                stimulus_params=marshel_stimulus_params,
                flicker_phase=0.0,
            )
            patterns.append(pattern)

        # Patterns at different positions should be different
        for i in range(len(patterns) - 1):
            assert not np.array_equal(patterns[i].pattern, patterns[i + 1].pattern), \
                f"Patterns at positions {positions[i]}° and {positions[i + 1]}° should be different"

        logger.info(f"  ✓ {direction.value} generates different patterns at different positions")

    @pytest.mark.skipif(not _video_generation_available(), reason="OpenCV not available")
    def test_generate_verification_videos(self, stimulus_calculator, marshel_spatial_config, marshel_stimulus_params):
        """Generate verification videos for all directions (optional)"""

        # Only run if explicitly requested
        if not _should_generate_videos():
            pytest.skip("Video generation not requested (use --generate-videos flag)")

        logger.info("Generating verification videos for visual inspection...")

        # Create output directory
        VIDEO_OUTPUT_DIR.mkdir(exist_ok=True)

        directions = [
            (StimulusDirection.LEFT_TO_RIGHT, "LR_drifting_bar.mp4"),
            (StimulusDirection.RIGHT_TO_LEFT, "RL_drifting_bar.mp4"),
            (StimulusDirection.TOP_TO_BOTTOM, "TB_drifting_bar.mp4"),
            (StimulusDirection.BOTTOM_TO_TOP, "BT_drifting_bar.mp4"),
        ]

        for direction, filename in directions:
            logger.info(f"Generating video for {direction.value}...")

            video_path = VIDEO_OUTPUT_DIR / filename
            _generate_stimulus_video(
                direction, video_path, stimulus_calculator,
                marshel_spatial_config, marshel_stimulus_params
            )

            # Verify video was created
            assert video_path.exists(), f"Video not created: {video_path}"
            assert video_path.stat().st_size > 0, f"Video file is empty: {video_path}"

            logger.info(f"  ✓ Created: {video_path}")

        logger.info("✅ All verification videos generated successfully")
        logger.info(f"Videos saved to: {VIDEO_OUTPUT_DIR}")


def _generate_stimulus_video(direction, output_path, calculator, spatial_config, stimulus_params):
    """Generate a short stimulus video for the given direction"""
    try:
        import cv2
    except ImportError:
        pytest.skip("OpenCV not available for video generation")

    # Use domain service to calculate bar positions for complete sweep
    # Domain service will determine the number of frames needed based on drift speed
    bar_width_degrees = stimulus_params["bar_width_degrees"]
    positions = calculator.calculate_bar_positions_for_sweep(
        direction=direction,
        spatial_config=spatial_config,
        bar_width_degrees=bar_width_degrees,
        stimulus_params=stimulus_params,
    )

    num_frames = len(positions)
    fps = int(stimulus_params.get("frame_rate_fps", 60))

    # Set up downsampling for faster test video generation
    downsample_factor = 4
    full_height = spatial_config["screen_height_pixels"]
    full_width = spatial_config["screen_width_pixels"]

    # Use downsampled dimensions for video (4x faster generation)
    height = full_height // downsample_factor
    width = full_width // downsample_factor

    # Use downsampled spatial config for faster pattern generation
    test_spatial_config = spatial_config.copy()
    test_spatial_config["screen_height_pixels"] = height
    test_spatial_config["screen_width_pixels"] = width

    # Set up video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video_writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height), isColor=False)


    frames_written = 0
    try:
        # Generate frames
        for frame_idx, bar_position in enumerate(positions):
            # Calculate flicker phase for counter-phase checkerboard
            flicker_frequency_hz = stimulus_params["flicker_frequency_hz"]
            time_sec = frame_idx / fps
            flicker_phase = (time_sec * flicker_frequency_hz) % 1.0

            # Generate pattern
            pattern = calculator.generate_drifting_bar_pattern(
                bar_position_degrees=bar_position,
                direction=direction,
                spatial_config=test_spatial_config,
                stimulus_params=stimulus_params,
                flicker_phase=flicker_phase,
            )

            # Convert to 8-bit grayscale
            frame_8bit = (pattern.pattern * 255).astype(np.uint8)

            # Write frame (already generated at downsampled resolution for speed)
            video_writer.write(frame_8bit)
            frames_written += 1

        logger.info(f"    Generated {frames_written} frames successfully")
        logger.info(f"    Video resolution: {width}x{height} (downsampled {downsample_factor}x from {full_width}x{full_height})")
        assert frames_written > 0, "Should generate at least one frame"

    finally:
        video_writer.release()


if __name__ == "__main__":
    # Allow running as script with video generation
    parser = argparse.ArgumentParser(description='Run stimulus generation tests')
    parser.add_argument('--generate-videos', action='store_true',
                       help='Generate verification videos')
    args = parser.parse_args()

    # Run tests
    if args.generate_videos:
        logger.info("Running tests with video generation enabled...")
        pytest.main([__file__ + "::TestStimulusGenerationComplete::test_generate_verification_videos", "-v", "-s"])
    else:
        logger.info("Running standard tests (no video generation)...")
        pytest.main([__file__, "-v"])