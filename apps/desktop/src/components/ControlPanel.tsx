import React, { useState } from 'react'
import { componentLogger } from '../utils/logger'
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
import { useParameters } from '../hooks/useParameters'
import type { ISIMessage } from '../types/ipc-messages'
import type {
  SystemStatus,
  SystemStatusValue,
  CameraInfo,
  DisplayInfo,
  SessionParameters,
  MonitorParameters,
  StimulusParameters,
  AcquisitionParameters,
  AnalysisParameters,
  CameraParameters
} from '../types/shared'

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

const createMonitorParameterConfigs = (autoDetected: boolean): ParameterConfig[] => [
  {
    key: 'selected_display',
    label: 'Display Device',
    type: 'select',
    options: [] // Will be populated dynamically from detectedDisplays
  },
  {
    key: 'monitor_distance_cm',
    label: 'Monitor Distance',
    type: 'number',
    unit: 'cm'
  },
  {
    key: 'monitor_lateral_angle_deg',
    label: 'Lateral Angle',
    type: 'number',
    unit: '°'
  },
  {
    key: 'monitor_tilt_angle_deg',
    label: 'Tilt Angle',
    type: 'number',
    unit: '°'
  },
  {
    key: 'monitor_width_cm',
    label: 'Monitor Width',
    type: 'number',
    unit: 'cm'
  },
  {
    key: 'monitor_height_cm',
    label: 'Monitor Height',
    type: 'number',
    unit: 'cm'
  },
  {
    key: 'monitor_width_px',
    label: 'Monitor Width (px)',
    type: 'number',
    disabled: autoDetected
  },
  {
    key: 'monitor_height_px',
    label: 'Monitor Height (px)',
    type: 'number',
    disabled: autoDetected
  },
  {
    key: 'monitor_fps',
    label: 'Monitor FPS',
    type: 'number',
    unit: 'fps',
    disabled: autoDetected
  }
]

const stimulusParameterConfigs: ParameterConfig[] = [
  {
    key: 'checker_size_deg',
    label: 'Checker Size',
    type: 'number',
    unit: '°'
  },
  {
    key: 'bar_width_deg',
    label: 'Bar Width',
    type: 'number',
    unit: '°'
  },
  {
    key: 'drift_speed_deg_per_sec',
    label: 'Drift Speed',
    type: 'number',
    unit: '°/s'
  },
  {
    key: 'strobe_rate_hz',
    label: 'Strobe Rate',
    type: 'number',
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
    unit: 's'
  },
  {
    key: 'between_sec',
    label: 'Between Trials',
    type: 'number',
    unit: 's'
  },
  {
    key: 'cycles',
    label: 'Number of Cycles',
    type: 'number'
  }
]

const analysisParameterConfigs: ParameterConfig[] = [
  {
    key: 'ring_size_mm',
    label: 'Ring Size',
    type: 'number',
    unit: 'mm'
  },
  {
    key: 'vfs_threshold_sd',
    label: 'VFS Threshold',
    type: 'number',
    unit: 'SD'
  },
  {
    key: 'smoothing_sigma',
    label: 'Smoothing Sigma',
    type: 'number',
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
    step: 0.1
  },
  {
    key: 'gradient_window_size',
    label: 'Gradient Window Size',
    type: 'number'
  },
  {
    key: 'area_min_size_mm2',
    label: 'Min Area Size',
    type: 'number',
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
    unit: 'fps',
    disabled: autoDetected
  },
  {
    key: 'camera_width_px',
    label: 'Camera Width',
    type: 'number',
    unit: 'px',
    disabled: autoDetected
  },
  {
    key: 'camera_height_px',
    label: 'Camera Height',
    type: 'number',
    unit: 'px',
    disabled: autoDetected
  }
]

