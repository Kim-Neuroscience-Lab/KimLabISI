#!/usr/bin/env python3
"""Process pre-computed phase/magnitude data through analysis pipeline.

This script takes the sample session data (which already has phase/magnitude maps)
and runs it through the later stages of the analysis pipeline to generate:
- Azimuth and elevation retinotopic maps
- Visual field sign map
- Area boundary detection

This allows testing the rendering system without needing full raw acquisition data.
"""

import sys
from pathlib import Path
import numpy as np
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from analysis.pipeline import AnalysisPipeline
from config import AnalysisConfig


def process_sample_data(session_dir: Path):
    """Process sample phase/magnitude data through analysis pipeline.

    Args:
        session_dir: Path to session directory with phase/magnitude data
    """
    print("=" * 70)
    print("Processing Sample Retinotopy Data")
    print("=" * 70)
    print(f"Session: {session_dir}")
    print()

    # Check that phase/magnitude files exist
    required_files = [
        "phase_LR.npy", "magnitude_LR.npy",
        "phase_RL.npy", "magnitude_RL.npy",
        "phase_TB.npy", "magnitude_TB.npy",
        "phase_BT.npy", "magnitude_BT.npy",
        "anatomical.npy"
    ]

    print("Checking for required files...")
    for filename in required_files:
        filepath = session_dir / filename
        if not filepath.exists():
            print(f"  ❌ Missing: {filename}")
            return 1
        else:
            print(f"  ✅ Found: {filename}")
    print()

    # Load phase and magnitude data
    print("Loading phase/magnitude data...")
    phase_data = {
        "LR": np.load(session_dir / "phase_LR.npy"),
        "RL": np.load(session_dir / "phase_RL.npy"),
        "TB": np.load(session_dir / "phase_TB.npy"),
        "BT": np.load(session_dir / "phase_BT.npy"),
    }

    magnitude_data = {
        "LR": np.load(session_dir / "magnitude_LR.npy"),
        "RL": np.load(session_dir / "magnitude_RL.npy"),
        "TB": np.load(session_dir / "magnitude_TB.npy"),
        "BT": np.load(session_dir / "magnitude_BT.npy"),
    }

    anatomical = np.load(session_dir / "anatomical.npy")

    print(f"  Shape: {phase_data['LR'].shape}")
    print(f"  Anatomical: {anatomical.shape}")
    print()

    # Create output directory
    output_dir = session_dir / "analysis_results"
    output_dir.mkdir(exist_ok=True)
    print(f"Output directory: {output_dir}")
    print()

    # Create analysis pipeline with default config
    print("Initializing analysis pipeline...")
    config = AnalysisConfig(
        magnitude_threshold=0.1,
        phase_filter_sigma=0.5,
        smoothing_sigma=1.0,
        gradient_window_size=3,
        response_threshold_percent=5.0,
        vfs_threshold_sd=2.0,
        ring_size_mm=1.0,
        area_min_size_mm2=0.1,
    )
    pipeline = AnalysisPipeline(config)
    print()

    # Run pipeline from phase/magnitude maps
    print("Running analysis pipeline...")
    print()
    results = pipeline.run_from_phase_maps(
        phase_data=phase_data,
        magnitude_data=magnitude_data,
        anatomical=anatomical
    )
    print()

    # Save all results
    print("Saving results...")
    for name, data in results.items():
        filename = f"{name}.npy"
        np.save(output_dir / filename, data)
        print(f"  ✅ Saved {filename}")


    # Save phase/magnitude for debugging (optional advanced layers)
    print("\nSaving advanced diagnostic layers...")
    for direction in ["LR", "RL", "TB", "BT"]:
        np.save(output_dir / f"phase_{direction}.npy", phase_data[direction].astype(np.float32))
        np.save(output_dir / f"magnitude_{direction}.npy", magnitude_data[direction].astype(np.float32))
        print(f"  ✅ Saved phase_{direction}.npy, magnitude_{direction}.npy")

    print()
    print("=" * 70)
    print("✅ Processing complete!")
    print(f"Results saved to: {output_dir}")
    print("You can now view these results in the Analysis tab!")
    print("=" * 70)

    return 0


def main():
    """Main entry point."""
    # Path to sample session
    session_dir = Path(__file__).parent.parent / "data" / "sessions" / "sample_session"

    if not session_dir.exists():
        print(f"❌ Error: Session directory not found: {session_dir}")
        print("Please run convert_sample_data.py first!")
        return 1

    return process_sample_data(session_dir)


if __name__ == "__main__":
    sys.exit(main())
