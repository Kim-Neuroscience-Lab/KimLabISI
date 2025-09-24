"""
Tests for Parameter Entities

Tests the parameter storage, management, and factory components:
- ParameterStore abstract interface and FileBasedParameterStore
- DefaultParameterFactory for Marshel and development defaults
- ParameterManager high-level interface
- Parameter persistence and retrieval
- Parameter validation integration
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch

from src.domain.entities.parameters import (
    ParameterStore,
    FileBasedParameterStore,
    DefaultParameterFactory,
    ParameterManager
)
from src.domain.value_objects.parameters import (
    SpatialConfiguration,
    StimulusGenerationParams,
    AcquisitionProtocolParams,
    CombinedParameters,
    ParameterSource,
    ParameterValidationError
)


class TestFileBasedParameterStore:
    """Test FileBasedParameterStore implementation"""

    def setup_method(self):
        """Setup temporary directory for each test"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.store = FileBasedParameterStore(self.temp_dir)

    def teardown_method(self):
        """Clean up temporary directory"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_store_initialization(self):
        """Test parameter store initialization"""
        assert self.store.storage_directory == self.temp_dir
        assert self.temp_dir.exists()
        assert hasattr(self.store, 'validator')

    def test_save_and_load_parameters(self):
        """Test saving and loading parameters"""
        # Create test parameters
        combined = CombinedParameters(
            spatial_config=SpatialConfiguration(monitor_distance_cm=15.0),
            stimulus_params=StimulusGenerationParams(bar_width_degrees=25.0),
            protocol_params=AcquisitionProtocolParams(num_cycles=5),
            parameter_source=ParameterSource.USER_CONFIG
        )

        # Save parameters
        param_id = "test_params"
        self.store.save_parameters(combined, param_id)

        # Verify file exists
        expected_file = self.temp_dir / f"{param_id}.json"
        assert expected_file.exists()

        # Load parameters
        loaded = self.store.load_parameters(param_id)

        # Verify loaded parameters match
        assert loaded.spatial_config.monitor_distance_cm == 15.0
        assert loaded.stimulus_params.bar_width_degrees == 25.0
        assert loaded.protocol_params.num_cycles == 5
        assert loaded.parameter_source == ParameterSource.USER_CONFIG

    def test_load_nonexistent_parameters(self):
        """Test loading nonexistent parameters raises error"""
        with pytest.raises(ParameterValidationError) as excinfo:
            self.store.load_parameters("nonexistent")
        assert "not found" in str(excinfo.value)

    def test_list_parameter_sets(self):
        """Test listing parameter sets"""
        # Initially empty
        assert self.store.list_parameter_sets() == []

        # Save some parameters
        combined = CombinedParameters(
            spatial_config=SpatialConfiguration(),
            stimulus_params=StimulusGenerationParams(),
            protocol_params=AcquisitionProtocolParams()
        )

        self.store.save_parameters(combined, "set1")
        self.store.save_parameters(combined, "set2")

        # Should list both sets
        sets = self.store.list_parameter_sets()
        assert "set1" in sets
        assert "set2" in sets
        assert len(sets) == 2

    def test_delete_parameter_set(self):
        """Test deleting parameter sets"""
        # Save parameters
        combined = CombinedParameters(
            spatial_config=SpatialConfiguration(),
            stimulus_params=StimulusGenerationParams(),
            protocol_params=AcquisitionProtocolParams()
        )

        self.store.save_parameters(combined, "to_delete")
        assert "to_delete" in self.store.list_parameter_sets()

        # Delete parameters
        self.store.delete_parameter_set("to_delete")
        assert "to_delete" not in self.store.list_parameter_sets()

    def test_delete_nonexistent_parameters(self):
        """Test deleting nonexistent parameters raises error"""
        with pytest.raises(ParameterValidationError) as excinfo:
            self.store.delete_parameter_set("nonexistent")
        assert "not found" in str(excinfo.value)

    def test_save_includes_metadata(self):
        """Test that saved parameters include metadata"""
        combined = CombinedParameters(
            spatial_config=SpatialConfiguration(),
            stimulus_params=StimulusGenerationParams(),
            protocol_params=AcquisitionProtocolParams()
        )

        self.store.save_parameters(combined, "test_metadata")

        # Load raw JSON to check metadata
        json_file = self.temp_dir / "test_metadata.json"
        with open(json_file, 'r') as f:
            data = json.load(f)

        assert "metadata" in data
        assert "generation_hash" in data["metadata"]
        assert "combined_hash" in data["metadata"]
        assert "created_timestamp" in data
        assert "modified_timestamp" in data

    @patch('src.domain.services.parameter_validator.ParameterValidator.validate_combined_parameters')
    def test_save_invalid_parameters_fails(self, mock_validate):
        """Test that saving invalid parameters fails"""
        mock_validate.return_value = (False, ["Test validation error"])

        combined = CombinedParameters(
            spatial_config=SpatialConfiguration(),
            stimulus_params=StimulusGenerationParams(),
            protocol_params=AcquisitionProtocolParams()
        )

        with pytest.raises(ParameterValidationError) as excinfo:
            self.store.save_parameters(combined, "invalid")
        assert "invalid parameters" in str(excinfo.value)

    def test_corrupted_json_handling(self):
        """Test handling of corrupted JSON files"""
        # Create corrupted JSON file
        corrupted_file = self.temp_dir / "corrupted.json"
        with open(corrupted_file, 'w') as f:
            f.write("{ invalid json }")

        with pytest.raises(ParameterValidationError) as excinfo:
            self.store.load_parameters("corrupted")
        assert "Failed to load parameter set" in str(excinfo.value)


class TestDefaultParameterFactory:
    """Test DefaultParameterFactory"""

    def test_create_marshel_2011_defaults(self):
        """Test creating Marshel 2011 default parameters"""
        params = DefaultParameterFactory.create_marshel_2011_defaults()

        # Verify parameter structure
        assert isinstance(params, CombinedParameters)
        assert params.parameter_source == ParameterSource.DEFAULT
        assert params.version == "1.0"

        # Verify Marshel values
        spatial = params.spatial_config
        assert spatial.monitor_distance_cm == 10.0
        assert spatial.monitor_angle_degrees == 20.0
        assert spatial.field_of_view_horizontal_degrees == 147.0
        assert spatial.field_of_view_vertical_degrees == 153.0

        stimulus = params.stimulus_params
        assert stimulus.bar_width_degrees == 20.0
        assert stimulus.drift_speed_degrees_per_sec == 9.0
        assert stimulus.checkerboard_size_degrees == 25.0
        assert stimulus.flicker_frequency_hz == 6.0

        protocol = params.protocol_params
        assert protocol.num_cycles == 10
        assert protocol.frame_rate == 60.0

    def test_create_development_defaults(self):
        """Test creating development default parameters"""
        params = DefaultParameterFactory.create_development_defaults()

        # Verify parameter structure
        assert isinstance(params, CombinedParameters)
        assert params.parameter_source == ParameterSource.DEFAULT

        # Verify development values (should be faster/smaller)
        spatial = params.spatial_config
        assert spatial.screen_width_pixels == 800  # Lower resolution
        assert spatial.screen_height_pixels == 600
        assert spatial.field_of_view_horizontal_degrees == 30.0  # Smaller field

        stimulus = params.stimulus_params
        assert stimulus.bar_width_degrees == 5.0  # Narrower bar
        assert stimulus.drift_speed_degrees_per_sec == 15.0  # Faster drift
        assert stimulus.checkerboard_size_degrees == 5.0  # Smaller checkerboard

        protocol = params.protocol_params
        assert protocol.num_cycles == 2  # Fewer cycles
        assert protocol.frame_rate == 30.0  # Lower frame rate

    def test_marshel_vs_development_differences(self):
        """Test that Marshel and development defaults are different"""
        marshel = DefaultParameterFactory.create_marshel_2011_defaults()
        dev = DefaultParameterFactory.create_development_defaults()

        # Should have different generation hashes
        assert marshel.generation_hash != dev.generation_hash

        # Key parameters should be different
        assert marshel.spatial_config.screen_width_pixels != dev.spatial_config.screen_width_pixels
        assert marshel.stimulus_params.bar_width_degrees != dev.stimulus_params.bar_width_degrees
        assert marshel.protocol_params.num_cycles != dev.protocol_params.num_cycles

    def test_parameter_timestamps(self):
        """Test that created parameters have timestamps"""
        before = datetime.now()
        params = DefaultParameterFactory.create_marshel_2011_defaults()
        after = datetime.now()

        assert params.created_timestamp is not None
        created_time = datetime.fromisoformat(params.created_timestamp)
        assert before <= created_time <= after


class TestParameterManager:
    """Test ParameterManager high-level interface"""

    def setup_method(self):
        """Setup temporary directory for each test"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.manager = ParameterManager(self.temp_dir)

    def teardown_method(self):
        """Clean up temporary directory"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_manager_initialization(self):
        """Test parameter manager initialization"""
        assert isinstance(self.manager.parameter_store, FileBasedParameterStore)
        assert hasattr(self.manager, 'validator')

    def test_defaults_created_on_init(self):
        """Test that default parameter sets are created on initialization"""
        available = self.manager.list_available_parameters()
        assert "marshel_2011_defaults" in available
        assert "development_defaults" in available

    def test_get_marshel_defaults(self):
        """Test getting Marshel defaults"""
        params = self.manager.get_marshel_defaults()

        assert isinstance(params, CombinedParameters)
        assert params.spatial_config.monitor_distance_cm == 10.0
        assert params.stimulus_params.bar_width_degrees == 20.0

    def test_get_development_defaults(self):
        """Test getting development defaults"""
        params = self.manager.get_development_defaults()

        assert isinstance(params, CombinedParameters)
        assert params.spatial_config.screen_width_pixels == 800
        assert params.stimulus_params.bar_width_degrees == 5.0

    def test_get_parameters_by_id(self):
        """Test getting parameters by ID"""
        # Should be able to get marshel defaults by ID
        params = self.manager.get_parameters("marshel_2011_defaults")
        assert params.stimulus_params.bar_width_degrees == 20.0

        # Should be able to get development defaults by ID
        params = self.manager.get_parameters("development_defaults")
        assert params.stimulus_params.bar_width_degrees == 5.0

    def test_save_custom_parameters(self):
        """Test saving custom parameters"""
        custom_params = CombinedParameters(
            spatial_config=SpatialConfiguration(monitor_distance_cm=12.0),
            stimulus_params=StimulusGenerationParams(bar_width_degrees=15.0),
            protocol_params=AcquisitionProtocolParams(num_cycles=8),
            parameter_source=ParameterSource.USER_CONFIG
        )

        self.manager.save_parameters(custom_params, "custom_set")

        # Should be able to retrieve custom parameters
        loaded = self.manager.get_parameters("custom_set")
        assert loaded.spatial_config.monitor_distance_cm == 12.0
        assert loaded.stimulus_params.bar_width_degrees == 15.0
        assert loaded.protocol_params.num_cycles == 8

    def test_validate_parameters(self):
        """Test parameter validation"""
        params = self.manager.get_marshel_defaults()

        validation = self.manager.validate_parameters(params)

        assert "is_valid" in validation
        assert "warnings" in validation
        assert "literature_compliance" in validation
        assert "generation_hash" in validation
        assert "combined_hash" in validation

        # Marshel defaults should be valid
        assert validation["is_valid"] == True

    def test_list_available_parameters(self):
        """Test listing available parameters"""
        available = self.manager.list_available_parameters()

        assert isinstance(available, list)
        assert "marshel_2011_defaults" in available
        assert "development_defaults" in available

    @patch('src.domain.entities.parameters.logger')
    def test_defaults_creation_failure_handling(self, mock_logger):
        """Test handling of defaults creation failure"""
        # Create a manager with a read-only directory to simulate failure
        import os
        readonly_dir = self.temp_dir / "readonly"
        readonly_dir.mkdir()
        os.chmod(readonly_dir, 0o444)  # Read-only

        try:
            # This should handle the exception gracefully
            ParameterManager(readonly_dir)
            # Logger should have been called with warning
            mock_logger.warning.assert_called()
        finally:
            # Restore permissions for cleanup
            os.chmod(readonly_dir, 0o755)

    def test_get_nonexistent_parameters(self):
        """Test getting nonexistent parameters raises error"""
        with pytest.raises(ParameterValidationError):
            self.manager.get_parameters("nonexistent_set")

    @patch('src.domain.services.parameter_validator.ParameterValidator.validate_combined_parameters')
    def test_validation_warnings_logged(self, mock_validate):
        """Test that validation warnings are logged"""
        mock_validate.return_value = (True, ["Test warning"])

        with patch('src.domain.entities.parameters.logger') as mock_logger:
            self.manager.get_parameters("marshel_2011_defaults")
            mock_logger.warning.assert_called()


class TestParameterStoreInterface:
    """Test ParameterStore abstract interface"""

    def test_parameter_store_is_abstract(self):
        """Test that ParameterStore cannot be instantiated directly"""
        with pytest.raises(TypeError):
            ParameterStore()

    def test_file_based_store_implements_interface(self):
        """Test that FileBasedParameterStore implements the interface"""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            store = FileBasedParameterStore(temp_dir)
            assert isinstance(store, ParameterStore)

            # Should have all required methods
            assert hasattr(store, 'load_parameters')
            assert hasattr(store, 'save_parameters')
            assert hasattr(store, 'list_parameter_sets')
            assert hasattr(store, 'delete_parameter_set')
        finally:
            import shutil
            shutil.rmtree(temp_dir)


class TestParameterPersistence:
    """Test parameter persistence edge cases"""

    def setup_method(self):
        """Setup temporary directory for each test"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.store = FileBasedParameterStore(self.temp_dir)

    def teardown_method(self):
        """Clean up temporary directory"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_timestamp_update_on_save(self):
        """Test that modified timestamp is updated on save"""
        combined = CombinedParameters(
            spatial_config=SpatialConfiguration(),
            stimulus_params=StimulusGenerationParams(),
            protocol_params=AcquisitionProtocolParams(),
            created_timestamp=datetime.now().isoformat()
        )

        # Save initially
        import time
        time.sleep(0.01)  # Small delay to ensure different timestamps
        self.store.save_parameters(combined, "timestamp_test")

        # Load and check timestamps
        loaded = self.store.load_parameters("timestamp_test")
        assert loaded.created_timestamp is not None
        assert loaded.modified_timestamp is not None
        assert loaded.created_timestamp != loaded.modified_timestamp

    def test_parameter_source_preservation(self):
        """Test that parameter source is preserved through save/load"""
        for source in ParameterSource:
            combined = CombinedParameters(
                spatial_config=SpatialConfiguration(),
                stimulus_params=StimulusGenerationParams(),
                protocol_params=AcquisitionProtocolParams(),
                parameter_source=source
            )

            param_id = f"test_{source.value}"
            self.store.save_parameters(combined, param_id)
            loaded = self.store.load_parameters(param_id)

            assert loaded.parameter_source == source

    def test_version_handling(self):
        """Test version handling in parameters"""
        combined = CombinedParameters(
            spatial_config=SpatialConfiguration(),
            stimulus_params=StimulusGenerationParams(),
            protocol_params=AcquisitionProtocolParams(),
            version="2.0"
        )

        self.store.save_parameters(combined, "version_test")
        loaded = self.store.load_parameters("version_test")

        assert loaded.version == "2.0"