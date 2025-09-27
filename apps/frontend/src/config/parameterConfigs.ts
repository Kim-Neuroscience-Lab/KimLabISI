export interface ParameterConfig {
  key: string
  label: string
  type: 'text' | 'number' | 'select' | 'range'
  options?: Array<{ value: string; label: string }>
  min?: number
  max?: number
  step?: number
  unit?: string
  placeholder?: string
  disabled?: boolean
}

export const sessionParameterConfigs: ParameterConfig[] = [
  {
    key: 'sessionName',
    label: 'Session Name',
    type: 'text',
    placeholder: 'Enter session name'
  },
  {
    key: 'subject',
    label: 'Subject ID',
    type: 'text',
    placeholder: 'Enter subject ID'
  },
  {
    key: 'researcher',
    label: 'Researcher',
    type: 'text',
    placeholder: 'Enter researcher name'
  },
  {
    key: 'notes',
    label: 'Notes',
    type: 'text',
    placeholder: 'Session notes'
  }
]

export const monitorParameterConfigs: ParameterConfig[] = [
  {
    key: 'cpuUsage',
    label: 'CPU Usage',
    type: 'range',
    min: 0,
    max: 100,
    unit: '%',
    disabled: true
  },
  {
    key: 'memoryUsage',
    label: 'Memory Usage',
    type: 'range',
    min: 0,
    max: 100,
    unit: '%',
    disabled: true
  },
  {
    key: 'diskUsage',
    label: 'Disk Usage',
    type: 'range',
    min: 0,
    max: 100,
    unit: '%',
    disabled: true
  },
  {
    key: 'temperature',
    label: 'System Temperature',
    type: 'number',
    unit: '°C',
    disabled: true
  }
]

export const stimulusParameterConfigs: ParameterConfig[] = [
  {
    key: 'stimulusType',
    label: 'Stimulus Type',
    type: 'select',
    options: [
      { value: 'gratings', label: 'Drifting Gratings' },
      { value: 'bars', label: 'Moving Bars' },
      { value: 'spots', label: 'Flashing Spots' },
      { value: 'natural', label: 'Natural Images' }
    ]
  },
  {
    key: 'orientation',
    label: 'Orientation',
    type: 'range',
    min: 0,
    max: 360,
    step: 15,
    unit: '°'
  },
  {
    key: 'spatialFreq',
    label: 'Spatial Frequency',
    type: 'number',
    min: 0.01,
    max: 2.0,
    step: 0.01,
    unit: 'cpd'
  },
  {
    key: 'temporalFreq',
    label: 'Temporal Frequency',
    type: 'number',
    min: 0.5,
    max: 20.0,
    step: 0.5,
    unit: 'Hz'
  },
  {
    key: 'contrast',
    label: 'Contrast',
    type: 'range',
    min: 0,
    max: 100,
    step: 1,
    unit: '%'
  },
  {
    key: 'duration',
    label: 'Stimulus Duration',
    type: 'number',
    min: 0.1,
    max: 10.0,
    step: 0.1,
    unit: 's'
  }
]

export const cameraParameterConfigs: ParameterConfig[] = [
  {
    key: 'cameraDevice',
    label: 'Camera Device',
    type: 'select',
    options: [
      { value: 'webcam', label: 'Webcam' },
      { value: 'scientific', label: 'Scientific Camera' }
    ]
  },
  {
    key: 'resolution',
    label: 'Resolution',
    type: 'select',
    options: [
      { value: '640x480', label: '640 x 480' },
      { value: '1280x720', label: '1280 x 720' },
      { value: '1920x1080', label: '1920 x 1080' }
    ]
  },
  {
    key: 'frameRate',
    label: 'Frame Rate',
    type: 'number',
    min: 1,
    max: 120,
    unit: 'fps'
  },
  {
    key: 'exposure',
    label: 'Exposure Time',
    type: 'number',
    min: 0.1,
    max: 1000,
    step: 0.1,
    unit: 'ms'
  },
  {
    key: 'gain',
    label: 'Gain',
    type: 'range',
    min: 0,
    max: 100,
    step: 1,
    unit: 'dB'
  },
  {
    key: 'binning',
    label: 'Binning',
    type: 'select',
    options: [
      { value: '1x1', label: '1 x 1' },
      { value: '2x2', label: '2 x 2' },
      { value: '4x4', label: '4 x 4' }
    ]
  }
]

