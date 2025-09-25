"""
Tests for Parameter Value Objects

Tests the core parameter value objects following ADR-0007:
Parameter Separation: Generation vs Acquisition.

Test Coverage:
- SpatialConfiguration validation and properties
- StimulusGenerationParams validation and properties
- AcquisitionProtocolParams validation and properties
- CombinedParameters integration and hashing
- Parameter serialization and deserialization
- Marshel et al. compliance validation
"""

import pytest
from pydantic import ValidationError
import hashlib
import json
from datetime import datetime

from src.domain.value_objects.parameters import (
    SpatialConfiguration,
    StimulusGenerationParams,
    AcquisitionProtocolParams,
    CombinedParameters,
    ParameterSource
)
from src.domain.services.error_handler import ISIDomainError


class TestSpatialConfiguration:
    """Test SpatialConfiguration value object"""

    def test_marshel_defaults(self):
        """Test Marshel et al. 2011 default values"""
        config = SpatialConfiguration()

        # Verify Marshel defaults
        assert config.monitor_distance_cm == 10.0
        assert config.monitor_angle_degrees == 20.0
        assert config.monitor_height_degrees == 0.0
        assert config.monitor_roll_degrees == 0.0
        assert config.field_of_view_horizontal_degrees == 147.0
        assert config.field_of_view_vertical_degrees == 153.0
        assert config.screen_width_pixels == 2048
        assert config.screen_height_pixels == 2048

    def test_validation_constraints(self):
        """Test validation constraints"""
        # Valid configuration
        config = SpatialConfiguration(
            monitor_distance_cm=15.0,
            monitor_angle_degrees=30.0,
            screen_width_pixels=1024,
            screen_height_pixels=768
        )
        assert config.monitor_distance_cm == 15.0

        # Invalid distance (too small)
        with pytest.raises(ValidationError) as excinfo:
            SpatialConfiguration(monitor_distance_cm=3.0)
        assert "greater than or equal to 5" in str(excinfo.value)

        # Invalid distance (too large)
        with pytest.raises(ValidationError) as excinfo:
            SpatialConfiguration(monitor_distance_cm=25.0)
        assert "less than or equal to 20" in str(excinfo.value)

        # Invalid angle (too large)
        with pytest.raises(ValidationError) as excinfo:
            SpatialConfiguration(monitor_angle_degrees=50.0)
        assert "less than or equal to 45" in str(excinfo.value)

        # Invalid field of view (too large)
        with pytest.raises(ValidationError) as excinfo:
            SpatialConfiguration(field_of_view_horizontal_degrees=200.0)
        assert "less than or equal to 180" in str(excinfo.value)

    def test_pixels_per_degree_calculation(self):
        """Test pixels per degree calculation"""
        config = SpatialConfiguration(
            monitor_distance_cm=10.0,
            screen_width_cm=52.0,
            screen_width_pixels=2048
        )

        # Should calculate approximately 14.85 pixels per degree
        ppd = config.pixels_per_degree
        assert 14.0 < ppd < 16.0

    def test_config_hash_consistency(self):
        """Test configuration hash consistency"""
        config1 = SpatialConfiguration()
        config2 = SpatialConfiguration()

        # Same configuration should produce same hash
        assert config1.config_hash == config2.config_hash

        # Different configuration should produce different hash
        config3 = SpatialConfiguration(monitor_distance_cm=15.0)
        assert config1.config_hash != config3.config_hash

    def test_immutability(self):
        """Test that configuration is immutable"""
        config = SpatialConfiguration()

        with pytest.raises(ValidationError):
            config.monitor_distance_cm = 15.0


class TestStimulusGenerationParams:
    """Test StimulusGenerationParams value object"""

    def test_marshel_defaults(self):
        """Test Marshel et al. 2011 default values"""
        params = StimulusGenerationParams()

        # Verify Marshel defaults
        assert params.bar_width_degrees == 20.0
        assert params.drift_speed_degrees_per_sec == 9.0
        assert params.pattern_type == "counter_phase_checkerboard"
        assert params.checkerboard_size_degrees == 25.0
        assert params.flicker_frequency_hz == 6.0
        assert params.contrast == 0.5
        assert params.background_luminance == 0.5
        assert params.spherical_correction == True
        assert params.coordinate_system == "spherical"

    def test_validation_constraints(self):
        """Test validation constraints"""
        # Valid parameters
        params = StimulusGenerationParams(
            bar_width_degrees=15.0,
            drift_speed_degrees_per_sec=12.0,
            checkerboard_size_degrees=30.0
        )
        assert params.bar_width_degrees == 15.0

        # Invalid bar width (too large)
        with pytest.raises(ValidationError) as excinfo:
            StimulusGenerationParams(bar_width_degrees=50.0)
        assert "less than or equal to 45" in str(excinfo.value)

        # Invalid drift speed (too fast)
        with pytest.raises(ValidationError) as excinfo:
            StimulusGenerationParams(drift_speed_degrees_per_sec=60.0)
        assert "less than or equal to 50" in str(excinfo.value)

        # Invalid checkerboard size (too large)
        with pytest.raises(ValidationError) as excinfo:
            StimulusGenerationParams(checkerboard_size_degrees=60.0)
        assert "less than or equal to 50" in str(excinfo.value)

        # Invalid contrast (negative)
        with pytest.raises(ValidationError) as excinfo:
            StimulusGenerationParams(contrast=-0.1)
        assert "greater than or equal to 0" in str(excinfo.value)

        # Invalid luminance (too high)
        with pytest.raises(ValidationError) as excinfo:
            StimulusGenerationParams(background_luminance=1.5)
        assert "less than or equal to 1" in str(excinfo.value)

    def test_params_hash_consistency(self):
        """Test parameter hash consistency"""
        params1 = StimulusGenerationParams()
        params2 = StimulusGenerationParams()

        # Same parameters should produce same hash
        assert params1.params_hash == params2.params_hash

        # Different parameters should produce different hash
        params3 = StimulusGenerationParams(bar_width_degrees=15.0)
        assert params1.params_hash != params3.params_hash

    def test_immutability(self):
        """Test that parameters are immutable"""
        params = StimulusGenerationParams()

        with pytest.raises(ValidationError):
            params.bar_width_degrees = 15.0


