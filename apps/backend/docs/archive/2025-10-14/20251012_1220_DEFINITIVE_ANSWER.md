# DEFINITIVE ANSWER: Sample Data Organization

## The Smoking Gun

Found in `/Users/Adam/KimLabISI/ISI-master/SerenoOverlay/generatekret.m` line 4:

```matlab
% generatekret('R43','000_005','000_004')
%              anim    AzExpt    AltExpt
```

**This example comment definitively shows:**
- **R43_000_005 = Azimuth (Horizontal)**
- **R43_000_004 = Altitude (Vertical)**

## The Conversion Script Error

`apps/backend/scripts/convert_sample_data.py` lines 31-42 **incorrectly assumes**:

```python
# Load horizontal retinotopy (R43_000_004)  ← WRONG! This is VERTICAL
# Load vertical retinotopy (R43_000_005)    ← WRONG! This is HORIZONTAL
```

**The files are SWAPPED!**

## Data Structure Complexity

However, my spatial analysis showed that:
- R43_004_[0,0] = Horizontal variation
- R43_004_[0,1] = Vertical variation
- R43_005_[0,0] = Horizontal variation
- R43_005_[0,1] = Vertical variation

This seems contradictory until we see the "one axes hack" in lines 56-60 and 387-391:

```matlab
%one axes hack
if length(f1m) == 2
    f1m{3} = f1m{2};
    f1m{4} = f1m{3};
    f1m{2} = f1m{1};
end
```

This transforms:
```
Original: f1m{1}, f1m{2}
After:    f1m{1}, f1m{1}, f1m{2}, f1m{2}
          (dup 1)  (dup 2)
```

## Reconciling the Findings

### Theory 1: Mixed Data Files
Each file contains **one measurement from each axis**:
- R43_000_005.mat (labeled "azimuth" but actually mixed):
  - [0,0] = Primary azimuth measurement
  - [0,1] = Secondary or cross-axis measurement
- R43_000_004.mat (labeled "altitude" but actually mixed):
  - [0,0] = Primary altitude measurement
  - [0,1] = Secondary or cross-axis measurement

### Theory 2: File Label vs Content Mismatch
The file naming convention (004/005 → altitude/azimuth) refers to the **primary stimulus type**, but each acquisition captured **both axes simultaneously**.

### Theory 3: Different Data Format
The sample data may be from a different acquisition setup or processing stage than what the MATLAB code expects.

## What We Can Conclude with Certainty

### ✅ CERTAIN:

1. **File assignment by MATLAB code:**
   - R43_000_005 is intended for azimuth (horizontal) processing
   - R43_000_004 is intended for altitude (vertical) processing

2. **Conversion script has wrong mapping:**
   - Current: 004→horizontal, 005→vertical
   - Should be: 005→horizontal, 004→vertical

3. **Each file contains BOTH horizontal and vertical components:**
   - Proven by spatial gradient analysis
   - [0,0] and [0,1] show orthogonal gradient patterns

### ❓ UNCERTAIN:

1. **Exact meaning of [0,0] and [0,1] in each file**
2. **Whether the files contain true opposing directions**
3. **Why spatial analysis shows mixed axes despite file labeling**

## Recommended Fix for Conversion Script

### Option A: Trust the MATLAB Label (Recommended)

```python
# R43_000_005.mat is the AZIMUTH (horizontal) experiment
mat1 = sio.loadmat(str(sample_dir / "R43_000_005.mat"))
azimuth_data = mat1['f1m']  # Contains 2 related measurements

# R43_000_004.mat is the ALTITUDE (vertical) experiment
mat2 = sio.loadmat(str(sample_dir / "R43_000_004.mat"))
altitude_data = mat2['f1m']  # Contains 2 related measurements

# Process based on what spatial analysis revealed:
# Each file has [0,0] with horizontal gradient and [0,1] with vertical gradient
# But the PRIMARY axis determines the file label

# For 005 (azimuth file):
primary_azimuth = azimuth_data[0, 0]  # Strong horizontal gradient
secondary_or_alt = azimuth_data[0, 1]  # Some vertical component

# For 004 (altitude file):
secondary_or_az = altitude_data[0, 0]  # Some horizontal component
primary_altitude = altitude_data[0, 1]  # Strong vertical gradient
```

### Option B: Trust Spatial Analysis

```python
# Ignore file labels, use spatial characteristics:
file1 = sio.loadmat('R43_000_004.mat')
file2 = sio.loadmat('R43_000_005.mat')

# Based on gradient analysis:
horizontal_1 = file1['f1m'][0, 0]  # Horizontal variation
vertical_1 = file1['f1m'][0, 1]    # Vertical variation
horizontal_2 = file2['f1m'][0, 0]  # Horizontal variation
vertical_2 = file2['f1m'][0, 1]    # Vertical variation

# Labels still unclear without experimental log
```

## Final Recommendation

1. **Update conversion script** to swap file assignments (005=horizontal, 004=vertical)
2. **Use spatial analysis results** to verify which array index is which
3. **Contact original lab** for definitive experimental log
4. **Document assumptions** clearly in code
5. **Validate** by comparing output with published figures

The example figure names `R43_005_004` suggest both files are used together, which is consistent with the MATLAB code that loads both AzExpt and AltExpt.