export const acquisitionParameterConfigs: ParameterConfig[] = [
  {
    key: 'acquisitionMode',
    label: 'Acquisition Mode',
    type: 'select',
    options: [
      { value: 'continuous', label: 'Continuous' },
      { value: 'triggered', label: 'Triggered' },
      { value: 'time_series', label: 'Time Series' }
    ]
  },
  {
    key: 'duration',
    label: 'Duration',
    type: 'number',
    min: 1,
    max: 3600,
    unit: 's'
  },
  {
    key: 'samplingRate',
    label: 'Sampling Rate',
    type: 'number',
    min: 1,
    max: 1000,
    unit: 'Hz'
  },
  {
    key: 'triggerSource',
    label: 'Trigger Source',
    type: 'select',
    options: [
      { value: 'manual', label: 'Manual' },
      { value: 'external', label: 'External' },
      { value: 'software', label: 'Software' }
    ]
  },
  {
    key: 'saveFormat',
    label: 'Save Format',
    type: 'select',
    options: [
      { value: 'hdf5', label: 'HDF5' },
      { value: 'tiff', label: 'TIFF Stack' },
      { value: 'avi', label: 'AVI Video' }
    ]
  },
  {
    key: 'compressionLevel',
    label: 'Compression Level',
    type: 'range',
    min: 0,
    max: 9,
    step: 1
  }
]

export const analysisParameterConfigs: ParameterConfig[] = [
  {
    key: 'analysisType',
    label: 'Analysis Type',
    type: 'select',
    options: [
      { value: 'optical_flow', label: 'Optical Flow' },
      { value: 'signal_extraction', label: 'Signal Extraction' },
      { value: 'response_mapping', label: 'Response Mapping' }
    ]
  },
  {
    key: 'roiSelection',
    label: 'ROI Selection',
    type: 'select',
    options: [
      { value: 'manual', label: 'Manual' },
      { value: 'automatic', label: 'Automatic' },
      { value: 'template', label: 'Template-based' }
    ]
  },
  {
    key: 'filterType',
    label: 'Filter Type',
    type: 'select',
    options: [
      { value: 'gaussian', label: 'Gaussian' },
      { value: 'butterworth', label: 'Butterworth' },
      { value: 'median', label: 'Median' }
    ]
  },
  {
    key: 'filterCutoff',
    label: 'Filter Cutoff',
    type: 'number',
    min: 0.1,
    max: 50.0,
    step: 0.1,
    unit: 'Hz'
  },
  {
    key: 'threshold',
    label: 'Detection Threshold',
    type: 'range',
    min: 0,
    max: 100,
    step: 1,
    unit: '%'
  },
  {
    key: 'windowSize',
    label: 'Analysis Window',
    type: 'number',
    min: 10,
    max: 1000,
    step: 10,
    unit: 'ms'
  }
]

export const defaultParameterValues = {
  session: {
    sessionName: '',
    subject: '',
    researcher: '',
    notes: ''
  },
  monitor: {
    cpuUsage: 45,
    memoryUsage: 62,
    diskUsage: 78,
    temperature: 65
  },
  stimulus: {
    stimulusType: 'gratings',
    orientation: 0,
    spatialFreq: 0.05,
    temporalFreq: 2.0,
    contrast: 50,
    duration: 2.0
  },
  camera: {
    cameraDevice: 'webcam',
    resolution: '1280x720',
    frameRate: 30,
    exposure: 33.3,
    gain: 0,
    binning: '1x1'
  },
  acquisition: {
    acquisitionMode: 'continuous',
    duration: 300,
    samplingRate: 100,
    triggerSource: 'manual',
    saveFormat: 'hdf5',
    compressionLevel: 5
  },
  analysis: {
    analysisType: 'optical_flow',
    roiSelection: 'manual',
    filterType: 'gaussian',
    filterCutoff: 10.0,
    threshold: 50,
    windowSize: 100
  }
}