interface ControlPanelProps {
  isConnected: boolean
  isExperimentRunning: boolean
  systemStatus: SystemStatus
  onStopExperiment: () => void
  parameterState: ReturnType<typeof useParameters>
  sendCommand?: (command: ISIMessage) => Promise<{ success: boolean; error?: string }>
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
  systemStatus,
  onCollapseChange,
  isReady,
  parameterState,
  sendCommand
}) => {
  const {
    sessionParams,
    monitorParams,
    stimulusParams,
    cameraParams,
    acquisitionParams,
    analysisParams,
    availableCameras,
    availableDisplays,
    parameterConfig,
    updateParameters
  } = parameterState

  const handleParameterChange = React.useCallback(async (section: string, params: Record<string, any>) => {
    try {
      await updateParameters(section as any, params)
      componentLogger.debug(`Updated ${section} parameters:`, params)
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error)
      componentLogger.error(`Failed to update ${section} parameters:`, errorMessage, params)
      // Show error to user
      console.error(`❌ Parameter Update Failed (${section}):`, errorMessage)
    }
  }, [updateParameters])

  React.useEffect(() => {
    if (!cameraParams || !availableCameras?.length) {
      return
    }

    if (!cameraParams.selected_camera && availableCameras.length > 0) {
      handleParameterChange('camera', {
        ...cameraParams,
        selected_camera: availableCameras[0]
      })
    }
  }, [availableCameras, cameraParams, handleParameterChange])

  React.useEffect(() => {
    if (!monitorParams || !availableDisplays?.length) {
      return
    }

    if (!monitorParams.selected_display && availableDisplays.length > 0) {
      handleParameterChange('monitor', {
        ...monitorParams,
        selected_display: availableDisplays[0]
      })
    }
  }, [availableDisplays, monitorParams, handleParameterChange])

  React.useEffect(() => {
    if (!cameraParams?.selected_camera || !sendCommand || !isReady) {
      return
    }

    sendCommand({
      type: 'get_camera_capabilities',
      camera_name: cameraParams.selected_camera
    }).catch(error => {
      componentLogger.error('Failed to send camera capabilities request:', error)
    })
  }, [cameraParams?.selected_camera, sendCommand, isReady, handleParameterChange])

  React.useEffect(() => {
    if (!monitorParams?.selected_display || !sendCommand || !isReady) {
      return
    }

    sendCommand({
      type: 'get_display_capabilities',
      display_id: monitorParams.selected_display
    }).catch(error => {
      componentLogger.error('Failed to send display capabilities request:', error)
    })
  }, [monitorParams?.selected_display, sendCommand, isReady, handleParameterChange])

  // Collapse state management
  const [isControlPanelCollapsed, setIsControlPanelCollapsed] = useState(true)
  const [collapsedSections, setCollapsedSections] = useState<{[key: string]: boolean}>({
    session: false,
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

      return newCollapsedSections
    })
  }

  // Auto-collapse control panel if all sections are closed
  React.useEffect(() => {
    const allSectionsClosed = Object.values(collapsedSections).every(isCollapsed => isCollapsed)

    if (allSectionsClosed && !isControlPanelCollapsed) {
      setIsControlPanelCollapsed(true)
      onCollapseChange?.(true)
    }
  }, [collapsedSections, isControlPanelCollapsed, onCollapseChange])

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

  // Ensure control panel is properly collapsed when all sections are collapsed
  // Disabled this auto-collapse behavior to prevent issues with expanding the panel
  // React.useEffect(() => {
  //   const allSectionsClosed = Object.values(collapsedSections).every(isCollapsed => isCollapsed)
  //   if (allSectionsClosed && !isControlPanelCollapsed) {
  //     setIsControlPanelCollapsed(true)
  //     onCollapseChange?.(true)
  //   }
  // }, [collapsedSections, isControlPanelCollapsed, onCollapseChange])


  const sectionConfigs = React.useMemo(() => [
    {
      key: 'session',
      title: 'Session',
      icon: FolderCog,
      configs: sessionParameterConfigs,
      initialValues: sessionParams ?? {},
      onParametersChange: (params: Record<string, any>) => handleParameterChange('session', params)
    },
    {
      key: 'monitor',
      title: 'Monitor',
      icon: MonitorCog,
      configs: createMonitorParameterConfigs(false).map(config =>
        config.key === 'selected_display'
          ? { ...config, options: availableDisplays.map(display => ({ value: display, label: display })) }
          : config
      ),
      initialValues: monitorParams ?? {},
      onParametersChange: (params: Record<string, any>) => handleParameterChange('monitor', params)
    },
    {
      key: 'stimulus',
      title: 'Stimulus',
      icon: Columns3Cog,
      configs: stimulusParameterConfigs,
      initialValues: stimulusParams ?? {},
      onParametersChange: (params: Record<string, any>) => handleParameterChange('stimulus', params)
    },
    {
      key: 'camera',
      title: 'Camera',
      icon: Video,
      configs: createCameraParameterConfigs(false).map(config =>
        config.key === 'selected_camera'
          ? { ...config, options: availableCameras.map(cam => ({ value: cam, label: cam })) }
          : config
      ),
      initialValues: cameraParams ?? {},
      onParametersChange: (params: Record<string, any>) => handleParameterChange('camera', params)
    },
    {
      key: 'acquisition',
      title: 'Acquisition',
      icon: FileVideoCamera,
      configs: acquisitionParameterConfigs,
      initialValues: acquisitionParams ?? {},
      onParametersChange: (params: Record<string, any>) => handleParameterChange('acquisition', params)
    },
    {
      key: 'analysis',
      title: 'Analysis',
      icon: BrainCog,
      configs: analysisParameterConfigs,
      initialValues: analysisParams ?? {},
      onParametersChange: (params: Record<string, any>) => handleParameterChange('analysis', params)
    }
  ], [
    sessionParams,
    monitorParams,
    stimulusParams,
    cameraParams,
    availableCameras,
    availableDisplays,
    acquisitionParams,
    analysisParams,
    handleParameterChange
  ])

  if (isControlPanelCollapsed) {
    return (
      <div className="w-12 h-full bg-sci-secondary-800 border-r border-sci-secondary-700 flex flex-col">
        {/* Control Panel Icon - Always in top-left */}
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
    )
  }

  return (
    <div className="w-80 h-full bg-sci-secondary-800 flex flex-col">
      {/* Control Panel Header with Icon - Always in top-left */}
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