"""
Test Stimulus Generation and Video Export

Generates visual stimuli and exports them as videos for visual verification.
Creates drifting bar stimuli with checkerboard patterns for all directions.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

import numpy as np
import cv2
from isi_system import ISISystem
import time

def create_stimulus_videos():
    """Generate stimulus videos for all directions"""

    print("=" * 60)
    print("STIMULUS GENERATION AND VIDEO EXPORT TEST")
    print("=" * 60)

    # Initialize ISI system
    system = ISISystem(use_mock_hardware=True)

    # Configure for faster/smaller stimulus for testing
    system.setup_spatial_configuration({
        'monitor_distance_cm': 10.0,
        'screen_width_pixels': 640,    # Smaller for faster processing
        'screen_height_pixels': 480,
        'field_of_view_horizontal': 120.0,
        'field_of_view_vertical': 90.0
    })

    # Set stimulus parameters for clear visualization
    system.stimulus_params.num_cycles = 2           # 2 cycles for demo
    system.stimulus_params.bar_width_degrees = 15.0 # Wider bar for visibility
    system.stimulus_params.drift_speed_degrees_per_sec = 20.0  # Faster for demo
    system.stimulus_params.checkerboard_size_degrees = 20.0    # Larger checkers
    system.stimulus_params.flicker_frequency_hz = 4.0          # Slower flicker
    system.stimulus_params.contrast = 0.8

    print(f"Stimulus parameters:")
    print(f"  Resolution: {system.spatial_config.screen_width_pixels}x{system.spatial_config.screen_height_pixels}")
    print(f"  Bar width: {system.stimulus_params.bar_width_degrees}°")
    print(f"  Drift speed: {system.stimulus_params.drift_speed_degrees_per_sec}°/s")
    print(f"  Cycles: {system.stimulus_params.num_cycles}")

    # Use existing stimulus_videos directory, clear previous content
    output_dir = "stimulus_videos"
    if os.path.exists(output_dir):
        # Clear existing content
        for file in os.listdir(output_dir):
            file_path = os.path.join(output_dir, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
    else:
        os.makedirs(output_dir)

    # Generate and export videos for each direction
    directions = ['LR', 'RL', 'TB', 'BT']

    for direction in directions:
        print(f"\n--- Processing {direction} Direction ---")

        # Generate stimulus
        start_time = time.time()
        frames, angles, timestamps = system.generate_drifting_bars(direction)
        generation_time = time.time() - start_time

        print(f"Generated {len(frames)} frames in {generation_time:.2f} seconds")
        print(f"Frame shape: {frames[0].shape}")
        print(f"Angle range: {angles.min():.1f}° to {angles.max():.1f}°")

        # Create video
        video_path = os.path.join(output_dir, f"{direction}_stimulus.mp4")
        create_video(frames, video_path, fps=30)

        # Save first and last frames as images for quick preview
        cv2.imwrite(os.path.join(output_dir, f"{direction}_first_frame.png"), frames[0])
        cv2.imwrite(os.path.join(output_dir, f"{direction}_last_frame.png"), frames[-1])

        print(f"Saved video: {video_path}")

    # Create a combined comparison video
    print(f"\n--- Creating Comparison Video ---")
    create_comparison_video(system, output_dir)

    print(f"\n" + "=" * 60)
    print("STIMULUS GENERATION COMPLETE")
    print(f"Videos saved in: {os.path.abspath(output_dir)}")
    print("=" * 60)

    # Print file listing
    print("\nGenerated files:")
    for file in os.listdir(output_dir):
        file_path = os.path.join(output_dir, file)
        file_size = os.path.getsize(file_path) / (1024*1024)  # MB
        print(f"  {file} ({file_size:.1f} MB)")

def create_video(frames, output_path, fps=30):
    """
    Create MP4 video from stimulus frames

    Args:
        frames: Array of stimulus frames
        output_path: Output video file path
        fps: Frames per second
    """
    height, width = frames[0].shape

    # Define codec and create VideoWriter
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height), isColor=False)

    if not out.isOpened():
        print(f"Error: Could not open video writer for {output_path}")
        return

    # Write frames
    for frame in frames:
        out.write(frame)

    out.release()
    print(f"  Video saved: {output_path}")

def create_comparison_video(system, output_dir):
    """Create a side-by-side comparison video of all directions"""

    print("Generating comparison frames...")

    # Generate smaller frames for comparison
    original_width = system.spatial_config.screen_width_pixels
    original_height = system.spatial_config.screen_height_pixels

    # Temporarily reduce resolution for comparison video
    system.setup_spatial_configuration({
        'screen_width_pixels': 320,
        'screen_height_pixels': 240
    })

    # Generate frames for all directions
    direction_frames = {}
    max_frames = 0

    for direction in ['LR', 'RL', 'TB', 'BT']:
        frames, _, _ = system.generate_drifting_bars(direction)
        direction_frames[direction] = frames
        max_frames = max(max_frames, len(frames))

    # Restore original resolution
    system.setup_spatial_configuration({
        'screen_width_pixels': original_width,
        'screen_height_pixels': original_height
    })

    # Create 2x2 grid comparison video
    frame_height, frame_width = direction_frames['LR'][0].shape
    comparison_width = frame_width * 2
    comparison_height = frame_height * 2

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    comparison_path = os.path.join(output_dir, "comparison_all_directions.mp4")
    out = cv2.VideoWriter(comparison_path, fourcc, 30, (comparison_width, comparison_height), isColor=False)

    for i in range(max_frames):
        # Create combined frame
        combined_frame = np.zeros((comparison_height, comparison_width), dtype=np.uint8)

        # Top row: LR and RL
        if i < len(direction_frames['LR']):
            combined_frame[:frame_height, :frame_width] = direction_frames['LR'][i]
        if i < len(direction_frames['RL']):
            combined_frame[:frame_height, frame_width:] = direction_frames['RL'][i]

        # Bottom row: TB and BT
        if i < len(direction_frames['TB']):
            combined_frame[frame_height:, :frame_width] = direction_frames['TB'][i]
        if i < len(direction_frames['BT']):
            combined_frame[frame_height:, frame_width:] = direction_frames['BT'][i]

        # Add labels
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(combined_frame, "LR", (10, 30), font, 1, 255, 2)
        cv2.putText(combined_frame, "RL", (frame_width + 10, 30), font, 1, 255, 2)
        cv2.putText(combined_frame, "TB", (10, frame_height + 30), font, 1, 255, 2)
        cv2.putText(combined_frame, "BT", (frame_width + 10, frame_height + 30), font, 1, 255, 2)

        out.write(combined_frame)

    out.release()
    print(f"  Comparison video saved: {comparison_path}")

def analyze_stimulus_properties():
    """Analyze stimulus properties and print detailed information"""

    print("\n--- STIMULUS ANALYSIS ---")

    system = ISISystem(use_mock_hardware=True)

    # Generate one direction for analysis
    frames, angles, timestamps = system.generate_drifting_bars('LR')

    print(f"Stimulus Properties:")
    print(f"  Total frames: {len(frames)}")
    print(f"  Frame rate: 60 FPS")
    print(f"  Duration: {len(frames)/60:.1f} seconds")
    print(f"  Frame size: {frames[0].shape}")
    print(f"  Data type: {frames[0].dtype}")
    print(f"  Value range: {frames.min()} to {frames.max()}")

    print(f"\nAngle Progression:")
    print(f"  Start angle: {angles[0]:.1f}°")
    print(f"  End angle: {angles[-1]:.1f}°")
    print(f"  Total sweep: {abs(angles[-1] - angles[0]):.1f}°")
    print(f"  Angular velocity: {(angles[-1] - angles[0]) / (len(angles)/60):.1f}°/s")

    print(f"\nTiming:")
    print(f"  Frame interval: {1/60*1000:.1f} ms")
    print(f"  First timestamp: {timestamps[0]} μs")
    print(f"  Last timestamp: {timestamps[-1]} μs")
    print(f"  Total time: {(timestamps[-1] - timestamps[0])/1e6:.1f} s")

    # Analyze checkerboard pattern
    print(f"\nCheckerboard Analysis:")
    middle_frame = len(frames) // 2
    frame = frames[middle_frame]

    # Count transitions (rough estimate of checkerboard)
    h_transitions = np.sum(np.abs(np.diff(frame, axis=1)) > 100)
    v_transitions = np.sum(np.abs(np.diff(frame, axis=0)) > 100)

    print(f"  Horizontal transitions: {h_transitions}")
    print(f"  Vertical transitions: {v_transitions}")
    print(f"  Pattern complexity: {'High' if h_transitions > 1000 else 'Low'}")


def main():
    """Run all stimulus tests"""

    print("Starting comprehensive stimulus testing...")

    # Main stimulus generation and video export
    create_stimulus_videos()

    # Detailed analysis
    analyze_stimulus_properties()

    print("\n" + "=" * 60)
    print("ALL STIMULUS TESTS COMPLETE")
    print("=" * 60)
    print("\nTo view the videos:")
    print("1. Open the 'stimulus_videos' folder")
    print("2. Play the MP4 files with any video player")
    print("3. Check 'comparison_all_directions.mp4' for side-by-side view")

if __name__ == "__main__":
    main()