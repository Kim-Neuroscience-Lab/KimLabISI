"""Compare VFS computation methods: Jacobian determinant vs gradient angle method."""

import sys
sys.path.insert(0, 'src')

import numpy as np
from pathlib import Path
from config import AppConfig
from analysis.pipeline import AnalysisPipeline

# Load sample session
session_path = Path('data/sessions/sample_session')
phase_LR = np.load(session_path / 'phase_LR.npy')
phase_RL = np.load(session_path / 'phase_RL.npy')
phase_TB = np.load(session_path / 'phase_TB.npy')
phase_BT = np.load(session_path / 'phase_BT.npy')

mag_LR = np.load(session_path / 'magnitude_LR.npy')
mag_RL = np.load(session_path / 'magnitude_RL.npy')
mag_TB = np.load(session_path / 'magnitude_TB.npy')
mag_BT = np.load(session_path / 'magnitude_BT.npy')

# Initialize pipeline
cfg = AppConfig.from_file('config/isi_parameters.json')
pipeline = AnalysisPipeline(cfg.analysis)

# Generate retinotopic maps
azimuth = pipeline.generate_azimuth_map(phase_LR, phase_RL)
elevation = pipeline.generate_elevation_map(phase_TB, phase_BT)

# Compute gradients (both methods need these)
from scipy.ndimage import gaussian_filter
sigma = cfg.analysis.smoothing_sigma
azimuth_smooth = gaussian_filter(azimuth, sigma=sigma)
elevation_smooth = gaussian_filter(elevation, sigma=sigma)

d_azimuth_dy, d_azimuth_dx = np.gradient(azimuth_smooth)
d_elevation_dy, d_elevation_dx = np.gradient(elevation_smooth)

print("=" * 80)
print("VFS METHOD COMPARISON")
print("=" * 80)

# METHOD 1: Current implementation - Jacobian determinant
print("\n[1] Jacobian Determinant Method (current):")
jacobian_vfs = d_azimuth_dx * d_elevation_dy - d_azimuth_dy * d_elevation_dx
print(f"  Range: [{np.nanmin(jacobian_vfs):.3f}, {np.nanmax(jacobian_vfs):.3f}]")
print(f"  Mean: {np.nanmean(jacobian_vfs):.3f}")
print(f"  Std: {np.nanstd(jacobian_vfs):.3f}")
print(f"  Positive pixels: {np.sum(jacobian_vfs > 0)} ({100*np.sum(jacobian_vfs > 0)/jacobian_vfs.size:.1f}%)")
print(f"  Negative pixels: {np.sum(jacobian_vfs < 0)} ({100*np.sum(jacobian_vfs < 0)/jacobian_vfs.size:.1f}%)")

# METHOD 2: Old implementation - Gradient angle method (MATLAB getAreaBorders.m)
print("\n[2] Gradient Angle Method (old_implementation / MATLAB):")

# Compute gradient directions
graddir_horizontal = np.arctan2(d_azimuth_dy, d_azimuth_dx)
graddir_vertical = np.arctan2(d_elevation_dy, d_elevation_dx)

# Compute angle difference
vdiff = np.exp(1j * graddir_horizontal) * np.exp(-1j * graddir_vertical)

# VFS = sine of angle difference
angle_vfs = np.sin(np.angle(vdiff))

print(f"  Range: [{np.nanmin(angle_vfs):.3f}, {np.nanmax(angle_vfs):.3f}]")
print(f"  Mean: {np.nanmean(angle_vfs):.3f}")
print(f"  Std: {np.nanstd(angle_vfs):.3f}")
print(f"  Positive pixels: {np.sum(angle_vfs > 0)} ({100*np.sum(angle_vfs > 0)/angle_vfs.size:.1f}%)")
print(f"  Negative pixels: {np.sum(angle_vfs < 0)} ({100*np.sum(angle_vfs < 0)/angle_vfs.size:.1f}%)")

# Compare correlation
correlation = np.corrcoef(jacobian_vfs.flatten(), angle_vfs.flatten())[0, 1]
print(f"\n[3] Correlation between methods: {correlation:.4f}")

# Check sign agreement
sign_agreement = np.sum(np.sign(jacobian_vfs) == np.sign(angle_vfs)) / jacobian_vfs.size
print(f"  Sign agreement: {sign_agreement:.1%}")

print("\n" + "=" * 80)
print("CONCLUSION:")
print("=" * 80)
if correlation > 0.95:
    print("✓ Methods are highly correlated - difference is mainly in scaling")
elif correlation > 0.5:
    print("⚠ Methods are moderately correlated - may produce different results")
else:
    print("✗ Methods are poorly correlated - produce fundamentally different results")

if sign_agreement > 0.9:
    print("✓ Sign agreement is high - area boundaries should be similar")
else:
    print("✗ Sign agreement is low - area boundaries will differ significantly")

print("=" * 80)
