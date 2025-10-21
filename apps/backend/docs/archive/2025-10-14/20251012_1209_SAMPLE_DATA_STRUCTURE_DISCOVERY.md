# Sample Data Structure Discovery

## Problem Statement

We needed to determine what each of the 4 matrices in the sample data actually represents, as the conversion script made assumptions about the data organization without verification.

## Analysis Method

Used spatial analysis of phase maps to determine stimulus direction:
1. **Phase wrapping analysis**: Count wraps along horizontal vs vertical axes
2. **Visual inspection**: Examine gradient direction in phase maps
3. **Gradient analysis**: Measure spatial derivatives

## Key Findings

### Actual Data Organization

The MATLAB files are organized **differently than assumed** by the conversion script:

```
ASSUMED (WRONG):
├── R43_000_004.mat
│   ├── [0,0] → LR (horizontal)
│   └── [0,1] → RL (horizontal)
└── R43_000_005.mat
    ├── [0,0] → TB (vertical)
    └── [0,1] → BT (vertical)

ACTUAL (CORRECT):
├── R43_000_004.mat
│   ├── [0,0] → HORIZONTAL (azimuth) - one direction
│   └── [0,1] → VERTICAL (altitude) - one direction
└── R43_000_005.mat
    ├── [0,0] → HORIZONTAL (azimuth) - opposite direction
    └── [0,1] → VERTICAL (altitude) - opposite direction
```

### Evidence

**Phase Wrapping Analysis:**
```
R43_004_[0,0]: 2 H-wraps, 0 V-wraps   → Horizontal variation (L-R or R-L)
R43_004_[0,1]: 18 H, 31 V-wraps       → Vertical variation (T-B or B-T)
R43_005_[0,0]: 8 H, 8 V-wraps         → Horizontal variation (opposite direction)
R43_005_[0,1]: 21 H, 46 V-wraps       → Vertical variation (opposite direction)
```

**Visual Confirmation:**
- R43_004_[0,0]: Clear LEFT→RIGHT color gradient
- R43_004_[0,1]: TOP→BOTTOM banding/gradient
- R43_005_[0,0]: LEFT→RIGHT gradient (similar to 004[0,0])
- R43_005_[0,1]: TOP→BOTTOM gradient (similar to 004[0,1])

### Consistency with MATLAB Reference

This structure matches the MATLAB reference code better:

```matlab
% From Gprocesskret.m line 7-10:
ang1 = f1{2}; %two axes
ang3 = f1{4};
ang0 = f1{1};
ang2 = f1{3};
```

The code expects 4 separate elements representing alternating axes:
- f1{1} (ang0) + f1{3} (ang2) = horizontal pair
- f1{2} (ang1) + f1{4} (ang3) = vertical pair

Our data structure is likely organized as two cycles, each containing both axes:
- File 004: First cycle with both axes
- File 005: Second cycle with both axes

## Impact on Current Implementation

### Files Affected

1. **`scripts/convert_sample_data.py`** (lines 82-110)
   - Makes incorrect assumptions about file organization
   - Needs correction to properly map directions

2. **All sample data analyses**
   - Any analysis using the converted data has incorrect direction labels
   - Need to re-verify results with corrected mapping

### Correct Mapping

**We need to determine which specific direction each represents:**

Option A (if 004 is first sweep, 005 is second):
```
R43_004_[0,0] → LR (horizontal forward)
R43_004_[0,1] → TB (vertical forward)
R43_005_[0,0] → RL (horizontal backward)
R43_005_[0,1] → BT (vertical backward)
```

Option B (if phase direction indicates reverse):
```
R43_004_[0,0] → RL
R43_004_[0,1] → BT
R43_005_[0,0] → LR
R43_005_[0,1] → TB
```

**Cannot determine specific L/R or T/B assignment without:**
- Original experimental log
- Expected retinotopic organization
- Anatomical reference alignment

## Next Steps

1. **Check phase relationships** between paired maps to determine if they're truly opposing
2. **Generate retinotopic maps** with different label permutations
3. **Validate against expected V1 organization** to find correct labeling
4. **Fix conversion script** once correct mapping is determined
5. **Re-run all analyses** with corrected labels

## Visualizations Generated

- `raw_phase_R43_004__00_.png` - Shows horizontal variation
- `raw_phase_R43_004__01_.png` - Shows vertical variation
- `raw_phase_R43_005__00_.png` - Shows horizontal variation (opposite)
- `raw_phase_R43_005__01_.png` - Shows vertical variation (opposite)
- `phase_analysis_*.png` - Gradient analysis for each map

## Conclusion

The conversion script's assumption that files are organized by stimulus axis (all horizontal in one file, all vertical in another) is **INCORRECT**. The files actually contain **paired orthogonal stimuli** from different acquisition cycles.

This explains why previous phase difference analysis showed ~0° instead of ~180° - we were comparing horizontal with vertical instead of opposing horizontals!
