# Hardware Interfaces

## Overview

This document defines the technical implementation details for controlling hardware components in the ISI Macroscope Control System. It focuses on HOW hardware is controlled at the API and protocol level, providing implementation specifications for RTX 4070 display control, PCO Panda 4.2 camera interface, timing synchronization, and calibration procedures.

## RTX 4070 Display Control Architecture

### DirectX 12 Implementation

**Exclusive Fullscreen Control:**
- **DXGI Factory**: Create swap chain with `DXGI_SWAP_EFFECT_FLIP_DISCARD` for WDDM optimization
- **Exclusive Mode**: Use `IDXGISwapChain::SetFullscreenState(TRUE, pTarget)` for mouse monitor
- **Command Queue**: Direct command queue with `D3D12_COMMAND_LIST_TYPE_DIRECT` for frame presentation
- **Fence Synchronization**: GPU/CPU synchronization using `ID3D12Fence` for timing validation

**Hardware Timer Queries:**
```cpp
// Microsecond precision timestamp implementation
ID3D12QueryHeap* pTimestampHeap;
D3D12_QUERY_HEAP_DESC queryHeapDesc = {
    .Type = D3D12_QUERY_HEAP_TYPE_TIMESTAMP,
    .Count = 2,  // Begin/End pairs
    .NodeMask = 0
};
device->CreateQueryHeap(&queryHeapDesc, IID_PPV_ARGS(&pTimestampHeap));

// Query GPU timestamp frequency
UINT64 timestampFrequency;
commandQueue->GetTimestampFrequency(&timestampFrequency);
```

**Frame Presentation Pipeline:**
- **Triple Buffering**: 3 swap chain buffers with `DXGI_SWAP_CHAIN_DESC1.BufferCount = 3`
- **Present Mode**: `Present(1, 0)` for VSYNC-locked 60 FPS presentation
- **Resource Barriers**: Proper transition barriers for `D3D12_RESOURCE_STATE_PRESENT`
- **Command List Execution**: Direct execution without intermediate command allocators

### Vulkan Alternative (Development/Cross-Platform)

**Surface Creation:**
- **WSI Integration**: Platform-specific surface creation (VK_KHR_win32_surface, VK_MVK_macos_surface)
- **Swap Chain**: `VK_PRESENT_MODE_FIFO_KHR` for consistent frame timing
- **Command Buffer**: Direct submission with minimal latency
- **Memory Management**: Device local memory allocation for stimulus frames

**Timing Implementation:**
```cpp
// Vulkan timestamp queries
VkQueryPool timestampPool;
VkQueryPoolCreateInfo poolInfo = {
    .sType = VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO,
    .queryType = VK_QUERY_TYPE_TIMESTAMP,
    .queryCount = 2
};
vkCreateQueryPool(device, &poolInfo, nullptr, &timestampPool);
```

### GPU Memory Management

**VRAM Allocation Strategy:**
- **Stimulus Cache**: 4 GB committed resource with `D3D12_HEAP_TYPE_DEFAULT`
- **Frame Buffers**: 3 GB for triple buffering using `D3D12_RESOURCE_DIMENSION_TEXTURE2D`
- **Processing Workspace**: 2 GB for compute shader operations
- **Memory Mapping**: CPU-accessible upload heap for stimulus data streaming

**Buffer Management:**
- **Upload Strategy**: Ring buffer for continuous HDF5-to-GPU streaming
- **Memory Barriers**: Proper UAV barriers for compute shader synchronization
- **Resource States**: Efficient transitions between `COPY_DEST` and `SHADER_RESOURCE`

## PCO Panda 4.2 USB Camera Interface

### PCO SDK Integration

**Camera Initialization:**
```cpp
// PCO SDK initialization sequence
HANDLE hCamera;
PCO_Description strDescription;
PCO_CameraType strCameraType;

// Open camera connection
dwError = PCO_OpenCamera(&hCamera, 0);  // Interface 0 (USB)
if(dwError != PCO_NOERROR) {
    // Handle initialization failure
}

// Get camera capabilities
PCO_GetCameraDescription(hCamera, &strDescription);
PCO_GetCameraType(hCamera, &strCameraType);
```

