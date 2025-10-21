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
        Tuple of (anatomical, file_005_data, file_004_data)

    Note:
        Based on analysis of ISI-master/SerenoOverlay/generatekret.m line 4:
        % generatekret('R43','000_005','000_004')
        %              anim    AzExpt    AltExpt

        - R43_000_005.mat = Azimuth experiment (horizontal)
        - R43_000_004.mat = Altitude experiment (vertical)

        However, spatial analysis shows each file contains BOTH axes:
        - 005[0,0] = horizontal component, 005[0,1] = vertical component
        - 004[0,0] = horizontal component, 004[0,1] = vertical component

        We extract horizontal pair from [0,0] of each file,
        and vertical pair from [0,1] of each file.
    """
    print("Loading MATLAB sample data...")
    print("  (Note: File assignments corrected based on MATLAB reference code)")

    # Load anatomical image
    print("  Loading anatomical image...")
    mat = sio.loadmat(str(sample_dir / "grab_r43_000_006_26_Jul_2012_19_02_23.mat"))
    anatomical = mat['grab'][0, 0]['img']
    print(f"    Anatomical: {anatomical.shape}, dtype={anatomical.dtype}")

    # Load R43_000_005 (azimuth/horizontal experiment)
    print("  Loading R43_000_005.mat (azimuth experiment)...")
    mat_005 = sio.loadmat(str(sample_dir / "R43_000_005.mat"))
    data_005 = mat_005['f1m']  # Shape (1, 2)
    print(f"    File 005: {data_005[0, 0].shape}, complex")

    # Load R43_000_004 (altitude/vertical experiment)
    print("  Loading R43_000_004.mat (altitude experiment)...")
    mat_004 = sio.loadmat(str(sample_dir / "R43_000_004.mat"))
    data_004 = mat_004['f1m']  # Shape (1, 2)
    print(f"    File 004: {data_004[0, 0].shape}, complex")

    return anatomical, data_005, data_004


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


def create_session_structure(output_dir: Path, anatomical, data_005, data_004):
    """Create session directory structure with converted data.

    Args:
        output_dir: Output directory for session
        anatomical: Anatomical reference image
        data_005: Data from R43_000_005.mat (azimuth experiment)
        data_004: Data from R43_000_004.mat (altitude experiment)

    Note:
        CORRECTED mapping verified against HDF5 reference (correlation=1.0):
        - Horizontal retinotopy (LR/RL): Both from 004[0,0] and 004[0,1]
        - Vertical retinotopy (TB/BT): Both from 005[0,0] and 005[0,1]

        The naming is counter-intuitive:
        - "azimuth experiment" (005) contains vertical retinotopy data
        - "altitude experiment" (004) contains horizontal retinotopy data
    """
    print(f"\nCreating session structure at: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save anatomical image (convert to uint8 for consistency)
    print("  Saving anatomical image...")
    # Normalize uint16 to uint8
    anatomical_norm = ((anatomical - anatomical.min()) / (anatomical.max() - anatomical.min()) * 255).astype(np.uint8)
    np.save(output_dir / "anatomical.npy", anatomical_norm)

    # Process horizontal retinotopy (azimuth)
    # CORRECTED: Horizontal pair comes from 004[0,0] and 004[0,1]
    print("  Processing horizontal retinotopy (azimuth: LR/RL)...")
    print("    Using 004[0,0] and 004[0,1] (horizontal components from altitude experiment)")

    # Assign 004[0,0] as LR (verified against HDF5 reference)
    phase_lr, mag_lr = extract_phase_magnitude(data_004[0, 0])
    np.save(output_dir / "phase_LR.npy", phase_lr.astype(np.float32))
    np.save(output_dir / "magnitude_LR.npy", mag_lr.astype(np.float32))
    print(f"    LR (from 004[0,0]): phase range [{phase_lr.min():.3f}, {phase_lr.max():.3f}], mag range [{mag_lr.min():.3f}, {mag_lr.max():.3f}]")

    # Assign 004[0,1] as RL (opposing direction)
    phase_rl, mag_rl = extract_phase_magnitude(data_004[0, 1])
    np.save(output_dir / "phase_RL.npy", phase_rl.astype(np.float32))
    np.save(output_dir / "magnitude_RL.npy", mag_rl.astype(np.float32))
    print(f"    RL (from 004[0,1]): phase range [{phase_rl.min():.3f}, {phase_rl.max():.3f}], mag range [{mag_rl.min():.3f}, {mag_rl.max():.3f}]")

    # Process vertical retinotopy (altitude)
    # CORRECTED: Vertical pair comes from 005[0,0] and 005[0,1]
    print("  Processing vertical retinotopy (altitude: TB/BT)...")
    print("    Using 005[0,0] and 005[0,1] (vertical components from azimuth experiment)")

    # Assign 005[0,0] as TB (verified against HDF5 reference)
    phase_tb, mag_tb = extract_phase_magnitude(data_005[0, 0])
    np.save(output_dir / "phase_TB.npy", phase_tb.astype(np.float32))
    np.save(output_dir / "magnitude_TB.npy", mag_tb.astype(np.float32))
    print(f"    TB (from 005[0,0]): phase range [{phase_tb.min():.3f}, {phase_tb.max():.3f}], mag range [{mag_tb.min():.3f}, {mag_tb.max():.3f}]")

    # Assign 005[0,1] as BT (opposing direction)
    phase_bt, mag_bt = extract_phase_magnitude(data_005[0, 1])
    np.save(output_dir / "phase_BT.npy", phase_bt.astype(np.float32))
    np.save(output_dir / "magnitude_BT.npy", mag_bt.astype(np.float32))
    print(f"    BT (from 005[0,1]): phase range [{phase_bt.min():.3f}, {phase_bt.max():.3f}], mag range [{mag_bt.min():.3f}, {mag_bt.max():.3f}]")

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
        "notes": "Sample retinotopic mapping data for testing analysis pipeline",
        "conversion_info": {
            "file_mapping": {
                "LR": "R43_000_004.mat[0,0] - altitude experiment, horizontal component",
                "RL": "R43_000_004.mat[0,1] - altitude experiment, horizontal component (opposing direction)",
                "TB": "R43_000_005.mat[0,0] - azimuth experiment, vertical component",
                "BT": "R43_000_005.mat[0,1] - azimuth experiment, vertical component (opposing direction)"
            },
            "reference": "Based on ISI-master/SerenoOverlay/generatekret.m",
            "spatial_analysis": "Verified against HDF5 reference via correlation analysis (correlation=1.0)",
            "correction_note": "Fixed direction mapping - horizontal/vertical were swapped in initial extraction"
        }
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
        anatomical, data_005, data_004 = load_matlab_data(sample_data_dir)
    except Exception as e:
        print(f"❌ Error loading MATLAB data: {e}")
        return 1

    # Create session structure
    try:
        create_session_structure(output_dir, anatomical, data_005, data_004)
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
