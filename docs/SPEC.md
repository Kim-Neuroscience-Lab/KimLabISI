# ISI Macroscope Control System - Minimal Functional Specification

## Overview
This document specifies a minimal but fully functional implementation of the ISI (Intrinsic Signal Imaging) Macroscope Control System for retinotopic mapping of mouse visual cortex. This specification strips away all architectural complexity while maintaining ALL scientific functionality required for valid experiments.

## Core Scientific Requirements (From Research Literature)

### Based on:
- **Marshel et al. 2011**: Core ISI methodology and stimulus parameters
- **Zhuang et al. 2017**: Visual field sign analysis and area segmentation
- **Kalatsky & Stryker 2003**: Fourier-based retinotopic analysis

## System Components

### Backend Implementation (~2000 lines total Python)

#### 1. **`isi_system.py`** - Main System Controller (~800 lines)

```python
class ISISystem:
    """Core system controller for all ISI operations"""

    def __init__(self):
        self.camera = None  # PCO Panda 4.2 connection
        self.display = None  # RTX 4070 display control
        self.ws_server = None  # WebSocket for frontend
        self.session_state = {}  # Current session data
        self.spatial_config = {}  # Monitor positioning

    # ========== SETUP & CALIBRATION ==========

    def setup_spatial_configuration(self, params):
        """Configure 3D spatial relationship between mouse and monitor

        Args:
            monitor_distance_cm: 10.0 (Marshel et al.)
            monitor_angle_degrees: 20.0 (inward toward nose)
            monitor_height_degrees: 0.0 (eye level)
            screen_width_cm: 52.0
            screen_height_cm: 52.0
            field_of_view_horizontal: 147.0
            field_of_view_vertical: 153.0
        """

    def calibrate_display(self):
        """Calibrate display for accurate stimulus presentation
        - Gamma correction
        - Luminance calibration
        - Refresh rate validation (60 Hz ±10¼s)
        """

    def calibrate_camera(self):
        """Configure PCO Panda camera settings
        - Exposure: 21¼s-5s range
        - Bit depth: 16-bit
        - Resolution: 2048×2048
        - Frame rate: 30 FPS
        """

    # ========== STIMULUS GENERATION ==========

    def generate_drifting_bars(self, direction, params):
        """Generate periodic drifting bar stimulus

        Args:
            direction: 'LR', 'RL', 'TB', or 'BT'
            bar_width_degrees: 20.0 (Marshel et al.)
            drift_speed_degrees_per_sec: 9.0 (8.5-9.5 range)
            num_cycles: 10

        Returns:
            frames: numpy array of stimulus frames
            angles: visual field angles for each frame
            timestamps: microsecond precision timing
        """

    def apply_checkerboard_pattern(self, frames):
        """Add counter-phase checkerboard pattern to bar

        Args:
            checkerboard_size_degrees: 25.0
            flicker_frequency_hz: 6.0 (166ms period)
            contrast: 0.5
        """

    def apply_spherical_correction(self, frames):
        """Apply spherical coordinate transformation
        - Corrects for flat monitor ’ curved visual field
        - Maintains constant spatial frequency
        - Separate corrections for azimuth/elevation
        """

    def save_stimulus_hdf5(self, direction, frames, metadata):
        """Save stimulus as HDF5 dataset

        Structure:
            /frames: uint8 array [n_frames, height, width]
            /angles: float32 array [n_frames] (visual field position)
            /timestamps: int64 array [n_frames] (microseconds)
            /metadata: parameter dictionary
        """

    # ========== HARDWARE CONTROL ==========

    def initialize_camera_pco(self):
        """Initialize PCO Panda 4.2 camera
        - USB 3.1 connection
        - Configure ring buffer
        - Set trigger mode
        """

    def initialize_display_rtx(self):
        """Initialize RTX 4070 display output
        - DirectX 12 exclusive fullscreen
        - Triple buffering setup
        - Hardware timer queries
        """

    def sync_hardware_timestamps(self):
        """Synchronize camera and display timestamps
        - Query RTX 4070 hardware timer
        - Align PCO Panda timestamps
        - Calculate offset and drift
        """

    # ========== ACQUISITION ==========

    def run_acquisition_protocol(self, directions=['LR','RL','TB','BT']):
        """Execute complete ISI acquisition protocol

        For each direction:
        1. Load stimulus HDF5
        2. Start camera recording
        3. Present stimulus at 60 FPS
        4. Record at 30 FPS
        5. Save synchronized data
        """

    def capture_anatomical_image(self):
        """Capture blood vessel pattern with green filter (530nm)
        - High-resolution structural reference
        - Manual filter placement
        """

    def capture_functional_data(self):
        """Capture ISI data with red filter (630nm)
        - Hemodynamic response imaging
        - Continuous recording during stimulus
        """

    def coordinate_stimulus_camera_sync(self):
        """Real-time coordination of display and camera
        - 60 FPS stimulus presentation
        - 30 FPS camera capture
        - Microsecond timestamp alignment
        - Zero dropped frames
        """

    # ========== DATA HANDLING ==========

    def save_acquisition_data(self, session_name):
        """Save all acquisition data

        Structure:
            session_name/
                anatomical.tif (green filter image)
                LR_camera.h5 (camera frames during LR stimulus)
                LR_events.csv (stimulus events with timestamps)
                RL_camera.h5, RL_events.csv
                TB_camera.h5, TB_events.csv
                BT_camera.h5, BT_events.csv
                metadata.json (all parameters)
        """
```

