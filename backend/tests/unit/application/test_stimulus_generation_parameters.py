"""
Tests for Stimulus Generation Parameter Integration

Tests the stimulus generation use case integration with parameter system:
- StimulusGenerationUseCase parameter loading and usage
- Protocol factory functions with parameter system
- Stimulus sequence creation with parameter validation
- Preview generation with different parameter sets
- Video export with parameter-driven configuration
- Integration with PatternGenerator parameter updates
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from src.application.use_cases.stimulus_generation import (
    StimulusGenerationUseCase,
    StimulusSequence,
    create_horizontal_bar_protocol_from_parameters,
    create_vertical_bar_protocol_from_parameters,
    create_polar_wedge_protocol_from_parameters
)
from src.domain.value_objects.stimulus_params import (
    StimulusParams, VisualFieldParams, RetinotopyProtocol
)
from src.domain.value_objects.parameters import (
    CombinedParameters,
    ParameterSource
)
from src.domain.entities.parameters import DefaultParameterFactory


class TestStimulusSequenceParameterIntegration:
    """Test StimulusSequence integration with parameter system"""

    def setup_method(self):
        """Setup test data"""
        self.marshel_params = DefaultParameterFactory.create_marshel_2011_defaults()
        self.dev_params = DefaultParameterFactory.create_development_defaults()

    def test_stimulus_sequence_initialization_with_combined_parameters(self):
        """Test StimulusSequence initialization includes combined parameters"""
        protocol = create_horizontal_bar_protocol_from_parameters()

        # Mock generator for testing
        mock_generator = Mock()

        sequence = StimulusSequence(protocol, mock_generator, self.marshel_params)

        assert sequence.protocol == protocol
        assert sequence.generator == mock_generator
        assert sequence.combined_parameters == self.marshel_params

    def test_stimulus_sequence_properties_use_protocol_params(self):
        """Test that sequence properties use protocol parameters"""
        protocol = create_horizontal_bar_protocol_from_parameters()
        mock_generator = Mock()

        sequence = StimulusSequence(protocol, mock_generator, self.marshel_params)

        # Properties should be derived from protocol stimulus params
        assert sequence.total_frames == protocol.stimulus_params.total_frames
        assert hasattr(sequence, 'params')

    def test_stimulus_sequence_with_different_parameter_sets(self):
        """Test stimulus sequences with different parameter sets"""
        marshel_protocol = create_horizontal_bar_protocol_from_parameters("marshel_2011_defaults")
        dev_protocol = create_horizontal_bar_protocol_from_parameters("development_defaults")

        mock_generator = Mock()

        marshel_sequence = StimulusSequence(marshel_protocol, mock_generator, self.marshel_params)
        dev_sequence = StimulusSequence(dev_protocol, mock_generator, self.dev_params)

        # Sequences should have different characteristics based on parameters
        assert marshel_sequence.total_frames != dev_sequence.total_frames


class TestStimulusGenerationUseCaseParameterIntegration:
    """Test StimulusGenerationUseCase integration with parameter system"""

    def setup_method(self):
        """Setup use case for testing"""
        self.use_case = StimulusGenerationUseCase()

    @pytest.mark.asyncio
    async def test_create_stimulus_sequence_with_parameter_set_id(self):
        """Test creating stimulus sequence with parameter set ID"""
        protocol = create_horizontal_bar_protocol_from_parameters()

        sequence = await self.use_case.create_stimulus_sequence(
            protocol,
            parameter_set_id="marshel_2011_defaults"
        )

        assert isinstance(sequence, StimulusSequence)
        assert hasattr(sequence, 'combined_parameters')
        assert sequence.combined_parameters.parameter_source == ParameterSource.DEFAULT

    @pytest.mark.asyncio
    async def test_create_stimulus_sequence_with_development_parameters(self):
        """Test creating stimulus sequence with development parameters"""
        protocol = create_horizontal_bar_protocol_from_parameters("development_defaults")

        sequence = await self.use_case.create_stimulus_sequence(
            protocol,
            parameter_set_id="development_defaults"
        )

        assert isinstance(sequence, StimulusSequence)
        # Development sequence should have different characteristics
        assert sequence.combined_parameters.spatial_config.screen_width_pixels == 800

    @pytest.mark.asyncio
    async def test_generate_preview_frames_with_parameter_set(self):
        """Test generating preview frames with specific parameter set"""
        protocol = create_horizontal_bar_protocol_from_parameters()

        previews = await self.use_case.generate_preview_frames(
            protocol,
            num_frames=5,
            parameter_set_id="marshel_2011_defaults"
        )

        assert isinstance(previews, list)
        assert len(previews) == 5
        for frame in previews:
            assert hasattr(frame, 'shape')
            # Marshel parameters should produce 2048x2048 frames
            assert frame.shape == (2048, 2048)

    @pytest.mark.asyncio
    async def test_generate_preview_frames_with_development_parameters(self):
        """Test generating preview frames with development parameters"""
        protocol = create_horizontal_bar_protocol_from_parameters("development_defaults")

        previews = await self.use_case.generate_preview_frames(
            protocol,
            num_frames=3,
            parameter_set_id="development_defaults"
        )

        assert isinstance(previews, list)
        assert len(previews) == 3
        for frame in previews:
            assert hasattr(frame, 'shape')
            # Development parameters should produce 800x600 frames
            assert frame.shape == (600, 800)

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="CV2 module dependency for video export not critical for parameter testing")
    async def test_export_stimulus_video_with_parameter_set(self):
        """Test exporting stimulus video with parameter set"""
        protocol = create_horizontal_bar_protocol_from_parameters()

        # This test requires cv2 which may not be available
        # Skip if cv2 is not available
        pytest.importorskip("cv2")

        with patch('src.application.use_cases.stimulus_generation.cv2') as mock_cv2:
            # Mock OpenCV components
            mock_writer = Mock()
            mock_writer.isOpened.return_value = True
            mock_cv2.VideoWriter.return_value = mock_writer
            mock_cv2.VideoWriter_fourcc.return_value = 'mp4v'

            output_path = Path(tempfile.mktemp(suffix='.mp4'))

            result_path = await self.use_case.export_stimulus_video(
                protocol,
                output_path,
                frame_skip=1,
                parameter_set_id="marshel_2011_defaults"
            )

            assert result_path == output_path
            # Should have created video writer with Marshel dimensions
            mock_cv2.VideoWriter.assert_called_once()
            call_args = mock_cv2.VideoWriter.call_args[0]
            # Check that video writer was called with correct dimensions
            # Note: call_args format is (path, fourcc, fps, (width, height), isColor)
            assert call_args[3] == (2048, 2048)  # Marshel screen dimensions

    @pytest.mark.asyncio
    async def test_sequence_validation_with_parameters(self):
        """Test sequence validation uses parameter-driven generation"""
        protocol = create_horizontal_bar_protocol_from_parameters()

        # This should not raise an exception
        sequence = await self.use_case.create_stimulus_sequence(protocol)

        # Should be able to get a frame
        frame = sequence.get_frame(0)
        assert frame is not None
        assert frame.shape == (2048, 2048)  # Marshel default dimensions

    @patch('src.application.use_cases.stimulus_generation.ParameterManager')
    @pytest.mark.asyncio
    async def test_parameter_manager_usage_in_use_case(self, mock_pm_class):
        """Test that use case properly uses ParameterManager"""
        mock_pm = Mock()
        mock_pm_class.return_value = mock_pm
        mock_pm.get_parameters.return_value = DefaultParameterFactory.create_marshel_2011_defaults()

        protocol = create_horizontal_bar_protocol_from_parameters()

        await self.use_case.create_stimulus_sequence(
            protocol,
            parameter_set_id="test_parameters"
        )

        # Should have used ParameterManager
        mock_pm_class.assert_called()
        mock_pm.get_parameters.assert_called_with("test_parameters")

    @pytest.mark.asyncio
    async def test_sequence_frame_generation_consistency(self):
        """Test that sequence frame generation is consistent with parameters"""
        protocol = create_horizontal_bar_protocol_from_parameters()

        sequence = await self.use_case.create_stimulus_sequence(protocol)

        # Generate multiple frames
        frame1 = sequence.get_frame(0)
        frame2 = sequence.get_frame(100)
        frame3 = sequence.get_frame(200)

        # All frames should have same dimensions (from parameters)
        assert frame1.shape == frame2.shape == frame3.shape
        # All frames should be in valid range
        for frame in [frame1, frame2, frame3]:
            assert 0.0 <= frame.min() <= frame.max() <= 1.0


class TestProtocolFactoryParameterIntegration:
    """Test protocol factory functions with parameter system integration"""

    def test_horizontal_bar_protocol_factory_uses_parameter_manager(self):
        """Test horizontal bar protocol factory uses ParameterManager"""
        # Test with actual parameter manager using marshel defaults
        protocol = create_horizontal_bar_protocol_from_parameters("marshel_2011_defaults")

        assert isinstance(protocol, RetinotopyProtocol)
        assert protocol.protocol_name == "Horizontal Bar Retinotopy"
        # Should use Marshel defaults
        assert protocol.stimulus_params.bar_width_degrees == 20.0

    def test_vertical_bar_protocol_factory_uses_parameter_manager(self):
        """Test vertical bar protocol factory uses ParameterManager"""
        # Test with actual parameter manager using marshel defaults
        protocol = create_vertical_bar_protocol_from_parameters("marshel_2011_defaults")

        assert isinstance(protocol, RetinotopyProtocol)
        assert protocol.protocol_name == "Vertical Bar Retinotopy"
        # Should use Marshel defaults
        assert protocol.stimulus_params.bar_width_degrees == 20.0

    def test_polar_wedge_protocol_factory_uses_parameter_manager(self):
        """Test polar wedge protocol factory uses ParameterManager"""
        # Test with actual parameter manager using marshel defaults
        protocol = create_polar_wedge_protocol_from_parameters("marshel_2011_defaults")

        assert isinstance(protocol, RetinotopyProtocol)
        assert protocol.protocol_name == "Polar Wedge Retinotopy"
        # Should use Marshel checkerboard defaults
        assert protocol.stimulus_params.checkerboard_size_degrees == 25.0

    def test_protocol_factories_create_proper_visual_field(self):
        """Test that protocol factories create proper visual field from spatial config"""
        protocol = create_horizontal_bar_protocol_from_parameters()

        assert isinstance(protocol.visual_field, VisualFieldParams)
        # Should match Marshel spatial configuration
        assert protocol.visual_field.screen_width_pixels == 2048
        assert protocol.visual_field.screen_height_pixels == 2048
        assert protocol.visual_field.screen_width_cm == 52.0
        assert protocol.visual_field.screen_distance_cm == 10.0

    def test_protocol_factories_use_baseline_times_from_parameters(self):
        """Test that protocol factories use baseline times from parameters"""
        protocol = create_horizontal_bar_protocol_from_parameters()

        # Should use baseline times from protocol parameters
        assert protocol.pre_stimulus_baseline_sec == 10.0
        assert protocol.post_stimulus_baseline_sec == 10.0

    def test_protocol_factories_with_parameter_overrides(self):
        """Test protocol factories with parameter overrides"""
        protocol = create_horizontal_bar_protocol_from_parameters(
            cycle_duration=25.0,
            num_cycles=5
        )

        # Should use overridden values
        assert protocol.stimulus_params.cycle_duration_sec == 25.0
        assert protocol.stimulus_params.num_cycles == 5

        # Other parameters should still come from parameter system
        assert protocol.stimulus_params.bar_width_degrees == 20.0  # Marshel default

    def test_protocol_factories_preserve_parameter_relationships(self):
        """Test that protocol factories preserve parameter relationships"""
        marshel_protocol = create_horizontal_bar_protocol_from_parameters("marshel_2011_defaults")
        dev_protocol = create_horizontal_bar_protocol_from_parameters("development_defaults")

        # Marshel protocol should use Marshel values
        assert marshel_protocol.stimulus_params.bar_width_degrees == 20.0
        assert marshel_protocol.visual_field.screen_width_pixels == 2048

        # Development protocol should use development values
        assert dev_protocol.stimulus_params.bar_width_degrees == 5.0
        assert dev_protocol.visual_field.screen_width_pixels == 800

    def test_different_stimulus_types_use_same_parameter_base(self):
        """Test that different stimulus types use same parameter base"""
        horizontal = create_horizontal_bar_protocol_from_parameters()
        vertical = create_vertical_bar_protocol_from_parameters()
        polar = create_polar_wedge_protocol_from_parameters()

        # All should use same spatial configuration
        assert horizontal.visual_field.screen_width_pixels == vertical.visual_field.screen_width_pixels
        assert vertical.visual_field.screen_width_pixels == polar.visual_field.screen_width_pixels

        # All should use same baseline times (from protocol params)
        assert horizontal.pre_stimulus_baseline_sec == vertical.pre_stimulus_baseline_sec
        assert vertical.pre_stimulus_baseline_sec == polar.pre_stimulus_baseline_sec

        # All should use same checkerboard size (from stimulus params)
        assert horizontal.stimulus_params.checkerboard_size_degrees == 25.0
        assert vertical.stimulus_params.checkerboard_size_degrees == 25.0
        assert polar.stimulus_params.checkerboard_size_degrees == 25.0


class TestParameterValidationInStimulusGeneration:
    """Test parameter validation during stimulus generation"""

    def setup_method(self):
        """Setup use case for testing"""
        self.use_case = StimulusGenerationUseCase()

    @pytest.mark.asyncio
    async def test_invalid_parameter_set_raises_error(self):
        """Test that invalid parameter set raises error"""
        protocol = create_horizontal_bar_protocol_from_parameters()

        with pytest.raises(Exception):  # Should raise ParameterValidationError
            await self.use_case.create_stimulus_sequence(
                protocol,
                parameter_set_id="nonexistent_parameters"
            )

    @pytest.mark.asyncio
    async def test_sequence_validation_checks_frame_generation(self):
        """Test that sequence validation checks frame generation"""
        protocol = create_horizontal_bar_protocol_from_parameters()

        # This should pass validation (generate valid frames)
        sequence = await self.use_case.create_stimulus_sequence(protocol)

        # Validation should have checked frame properties
        frame = sequence.get_frame(0)
        assert frame is not None
        assert frame.size > 0
        assert 0.0 <= frame.min() <= frame.max() <= 1.0

    @patch('src.application.use_cases.stimulus_generation.logger')
    @pytest.mark.asyncio
    async def test_parameter_loading_logged(self, mock_logger):
        """Test that parameter loading is logged"""
        protocol = create_horizontal_bar_protocol_from_parameters()

        await self.use_case.create_stimulus_sequence(
            protocol,
            parameter_set_id="marshel_2011_defaults"
        )

        # Should log parameter loading
        mock_logger.info.assert_called()


class TestStimulusGenerationParameterEdgeCases:
    """Test edge cases in stimulus generation parameter integration"""

    def setup_method(self):
        """Setup use case for testing"""
        self.use_case = StimulusGenerationUseCase()

    def test_protocol_factory_with_none_overrides(self):
        """Test protocol factory with None parameter overrides"""
        protocol = create_horizontal_bar_protocol_from_parameters(
            cycle_duration=None,
            num_cycles=None
        )

        # Should use defaults from parameter system
        assert protocol.stimulus_params.num_cycles == 10  # Marshel default

    def test_visual_field_calculation_consistency(self):
        """Test visual field parameter calculation consistency"""
        protocol = create_horizontal_bar_protocol_from_parameters()

        # Visual field should be consistent with spatial configuration
        visual_field = protocol.visual_field

        assert visual_field.pixels_per_degree > 0
        assert visual_field.degrees_per_pixel > 0
        assert abs(visual_field.pixels_per_degree * visual_field.degrees_per_pixel - 1.0) < 0.001

    @pytest.mark.asyncio
    async def test_large_parameter_set_handling(self):
        """Test handling of large parameter sets"""
        # Test with maximum resolution parameters
        protocol = create_horizontal_bar_protocol_from_parameters()

        # Should handle large sequences
        sequence = await self.use_case.create_stimulus_sequence(protocol)

        # Should be able to get frames from large sequence
        frame = sequence.get_frame(0)
        assert frame.shape == (2048, 2048)

    def test_parameter_consistency_across_factory_calls(self):
        """Test parameter consistency across multiple factory calls"""
        protocol1 = create_horizontal_bar_protocol_from_parameters("marshel_2011_defaults")
        protocol2 = create_horizontal_bar_protocol_from_parameters("marshel_2011_defaults")

        # Should produce identical configurations
        assert protocol1.stimulus_params.bar_width_degrees == protocol2.stimulus_params.bar_width_degrees
        assert protocol1.visual_field.screen_width_pixels == protocol2.visual_field.screen_width_pixels
        assert protocol1.pre_stimulus_baseline_sec == protocol2.pre_stimulus_baseline_sec

    @pytest.mark.asyncio
    async def test_concurrent_sequence_creation(self):
        """Test concurrent sequence creation with parameters"""
        protocol = create_horizontal_bar_protocol_from_parameters()

        # Create multiple sequences concurrently
        tasks = [
            self.use_case.create_stimulus_sequence(protocol, parameter_set_id="marshel_2011_defaults")
            for _ in range(3)
        ]

        sequences = await asyncio.gather(*tasks)

        # All sequences should be valid and have same characteristics
        for sequence in sequences:
            assert isinstance(sequence, StimulusSequence)
            frame = sequence.get_frame(0)
            assert frame.shape == (2048, 2048)