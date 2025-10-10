#!/usr/bin/env python3
"""Convert sample MATLAB data to ISI internal session format.

This script converts the sample retinotopy data from MATLAB format
to the internal session format used by the ISI analysis system.
"""

import scipy.io as sio
import numpy as np
from pathlib import Path
import json
from datetime import datetime

def load_matlab_data(sample_dir: Path):
    """Load sample data from MATLAB files.

    Args:
        sample_dir: Path to sample_data directory

    Returns:
        Tuple of (anatomical, horizontal_complex, vertical_complex)
    """
    print("Loading MATLAB sample data...")

    # Load anatomical image
    print("  Loading anatomical image...")
    mat = sio.loadmat(str(sample_dir / "grab_r43_000_006_26_Jul_2012_19_02_23.mat"))
    anatomical = mat['grab'][0, 0]['img']
    print(f"    Anatomical: {anatomical.shape}, dtype={anatomical.dtype}")

    # Load horizontal retinotopy (R43_000_004)
    print("  Loading horizontal retinotopy...")
    mat1 = sio.loadmat(str(sample_dir / "R43_000_004.mat"))
    horizontal_complex = mat1['f1m']  # Shape (1, 2) - two cycles
    print(f"    Horizontal: {horizontal_complex[0, 0].shape}, complex")

    # Load vertical retinotopy (R43_000_005)
    print("  Loading vertical retinotopy...")
    mat2 = sio.loadmat(str(sample_dir / "R43_000_005.mat"))
    vertical_complex = mat2['f1m']  # Shape (1, 2) - two cycles
    print(f"    Vertical: {vertical_complex[0, 0].shape}, complex")

    return anatomical, horizontal_complex, vertical_complex


def extract_phase_magnitude(complex_data):
    """Extract phase and magnitude from complex Fourier data.

    Args:
        complex_data: Complex128 array

    Returns:
        Tuple of (phase, magnitude)
    """
    # Phase in radians [-π, π]
    phase = np.angle(complex_data)

    # Magnitude (amplitude)
    magnitude = np.abs(complex_data)

    return phase, magnitude


def create_session_structure(output_dir: Path, anatomical, horizontal, vertical):
    """Create session directory structure with converted data.

    Args:
        output_dir: Output directory for session
        anatomical: Anatomical reference image
        horizontal: Horizontal retinotopy complex data (1, 2) array
        vertical: Vertical retinotopy complex data (1, 2) array
    """
    print(f"\nCreating session structure at: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save anatomical image (convert to uint8 for consistency)
    print("  Saving anatomical image...")
    # Normalize uint16 to uint8
    anatomical_norm = ((anatomical - anatomical.min()) / (anatomical.max() - anatomical.min()) * 255).astype(np.uint8)
    np.save(output_dir / "anatomical.npy", anatomical_norm)

    # Process horizontal data (assume LR = [0,0], RL = [0,1])
    print("  Processing horizontal retinotopy (LR/RL)...")

    # LR direction
    phase_lr, mag_lr = extract_phase_magnitude(horizontal[0, 0])
    np.save(output_dir / "phase_LR.npy", phase_lr.astype(np.float32))
    np.save(output_dir / "magnitude_LR.npy", mag_lr.astype(np.float32))
    print(f"    LR: phase range [{phase_lr.min():.3f}, {phase_lr.max():.3f}], mag range [{mag_lr.min():.3f}, {mag_lr.max():.3f}]")

    # RL direction
    phase_rl, mag_rl = extract_phase_magnitude(horizontal[0, 1])
    np.save(output_dir / "phase_RL.npy", phase_rl.astype(np.float32))
    np.save(output_dir / "magnitude_RL.npy", mag_rl.astype(np.float32))
    print(f"    RL: phase range [{phase_rl.min():.3f}, {phase_rl.max():.3f}], mag range [{mag_rl.min():.3f}, {mag_rl.max():.3f}]")

    # Process vertical data (assume TB = [0,0], BT = [0,1])
    print("  Processing vertical retinotopy (TB/BT)...")

    # TB direction
    phase_tb, mag_tb = extract_phase_magnitude(vertical[0, 0])
    np.save(output_dir / "phase_TB.npy", phase_tb.astype(np.float32))
    np.save(output_dir / "magnitude_TB.npy", mag_tb.astype(np.float32))
    print(f"    TB: phase range [{phase_tb.min():.3f}, {phase_tb.max():.3f}], mag range [{mag_tb.min():.3f}, {mag_tb.max():.3f}]")

    # BT direction
    phase_bt, mag_bt = extract_phase_magnitude(vertical[0, 1])
    np.save(output_dir / "phase_BT.npy", phase_bt.astype(np.float32))
    np.save(output_dir / "magnitude_BT.npy", mag_bt.astype(np.float32))
    print(f"    BT: phase range [{phase_bt.min():.3f}, {phase_bt.max():.3f}], mag range [{mag_bt.min():.3f}, {mag_bt.max():.3f}]")

    # Create session metadata
    print("  Creating session metadata...")
    metadata = {
        "session_name": "sample_session",
        "timestamp": datetime.now().isoformat(),
        "source": "Converted from sample MATLAB data (R43)",
        "shape": list(anatomical.shape),  # [height, width]
        "directions": ["LR", "RL", "TB", "BT"],
        "has_anatomical": True,
        "data_type": "retinotopy",
        "notes": "Sample retinotopic mapping data for testing analysis pipeline"
    }

    with open(output_dir / "metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"\n✅ Session created successfully!")
    print(f"   Location: {output_dir}")
    print(f"   Files created:")
    print(f"     - anatomical.npy")
    print(f"     - phase_LR.npy, magnitude_LR.npy")
    print(f"     - phase_RL.npy, magnitude_RL.npy")
    print(f"     - phase_TB.npy, magnitude_TB.npy")
    print(f"     - phase_BT.npy, magnitude_BT.npy")
    print(f"     - metadata.json")


def main():
    """Main conversion script."""
    # Paths
    repo_root = Path(__file__).parent.parent.parent.parent
    sample_data_dir = repo_root / "sample_data"
    sessions_dir = repo_root / "apps" / "backend" / "data" / "sessions"
    output_dir = sessions_dir / "sample_session"

    print("=" * 70)
    print("ISI Sample Data Converter")
    print("=" * 70)
    print(f"Sample data: {sample_data_dir}")
    print(f"Output location: {output_dir}")
    print()

    # Check if sample data exists
    if not sample_data_dir.exists():
        print(f"❌ Error: Sample data directory not found: {sample_data_dir}")
        return 1

    # Load MATLAB data
    try:
        anatomical, horizontal, vertical = load_matlab_data(sample_data_dir)
    except Exception as e:
        print(f"❌ Error loading MATLAB data: {e}")
        return 1

    # Create session structure
    try:
        create_session_structure(output_dir, anatomical, horizontal, vertical)
    except Exception as e:
        print(f"❌ Error creating session structure: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print()
    print("=" * 70)
    print("Conversion complete! You can now:")
    print("1. Start the ISI application")
    print("2. Go to the Analysis tab")
    print("3. Select 'sample_session' from the dropdown")
    print("4. Click 'Analyze' to run the analysis pipeline")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
