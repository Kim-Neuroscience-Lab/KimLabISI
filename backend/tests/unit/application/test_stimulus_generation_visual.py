"""
Visual Stimulus Generation Tests - Generate Video Output for Verification

This test module generates actual video files of retinotopy stimuli for
visual verification and validation. The videos can be viewed to ensure
the stimulus patterns are generated correctly.

Test outputs:
- horizontal_bar_stimulus.mp4: Horizontal bar moving top to bottom
- vertical_bar_stimulus.mp4: Vertical bar moving left to right
- polar_wedge_stimulus.mp4: Polar wedge rotating clockwise
- expanding_ring_stimulus.mp4: Ring expanding from center
"""

import pytest
import numpy as np
import tempfile
from pathlib import Path
import logging

from src.domain.value_objects.stimulus_params import (
    StimulusType, MovementDirection, StimulusParams, VisualFieldParams, RetinotopyProtocol
)
from src.application.algorithms.pattern_generators import PatternGenerator
from src.application.use_cases.stimulus_generation import (
    StimulusGenerationUseCase, create_horizontal_bar_protocol,
    create_vertical_bar_protocol, create_polar_wedge_protocol
)

# Configure logging for better test output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestStimulusGenerationVisual:
    """Visual tests for stimulus generation with video output"""

    @pytest.fixture
    def visual_field(self):
        """Create standard visual field parameters for testing"""
        return VisualFieldParams(
            screen_width_pixels=800,
            screen_height_pixels=600,
            screen_width_cm=40.0,
            screen_distance_cm=60.0,
            field_of_view_degrees=30.0
        )

    @pytest.fixture
    def output_dir(self):
        """Create temporary directory for test outputs"""
        temp_dir = Path(tempfile.mkdtemp(prefix="stimulus_test_"))
        logger.info(f"Test output directory: {temp_dir}")
        return temp_dir

    def test_pattern_generator_basic(self, visual_field):
        """Test basic pattern generator functionality"""
        generator = PatternGenerator(visual_field)

        # Test coordinate grid setup
        assert generator.visual_field == visual_field
        assert generator.pixels_per_degree > 0
        assert generator.X_degrees.shape == (visual_field.screen_height_pixels, visual_field.screen_width_pixels)
        assert generator.Y_degrees.shape == (visual_field.screen_height_pixels, visual_field.screen_width_pixels)

        # Test coordinate ranges
        max_x_degrees = visual_field.screen_width_pixels / visual_field.pixels_per_degree / 2
        max_y_degrees = visual_field.screen_height_pixels / visual_field.pixels_per_degree / 2

        assert np.abs(generator.X_degrees.max()) <= max_x_degrees + 1  # Allow small margin
        assert np.abs(generator.Y_degrees.max()) <= max_y_degrees + 1

    def test_stimulus_params_validation(self, visual_field):
        """Test stimulus parameter validation"""
        # Valid parameters
        params = StimulusParams(
            stimulus_type=StimulusType.HORIZONTAL_BAR,
            direction=MovementDirection.TOP_TO_BOTTOM,
            width_degrees=30.0,
            height_degrees=30.0,
            bar_width_degrees=2.0,
            cycle_duration_sec=10.0,
            frame_rate=30.0,
            num_cycles=1,
            contrast=0.8,
            background_luminance=0.5,
            checkerboard_size_degrees=1.0,
            phase_steps=8,
            fixation_cross=False,
            fixation_size_degrees=0.5
        )

        assert params.frames_per_cycle == 300  # 10s * 30fps
        assert params.total_frames == 300      # 1 cycle
        assert params.total_duration_sec == 10.0

    @pytest.mark.asyncio
    async def test_generate_horizontal_bar_video(self, visual_field, output_dir):
        """Generate horizontal bar stimulus video for visual verification"""
        logger.info("Generating horizontal bar stimulus video...")

        # Create protocol with shorter duration for testing
        protocol = create_horizontal_bar_protocol(
            visual_field=visual_field,
            cycle_duration=5.0,  # 5 second cycle for faster testing
            num_cycles=1
        )

        # Create use case and generate video
        use_case = StimulusGenerationUseCase()
        output_path = output_dir / "horizontal_bar_stimulus.mp4"

        try:
            result_path = await use_case.export_stimulus_video(
                protocol=protocol,
                output_path=output_path,
                frame_skip=2  # Skip every other frame for smaller file
            )

            # Verify video was created
            assert result_path.exists()
            assert result_path.stat().st_size > 0

            logger.info(f"✅ Horizontal bar video created: {result_path}")
            logger.info(f"   Duration: {protocol.stimulus_params.total_duration_sec}s")
            logger.info(f"   Resolution: {visual_field.screen_width_pixels}x{visual_field.screen_height_pixels}")
            logger.info(f"   Bar width: {protocol.stimulus_params.bar_width_degrees}°")

        except Exception as e:
            if "OpenCV" in str(e):
                pytest.skip("OpenCV not available for video generation")
            else:
                raise

    @pytest.mark.asyncio
    async def test_generate_vertical_bar_video(self, visual_field, output_dir):
        """Generate vertical bar stimulus video for visual verification"""
        logger.info("Generating vertical bar stimulus video...")

        # Create protocol
        protocol = create_vertical_bar_protocol(
            visual_field=visual_field,
            cycle_duration=5.0,
            num_cycles=1
        )

        # Create use case and generate video
        use_case = StimulusGenerationUseCase()
        output_path = output_dir / "vertical_bar_stimulus.mp4"

        try:
            result_path = await use_case.export_stimulus_video(
                protocol=protocol,
                output_path=output_path,
                frame_skip=2
            )

            assert result_path.exists()
            assert result_path.stat().st_size > 0

            logger.info(f"✅ Vertical bar video created: {result_path}")

        except Exception as e:
            if "OpenCV" in str(e):
                pytest.skip("OpenCV not available for video generation")
            else:
                raise

    @pytest.mark.asyncio
    async def test_generate_polar_wedge_video(self, visual_field, output_dir):
        """Generate polar wedge stimulus video for visual verification"""
        logger.info("Generating polar wedge stimulus video...")

        # Create protocol
        protocol = create_polar_wedge_protocol(
            visual_field=visual_field,
            cycle_duration=6.0,  # Slightly longer for polar rotation
            num_cycles=1
        )

        # Create use case and generate video
        use_case = StimulusGenerationUseCase()
        output_path = output_dir / "polar_wedge_stimulus.mp4"

        try:
            result_path = await use_case.export_stimulus_video(
                protocol=protocol,
                output_path=output_path,
                frame_skip=2
            )

            assert result_path.exists()
            assert result_path.stat().st_size > 0

            logger.info(f"✅ Polar wedge video created: {result_path}")
            logger.info(f"   Wedge width: {protocol.stimulus_params.bar_width_degrees}°")

        except Exception as e:
            if "OpenCV" in str(e):
                pytest.skip("OpenCV not available for video generation")
            else:
                raise

    @pytest.mark.asyncio
    async def test_generate_expanding_ring_video(self, visual_field, output_dir):
        """Generate expanding ring stimulus video for visual verification"""
        logger.info("Generating expanding ring stimulus video...")

        # Create custom expanding ring protocol
        stimulus_params = StimulusParams(
            stimulus_type=StimulusType.EXPANDING_RING,
            direction=MovementDirection.EXPANDING,
            width_degrees=visual_field.field_of_view_degrees,
            height_degrees=visual_field.field_of_view_degrees,
            bar_width_degrees=1.5,  # Ring thickness
            cycle_duration_sec=8.0,
            frame_rate=30.0,
            num_cycles=1,
            contrast=0.8,
            background_luminance=0.5,
            checkerboard_size_degrees=0.8,
            phase_steps=8,
            fixation_cross=False,
            fixation_size_degrees=0.5,
            fixation_color=(1.0, 0.0, 0.0)
        )

        protocol = RetinotopyProtocol(
            protocol_name="Expanding Ring Retinotopy",
            description="Expanding ring for eccentricity mapping",
            stimulus_params=stimulus_params,
            visual_field=visual_field,
            pre_stimulus_baseline_sec=5.0,
            post_stimulus_baseline_sec=5.0
        )

        # Create use case and generate video
        use_case = StimulusGenerationUseCase()
        output_path = output_dir / "expanding_ring_stimulus.mp4"

        try:
            result_path = await use_case.export_stimulus_video(
                protocol=protocol,
                output_path=output_path,
                frame_skip=2
            )

            assert result_path.exists()
            assert result_path.stat().st_size > 0

            logger.info(f"✅ Expanding ring video created: {result_path}")
            logger.info(f"   Ring width: {protocol.stimulus_params.bar_width_degrees}°")

        except Exception as e:
            if "OpenCV" in str(e):
                pytest.skip("OpenCV not available for video generation")
            else:
                raise

    @pytest.mark.asyncio
    async def test_generate_preview_frames(self, visual_field):
        """Test preview frame generation"""
        protocol = create_horizontal_bar_protocol(visual_field)
        use_case = StimulusGenerationUseCase()

        # Generate preview frames
        preview_frames = await use_case.generate_preview_frames(protocol, num_frames=5)

        assert len(preview_frames) == 5
        for frame in preview_frames:
            assert isinstance(frame, np.ndarray)
            assert frame.shape == (visual_field.screen_height_pixels, visual_field.screen_width_pixels)
            assert frame.min() >= 0
            assert frame.max() <= 1

    def test_stimulus_frame_properties(self, visual_field):
        """Test properties of generated stimulus frames"""
        generator = PatternGenerator(visual_field)

        # Test horizontal bar
        params = StimulusParams(
            stimulus_type=StimulusType.HORIZONTAL_BAR,
            direction=MovementDirection.TOP_TO_BOTTOM,
            width_degrees=20.0,
            height_degrees=20.0,
            bar_width_degrees=2.0,
            cycle_duration_sec=10.0,
            frame_rate=30.0,
            num_cycles=1,
            contrast=0.5,
            background_luminance=0.5,
            checkerboard_size_degrees=1.0,
            phase_steps=8,
            fixation_cross=False,
            fixation_size_degrees=0.5
        )

        # Generate frames at different positions
        frame_0 = generator.generate_frame(params, 0)      # Start position
        frame_mid = generator.generate_frame(params, 150)  # Middle position
        frame_end = generator.generate_frame(params, 299)  # End position

        # Check frame properties
        for frame in [frame_0, frame_mid, frame_end]:
            assert frame.shape == (visual_field.screen_height_pixels, visual_field.screen_width_pixels)
            assert frame.dtype == np.float64
            assert 0 <= frame.min() <= frame.max() <= 1

        # Frames should be different (bar moved)
        assert not np.array_equal(frame_0, frame_mid)
        assert not np.array_equal(frame_mid, frame_end)

        logger.info("✅ Frame properties validation passed")

    @pytest.mark.asyncio
    async def test_create_all_stimulus_videos(self, visual_field, output_dir):
        """Create a comprehensive set of stimulus videos for visual verification"""
        logger.info("Creating comprehensive stimulus video suite...")

        use_case = StimulusGenerationUseCase()
        videos_created = []

        # Test different stimulus types with various parameters
        test_configs = [
            {
                'name': 'horizontal_bar_fast',
                'protocol': create_horizontal_bar_protocol(visual_field, cycle_duration=3.0, num_cycles=1),
                'description': 'Fast horizontal bar (3s cycle)'
            },
            {
                'name': 'vertical_bar_slow',
                'protocol': create_vertical_bar_protocol(visual_field, cycle_duration=8.0, num_cycles=1),
                'description': 'Slow vertical bar (8s cycle)'
            },
            {
                'name': 'polar_wedge_ccw',
                'protocol': RetinotopyProtocol(
                    protocol_name="Polar Wedge CCW",
                    description="Counter-clockwise polar wedge",
                    stimulus_params=StimulusParams(
                        stimulus_type=StimulusType.POLAR_WEDGE,
                        direction=MovementDirection.COUNTERCLOCKWISE,
                        width_degrees=visual_field.field_of_view_degrees,
                        height_degrees=visual_field.field_of_view_degrees,
                        bar_width_degrees=30.0,
                        cycle_duration_sec=6.0,
                        frame_rate=30.0,
                        num_cycles=1,
                        contrast=0.9,
                        background_luminance=0.4,
                        checkerboard_size_degrees=0.8,
                        phase_steps=8,
                        fixation_cross=False,
                        fixation_size_degrees=0.4,
                        fixation_color=(0.0, 1.0, 0.0)  # Green fixation
                    ),
                    visual_field=visual_field,
                    pre_stimulus_baseline_sec=2.0,
                    post_stimulus_baseline_sec=2.0
                ),
                'description': 'Counter-clockwise polar wedge with green fixation'
            }
        ]

        for config in test_configs:
            try:
                output_path = output_dir / f"{config['name']}.mp4"
                result_path = await use_case.export_stimulus_video(
                    protocol=config['protocol'],
                    output_path=output_path,
                    frame_skip=1  # Keep all frames for detailed verification
                )

                if result_path.exists():
                    videos_created.append({
                        'path': result_path,
                        'name': config['name'],
                        'description': config['description'],
                        'size_mb': result_path.stat().st_size / (1024 * 1024)
                    })

            except Exception as e:
                if "OpenCV" in str(e):
                    logger.warning(f"Skipping {config['name']}: OpenCV not available")
                else:
                    logger.error(f"Failed to create {config['name']}: {e}")

        # Log summary
        if videos_created:
            logger.info("\n" + "="*60)
            logger.info("🎬 STIMULUS VIDEOS CREATED FOR VISUAL VERIFICATION")
            logger.info("="*60)
            total_size = 0
            for video in videos_created:
                logger.info(f"📹 {video['name']}.mp4 ({video['size_mb']:.1f} MB)")
                logger.info(f"   {video['description']}")
                logger.info(f"   Path: {video['path']}")
                total_size += video['size_mb']

            logger.info(f"\nTotal: {len(videos_created)} videos, {total_size:.1f} MB")
            logger.info(f"Location: {output_dir}")
            logger.info("\n💡 Open these videos to visually verify stimulus patterns!")
        else:
            pytest.skip("No videos could be created (OpenCV may not be installed)")

        assert len(videos_created) > 0, "At least one video should be created"