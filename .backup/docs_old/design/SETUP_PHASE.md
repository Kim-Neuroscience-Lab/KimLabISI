# Setup Phase

## Overview

The Setup Phase provides an interactive 3D visualization interface for configuring the spatial relationship between the mouse and stimulus monitor. This phase ensures that software parameters accurately represent the real-world physical experimental setup, which is critical for accurate ISI retinotopic mapping.

## Scope Definition

### Setup Phase Focus: Spatial Geometry Configuration

The Setup Phase is specifically concerned with:
- **3D spatial positioning** of monitor relative to mouse
- **Visual field geometry** and stimulus coverage validation
- **Spherical coordinate system** parameter definition
- **Real-time visualization** to match software to physical setup

### What Setup Phase Does NOT Include

**Hardware Verification** (separate workflow concern):
- PCO Panda 4.2 USB connection testing
- RTX 4070 display driver validation
- Storage system accessibility checks

**Session Configuration** (separate workflow concern):
- Session naming and data storage paths
- Protocol parameters (repetitions, trial timing)
- Experimental metadata entry

**Calibration** (separate workflow concern):
- Display gamma/color calibration
- Camera focus and exposure settings
- Hardware timing synchronization

## 3D Visualization Interface

### Three.js Implementation

**Interactive 3D Scene Components:**
- **WebGL Rendering**: Hardware-accelerated 3D visualization in Electron renderer
- **Real-time Updates**: Parameter changes immediately reflected in 3D view
- **Multiple Viewing Angles**: Orbital camera controls for comprehensive visualization
- **Measurement Overlays**: Distance and angle measurements displayed in 3D space

**3D Model Components:**
```
3D Scene Hierarchy:
├── Mouse Model (at origin)
│   ├── Body representation with anatomical orientation
│   ├── Eye position markers (left/right)
│   └── Visual field projection cones
├── Monitor Model
│   ├── Rectangular display surface
│   ├── Position/rotation controls
│   └── Visual field coverage visualization
├── Coordinate System
│   ├── Spherical coordinate grid
│   ├── Cartesian axes reference
│   └── Visual field mapping overlay
└── Measurement Annotations
    ├── Distance rulers
    ├── Angle indicators
    └── Coverage area highlights
```

### Interactive Parameter Controls

**Monitor Distance Configuration:**
- **Control**: Slider and numeric input (range: 5-20 cm)
- **Default**: 10 cm (Marshel 2011 reference value)
- **Visualization**: Real-time distance measurement in 3D scene
- **Information**: Distance affects visual field coverage and pixel-to-degree mapping

**Monitor Angle Configuration:**
- **Control**: 3D rotation gizmo and numeric inputs
- **Default**: 20° inward toward nose (ISI standard reference from literature)
- **Axes**: Pitch, yaw, roll adjustment with visual feedback
- **Visualization**: Monitor orientation updates in real-time

**Monitor Height Configuration:**
- **Control**: Vertical position slider relative to mouse eye level
- **Default**: Eye-level alignment (0° elevation)
- **Range**: ±15° elevation adjustment
- **Visualization**: Height indicator with mouse eye reference

**Visual Field Coverage Preview:**
- **Coverage Area**: Real-time preview of stimulus bar sweep coverage
- **Field Boundaries**: Configurable coverage area visualization
- **Coverage Display**: Shows areas covered by stimulus with current configuration
- **Reference Info**: Literature values (153° vertical, 147° horizontal from Marshel 2011)

## Spatial Configuration Parameters

### Core Geometric Parameters

**Monitor-to-Mouse Geometry:**
```
Spatial Configuration:
- Distance: 10.0 cm (Marshel 2011 default, user configurable: 5-20 cm)
- Angle: 20.0° inward toward nose (literature default, user configurable: 0-45°)
- Height: 0.0° elevation (eye-level default, user configurable: ±15°)
- Rotation: 0.0° roll (neutral default, user configurable: ±10°)
```

**Visual Field Mapping:**
- **Coordinate Origin**: Mouse eye position as (0°, 0°) reference
- **Azimuth Range**: ±73.5° horizontal coverage
- **Elevation Range**: ±76.5° vertical coverage
- **Eccentricity**: Calculated from spherical coordinate transformation

**Spherical Coordinate System:**
- **Theta (θ)**: Altitude/elevation angle (vertical retinotopy)
- **Phi (φ)**: Azimuth angle (horizontal retinotopy)
- **Radius**: Constant at monitor distance
- **Transform**: Spherical → Cartesian mapping for flat monitor display

### Parameter Information and Ranges