**Frame Capture Configuration:**
- **Pixel Format**: 16-bit monochrome (`PCO_GREY16` mode)
- **ROI Setting**: Full sensor 2048×2048 using `PCO_SetROI()`
- **Trigger Mode**: Software trigger with `PCO_SetTriggerMode()`
- **Exposure Control**: Range 21μs - 5s with `PCO_SetDelayExposureTime()`

**Buffer Management:**
```cpp
// Allocate frame buffers
WORD* pImageBuffer[4];  // Quad buffering
for(int i = 0; i < 4; i++) {
    pImageBuffer[i] = (WORD*)_aligned_malloc(
        strDescription.wMaxHorzResStd * strDescription.wMaxVertResStd * 2,
        16  // 16-byte alignment for CUDA
    );
    PCO_AllocateBuffer(hCamera, pImageBuffer[i], &dwBufferSize);
}
```

### USB 3.1 Protocol Implementation

**Bandwidth Optimization:**
- **Transfer Mode**: Bulk transfer with maximum packet size
- **Queue Depth**: 4-8 outstanding transfers for sustained throughput
- **Buffer Size**: 16.7 MB per frame (4.2 MPixel × 16-bit × overhead)
- **USB Descriptor**: Validate SuperSpeed capability and bandwidth allocation

**Data Pipeline:**
```
PCO Panda → USB 3.1 Controller → System RAM → CUDA Memory → Processing
```

**Transfer Validation:**
- **Frame Integrity**: Checksum validation for each 16-bit frame
- **Sequence Numbers**: Detect dropped or duplicate frames
- **Bandwidth Monitoring**: Real-time USB utilization tracking
- **Error Recovery**: Automatic transfer retry with exponential backoff

### Frame Capture Pipeline

**Acquisition Sequence:**
```cpp
// Start acquisition
PCO_SetRecordingState(hCamera, 1);  // Start recording

// Capture loop (30 FPS target)
while(acquisitionActive) {
    // Arm camera for next frame
    PCO_ArmCamera(hCamera);

    // Software trigger
    PCO_ForceTrigger(hCamera);

    // Wait for frame completion
    PCO_GetImageEx(hCamera, 1, 0, 0, pImageBuffer[bufferIndex],
                   wXRes, wYRes, sizeof(WORD));

    // Record timestamp
    recordFrameTimestamp(bufferIndex);

    // Process frame (CUDA transfer)
    processFrame(pImageBuffer[bufferIndex], bufferIndex);

    bufferIndex = (bufferIndex + 1) % 4;  // Ring buffer
}
```

**Timestamp Correlation:**
- **PCO Timestamps**: Camera internal timestamps via `PCO_GetTimestampMode()`
- **System Timestamps**: High-resolution `QueryPerformanceCounter()`
- **GPU Correlation**: Synchronize with RTX 4070 timer queries
- **Drift Compensation**: Periodic clock synchronization validation

## Manual Filter Switching Protocols

### Filter Specifications

**Filter Types:**
- **Green Filter (530 nm)**: Anatomical imaging, baseline vasculature
- **Red Filter (630 nm)**: Functional ISI imaging, hemodynamic response
- **Transmission Characteristics**: >90% transmission in passband, <1% outside
- **Physical Mounting**: Standard 25mm filter holders with manual rotation

### Switching Procedures

**Manual Protocol:**
1. **Acquisition Pause**: Stop camera capture during filter change
2. **Filter Rotation**: Manual 90° rotation between green/red positions
3. **Alignment Check**: Visual confirmation of proper filter positioning
4. **System Resume**: Restart acquisition with appropriate filter metadata

**Timing Considerations:**
- **Switch Duration**: ~10-15 seconds for manual filter change
- **Stabilization Time**: 2-3 seconds for optical settling
- **State Detection**: Software prompt for filter confirmation
- **Metadata Logging**: Record filter state with each acquisition session

**Integration Points:**
- **Acquisition Pipeline**: Automatic metadata inclusion in data files
- **Analysis Pipeline**: Filter-specific processing algorithms
- **UI Indication**: Clear filter state display in frontend interface

