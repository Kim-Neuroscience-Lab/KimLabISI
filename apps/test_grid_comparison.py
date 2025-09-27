#!/usr/bin/env python3
"""
Generate only grid comparison video to test corrected directions
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

import numpy as np
import cv2
from isi_system import ISISystem

def create_grid_comparison():
    """Create 2x2 grid comparison video only"""

    print("Creating Grid Comparison Video")
    print("=" * 40)

    # Initialize system
    system = ISISystem(use_mock_hardware=True)

    # Use default parameters - proper spatial configuration and stimulus parameters already set
    # Only reduce cycles for quick test
    system.stimulus_params.num_cycles = 1

    # Clear output directory
    output_dir = "stimulus_videos"
    if os.path.exists(output_dir):
        for file in os.listdir(output_dir):
            os.remove(os.path.join(output_dir, file))
    else:
        os.makedirs(output_dir)

    print("\\nGenerating frames for all directions...")

    # Generate frames for all directions
    direction_frames = {}
    max_frames = 0

    for direction in ['LR', 'RL', 'TB', 'BT']:
        print(f"  {direction}...", end="")
        frames, _, _ = system.generate_drifting_bars(direction)
        direction_frames[direction] = frames
        max_frames = max(max_frames, len(frames))
        print(f" {len(frames)} frames")

    # Create 2x2 grid comparison video
    frame_height, frame_width = direction_frames['LR'][0].shape
    comparison_width = frame_width * 2
    comparison_height = frame_height * 2

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    comparison_path = os.path.join(output_dir, "grid_comparison.mp4")
    out = cv2.VideoWriter(comparison_path, fourcc, 30, (comparison_width, comparison_height), isColor=False)

    print(f"\\nCreating grid video with {max_frames} frames...")

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
        cv2.putText(combined_frame, "LR", (10, 30), font, 0.7, 255, 2)
        cv2.putText(combined_frame, "RL", (frame_width + 10, 30), font, 0.7, 255, 2)
        cv2.putText(combined_frame, "TB", (10, frame_height + 30), font, 0.7, 255, 2)
        cv2.putText(combined_frame, "BT", (frame_width + 10, frame_height + 30), font, 0.7, 255, 2)

        out.write(combined_frame)

    out.release()

    print(f"✅ Grid comparison video saved: {comparison_path}")
    print(f"   Resolution: {comparison_width}x{comparison_height}")
    print(f"   Frames: {max_frames}")

if __name__ == "__main__":
    create_grid_comparison()