**Distance Range:**
- **Range**: 5-20 cm (practical limits for typical setups)
- **Reference**: 10 cm (Marshel 2011 - beyond "infinite focus" point)
- **Effect**: Distance affects visual field coverage and stimulus angular size
- **Display**: Real-time coverage area shown in 3D visualization

**Angle Range:**
- **Range**: 0-45° inward toward nose, ±15° elevation, ±10° roll
- **Reference**: 20° inward (ISI standard orientation from literature)
- **Effect**: Angle affects spherical coordinate transformation
- **Display**: Real-time orientation shown with coordinate grid overlay

**Coverage Information:**
- **Display**: Real-time coverage percentage and area visualization
- **Reference**: 147°H × 153°V (Marshel 2011 full hemifield coverage)
- **User Choice**: Coverage requirements depend on experimental goals
- **Calculation**: Coverage computed from current spatial configuration

## Spherical Coordinate System Integration

### ISI Retinotopic Mapping Coordinate System

**Coordinate System Definition:**
- **Origin**: Mouse eye position (anatomical center)
- **Reference Plane**: Horizontal plane through eye level
- **Perpendicular Bisector**: 0° azimuth, 0° elevation reference line
- **Monitor Surface**: Tangent plane in spherical coordinate space

**Spherical-to-Cartesian Transformation:**
```
Mathematical Relationship:
S(θ,φ) → Monitor(x,y)

Where:
- θ = elevation angle (vertical position on retina)
- φ = azimuth angle (horizontal position on retina)
- Distance = constant radius in spherical system
- Transform maintains constant spatial frequency across visual field
```

**Real-time Transformation Preview:**
- **Grid Overlay**: Spherical coordinate grid projected onto monitor
- **Distortion Visualization**: Shows how rectangular stimulus appears in visual field
- **Correction Preview**: Demonstrates spherical correction effect on stimulus bars
- **Information**: Shows how spatial configuration affects coordinate transformation

### Integration with Stimulus Generation

**Parameter Export to [Generation Phase](./STIMULUS_GENERATION.md):**
- **Spatial Configuration**: Complete geometric parameter set
- **Transformation Matrix**: Spherical-to-cartesian conversion parameters
- **Coverage Map**: Visual field coverage validation results
- **Quality Metrics**: Setup validation and adequacy scores

**Stimulus Generation Dependencies:**
- **Bar Width**: Adjusted for spherical coordinate system (20° visual angle)
- **Correction Curves**: Altitude/azimuth correction based on monitor geometry
- **Coverage Validation**: Ensures generated stimuli cover configured visual field
- **Frame Resolution**: Pixel-to-degree mapping based on monitor distance/size

## 3D Visualization Features

### Interactive Viewing Controls

**Camera Navigation:**
- **Orbital Controls**: Mouse drag to rotate around experimental setup
- **Zoom**: Mouse wheel for distance adjustment
- **Pan**: Right-click drag for scene translation
- **Reset Views**: Preset camera positions (front, side, top, perspective)

**Visual Aids:**
- **Grid Reference**: Floor grid for spatial orientation
- **Measurement Tools**: Real-time distance and angle measurements
- **Transparency Controls**: See-through models for internal geometry
- **Lighting**: Proper 3D lighting for depth perception

**Model Interaction:**
- **Monitor Manipulation**: Direct 3D gizmo controls for position/rotation
- **Parameter Feedback**: Visual parameter values updated during interaction
- **Constraint Visualization**: Show valid parameter ranges in 3D
- **Collision Detection**: Prevent unrealistic configurations

### Real-time Information Display

**Measurement Indicators:**
- **Current Values**: Real-time display of distance, angles, and coverage
- **Reference Comparison**: Show how current values compare to literature defaults
- **Coverage Visualization**: Visual representation of stimulus coverage area
- **Transform Display**: Real-time spherical coordinate grid and mapping

**Information Systems:**
- **Literature References**: Display reference values from Marshel 2011 and other papers
- **Parameter Effects**: Show how changes affect coverage and coordinate mapping
- **Measurement Precision**: Display current measurement accuracy
- **Configuration Summary**: Current spatial parameter summary

## Configuration Management

### Save and Load Functionality

**Configuration Persistence:**
- **Auto-save**: Continuous saving of parameter changes
- **Named Configurations**: Save multiple setup configurations for different experiments
- **Import/Export**: JSON-based configuration file format
- **Version Control**: Track configuration changes over time