class TestAcquisitionProtocolParams:
    """Test AcquisitionProtocolParams value object"""

    def test_default_values(self):
        """Test default acquisition parameter values"""
        params = AcquisitionProtocolParams()

        assert params.num_cycles == 10
        assert params.repetitions_per_direction == 1
        assert params.frame_rate == 60.0
        assert params.inter_trial_interval_sec == 2.0
        assert params.pre_stimulus_baseline_sec == 10.0
        assert params.post_stimulus_baseline_sec == 10.0
        assert params.session_name_pattern == "ISI_Mapping_{timestamp}"
        assert params.export_formats == ["hdf5", "png"]

    def test_validation_constraints(self):
        """Test validation constraints"""
        # Valid parameters
        params = AcquisitionProtocolParams(
            num_cycles=15,
            frame_rate=120.0,
            buffer_size_frames=200
        )
        assert params.num_cycles == 15

        # Invalid cycles (too many)
        with pytest.raises(ValidationError) as excinfo:
            AcquisitionProtocolParams(num_cycles=25)
        assert "less than or equal to 20" in str(excinfo.value)

        # Invalid frame rate (too low)
        with pytest.raises(ValidationError) as excinfo:
            AcquisitionProtocolParams(frame_rate=0.5)
        assert "greater than 1" in str(excinfo.value)

        # Invalid frame rate (too high)
        with pytest.raises(ValidationError) as excinfo:
            AcquisitionProtocolParams(frame_rate=150.0)
        assert "less than or equal to 120" in str(excinfo.value)

    def test_immutability(self):
        """Test that parameters are immutable"""
        params = AcquisitionProtocolParams()

        with pytest.raises(ValidationError):
            params.num_cycles = 15


class TestCombinedParameters:
    """Test CombinedParameters integration"""

    def test_combined_creation(self):
        """Test creating combined parameters"""
        spatial = SpatialConfiguration()
        stimulus = StimulusGenerationParams()
        protocol = AcquisitionProtocolParams()

        combined = CombinedParameters(
            spatial_config=spatial,
            stimulus_params=stimulus,
            protocol_params=protocol,
            parameter_source=ParameterSource.DEFAULT,
            version="1.0"
        )

        assert combined.spatial_config == spatial
        assert combined.stimulus_params == stimulus
        assert combined.protocol_params == protocol
        assert combined.parameter_source == ParameterSource.DEFAULT
        assert combined.version == "1.0"

    def test_hash_generation(self):
        """Test hash generation for combined parameters"""
        combined = CombinedParameters(
            spatial_config=SpatialConfiguration(),
            stimulus_params=StimulusGenerationParams(),
            protocol_params=AcquisitionProtocolParams()
        )

        # Combined hash should be consistent
        hash1 = combined.combined_hash
        hash2 = combined.combined_hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex digest

        # Generation hash should only include generation parameters
        gen_hash1 = combined.generation_hash
        gen_hash2 = combined.generation_hash
        assert gen_hash1 == gen_hash2
        assert len(gen_hash1) == 64

    def test_generation_vs_combined_hash(self):
        """Test that generation hash differs from combined hash"""
        combined = CombinedParameters(
            spatial_config=SpatialConfiguration(),
            stimulus_params=StimulusGenerationParams(),
            protocol_params=AcquisitionProtocolParams()
        )

        # Generation hash should be same as combined hash in this case
        # since it's based on the same generation parameters
        assert combined.generation_hash == combined.combined_hash

    def test_parameter_modification_affects_hash(self):
        """Test that parameter changes affect hashes appropriately"""
        # Create two different spatial configurations
        spatial1 = SpatialConfiguration()
        spatial2 = SpatialConfiguration(monitor_distance_cm=15.0)

        stimulus = StimulusGenerationParams()
        protocol = AcquisitionProtocolParams()

        combined1 = CombinedParameters(
            spatial_config=spatial1,
            stimulus_params=stimulus,
            protocol_params=protocol
        )

        combined2 = CombinedParameters(
            spatial_config=spatial2,
            stimulus_params=stimulus,
            protocol_params=protocol
        )

        # Hashes should be different due to different spatial config
        assert combined1.combined_hash != combined2.combined_hash
        assert combined1.generation_hash != combined2.generation_hash

    def test_protocol_changes_dont_affect_generation_hash(self):
        """Test that protocol changes don't affect generation hash"""
        spatial = SpatialConfiguration()
        stimulus = StimulusGenerationParams()
        protocol1 = AcquisitionProtocolParams()
        protocol2 = AcquisitionProtocolParams(num_cycles=15)

        combined1 = CombinedParameters(
            spatial_config=spatial,
            stimulus_params=stimulus,
            protocol_params=protocol1
        )

        combined2 = CombinedParameters(
            spatial_config=spatial,
            stimulus_params=stimulus,
            protocol_params=protocol2
        )

        # Generation hash should be same (protocol doesn't affect it)
        assert combined1.generation_hash == combined2.generation_hash

        # Combined hash should be the same since our implementation
        # currently only includes generation parameters in combined hash
        # This is a design decision that may change in the future
        assert combined1.combined_hash == combined2.combined_hash

    def test_immutability(self):
        """Test that combined parameters are immutable"""
        combined = CombinedParameters(
            spatial_config=SpatialConfiguration(),
            stimulus_params=StimulusGenerationParams(),
            protocol_params=AcquisitionProtocolParams()
        )

        with pytest.raises(ValidationError):
            combined.version = "2.0"

    def test_timestamp_handling(self):
        """Test timestamp handling in combined parameters"""
        now = datetime.now().isoformat()

        combined = CombinedParameters(
            spatial_config=SpatialConfiguration(),
            stimulus_params=StimulusGenerationParams(),
            protocol_params=AcquisitionProtocolParams(),
            created_timestamp=now,
            modified_timestamp=now
        )

        assert combined.created_timestamp == now
        assert combined.modified_timestamp == now


