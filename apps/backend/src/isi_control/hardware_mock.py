"""
Mock Hardware for ISI System Development
Simulates PCO Panda camera and RTX 4070 display for testing
"""

import numpy as np
import time
from typing import Tuple, List, Dict, Optional
import json

class MockCamera:
    """Simulate PCO Panda 4.2 camera with realistic ISI responses"""

    def __init__(self):
        self.resolution = (2048, 2048)
        self.bit_depth = 16
        self.fps = 30
        self.exposure_time = 0.001  # 1ms default
        self.is_recording = False
        self.frame_count = 0
        self.timestamps = []

    def initialize(self) -> bool:
        """Initialize mock camera"""
        print("Mock Camera: Initialized PCO Panda 4.2")
        print(f"  Resolution: {self.resolution}")
        print(f"  Bit depth: {self.bit_depth}")
        print(f"  Frame rate: {self.fps} FPS")
        return True

    def set_exposure(self, exposure_ms: float):
        """Set exposure time in milliseconds"""
        self.exposure_time = exposure_ms / 1000.0
        print(f"Mock Camera: Exposure set to {exposure_ms}ms")

    def start_recording(self):
        """Start recording frames"""
        self.is_recording = True
        self.frame_count = 0
        self.timestamps = []
        print("Mock Camera: Recording started")

    def stop_recording(self):
        """Stop recording frames"""
        self.is_recording = False
        print(f"Mock Camera: Recording stopped. Captured {self.frame_count} frames")

    def capture_frame(self, stimulus_angle: Optional[float] = None) -> Tuple[np.ndarray, int]:
        """
        Capture a single frame with simulated hemodynamic response

        Args:
            stimulus_angle: Current visual field angle of stimulus (for ISI simulation)

        Returns:
            frame: 16-bit image array
            timestamp: Microsecond timestamp
        """
        if not self.is_recording:
            return None, None

        # Generate base anatomical image with blood vessels
        frame = self._generate_anatomical_frame()

        # Add hemodynamic response if stimulus angle provided
        if stimulus_angle is not None:
            frame = self._add_hemodynamic_response(frame, stimulus_angle)

        # Add realistic noise
        noise = np.random.normal(0, 100, self.resolution).astype(np.int16)
        frame = np.clip(frame + noise, 0, 65535).astype(np.uint16)

        # Generate timestamp
        timestamp = int(time.time() * 1e6)  # Microseconds

        self.frame_count += 1
        self.timestamps.append(timestamp)

        return frame, timestamp

    def _generate_anatomical_frame(self) -> np.ndarray:
        """Generate realistic blood vessel pattern"""
        # Create base intensity
        base = np.ones(self.resolution, dtype=np.float32) * 30000

        # Add blood vessel pattern using sinusoidal functions
        x = np.linspace(0, 10*np.pi, self.resolution[1])
        y = np.linspace(0, 10*np.pi, self.resolution[0])
        X, Y = np.meshgrid(x, y)

        # Create vessel-like patterns
        vessels = np.sin(X/2) * np.cos(Y/3) * 5000
        vessels += np.sin(X/3 + np.pi/4) * np.sin(Y/2) * 3000
        vessels += np.cos(X/4) * np.cos(Y/4 - np.pi/3) * 2000

        frame = base + vessels
        return frame.astype(np.uint16)

    def _add_hemodynamic_response(self, frame: np.ndarray, stimulus_angle: float) -> np.ndarray:
        """
        Add simulated hemodynamic response based on stimulus position

        Creates realistic retinotopic responses in different visual areas
        """
        h, w = self.resolution

        # Create coordinate grids
        x = np.linspace(-1, 1, w)
        y = np.linspace(-1, 1, h)
        X, Y = np.meshgrid(x, y)

        # Simulate V1 response (primary visual cortex)
        # V1 is centered and responds to stimulus angle
        v1_center = (0, 0)
        v1_response = self._create_area_response(X, Y, v1_center, stimulus_angle, size=0.3)

        # Simulate higher visual areas with different retinotopic organizations
        # LM (lateromedial area) - lateral and slightly anterior
        lm_center = (-0.4, 0.2)
        lm_response = self._create_area_response(X, Y, lm_center, -stimulus_angle, size=0.2)

        # AL (anterolateral area) - anterior and lateral
        al_center = (-0.3, 0.5)
        al_response = self._create_area_response(X, Y, al_center, stimulus_angle * 0.8, size=0.15)

        # PM (posteromedial area) - posterior and medial
        pm_center = (0.3, -0.3)
        pm_response = self._create_area_response(X, Y, pm_center, -stimulus_angle * 1.2, size=0.2)

        # Combine all responses with appropriate delays (hemodynamic lag)
        total_response = (v1_response * 0.5 +
                         lm_response * 0.3 +
                         al_response * 0.2 +
                         pm_response * 0.2)

        # Apply hemodynamic response function (delayed and smoothed)
        # Typical delay is 1-2 seconds, we simulate this with scaling
        response_amplitude = 2000 * (1 - np.exp(-self.frame_count / (self.fps * 1.5)))

        # Subtract response (blood flow decreases reflectance)
        frame = frame.astype(np.float32)
        frame -= total_response * response_amplitude

        return np.clip(frame, 0, 65535).astype(np.uint16)

    def _create_area_response(self, X: np.ndarray, Y: np.ndarray,
                             center: Tuple[float, float],
                             stimulus_angle: float,
                             size: float = 0.2) -> np.ndarray:
        """
        Create response for a single visual area

        Args:
            X, Y: Coordinate grids
            center: Center of the visual area
            stimulus_angle: Current stimulus position in visual field
            size: Size of the visual area

        Returns:
            Response map for this area
        """
        # Distance from area center
        dist = np.sqrt((X - center[0])**2 + (Y - center[1])**2)

        # Area mask (Gaussian falloff)
        area_mask = np.exp(-(dist**2) / (2 * size**2))

        # Retinotopic gradient within area
        # Different areas have different retinotopic organizations
        angle_map = np.arctan2(Y - center[1], X - center[0])

        # Response based on stimulus position
        # Peak response when stimulus matches retinotopic position
        angle_diff = np.abs(angle_map - np.radians(stimulus_angle))
        angle_diff = np.minimum(angle_diff, 2*np.pi - angle_diff)  # Wrap around

        response = np.exp(-(angle_diff**2) / (2 * (np.pi/4)**2))

        return area_mask * response


