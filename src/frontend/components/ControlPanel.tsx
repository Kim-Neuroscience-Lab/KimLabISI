import React, { useState } from 'react'
import {
  SlidersHorizontal,
  FolderCog,
  MonitorCog,
  Columns3Cog,
  Video,
  FileVideoCamera,
  BrainCog,
  LucideIcon
} from 'lucide-react'
import { ParameterSection, ParameterConfig } from './ParameterSection'

interface SessionParameters {
  session_name: string
  animal_id: string
  animal_age: string
}

interface MonitorParameters {
  monitor_distance_cm: number
  monitor_lateral_angle_deg: number
  monitor_tilt_angle_deg: number
  monitor_width_cm: number
  monitor_height_cm: number
  monitor_width_px: number
  monitor_height_px: number
  monitor_fps: number
}

interface StimulusParameters {
  checker_size_deg: number
  bar_width_deg: number
  drift_speed_deg_per_sec: number
  strobe_rate_hz: number
  contrast: number
}

interface AcquisitionParameters {
  baseline_sec: number
  between_sec: number
  cycles: number
  directions: string[]
}

interface AnalysisParameters {
  ring_size_mm: number
  vfs_threshold_sd: number
  smoothing_sigma: number
  magnitude_threshold: number
  phase_filter_sigma: number
  gradient_window_size: number
  area_min_size_mm2: number
  response_threshold_percent: number
}

interface CameraParameters {
  selected_camera: string
  camera_fps: number
  camera_width_px: number
  camera_height_px: number
}

// Backend-compatible parameter configurations
const sessionParameterConfigs: ParameterConfig[] = [
  {
    key: 'session_name',
    label: 'Session Name',
    type: 'text',
    placeholder: 'Enter session name'
  },
  {
    key: 'animal_id',
    label: 'Animal ID',
    type: 'text',
    placeholder: 'Enter animal ID'
  },
  {
    key: 'animal_age',
    label: 'Animal Age',
    type: 'text',
    placeholder: 'Enter animal age'
  }
]

const monitorParameterConfigs: ParameterConfig[] = [
  {
    key: 'monitor_distance_cm',
    label: 'Monitor Distance',
    type: 'number',
    min: 1,
    max: 100,
    unit: 'cm'
  },
  {
    key: 'monitor_lateral_angle_deg',
    label: 'Lateral Angle',
    type: 'number',
    min: -90,
    max: 90,
    unit: '°'
  },
  {
    key: 'monitor_tilt_angle_deg',
    label: 'Tilt Angle',
    type: 'number',
    min: -90,
    max: 90,
    unit: '°'
  },
  {
    key: 'monitor_width_cm',
    label: 'Monitor Width',
    type: 'number',
    min: 10,
    max: 200,
    unit: 'cm'
  },
  {
    key: 'monitor_height_cm',
    label: 'Monitor Height',
    type: 'number',
    min: 10,
    max: 200,
    unit: 'cm'
  },
  {
    key: 'monitor_width_px',
    label: 'Monitor Width (px)',
    type: 'number',
    min: 640,
    max: 4096
  },
  {
    key: 'monitor_height_px',
    label: 'Monitor Height (px)',
    type: 'number',
    min: 480,
    max: 2160
  },
  {
    key: 'monitor_fps',
    label: 'Monitor FPS',
    type: 'number',
    min: 30,
    max: 240,
    unit: 'fps'
  }
]

const stimulusParameterConfigs: ParameterConfig[] = [
  {
    key: 'checker_size_deg',
    label: 'Checker Size',
    type: 'number',
    min: 1,
    max: 100,
    unit: '°'
  },
  {
    key: 'bar_width_deg',
    label: 'Bar Width',
    type: 'number',
    min: 1,
    max: 100,
    unit: '°'
  },
  {
    key: 'drift_speed_deg_per_sec',
    label: 'Drift Speed',
    type: 'number',
    min: 0.1,
    max: 50,
    unit: '°/s'
  },
  {
    key: 'strobe_rate_hz',
    label: 'Strobe Rate',
    type: 'number',
    min: 0.1,
    max: 100,
    unit: 'Hz'
  },
  {
    key: 'contrast',
    label: 'Contrast',
    type: 'range',
    min: 0,
    max: 1,
    step: 0.01
  }
]