**Configuration File Format:**
```json
{
  "setup_configuration": {
    "version": "1.0",
    "timestamp": "2024-03-15T14:30:45Z",
    "monitor_geometry": {
      "distance_cm": 10.0,
      "angle_degrees": 20.0,
      "height_degrees": 0.0,
      "roll_degrees": 0.0
    },
    "visual_field": {
      "coverage_horizontal": 147.0,
      "coverage_vertical": 153.0,
      "quality_score": 0.95
    },
    "spherical_transform": {
      "origin": [0.0, 0.0, 0.0],
      "reference_plane": "horizontal",
      "transform_matrix": [...],
      "validation_passed": true
    }
  }
}
```

### Workflow Integration

**Setup Completion:**
- **Parameter Confirmation**: User confirms spatial configuration matches physical setup
- **Coverage Review**: User reviews stimulus coverage area for their experimental needs
- **Transform Confirmation**: User confirms spherical coordinate mapping is appropriate
- **Ready for Generation**: User indicates setup is complete and ready to proceed

**Transition to [Generation Phase](./STIMULUS_GENERATION.md):**
- **Parameter Export**: User-confirmed spatial configuration passed to stimulus generation
- **Configuration Lock**: Setup parameters locked during generation to maintain consistency
- **Change Detection**: System tracks if spatial configuration is modified
- **Resume Capability**: Return to Setup phase for reconfiguration at any time

## Hardware Integration Considerations

### Display Hardware Awareness

**Monitor Specifications:**
- **Physical Size**: Actual monitor dimensions for accurate spatial calculations
- **Resolution**: Pixel-to-degree mapping for stimulus generation
- **Refresh Rate**: 60 Hz capability validation for stimulus presentation
- **Color Gamut**: Display capability assessment for stimulus quality

**RTX 4070 Integration:**
- **3D Acceleration**: Leverage GPU for smooth Three.js rendering
- **Real-time Performance**: Maintain 60 FPS visualization during parameter adjustment
- **Memory Efficiency**: Optimize 3D scene for VRAM usage within budget
- **DirectX Integration**: Coordinate with display control system

### Cross-Platform Considerations

**Development vs Production:**
- **macOS Development**: Metal backend for Three.js rendering
- **Windows Production**: DirectX/OpenGL backend optimization
- **Performance Parity**: Ensure consistent 3D visualization across platforms
- **Hardware Abstraction**: Abstract spatial calculations from rendering backend

## User Experience Design

### Intuitive Interface Elements

**Parameter Input Methods:**
- **Sliders**: For continuous parameter adjustment with immediate feedback
- **Numeric Inputs**: For precise value entry with validation
- **3D Gizmos**: Direct manipulation of monitor position in 3D space
- **Preset Buttons**: Common configurations for quick setup

**Visual Feedback Systems:**
- **Real-time Measurements**: Distance and angle values updated during interaction
- **Coverage Indicators**: Visual representation of stimulus coverage quality
- **Validation Messages**: Clear indication of configuration validity
- **Progress Indicators**: Setup completion status and next steps

**Help and Guidance:**
- **Interactive Tooltips**: Parameter explanation and recommended values
- **Setup Wizard**: Guided configuration for new users
- **Video Tutorials**: Embedded help for complex spatial configuration
- **Reference Images**: Photos of actual experimental setups for comparison

### Error Prevention and Recovery

**Input Range Limits:**
- **Physical Limits**: Prevent impossible values (negative distances, etc.)
- **Real-time Updates**: Immediate display of measurement changes
- **User Freedom**: Allow any reasonable configuration within physical limits
- **Undo/Redo**: Configuration change history for easy correction

**Configuration Management:**
- **Literature Defaults**: Reset to reference paper values (Marshel 2011, etc.)
- **Last Session**: Restore previous user configuration
- **Import/Export**: Load and save user configuration files
- **Multiple Setups**: Save different configurations for different experiments

## Integration with Analysis Pipeline

### Spatial Parameter Handoff

**Analysis Dependencies:**
- **Spherical Correction**: Setup parameters required for stimulus generation spherical correction
- **Visual Field Mapping**: Spatial configuration affects retinotopic coordinate calculation
- **Coverage Information**: Setup configuration informs analysis interpretation
- **Geometric Consistency**: Ensure spatial parameters consistent across workflow phases

**Data Correlation:**
- **Spatial Metadata**: Setup configuration saved with acquisition session
- **Configuration Record**: Complete spatial parameter history included with data
- **Parameter Documentation**: Setup choices documented for analysis interpretation
- **Reproducibility**: Ensure analysis results reproducible with same spatial configuration

The Setup Phase provides the essential spatial foundation for accurate ISI retinotopic mapping by ensuring precise correspondence between the software spatial model and the physical experimental configuration.