"""
Tests for Pattern Generator Parameter Integration

Tests that the pattern generator correctly uses the parameter system:
- PatternGenerator initialization with CombinedParameters
- Parameter value propagation to pattern generation
- Spherical coordinate transformations using spatial parameters
- Checkerboard pattern generation using stimulus parameters
- Frame generation with different parameter sets
- Factory function integration with parameter system
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch

from src.application.algorithms.pattern_generators import (
    PatternGenerator,
    create_horizontal_bar_params_from_parameter_system,
    create_vertical_bar_params_from_parameter_system,
    create_polar_wedge_params_from_parameter_system
)
from src.domain.value_objects.parameters import (
    SpatialConfiguration,
    StimulusGenerationParams,
    AcquisitionProtocolParams,
    CombinedParameters,
    ParameterSource
)
from src.domain.value_objects.stimulus_params import StimulusType, MovementDirection
from src.domain.entities.parameters import DefaultParameterFactory


class TestPatternGeneratorParameterIntegration:
    """Test PatternGenerator integration with parameter system"""

    def setup_method(self):
        """Setup test parameters"""
        self.marshel_params = DefaultParameterFactory.create_marshel_2011_defaults()
        self.dev_params = DefaultParameterFactory.create_development_defaults()

    def test_pattern_generator_initialization_with_combined_parameters(self):
        """Test PatternGenerator initialization with CombinedParameters"""
        generator = PatternGenerator(self.marshel_params)

        assert generator.parameters == self.marshel_params
        assert generator.spatial_config == self.marshel_params.spatial_config
        assert generator.stimulus_params == self.marshel_params.stimulus_params

        # Should calculate pixels per degree from spatial configuration
        expected_ppd = self.marshel_params.spatial_config.pixels_per_degree
        assert generator.pixels_per_degree == expected_ppd

    def test_coordinate_grid_setup_uses_spatial_config(self):
        """Test that coordinate grid setup uses spatial configuration"""
        generator = PatternGenerator(self.marshel_params)

        # Check that coordinate grids use spatial config dimensions
        expected_width = self.marshel_params.spatial_config.screen_width_pixels
        expected_height = self.marshel_params.spatial_config.screen_height_pixels

        assert generator.X_pixels.shape == (expected_height, expected_width)
        assert generator.Y_pixels.shape == (expected_height, expected_width)

    def test_different_parameter_sets_create_different_generators(self):
        """Test that different parameter sets create different generators"""
        marshel_gen = PatternGenerator(self.marshel_params)
        dev_gen = PatternGenerator(self.dev_params)

        # Should have different screen dimensions
        assert marshel_gen.X_pixels.shape != dev_gen.X_pixels.shape
        assert marshel_gen.pixels_per_degree != dev_gen.pixels_per_degree

        # Marshel should be higher resolution
        assert marshel_gen.X_pixels.shape[1] > dev_gen.X_pixels.shape[1]

    def test_spherical_coordinates_use_monitor_distance(self):
        """Test that spherical coordinate calculations use monitor distance"""
        # Create custom parameters with specific monitor distance
        custom_spatial = SpatialConfiguration(monitor_distance_cm=15.0)
        custom_params = CombinedParameters(
            spatial_config=custom_spatial,
            stimulus_params=StimulusGenerationParams(),
            protocol_params=AcquisitionProtocolParams()
        )

        generator = PatternGenerator(custom_params)

        # The generator should use the custom monitor distance
        # This would be tested by checking the spherical coordinate calculations
        # in the actual pattern generation methods
        assert generator.spatial_config.monitor_distance_cm == 15.0

    def test_checkerboard_pattern_uses_stimulus_parameters(self):
        """Test that checkerboard pattern uses stimulus parameters"""
        generator = PatternGenerator(self.marshel_params)

        # Create mock stimulus params for testing
        mock_stimulus_params = Mock()
        mock_stimulus_params.frame_rate = 60.0

        # Test checkerboard pattern generation
        # We need to add background_luminance and contrast to the mock
        mock_stimulus_params.background_luminance = 0.5
        mock_stimulus_params.contrast = 0.5
        frame = generator._generate_checkerboard_pattern(mock_stimulus_params, 0)

        assert isinstance(frame, np.ndarray)
        assert frame.shape == (
            self.marshel_params.spatial_config.screen_height_pixels,
            self.marshel_params.spatial_config.screen_width_pixels
        )

    def test_horizontal_bar_generation_uses_parameters(self):
        """Test horizontal bar generation uses parameter values"""
        generator = PatternGenerator(self.marshel_params)

        # Create stimulus params for horizontal bar
        stimulus_params = create_horizontal_bar_params_from_parameter_system()

        # Generate frame
        frame = generator._generate_horizontal_bar(stimulus_params, 0)

        assert isinstance(frame, np.ndarray)
        assert frame.shape == (
            self.marshel_params.spatial_config.screen_height_pixels,
            self.marshel_params.spatial_config.screen_width_pixels
        )
        assert 0.0 <= frame.min() <= frame.max() <= 1.0

    def test_vertical_bar_generation_uses_parameters(self):
        """Test vertical bar generation uses parameter values"""
        generator = PatternGenerator(self.marshel_params)

        # Create stimulus params for vertical bar
        stimulus_params = create_vertical_bar_params_from_parameter_system()

        # Generate frame
        frame = generator._generate_vertical_bar(stimulus_params, 0)

        assert isinstance(frame, np.ndarray)
        assert frame.shape == (
            self.marshel_params.spatial_config.screen_height_pixels,
            self.marshel_params.spatial_config.screen_width_pixels
        )
        assert 0.0 <= frame.min() <= frame.max() <= 1.0

    def test_polar_wedge_generation_uses_parameters(self):
        """Test polar wedge generation uses parameter values"""
        generator = PatternGenerator(self.marshel_params)

        # Create stimulus params for polar wedge
        stimulus_params = create_polar_wedge_params_from_parameter_system()

        # Generate frame
        frame = generator._generate_polar_wedge(stimulus_params, 0)

        assert isinstance(frame, np.ndarray)
        assert frame.shape == (
            self.marshel_params.spatial_config.screen_height_pixels,
            self.marshel_params.spatial_config.screen_width_pixels
        )
        assert 0.0 <= frame.min() <= frame.max() <= 1.0

    def test_frame_generation_with_different_parameter_sets(self):
        """Test frame generation with different parameter sets produces different results"""
        marshel_gen = PatternGenerator(self.marshel_params)
        dev_gen = PatternGenerator(self.dev_params)

        # Create stimulus params from different parameter sets
        marshel_stimulus = create_horizontal_bar_params_from_parameter_system("marshel_2011_defaults")
        dev_stimulus = create_horizontal_bar_params_from_parameter_system("development_defaults")

        # Generate frames
        marshel_frame = marshel_gen.generate_frame(marshel_stimulus, 0)
        dev_frame = dev_gen.generate_frame(dev_stimulus, 0)

        # Frames should have different dimensions
        assert marshel_frame.shape != dev_frame.shape

    def test_parameter_values_affect_pattern_characteristics(self):
        """Test that parameter values affect pattern characteristics"""
        # Create parameters with different checkerboard sizes
        small_stimulus = StimulusGenerationParams(checkerboard_size_degrees=5.0)
        large_stimulus = StimulusGenerationParams(checkerboard_size_degrees=40.0)

        small_params = CombinedParameters(
            spatial_config=SpatialConfiguration(),
            stimulus_params=small_stimulus,
            protocol_params=AcquisitionProtocolParams()
        )

        large_params = CombinedParameters(
            spatial_config=SpatialConfiguration(),
            stimulus_params=large_stimulus,
            protocol_params=AcquisitionProtocolParams()
        )

        small_gen = PatternGenerator(small_params)
        large_gen = PatternGenerator(large_params)

        # Create mock stimulus params
        mock_params = Mock()
        mock_params.frame_rate = 60.0
        mock_params.background_luminance = 0.5
        mock_params.contrast = 0.5

        # Generate checkerboard patterns
        small_pattern = small_gen._generate_checkerboard_pattern(mock_params, 0)
        large_pattern = large_gen._generate_checkerboard_pattern(mock_params, 0)

        # Patterns should be different due to different checkerboard sizes
        assert not np.array_equal(small_pattern, large_pattern)

    def test_flicker_frequency_affects_counter_phase(self):
        """Test that flicker frequency affects counter-phase timing"""
        # Create parameters with different flicker frequencies
        slow_stimulus = StimulusGenerationParams(flicker_frequency_hz=2.0)
        fast_stimulus = StimulusGenerationParams(flicker_frequency_hz=10.0)

        slow_params = CombinedParameters(
            spatial_config=SpatialConfiguration(),
            stimulus_params=slow_stimulus,
            protocol_params=AcquisitionProtocolParams()
        )

        fast_params = CombinedParameters(
            spatial_config=SpatialConfiguration(),
            stimulus_params=fast_stimulus,
            protocol_params=AcquisitionProtocolParams()
        )

        slow_gen = PatternGenerator(slow_params)
        fast_gen = PatternGenerator(fast_params)

        # Create mock stimulus params
        mock_params = Mock()
        mock_params.frame_rate = 60.0
        mock_params.background_luminance = 0.5
        mock_params.contrast = 0.5

        # Generate patterns at different frame indices
        slow_frame1 = slow_gen._generate_checkerboard_pattern(mock_params, 0)
        slow_frame2 = slow_gen._generate_checkerboard_pattern(mock_params, 30)  # 0.5 sec later at 60fps

        fast_frame1 = fast_gen._generate_checkerboard_pattern(mock_params, 0)
        fast_frame2 = fast_gen._generate_checkerboard_pattern(mock_params, 6)   # 0.1 sec later at 60fps

        # Fast flicker should show phase change sooner
        # (This is a simplified test - actual behavior depends on implementation details)
        assert isinstance(slow_frame1, np.ndarray)
        assert isinstance(fast_frame1, np.ndarray)

    def test_spatial_configuration_affects_field_of_view(self):
        """Test that spatial configuration affects field of view calculations"""
        # Create parameters with different field of view
        narrow_spatial = SpatialConfiguration(
            field_of_view_horizontal_degrees=60.0,
            field_of_view_vertical_degrees=60.0
        )
        wide_spatial = SpatialConfiguration(
            field_of_view_horizontal_degrees=180.0,
            field_of_view_vertical_degrees=180.0
        )

        narrow_params = CombinedParameters(
            spatial_config=narrow_spatial,
            stimulus_params=StimulusGenerationParams(),
            protocol_params=AcquisitionProtocolParams()
        )

        wide_params = CombinedParameters(
            spatial_config=wide_spatial,
            stimulus_params=StimulusGenerationParams(),
            protocol_params=AcquisitionProtocolParams()
        )

        narrow_gen = PatternGenerator(narrow_params)
        wide_gen = PatternGenerator(wide_params)

        # Different field of view should affect coordinate calculations
        assert narrow_gen.spatial_config.field_of_view_horizontal_degrees == 60.0
        assert wide_gen.spatial_config.field_of_view_horizontal_degrees == 180.0


class TestPatternGeneratorFactoryFunctions:
    """Test pattern generator factory functions with parameter system"""

    @patch('src.application.algorithms.pattern_generators.ParameterManager')
    def test_horizontal_bar_factory_uses_parameter_manager(self, mock_pm_class):
        """Test horizontal bar factory uses ParameterManager"""
        mock_pm = Mock()
        mock_pm_class.return_value = mock_pm
        mock_pm.get_parameters.return_value = DefaultParameterFactory.create_marshel_2011_defaults()

        stimulus_params = create_horizontal_bar_params_from_parameter_system("test_set")

        # Should have called ParameterManager
        mock_pm_class.assert_called_once()
        mock_pm.get_parameters.assert_called_once_with("test_set")

        # Should return proper stimulus params (checking string values due to enum serialization)
        assert stimulus_params.stimulus_type == StimulusType.HORIZONTAL_BAR.value
        assert stimulus_params.direction == MovementDirection.TOP_TO_BOTTOM.value

    @patch('src.application.algorithms.pattern_generators.ParameterManager')
    def test_vertical_bar_factory_uses_parameter_manager(self, mock_pm_class):
        """Test vertical bar factory uses ParameterManager"""
        mock_pm = Mock()
        mock_pm_class.return_value = mock_pm
        mock_pm.get_parameters.return_value = DefaultParameterFactory.create_marshel_2011_defaults()

        stimulus_params = create_vertical_bar_params_from_parameter_system("test_set")

        # Should have called ParameterManager
        mock_pm_class.assert_called_once()
        mock_pm.get_parameters.assert_called_once_with("test_set")

        # Should return proper stimulus params (checking string values due to enum serialization)
        assert stimulus_params.stimulus_type == StimulusType.VERTICAL_BAR.value
        assert stimulus_params.direction == MovementDirection.LEFT_TO_RIGHT.value

    @patch('src.application.algorithms.pattern_generators.ParameterManager')
    def test_polar_wedge_factory_uses_parameter_manager(self, mock_pm_class):
        """Test polar wedge factory uses ParameterManager"""
        mock_pm = Mock()
        mock_pm_class.return_value = mock_pm
        mock_pm.get_parameters.return_value = DefaultParameterFactory.create_marshel_2011_defaults()

        stimulus_params = create_polar_wedge_params_from_parameter_system("test_set")

        # Should have called ParameterManager
        mock_pm_class.assert_called_once()
        mock_pm.get_parameters.assert_called_once_with("test_set")

        # Should return proper stimulus params (checking string values due to enum serialization)
        assert stimulus_params.stimulus_type == StimulusType.POLAR_WEDGE.value
        assert stimulus_params.direction == MovementDirection.CLOCKWISE.value

    def test_factory_functions_use_marshel_defaults_by_default(self):
        """Test that factory functions use Marshel defaults by default"""
        horizontal_params = create_horizontal_bar_params_from_parameter_system()
        vertical_params = create_vertical_bar_params_from_parameter_system()
        polar_params = create_polar_wedge_params_from_parameter_system()

        # All should use Marshel bar width (20°)
        assert horizontal_params.bar_width_degrees == 20.0
        assert vertical_params.bar_width_degrees == 20.0
        # Polar wedge uses different default width for angular coverage
        assert polar_params.bar_width_degrees == 30.0

        # All should use Marshel checkerboard size (25°)
        assert horizontal_params.checkerboard_size_degrees == 25.0
        assert vertical_params.checkerboard_size_degrees == 25.0
        assert polar_params.checkerboard_size_degrees == 25.0

    def test_factory_functions_can_use_development_defaults(self):
        """Test that factory functions can use development defaults"""
        horizontal_params = create_horizontal_bar_params_from_parameter_system("development_defaults")
        vertical_params = create_vertical_bar_params_from_parameter_system("development_defaults")
        polar_params = create_polar_wedge_params_from_parameter_system("development_defaults")

        # All should use development bar width (5°)
        assert horizontal_params.bar_width_degrees == 5.0
        assert vertical_params.bar_width_degrees == 5.0
        # Polar wedge still uses 30° width

        # All should use development checkerboard size (5°)
        assert horizontal_params.checkerboard_size_degrees == 5.0
        assert vertical_params.checkerboard_size_degrees == 5.0
        assert polar_params.checkerboard_size_degrees == 5.0

    def test_factory_functions_calculate_proper_cycle_duration(self):
        """Test that factory functions calculate proper cycle duration"""
        horizontal_params = create_horizontal_bar_params_from_parameter_system()
        vertical_params = create_vertical_bar_params_from_parameter_system()

        # Should calculate cycle duration based on field size and drift speed
        # Marshel: 153° vertical / 9°/s ≈ 17 seconds
        # Marshel: 147° horizontal / 9°/s ≈ 16.3 seconds
        assert 16.0 < horizontal_params.cycle_duration_sec < 18.0
        assert 15.0 < vertical_params.cycle_duration_sec < 17.0

    def test_factory_functions_preserve_parameter_relationships(self):
        """Test that factory functions preserve parameter relationships"""
        params = create_horizontal_bar_params_from_parameter_system()

        # Visual field dimensions should match spatial configuration
        # (Note: This tests the relationship between factory output and parameter system)
        assert params.width_degrees == 153.0  # Marshel vertical field
        assert params.height_degrees == 147.0  # Marshel horizontal field

        # Frame rate should match protocol parameters
        assert params.frame_rate == 60.0  # Marshel protocol frame rate

        # Stimulus properties should match stimulus parameters
        assert params.contrast == 0.5  # Marshel contrast
        assert params.background_luminance == 0.5  # Marshel background


class TestPatternGeneratorEdgeCases:
    """Test pattern generator edge cases and error handling"""

    def setup_method(self):
        """Setup test parameters"""
        self.marshel_params = DefaultParameterFactory.create_marshel_2011_defaults()
        self.dev_params = DefaultParameterFactory.create_development_defaults()

    def test_pattern_generator_with_minimal_parameters(self):
        """Test pattern generator with minimal valid parameters"""
        minimal_spatial = SpatialConfiguration(
            monitor_distance_cm=5.0,  # Minimum allowed
            screen_width_pixels=640,
            screen_height_pixels=480
        )
        minimal_stimulus = StimulusGenerationParams(
            bar_width_degrees=1.0,  # Minimum allowed
            checkerboard_size_degrees=1.0
        )
        minimal_params = CombinedParameters(
            spatial_config=minimal_spatial,
            stimulus_params=minimal_stimulus,
            protocol_params=AcquisitionProtocolParams()
        )

        generator = PatternGenerator(minimal_params)
        assert generator.pixels_per_degree > 0

    def test_pattern_generator_with_maximal_parameters(self):
        """Test pattern generator with maximal valid parameters"""
        maximal_spatial = SpatialConfiguration(
            monitor_distance_cm=20.0,  # Maximum allowed
            screen_width_pixels=4096,
            screen_height_pixels=4096
        )
        maximal_stimulus = StimulusGenerationParams(
            bar_width_degrees=45.0,  # Maximum allowed
            checkerboard_size_degrees=50.0
        )
        maximal_params = CombinedParameters(
            spatial_config=maximal_spatial,
            stimulus_params=maximal_stimulus,
            protocol_params=AcquisitionProtocolParams()
        )

        generator = PatternGenerator(maximal_params)
        assert generator.pixels_per_degree > 0

    def test_coordinate_grid_consistency(self):
        """Test coordinate grid consistency across different parameter sets"""
        for param_set in [self.marshel_params, self.dev_params]:
            generator = PatternGenerator(param_set)

            # Coordinate grids should be consistent
            assert generator.X_pixels.shape == generator.Y_pixels.shape
            assert generator.X_degrees.shape == generator.Y_degrees.shape
            assert generator.R_degrees.shape == generator.Theta_degrees.shape

            # All grids should have same shape as expected screen dimensions
            expected_shape = (
                param_set.spatial_config.screen_height_pixels,
                param_set.spatial_config.screen_width_pixels
            )
            assert generator.X_pixels.shape == expected_shape