#### 2. **`isi_analysis.py`** - Complete Analysis Pipeline (~600 lines)

```python
class ISIAnalysis:
    """Complete analysis pipeline for ISI data"""

    # ========== PREPROCESSING ==========

    def load_acquisition_data(self, session_path):
        """Load all data from acquisition session"""

    def correlate_temporal_data(self, camera_frames, stimulus_events):
        """Match camera frames to stimulus angles using timestamps
        - Interpolate 30 FPS camera to 60 FPS stimulus timing
        - Account for hemodynamic delay
        """

    def compensate_hemodynamic_delay(self, data):
        """Compensate for blood flow response delay
        - Typically 1-2 seconds after stimulus
        - Different for opposing directions
        """

    # ========== FOURIER ANALYSIS (Kalatsky & Stryker Method) ==========

    def compute_fft_phase_maps(self, frames, stimulus_frequency):
        """Compute phase at stimulus frequency for each pixel

        Args:
            frames: [n_frames, height, width] 16-bit data
            stimulus_frequency: Hz of periodic stimulus

        Returns:
            phase_map: [height, width] phase in radians
            magnitude_map: [height, width] response amplitude
        """

    def bidirectional_analysis(self, forward_phase, reverse_phase):
        """Combine opposing directions to find retinotopic center

        Args:
            forward_phase: Phase map from LR or TB
            reverse_phase: Phase map from RL or BT

        Returns:
            center_map: Estimated center position for each pixel
        """

    # ========== RETINOTOPIC MAPPING ==========

    def generate_azimuth_map(self, LR_phase, RL_phase):
        """Generate horizontal retinotopy (azimuth) map
        - Combine LR and RL phase maps
        - Convert to degrees of visual angle
        - Range: -60° to +60° (mouse visual field)
        """

    def generate_elevation_map(self, TB_phase, BT_phase):
        """Generate vertical retinotopy (elevation) map
        - Combine TB and BT phase maps
        - Convert to degrees of visual angle
        - Range: -30° to +30°
        """

    def convert_to_visual_degrees(self, phase_map, direction):
        """Convert phase to degrees of visual field"""

    # ========== VISUAL FIELD SIGN (Zhuang et al. Method) ==========

    def compute_spatial_gradients(self, azimuth_map, elevation_map):
        """Calculate spatial gradients of retinotopic maps

        Returns:
            d_azimuth_dx, d_azimuth_dy: Horizontal gradients
            d_elevation_dx, d_elevation_dy: Vertical gradients
        """

    def calculate_visual_field_sign(self, gradients):
        """Calculate sign of visual field representation

        VFS = sign(d_azimuth_dx * d_elevation_dy -
                   d_azimuth_dy * d_elevation_dx)

        Returns:
            sign_map: +1 (non-mirror) or -1 (mirror) for each pixel
        """

    def detect_area_boundaries(self, sign_map):
        """Find boundaries where visual field sign reverses
        - Indicates borders between visual areas
        - Use spatial filtering to reduce noise
        """

    def segment_visual_areas(self, sign_map, boundaries):
        """Identify distinct visual areas
        - V1 (primary visual cortex)
        - Higher visual areas (LM, AL, PM, AM, RL, etc.)
        - Each area has consistent sign
        """

    # ========== EXPORT & VISUALIZATION ==========

    def generate_publication_maps(self):
        """Create publication-ready figures
        - Azimuth and elevation maps with colorbars
        - Visual field sign map
        - Area boundaries overlaid
        """

    def overlay_on_anatomy(self, retinotopy, blood_vessels):
        """Overlay functional maps on anatomical image
        - Align retinotopic maps with blood vessel pattern
        - Show area boundaries on anatomy
        """

    def export_results(self, output_path):
        """Export all analysis results
        - Retinotopic maps (HDF5)
        - Area segmentation (HDF5)
        - Publication figures (PNG/PDF)
        - Statistical metrics (CSV)
        """
```