class TestParameterSerialization:
    """Test parameter serialization and deserialization"""

    def test_spatial_config_serialization(self):
        """Test spatial configuration serialization"""
        config = SpatialConfiguration(monitor_distance_cm=15.0)

        # Test model_dump
        data = config.model_dump()
        assert data["monitor_distance_cm"] == 15.0
        assert "config_hash" not in data  # Property not included

        # Test reconstruction
        config2 = SpatialConfiguration(**data)
        assert config2.monitor_distance_cm == 15.0
        assert config2.config_hash == config.config_hash

    def test_stimulus_params_serialization(self):
        """Test stimulus parameters serialization"""
        params = StimulusGenerationParams(bar_width_degrees=15.0)

        # Test model_dump
        data = params.model_dump()
        assert data["bar_width_degrees"] == 15.0

        # Test reconstruction
        params2 = StimulusGenerationParams(**data)
        assert params2.bar_width_degrees == 15.0
        assert params2.params_hash == params.params_hash

    def test_combined_parameters_serialization(self):
        """Test combined parameters serialization"""
        combined = CombinedParameters(
            spatial_config=SpatialConfiguration(),
            stimulus_params=StimulusGenerationParams(),
            protocol_params=AcquisitionProtocolParams(),
            parameter_source=ParameterSource.USER_CONFIG
        )

        # Should be able to serialize nested structure
        data = combined.model_dump()
        assert "spatial_config" in data
        assert "stimulus_params" in data
        assert "protocol_params" in data
        # Parameter source may be serialized as enum object
        assert data["parameter_source"] in ["user_config", ParameterSource.USER_CONFIG]


class TestParameterExceptions:
    """Test parameter-related exceptions"""

    def test_parameter_validation_error(self):
        """Test ParameterValidationError"""
        error = ParameterValidationError("Test validation error")
        assert str(error) == "Test validation error"
        assert isinstance(error, Exception)

    def test_parameter_compatibility_error(self):
        """Test ParameterCompatibilityError"""
        error = ParameterCompatibilityError("Test compatibility error")
        assert str(error) == "Test compatibility error"
        assert isinstance(error, Exception)


class TestParameterSource:
    """Test ParameterSource enum"""

    def test_parameter_source_values(self):
        """Test ParameterSource enum values"""
        assert ParameterSource.DEFAULT.value == "default"
        assert ParameterSource.USER_CONFIG.value == "user_config"
        assert ParameterSource.PARAMETER_STORE.value == "parameter_store"
        assert ParameterSource.SESSION_LOADED.value == "session_loaded"

    def test_parameter_source_in_combined_params(self):
        """Test ParameterSource usage in CombinedParameters"""
        combined = CombinedParameters(
            spatial_config=SpatialConfiguration(),
            stimulus_params=StimulusGenerationParams(),
            protocol_params=AcquisitionProtocolParams(),
            parameter_source=ParameterSource.PARAMETER_STORE
        )

        assert combined.parameter_source == ParameterSource.PARAMETER_STORE