## Hardware Timing Synchronization

### Cross-Hardware Timestamp Correlation

**RTX 4070 Timer Queries:**
```cpp
// Get GPU timestamp
commandList->EndQuery(timestampHeap, D3D12_QUERY_TYPE_TIMESTAMP, 0);
commandList->ResolveQueryData(timestampHeap, D3D12_QUERY_TYPE_TIMESTAMP,
                              0, 1, timestampBuffer, 0);

// Convert to microseconds
UINT64 gpuTimestamp, frequency;
commandQueue->GetTimestampFrequency(&frequency);
double microseconds = (double)gpuTimestamp / frequency * 1000000.0;
```

**PCO Timestamp Integration:**
```cpp
// Correlate camera and GPU timestamps
struct TimestampPair {
    UINT64 gpuTimestamp;    // RTX 4070 timer query
    UINT64 cameraTimestamp; // PCO Panda internal clock
    UINT64 systemTimestamp; // QueryPerformanceCounter
    double correlationOffset; // Calculated drift compensation
};
```

### Clock Synchronization Implementation

**Synchronization Strategy:**
- **Master Clock**: System `QueryPerformanceCounter()` as reference
- **GPU Correlation**: Periodic GPU-to-system timestamp mapping
- **Camera Correlation**: PCO internal clock offset calculation
- **Drift Monitoring**: Continuous offset tracking and compensation

**Precision Requirements:**
- **Target Accuracy**: <1μs timestamp precision
- **Validation Method**: Cross-reference multiple timestamp sources
- **Error Detection**: Statistical analysis of timestamp consistency
- **Calibration Frequency**: Every 60 seconds during acquisition

## Monitor Calibration Procedures

### Display Calibration

**Gamma Correction:**
```cpp
// DirectX 12 gamma ramp programming
DXGI_GAMMA_CONTROL gammaControl;
for(int i = 0; i < 1024; i++) {
    float normalized = (float)i / 1023.0f;
    // Apply gamma curve (typically 2.2)
    gammaControl.GammaCurve[i] = pow(normalized, 1.0f / 2.2f);
}
swapChain->SetGammaControl(&gammaControl);
```

**Color Space Management:**
- **sRGB Standard**: Ensure accurate color representation for scientific imaging
- **Luminance Calibration**: Measure and calibrate display brightness levels
- **Uniformity Validation**: Check display uniformity across stimulus presentation area

### Spatial Calibration

**Pixel-to-Degree Mapping:**
- **Physical Measurement**: Actual monitor distance and size verification
- **Angular Calculation**: Convert monitor pixels to visual field degrees
- **Spherical Correction**: Apply geometric correction for flat display on spherical retina
- **Validation**: Compare calculated vs. measured angular coverage

**Geometry Correction:**
```cpp
// Spherical coordinate transformation matrix
struct SphericalTransform {
    float distance;      // Monitor distance in cm
    float angle;         // Monitor angle in degrees
    float pixelsPerDegree; // Calibrated pixel density
    Matrix4x4 transformMatrix; // 3D transformation
};
```

### Timing Calibration

**Refresh Rate Validation:**
- **VSYNC Timing**: Measure actual refresh rate vs. 60 Hz target
- **Frame Duration**: Validate 16.667ms frame periods
- **Jitter Analysis**: Statistical analysis of frame timing consistency
- **Hardware Validation**: Compare software timing with external photodiode

**Frame Timing Verification:**
```cpp
// Measure actual frame presentation timing
LARGE_INTEGER frequency, startTime, endTime;
QueryPerformanceFrequency(&frequency);

for(int frame = 0; frame < 1800; frame++) {  // 30 seconds @ 60 FPS
    QueryPerformanceCounter(&startTime);

    // Present frame
    swapChain->Present(1, 0);

    QueryPerformanceCounter(&endTime);
    double frameDuration = (double)(endTime.QuadPart - startTime.QuadPart)
                          / frequency.QuadPart * 1000000.0;  // μs

    // Validate 16667μs ± 10μs tolerance
    validateFrameTiming(frameDuration);
}
```

### Calibration Data Persistence