#### 3. **`hardware_mock.py`** - Development Mode (~300 lines)

```python
class MockHardware:
    """Simulated hardware for development and testing"""

    class MockCamera:
        """Simulate PCO Panda camera"""
        def capture(self):
            # Return simulated 16-bit frames
            # Include realistic noise and hemodynamic response

    class MockDisplay:
        """Simulate RTX 4070 display"""
        def present(self, frames):
            # Simulate stimulus presentation
            # Return accurate timestamps

    def generate_mock_isi_data(self):
        """Generate realistic test data
        - Simulated retinotopic responses
        - Multiple visual areas
        - Realistic noise levels
        """

    def simulate_blood_vessels(self):
        """Generate anatomical image with vessel pattern"""
```

#### 4. **`simple_server.py`** - WebSocket Communication (~200 lines)

```python
import asyncio
import websockets
import json

class SimpleServer:
    """Direct WebSocket communication with frontend"""

    async def handle_message(self, websocket, message):
        """Route messages to appropriate handlers"""
        data = json.loads(message)

        if data['type'] == 'setup':
            await self.handle_setup(data['params'])
        elif data['type'] == 'generate_stimulus':
            await self.handle_stimulus(data['params'])
        elif data['type'] == 'start_acquisition':
            await self.handle_acquisition()
        elif data['type'] == 'analyze':
            await self.handle_analysis()

    async def handle_setup(self, params):
        """Configure spatial setup and calibration"""

    async def handle_stimulus(self, params):
        """Generate stimulus with specified parameters"""

    async def handle_acquisition(self):
        """Start data acquisition protocol"""

    async def handle_analysis(self):
        """Run complete analysis pipeline"""

    async def send_progress(self, progress):
        """Send progress updates to frontend"""

    async def send_results(self, results):
        """Send analysis results to frontend"""

async def main():
    """Start WebSocket server on port 8765"""
    async with websockets.serve(handler, "localhost", 8765):
        await asyncio.Future()  # run forever
```

### Frontend Implementation (React)

#### Core Components:

1. **`SetupPanel.jsx`** - Hardware and Spatial Configuration
   - Monitor distance/angle inputs
   - Calibration controls
   - 3D visualization of setup

2. **`StimulusPanel.jsx`** - Stimulus Parameter Control
   - Bar width, speed, directions
   - Number of cycles
   - Preview generation

3. **`AcquisitionPanel.jsx`** - Data Acquisition Control
   - Start/Stop buttons
   - Filter selection (green/red)
   - Live camera preview
   - Progress indicators