const acquisitionParameterConfigs: ParameterConfig[] = [
  {
    key: 'baseline_sec',
    label: 'Baseline Duration',
    type: 'number',
    min: 0.1,
    max: 60,
    unit: 's'
  },
  {
    key: 'between_sec',
    label: 'Between Trials',
    type: 'number',
    min: 0.1,
    max: 60,
    unit: 's'
  },
  {
    key: 'cycles',
    label: 'Number of Cycles',
    type: 'number',
    min: 1,
    max: 100
  }
]

const analysisParameterConfigs: ParameterConfig[] = [
  {
    key: 'ring_size_mm',
    label: 'Ring Size',
    type: 'number',
    min: 0.1,
    max: 10,
    unit: 'mm'
  },
  {
    key: 'vfs_threshold_sd',
    label: 'VFS Threshold',
    type: 'number',
    min: 0.1,
    max: 10,
    unit: 'SD'
  },
  {
    key: 'smoothing_sigma',
    label: 'Smoothing Sigma',
    type: 'number',
    min: 0.1,
    max: 5,
    step: 0.1
  },
  {
    key: 'magnitude_threshold',
    label: 'Magnitude Threshold',
    type: 'range',
    min: 0,
    max: 1,
    step: 0.01
  },
  {
    key: 'phase_filter_sigma',
    label: 'Phase Filter Sigma',
    type: 'number',
    min: 0.1,
    max: 10,
    step: 0.1
  },
  {
    key: 'gradient_window_size',
    label: 'Gradient Window Size',
    type: 'number',
    min: 1,
    max: 20
  },
  {
    key: 'area_min_size_mm2',
    label: 'Min Area Size',
    type: 'number',
    min: 0.01,
    max: 5,
    unit: 'mm²'
  },
  {
    key: 'response_threshold_percent',
    label: 'Response Threshold',
    type: 'range',
    min: 0,
    max: 100,
    unit: '%'
  }
]

// Create camera parameter configs dynamically to handle disabled state
const createCameraParameterConfigs = (autoDetected: boolean): ParameterConfig[] => [
  {
    key: 'selected_camera',
    label: 'Camera Device',
    type: 'select',
    options: [] // Will be populated dynamically from availableCameras
  },
  {
    key: 'camera_fps',
    label: 'Camera FPS',
    type: 'number',
    min: 1,
    max: 240,
    unit: 'fps',
    disabled: autoDetected
  },
  {
    key: 'camera_width_px',
    label: 'Camera Width',
    type: 'number',
    min: 64,
    max: 4096,
    unit: 'px',
    disabled: autoDetected
  },
  {
    key: 'camera_height_px',
    label: 'Camera Height',
    type: 'number',
    min: 64,
    max: 4096,
    unit: 'px',
    disabled: autoDetected
  }
]

interface HardwareStatus {
  camera: 'online' | 'offline' | 'error'
  display: 'online' | 'offline' | 'error'
}

interface ControlPanelProps {
  isConnected: boolean
  isExperimentRunning: boolean
  hardwareStatus: HardwareStatus
  onStopExperiment: () => void
  sendCommand: (command: any) => Promise<any>
  onCollapseChange?: (isCollapsed: boolean) => void
  isReady: boolean
}

interface CollapsibleSectionProps {
  title: string
  icon: LucideIcon
  sectionKey: string
  isCollapsed: boolean
  onToggle: (sectionKey: string) => void
  children: React.ReactNode
}

const CollapsibleSection: React.FC<CollapsibleSectionProps> = ({
  title,
  icon: Icon,
  sectionKey,
  isCollapsed,
  onToggle,
  children
}) => (
  <div className="border-b border-sci-secondary-700">
    <div className={`h-12 flex items-center gap-2 px-4 ${!isCollapsed ? 'border-b border-sci-secondary-700' : ''}`}>
      <Icon
        className="w-4 h-4 cursor-pointer hover:text-sci-primary-400 transition-colors"
        onClick={() => onToggle(sectionKey)}
      />
      <h3 className="text-sm font-semibold text-sci-secondary-200">{title}</h3>
    </div>
    {!isCollapsed && (
      <div className="px-4 pt-4 pb-8 space-y-4">
        {children}
      </div>
    )}
  </div>
)