**Storage Format:**
```json
{
  "calibration_data": {
    "timestamp": "2024-03-15T14:30:45Z",
    "display": {
      "gamma_curve": [0.0, 0.001, 0.002, ...],
      "color_profile": "sRGB",
      "luminance_max": 120.0,
      "uniformity_map": [[1.0, 0.98, ...], ...]
    },
    "spatial": {
      "pixels_per_degree": 28.5,
      "transform_matrix": [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 0.9848, -0.1736, 0.0],
        [0.0, 0.1736, 0.9848, 0.0],
        [0.0, 0.0, 0.0, 1.0]
      ]
    },
    "timing": {
      "refresh_rate": 59.997,
      "frame_jitter_std": 8.2,
      "vsync_accuracy": 0.95
    }
  }
}
```

**Validation and Recalibration:**
- **Validity Period**: 30 days for display calibration, 7 days for timing
- **Drift Detection**: Automatic validation during system startup
- **Recalibration Triggers**: Hardware changes, performance degradation
- **Quality Metrics**: Statistical validation of calibration accuracy

## System Integration (Intel 13700K + Windows 11)

### CPU Core Assignment

**Real-Time Thread Allocation:**
```cpp
// Assign display timing thread to P-core
HANDLE displayThread = CreateThread(NULL, 0, DisplayTimingThread, NULL,
                                   CREATE_SUSPENDED, &threadId);

// Set thread affinity to specific P-core (core 0)
DWORD_PTR affinityMask = 1ULL << 0;
SetThreadAffinityMask(displayThread, affinityMask);

// Set real-time priority
SetThreadPriority(displayThread, THREAD_PRIORITY_TIME_CRITICAL);
```

**Performance Isolation:**
- **P-Core Assignment**: Real-time display and camera threads
- **E-Core Assignment**: Background processing, file I/O, frontend
- **NUMA Awareness**: Memory allocation close to assigned cores
- **Interrupt Handling**: Isolate real-time threads from system interrupts

### Windows 11 Integration

**WDDM Exclusive Mode:**
- **Display Driver Model**: Leverage WDDM 3.0 for hardware page flipping
- **Exclusive Access**: Bypass Windows compositor for minimal latency
- **Hardware Scheduling**: Enable GPU hardware scheduling for reduced overhead
- **Memory Management**: Large page support for VRAM allocations

**DirectShow/Media Foundation:**
```cpp
// Camera interface integration
IMFMediaSource* pMediaSource;
IMFSourceReader* pSourceReader;

// Configure camera source
hr = MFCreateSourceReaderFromMediaSource(pMediaSource,
                                        pAttributes, &pSourceReader);

// Set media type for 16-bit capture
IMFMediaType* pMediaType;
MFCreateMediaType(&pMediaType);
pMediaType->SetGUID(MF_MT_MAJOR_TYPE, MFMediaType_Video);
pMediaType->SetGUID(MF_MT_SUBTYPE, MFVideoFormat_Y16);
pSourceReader->SetCurrentMediaType(MF_SOURCE_READER_FIRST_VIDEO_STREAM,
                                  NULL, pMediaType);
```

### Cross-Platform Abstraction Layer

**Development vs. Production:**
- **macOS Development**: Metal Compute/MetalKit for GPU operations
- **Windows Production**: DirectX 12/CUDA optimized implementation
- **Interface Abstraction**: Common interface layer for hardware operations
- **Performance Parity**: Ensure equivalent timing and precision across platforms

**Hardware Abstraction:**
```cpp
// Platform-agnostic hardware interface
class IHardwareInterface {
public:
    virtual bool InitializeDisplay() = 0;
    virtual bool InitializeCamera() = 0;
    virtual uint64_t GetHardwareTimestamp() = 0;
    virtual bool PresentFrame(void* frameData) = 0;
    virtual bool CaptureFrame(void* buffer) = 0;
};

// Platform-specific implementations
class WindowsHardwareInterface : public IHardwareInterface;
class MacOSHardwareInterface : public IHardwareInterface;
```

This hardware interface specification provides the technical foundation for precise, real-time control of the ISI imaging system while maintaining cross-platform compatibility and development efficiency.