4. **`AnalysisPanel.jsx`** - Data Analysis Interface
   - Load session data
   - Run analysis pipeline
   - Progress monitoring

5. **`ResultsViewer.jsx`** - Visualization of Results
   - Retinotopic maps (azimuth/elevation)
   - Visual field sign map
   - Area boundaries
   - Overlay on anatomy

## Data Flow

### 1. Setup Phase
```
Frontend: Configure parameters ’
Backend: Initialize hardware, calibrate ’
Frontend: Show ready status
```

### 2. Stimulus Generation
```
Frontend: Set stimulus parameters ’
Backend: Generate frames, apply corrections, save HDF5 ’
Frontend: Show preview
```

### 3. Acquisition
```
Frontend: Start acquisition ’
Backend: Present stimulus + capture camera ’
Backend: Save synchronized data ’
Frontend: Show live preview and progress
```

### 4. Analysis
```
Frontend: Start analysis ’
Backend: Load data ’ Fourier analysis ’ Retinotopy ’ Area segmentation ’
Frontend: Display results
```

## File Structure

```
/Users/Adam/KimLabISI/apps/
   backend/
      isi_system.py      # Main system controller
      isi_analysis.py    # Analysis pipeline
      hardware_mock.py   # Development mode
      simple_server.py   # WebSocket server
   frontend/
      src/
         SetupPanel.jsx
         StimulusPanel.jsx
         AcquisitionPanel.jsx
         AnalysisPanel.jsx
         ResultsViewer.jsx
      package.json
   data/
       sessions/           # Acquired data storage
```

## Key Simplifications

1. **No Complex Architecture**
   - Direct function calls instead of use cases
   - Simple classes instead of repositories
   - No dependency injection
   - No state machines

2. **No Excessive Validation**
   - Assume correct inputs
   - Basic try/catch for errors
   - No complex error hierarchies

3. **Direct Hardware Control**
   - Simple SDK calls
   - No abstraction layers
   - Direct file I/O

4. **Simple Data Structures**
   - NumPy arrays for images
   - Dictionaries for parameters
   - HDF5 for storage
   - JSON for metadata

## Development Strategy

1. **Phase 1: Mock Mode (Day 1)**
   - Complete pipeline with simulated data
   - Test all algorithms
   - Verify analysis correctness

2. **Phase 2: Real Hardware (Day 2)**
   - Replace mock with actual hardware calls
   - Test timing and synchronization
   - Validate with real mouse data

3. **Phase 3: Polish (Day 3)**
   - UI improvements
   - Performance optimization
   - Documentation

## Critical Success Factors

1. **Correct Science**: Must implement Marshel/Zhuang methods exactly
2. **Timing Precision**: Microsecond synchronization required
3. **Data Integrity**: No dropped frames or corrupted data
4. **Complete Pipeline**: Every step from setup to final maps must work
5. **Usable Interface**: Scientists must be able to operate it easily

## Dependencies

### Python:
- numpy (array operations)
- scipy (FFT analysis)
- h5py (HDF5 storage)
- opencv-python (image processing)
- websockets (frontend communication)
- pillow (image export)

### Frontend:
- react (UI framework)
- websocket (backend communication)
- plotly.js (data visualization)
- three.js (3D setup visualization)

## Testing Requirements

1. **Mock Data Tests**: Verify analysis with known outputs
2. **Timing Tests**: Confirm synchronization precision
3. **End-to-End Tests**: Complete workflow validation
4. **Hardware Tests**: Real device integration (when available)

## Success Metrics

- Generate correct retinotopic maps matching published data
- Identify known visual areas (V1, LM, AL, PM, etc.)
- Process full dataset in < 5 minutes
- Zero dropped frames during acquisition
- Reproducible results across sessions

---

This specification provides a complete, minimal implementation that maintains ALL scientific functionality while removing architectural complexity. The system can perform real ISI experiments and produce publication-quality retinotopic maps.