class MockDisplay:
    """Simulate RTX 4070 display output"""

    def __init__(self):
        self.resolution = (1920, 1080)  # Display resolution
        self.fps = 60
        self.is_presenting = False
        self.frame_count = 0
        self.frame_times = []

    def initialize(self) -> bool:
        """Initialize mock display"""
        print("Mock Display: Initialized RTX 4070")
        print(f"  Resolution: {self.resolution}")
        print(f"  Frame rate: {self.fps} FPS")
        return True

    def start_presentation(self):
        """Start stimulus presentation"""
        self.is_presenting = True
        self.frame_count = 0
        self.frame_times = []
        print("Mock Display: Presentation started")

    def stop_presentation(self):
        """Stop stimulus presentation"""
        self.is_presenting = False
        print(f"Mock Display: Presentation stopped. Presented {self.frame_count} frames")

    def present_frame(self, frame: np.ndarray) -> int:
        """
        Present a stimulus frame

        Args:
            frame: Stimulus frame to display

        Returns:
            timestamp: Microsecond timestamp of presentation
        """
        if not self.is_presenting:
            return None

        # Simulate frame presentation timing
        timestamp = int(time.time() * 1e6)  # Microseconds

        # Simulate consistent 60 FPS timing
        if self.frame_times:
            target_time = self.frame_times[-1] + (1.0/self.fps * 1e6)
            if timestamp < target_time:
                # Would normally wait here, but for mock we just adjust timestamp
                timestamp = int(target_time)

        self.frame_count += 1
        self.frame_times.append(timestamp)

        return timestamp

    def query_hardware_timer(self) -> int:
        """Query high-precision hardware timer"""
        return int(time.time() * 1e6)  # Microseconds