const ControlPanel: React.FC<ControlPanelProps> = ({
  isConnected,
  isExperimentRunning,
  hardwareStatus,
  onStopExperiment,
  sendCommand,
  onCollapseChange,
  isReady
}) => {
  // Parameter states for all sections
  const [sessionParams, setSessionParams] = useState<SessionParameters>({
    session_name: '',
    animal_id: '',
    animal_age: ''
  })

  const [monitorParams, setMonitorParams] = useState<MonitorParameters>({
    monitor_distance_cm: 10.0,
    monitor_lateral_angle_deg: 20.0,
    monitor_tilt_angle_deg: 0.0,
    monitor_width_cm: 52.0,
    monitor_height_cm: 52.0,
    monitor_width_px: 1920,
    monitor_height_px: 1080,
    monitor_fps: 60.0
  })

  const [stimulusParams, setStimulusParams] = useState<StimulusParameters>({
    checker_size_deg: 25.0,
    bar_width_deg: 20.0,
    drift_speed_deg_per_sec: 9.0,
    strobe_rate_hz: 6.0,
    contrast: 0.8
  })

  const [acquisitionParams, setAcquisitionParams] = useState<AcquisitionParameters>({
    baseline_sec: 5.0,
    between_sec: 10.0,
    cycles: 10,
    directions: ['LR', 'RL', 'TB', 'BT']
  })

  const [analysisParams, setAnalysisParams] = useState<AnalysisParameters>({
    ring_size_mm: 2.0,
    vfs_threshold_sd: 2.5,
    smoothing_sigma: 1.0,
    magnitude_threshold: 0.3,
    phase_filter_sigma: 2.0,
    gradient_window_size: 5,
    area_min_size_mm2: 0.25,
    response_threshold_percent: 30.0
  })

  const [cameraParams, setCameraParams] = useState<CameraParameters>({
    selected_camera: '',
    camera_fps: 0,
    camera_width_px: 0,
    camera_height_px: 0
  })

  // Track if camera parameters were auto-detected
  const [cameraParamsAutoDetected, setCameraParamsAutoDetected] = useState(false)

  // Available cameras - fetched from backend camera detection
  const [availableCameras, setAvailableCameras] = useState<string[]>([])

  // Function to get camera capabilities from backend via IPC
  const getCameraCapabilities = async (cameraName: string) => {
    try {
      const response = await sendCommand({
        type: 'get_camera_capabilities',
        camera_name: cameraName
      })

      if (response && response.capabilities) {
        return {
          width: response.capabilities.width,
          height: response.capabilities.height,
          frameRate: response.capabilities.frameRate
        }
      }
    } catch (error) {
      console.error('Failed to get camera capabilities from backend:', error)
    }

    return {
      width: undefined,
      height: undefined,
      frameRate: undefined
    }
  }

  // Function to fetch available cameras from backend
  const fetchAvailableCameras = async () => {
    // Only try backend detection if system is connected
    if (isConnected) {
      try {
        // Call the backend camera detection API
        const response = await sendCommand({
          type: 'detect_cameras'
        })


        if (response && response.cameras && Array.isArray(response.cameras)) {
          setAvailableCameras(response.cameras)
          return
        }
      } catch (error) {
        // Backend camera detection failed, fall back to browser detection
      }
    }

    // Browser-based fallback detection
    try {
      const devices = await navigator.mediaDevices.enumerateDevices()
      const videoDevices = devices
        .filter(device => device.kind === 'videoinput')
        .map(device => device.label || `Camera ${device.deviceId.slice(0, 8)}`)

      if (videoDevices.length > 0) {
        setAvailableCameras(videoDevices)
      } else {
        setAvailableCameras(['Built-in Camera'])
      }
    } catch (mediaError) {
      // Browser camera detection failed, use fallback
      setAvailableCameras(['Built-in Camera'])
    }
  }

  // Handle camera selection changes and auto-detect capabilities
  const handleCameraChange = React.useCallback(async (newCameraParams: Record<string, any>) => {
    // Check if the camera selection changed
    if (newCameraParams.selected_camera && newCameraParams.selected_camera !== cameraParams.selected_camera) {
      try {
        // Auto-detect camera capabilities
        const capabilities = await getCameraCapabilities(newCameraParams.selected_camera)

        // Update camera parameters with detected values
        const updatedParams = {
          ...cameraParams,
          ...newCameraParams
        }

        // Set detected values if they exist and are valid
        if (capabilities.frameRate !== undefined && capabilities.frameRate > 0) {
          updatedParams.camera_fps = capabilities.frameRate
        }
        if (capabilities.width !== undefined && capabilities.width > 0) {
          updatedParams.camera_width_px = capabilities.width
        }
        if (capabilities.height !== undefined && capabilities.height > 0) {
          updatedParams.camera_height_px = capabilities.height
        }

        setCameraParams(updatedParams as CameraParameters)

        // Mark as auto-detected if we successfully detected any camera capabilities
        const hasDetectedValues = (capabilities.frameRate !== undefined && capabilities.frameRate > 0) ||
                                 (capabilities.width !== undefined && capabilities.width > 0) ||
                                 (capabilities.height !== undefined && capabilities.height > 0)
        setCameraParamsAutoDetected(hasDetectedValues)
      } catch (error) {
        console.error('Failed to auto-detect camera capabilities:', error)
        // Just update the camera selection without auto-detection
        setCameraParams(prev => ({ ...prev, ...newCameraParams }) as CameraParameters)
        setCameraParamsAutoDetected(false)
      }
    } else {
      // Just update the parameters normally without auto-detection
      setCameraParams(prev => ({ ...prev, ...newCameraParams }) as CameraParameters)
    }
  }, [getCameraCapabilities])

  // Fetch cameras only when both connected AND ready
  React.useEffect(() => {
    if (isConnected && isReady) {
      fetchAvailableCameras()
    }
  }, [isConnected, isReady])

  // Auto-detect capabilities for first camera when cameras are loaded
  React.useEffect(() => {
    if (availableCameras.length > 0 && !cameraParamsAutoDetected && cameraParams.selected_camera === '' && isReady) {
      const firstCamera = availableCameras[0]
      handleCameraChange({ selected_camera: firstCamera })
    }
  }, [availableCameras, cameraParamsAutoDetected, cameraParams.selected_camera, handleCameraChange, isReady])

  // Collapse state management
  const [isControlPanelCollapsed, setIsControlPanelCollapsed] = useState(true)
  const [collapsedSections, setCollapsedSections] = useState<{[key: string]: boolean}>({
    session: true,
    monitor: true,
    stimulus: true,
    camera: true,
    acquisition: true,
    analysis: true
  })

  const toggleControlPanel = () => {
    const newCollapsedState = !isControlPanelCollapsed
    setIsControlPanelCollapsed(newCollapsedState)
    onCollapseChange?.(newCollapsedState)
  }

  const toggleSection = (section: string) => {
    setCollapsedSections(prev => {
      const newCollapsedSections = {
        ...prev,
        [section]: !prev[section]
      }

      // Auto-collapse control panel if all sections are now closed AND we just closed a section
      const allSectionsClosed = Object.values(newCollapsedSections).every(isCollapsed => isCollapsed)
      const justClosedSection = !prev[section] && newCollapsedSections[section] // was open, now closed

      if (allSectionsClosed && justClosedSection && !isControlPanelCollapsed) {
        setIsControlPanelCollapsed(true)
        onCollapseChange?.(true)
      }

      return newCollapsedSections
    })
  }

  const handleSectionExpand = (sectionKey: string) => {
    if (isControlPanelCollapsed) {
      setIsControlPanelCollapsed(false)
      onCollapseChange?.(false)
    }
    setCollapsedSections(prev => ({
      ...prev,
      [sectionKey]: false
    }))
  }

  // Ensure control panel is properly collapsed when all sections are collapsed on mount
  React.useEffect(() => {
    const allSectionsClosed = Object.values(collapsedSections).every(isCollapsed => isCollapsed)
    if (allSectionsClosed && !isControlPanelCollapsed) {
      setIsControlPanelCollapsed(true)
      onCollapseChange?.(true)
    }
  }, [collapsedSections, isControlPanelCollapsed, onCollapseChange])


  const sectionConfigs = [
    {
      key: 'session',
      title: 'Session',
      icon: FolderCog,
      configs: sessionParameterConfigs,
      initialValues: sessionParams,
      onParametersChange: (params: Record<string, any>) => setSessionParams(params as typeof sessionParams)
    },
    {
      key: 'monitor',
      title: 'Monitor',
      icon: MonitorCog,
      configs: monitorParameterConfigs,
      initialValues: monitorParams,
      onParametersChange: (params: Record<string, any>) => setMonitorParams(params as typeof monitorParams)
    },
    {
      key: 'stimulus',
      title: 'Stimulus',
      icon: Columns3Cog,
      configs: stimulusParameterConfigs,
      initialValues: stimulusParams,
      onParametersChange: (params: Record<string, any>) => setStimulusParams(params as typeof stimulusParams)
    },
    {
      key: 'camera',
      title: 'Camera',
      icon: Video,
      configs: createCameraParameterConfigs(cameraParamsAutoDetected).map(config =>
        config.key === 'selected_camera'
          ? { ...config, options: availableCameras.map(cam => ({ value: cam, label: cam })) }
          : config
      ),
      initialValues: cameraParams,
      onParametersChange: handleCameraChange
    },
    {
      key: 'acquisition',
      title: 'Acquisition',
      icon: FileVideoCamera,
      configs: acquisitionParameterConfigs,
      initialValues: acquisitionParams,
      onParametersChange: (params: Record<string, any>) => setAcquisitionParams(params as typeof acquisitionParams)
    },
    {
      key: 'analysis',
      title: 'Analysis',
      icon: BrainCog,
      configs: analysisParameterConfigs,
      initialValues: analysisParams,
      onParametersChange: (params: Record<string, any>) => setAnalysisParams(params as typeof analysisParams)
    }
  ]

  if (isControlPanelCollapsed) {
    return (
      <div className="relative">
        {/* Collapsed Control Panel - Sidebar */}
        <div className="w-12 h-full bg-sci-secondary-800 border-r border-sci-secondary-700 flex flex-col">
          {/* Control Panel Icon */}
          <div className="h-12 flex items-center justify-center border-b border-sci-secondary-700">
            <SlidersHorizontal
              className="w-6 h-6 cursor-pointer text-sci-secondary-200 hover:text-sci-primary-400 transition-colors"
              onClick={toggleControlPanel}
            />
          </div>

          {/* Subsection Icons */}
          <div className="flex-1">
            {sectionConfigs.map(({ key, icon: Icon }) => (
              <div
                key={key}
                className="h-12 flex items-center justify-center"
              >
                <Icon
                  className="w-4 h-4 cursor-pointer text-sci-secondary-400 hover:text-sci-primary-400 transition-colors"
                  onClick={() => handleSectionExpand(key)}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="w-80 h-full bg-sci-secondary-800 flex flex-col">
      {/* Control Panel Header */}
      <div className="h-12 flex items-center gap-3 px-4 border-b border-sci-secondary-700">
        <SlidersHorizontal
          className="w-6 h-6 cursor-pointer text-sci-secondary-200 hover:text-sci-primary-400 transition-colors"
          onClick={toggleControlPanel}
        />
        <h2 className="text-lg font-semibold text-sci-secondary-100">Control Panel</h2>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto">
        {/* Parameter Sections */}
        {sectionConfigs.map(({ key, title, icon, configs, initialValues, onParametersChange }) => (
          <CollapsibleSection
            key={key}
            title={title}
            icon={icon}
            sectionKey={key}
            isCollapsed={collapsedSections[key]}
            onToggle={toggleSection}
          >
            <ParameterSection
              title={title}
              initialValues={initialValues}
              configs={configs}
              onParametersChange={onParametersChange}
            />
          </CollapsibleSection>
        ))}

      </div>
    </div>
  )
}

export default ControlPanel