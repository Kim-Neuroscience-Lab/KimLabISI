# Sample Data Direction Identity - Final Analysis Report

## Executive Summary

Through data-driven spatial analysis, we determined that **the sample data is organized differently than assumed by the conversion script**, but we **cannot definitively assign specific direction labels** (LR/RL/TB/BT) without additional experimental documentation.

## What We Know for Certain

### 1. File Organization Discovery ✓

**PROVEN:** Each MATLAB file contains **mixed axis data**, not pure horizontal or pure vertical:

```
CONVERSION SCRIPT ASSUMPTION (WRONG):
├── R43_000_004.mat = {horizontal_1, horizontal_2}
└── R43_000_005.mat = {vertical_1, vertical_2}

ACTUAL ORGANIZATION:
├── R43_000_004.mat = {horizontal, vertical} - one cycle
└── R43_000_005.mat = {horizontal, vertical} - another cycle
```

**Evidence:**
- **Spatial gradient analysis**: Clear horizontal vs vertical patterns
- **Phase wrapping counts**:
  - R43_004_[0,0]: 2 H-wraps, 0 V-wraps → Horizontal
  - R43_004_[0,1]: 18 H, 31 V-wraps → Vertical
  - R43_005_[0,0]: 8 H wraps → Horizontal
  - R43_005_[0,1]: 21 H, 46 V-wraps → Vertical
- **Visual inspection**: Phase maps show orthogonal gradient directions

### 2. Stimulus Axis Classification ✓

**PROVEN mapping:**
```
R43_004_[0,0] → HORIZONTAL (Azimuth: L-R or R-L)
R43_004_[0,1] → VERTICAL (Altitude: T-B or B-T)
R43_005_[0,0] → HORIZONTAL (Azimuth: L-R or R-L)
R43_005_[0,1] → VERTICAL (Altitude: T-B or B-T)
```

## What We Cannot Determine

### Specific Direction Assignments ✗

**UNKNOWN:** Which file/array corresponds to which specific direction:
- Is R43_004_[0,0] = LR or RL?
- Is R43_004_[0,1] = TB or BT?
- Is R43_005_[0,0] the opposite of R43_004_[0,0]?

**Why we can't determine this:**

1. **Phase relationships are inconclusive:**
   - R43_004_[0,0] vs R43_005_[0,0]: 55° difference (expected ~180° for opposing)
   - R43_004_[0,1] vs R43_005_[0,1]: -21° difference (expected ~180° for opposing)

2. **Possible explanations for unexpected phase relationships:**
   - Data may be pre-processed or delay-corrected
   - Acquisitions may have had different phase offsets
   - Data may represent something other than bidirectional pairs
   - Hemodynamic response variations between cycles

3. **Missing information needed:**
   - Original experimental log/parameters
   - Expected retinotopic organization for this animal
   - Anatomical alignment reference
   - Stimulus presentation order/timing

## Impact on Conversion Script

### Current Issues in `scripts/convert_sample_data.py`

**Lines 31-42:**
```python
# Load horizontal retinotopy (R43_000_004)  ← WRONG ASSUMPTION
# Load vertical retinotopy (R43_000_005)    ← WRONG ASSUMPTION
```

**Lines 82-110:**
```python
# Process horizontal data (assume LR = [0,0], RL = [0,1])  ← WRONG
# Process vertical data (assume TB = [0,0], BT = [0,1])    ← WRONG
```

### Recommended Fix (Multiple Options)

**Option 1: Conservative labeling (recommended)**
```python
# R43_000_004.mat contains one horizontal and one vertical
h1_phase, h1_mag = extract_phase_magnitude(file1['f1m'][0, 0])  # Horizontal A
v1_phase, v1_mag = extract_phase_magnitude(file1['f1m'][0, 1])  # Vertical A

# R43_000_005.mat contains opposite horizontal and vertical
h2_phase, h2_mag = extract_phase_magnitude(file2['f1m'][0, 0])  # Horizontal B
v2_phase, v2_mag = extract_phase_magnitude(file2['f1m'][0, 1])  # Vertical B

# Use generic labels until specific directions are verified
labels = ['horizontal_A', 'vertical_A', 'horizontal_B', 'vertical_B']
```

**Option 2: Assume conventional order**
```python
# ASSUMPTION: Files are in acquisition order, first cycle is forward direction
LR = file1['f1m'][0, 0]
TB = file1['f1m'][0, 1]
RL = file2['f1m'][0, 0]
BT = file2['f1m'][0, 1]
# NOTE: This is an educated guess, not verified!
```

**Option 3: Test all permutations**
```python
# Generate retinotopic maps for all possible label combinations
# Validate against expected V1 organization
# Select the combination that produces most coherent maps
```

## Generated Visualizations

All visualization files have been saved to document this analysis:

### Spatial Pattern Analysis
- `raw_phase_R43_004__00_.png` - Horizontal variation evident
- `raw_phase_R43_004__01_.png` - Vertical variation evident
- `raw_phase_R43_005__00_.png` - Horizontal variation
- `raw_phase_R43_005__01_.png` - Vertical variation
- `phase_analysis_*.png` - Detailed gradient analysis

### Retinotopic Maps with Corrected Pairing
- `corrected_azimuth_map.png` - Using 004[0,0] + 005[0,0]
- `corrected_elevation_map.png` - Using 004[0,1] + 005[0,1]

Note: These maps show reasonable spatial structure despite non-ideal phase relationships, suggesting the pairing may be functionally correct even if not perfectly opposed in phase.

## Recommendations

### Immediate Actions

1. **Update conversion script** to reflect actual file organization
2. **Use generic labels** (horizontal_A/B, vertical_A/B) until verified
3. **Document assumptions** clearly in code and metadata

### For Definitive Verification

To determine exact direction assignments, try one of:

1. **Contact original researchers** (Juavinett/Marshel lab) for experimental logs
2. **Anatomical validation**: Align maps with known V1 organization
3. **Test permutations**: Generate all possible label combinations and select most coherent
4. **Gradient sign analysis**: Determine increasing vs decreasing phase direction
5. **Compare with literature**: Check if published examples show expected patterns

### For Your Current Analysis

The uncertainty in sample data labels **does not affect** analysis of your experimental data ("names n stuff" session), as long as:
- Your acquisition system correctly labels directions during capture
- The analysis pipeline processes the data consistently
- You verify your own experimental setup's coordinate system

## Conclusion

**What we achieved:**
- ✅ Identified incorrect assumptions in conversion script
- ✅ Determined actual file organization structure
- ✅ Classified each map as horizontal or vertical axis
- ✅ Generated corrected retinotopic maps

**What remains uncertain:**
- ❓ Specific direction labels (LR vs RL, TB vs BT)
- ❓ Whether 004/005 pairs represent opposing directions
- ❓ Any preprocessing applied to original data

**Bottom line:** The sample data is useful for testing the analysis **pipeline**, but the specific direction labels should be considered **provisional** without additional documentation.