class MockHardware:
    """Complete mock hardware system for ISI development"""

    def __init__(self):
        self.camera = MockCamera()
        self.display = MockDisplay()
        self.is_initialized = False

    def initialize(self) -> bool:
        """Initialize all mock hardware"""
        print("\n=== Initializing Mock Hardware ===")
        camera_ok = self.camera.initialize()
        display_ok = self.display.initialize()
        self.is_initialized = camera_ok and display_ok
        print(f"Mock Hardware: Initialization {'successful' if self.is_initialized else 'failed'}\n")
        return self.is_initialized

    def shutdown(self):
        """Shutdown mock hardware"""
        if self.camera.is_recording:
            self.camera.stop_recording()
        if self.display.is_presenting:
            self.display.stop_presentation()
        print("Mock Hardware: Shutdown complete")

    def generate_test_session(self, output_dir: str = "data/sessions/test"):
        """
        Generate a complete test session with realistic ISI data

        Creates stimulus files and simulated camera data for all directions
        """
        import os
        import h5py

        os.makedirs(output_dir, exist_ok=True)
        print(f"\nGenerating test session in {output_dir}")

        directions = ['LR', 'RL', 'TB', 'BT']

        for direction in directions:
            print(f"\nGenerating data for {direction} direction...")

            # Generate stimulus frames
            stimulus_frames, angles = self._generate_stimulus_frames(direction)

            # Save stimulus file
            stimulus_path = os.path.join(output_dir, f"{direction}_stimulus.h5")
            with h5py.File(stimulus_path, 'w') as f:
                f.create_dataset('frames', data=stimulus_frames)
                f.create_dataset('angles', data=angles)
                f.attrs['direction'] = direction
                f.attrs['num_frames'] = len(stimulus_frames)

            print(f"  Saved stimulus: {stimulus_path}")

            # Generate corresponding camera data
            camera_frames = []
            camera_timestamps = []

            self.camera.start_recording()
            for angle in angles:
                frame, timestamp = self.camera.capture_frame(stimulus_angle=angle)
                camera_frames.append(frame)
                camera_timestamps.append(timestamp)

            self.camera.stop_recording()

            # Save camera data
            camera_path = os.path.join(output_dir, f"{direction}_camera.h5")
            with h5py.File(camera_path, 'w') as f:
                f.create_dataset('frames', data=np.array(camera_frames))
                f.create_dataset('timestamps', data=np.array(camera_timestamps))
                f.attrs['direction'] = direction
                f.attrs['num_frames'] = len(camera_frames)

            print(f"  Saved camera data: {camera_path}")

        # Generate anatomical image
        anatomical = self.camera._generate_anatomical_frame()
        anatomical_path = os.path.join(output_dir, "anatomical.npy")
        np.save(anatomical_path, anatomical)
        print(f"\nSaved anatomical image: {anatomical_path}")

        # Save session metadata
        metadata = {
            "session_type": "mock",
            "timestamp": time.strftime("%Y%m%d_%H%M%S"),
            "directions": directions,
            "camera_resolution": self.camera.resolution,
            "display_resolution": self.display.resolution,
            "camera_fps": self.camera.fps,
            "display_fps": self.display.fps
        }

        metadata_path = os.path.join(output_dir, "metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        print(f"Saved metadata: {metadata_path}")
        print(f"\nTest session generation complete!")

    def _generate_stimulus_frames(self, direction: str, num_cycles: int = 3) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate stimulus frames for a given direction

        Args:
            direction: 'LR', 'RL', 'TB', or 'BT'
            num_cycles: Number of complete sweeps

        Returns:
            frames: Stimulus frames
            angles: Visual field angles for each frame
        """
        # Simplified stimulus generation
        # In reality, would create drifting bars with checkerboard patterns

        frames_per_cycle = 180  # 3 seconds at 60 FPS
        total_frames = frames_per_cycle * num_cycles

        # Generate angle progression
        if direction in ['LR', 'RL']:
            # Horizontal sweep: -60 to +60 degrees
            start_angle = -60 if direction == 'LR' else 60
            end_angle = 60 if direction == 'LR' else -60
        else:  # TB or BT
            # Vertical sweep: -30 to +30 degrees
            start_angle = -30 if direction == 'TB' else 30
            end_angle = 30 if direction == 'TB' else -30

        angles = []
        for cycle in range(num_cycles):
            cycle_angles = np.linspace(start_angle, end_angle, frames_per_cycle)
            angles.extend(cycle_angles)

        # Generate simple bar frames (placeholder)
        frames = np.zeros((total_frames, 100, 100), dtype=np.uint8)
        for i, angle in enumerate(angles):
            # Create a simple bar at the appropriate position
            bar_pos = int((angle - start_angle) / (end_angle - start_angle) * 100)
            bar_pos = np.clip(bar_pos, 5, 95)

            if direction in ['LR', 'RL']:
                # Vertical bar for horizontal motion
                frames[i, :, bar_pos-5:bar_pos+5] = 255
            else:
                # Horizontal bar for vertical motion
                frames[i, bar_pos-5:bar_pos+5, :] = 255

        return frames, np.array(angles)


if __name__ == "__main__":
    # Test mock hardware
    print("Testing Mock Hardware System")
    print("=" * 50)

    hardware = MockHardware()
    hardware.initialize()

    # Test camera
    print("\nTesting camera capture...")
    hardware.camera.start_recording()
    for i in range(5):
        frame, timestamp = hardware.camera.capture_frame(stimulus_angle=i*10)
        print(f"  Frame {i}: shape={frame.shape}, timestamp={timestamp}, mean={frame.mean():.1f}")
    hardware.camera.stop_recording()

    # Test display
    print("\nTesting display presentation...")
    hardware.display.start_presentation()
    test_frame = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    for i in range(5):
        timestamp = hardware.display.present_frame(test_frame)
        print(f"  Frame {i}: timestamp={timestamp}")
    hardware.display.stop_presentation()

    # Generate test session
    print("\n" + "=" * 50)
    hardware.generate_test_session("data/sessions/test_mock")

    hardware.shutdown()