import { useState, useEffect, useCallback } from 'react'

export interface SessionParameters {
  session_name: string
  animal_id: string
  animal_age: string
}

export interface MonitorParameters {
  selected_display: string
  monitor_distance_cm: number
  monitor_lateral_angle_deg: number
  monitor_tilt_angle_deg: number
  monitor_width_cm: number
  monitor_height_cm: number
  monitor_width_px: number
  monitor_height_px: number
  monitor_fps: number
  available_displays?: string[]
}

export interface StimulusParameters {
  checker_size_deg: number
  bar_width_deg: number
  drift_speed_deg_per_sec: number
  strobe_rate_hz: number
  contrast: number
}

export interface CameraParameters {
  selected_camera: string
  camera_fps: number
  camera_width_px: number
  camera_height_px: number
  available_cameras?: string[]
}

export interface AcquisitionParameters {
  baseline_sec: number
  between_sec: number
  cycles: number
  directions: string[]
}

export interface AnalysisParameters {
  ring_size_mm: number
  vfs_threshold_sd: number
  smoothing_sigma: number
  magnitude_threshold: number
  phase_filter_sigma: number
  gradient_window_size: number
  area_min_size_mm2: number
  response_threshold_percent: number
}

export interface AllParameters {
  session?: SessionParameters
  monitor?: MonitorParameters
  stimulus?: StimulusParameters
  camera?: CameraParameters
  acquisition?: AcquisitionParameters
  analysis?: AnalysisParameters
}

export function useParameterManager(sendCommand?: (command: any) => Promise<any>, lastMessage?: any) {
  const [parameters, setParameters] = useState<AllParameters>({})
  const [parameterConfig, setParameterConfig] = useState<any>({})
  const [isLoading, setIsLoading] = useState(true)
  const [lastError, setLastError] = useState<string | null>(null)

  // Fetch all parameters from backend
  const fetchAllParameters = useCallback(async () => {
    if (!sendCommand) return

    try {
      setIsLoading(true)
      setLastError(null)

      const response = await sendCommand({ type: 'get_all_parameters' })

      if (response?.success && response?.parameters) {
        setParameters(response.parameters)
      } else {
        console.error('useParameterManager: Failed to fetch parameters:', response)
        setLastError('Failed to fetch parameters from backend')
      }
    } catch (error) {
      console.error('useParameterManager: Error fetching parameters:', error)
      setLastError(`Error fetching parameters: ${error.message}`)
    } finally {
      setIsLoading(false)
    }
  }, [sendCommand])

  // Fetch parameter info including validation boundaries
  const fetchParameterInfo = useCallback(async () => {
    if (!sendCommand) return

    try {
      const response = await sendCommand({ type: 'get_parameter_info' })

      if (response?.success && response?.info?.parameter_config) {
        setParameterConfig(response.info.parameter_config)
      }
    } catch (error) {
      console.error('useParameterManager: Error fetching parameter info:', error)
    }
  }, [sendCommand])

  // Update specific parameter category
  const updateParameters = useCallback(async (category: keyof AllParameters, newParams: any) => {
    if (!sendCommand) return

    try {
      const response = await sendCommand({
        type: 'update_parameter_group',
        group_name: category,
        parameters: newParams
      })

      if (response?.success) {
        // Update local state immediately
        setParameters(prev => ({
          ...prev,
          [category]: newParams
        }))
        return true
      } else {
        setLastError(`Failed to update ${category} parameters`)
        return false
      }
    } catch (error) {
      setLastError(`Error updating ${category} parameters: ${error.message}`)
      return false
    }
  }, [sendCommand])

  // Listen for parameter updates from backend startup coordinator
  useEffect(() => {
    if (lastMessage?.type === 'parameters_updated') {
      setParameters(lastMessage.parameters)
      setIsLoading(false)
      setLastError(null)

      // Fetch parameter info after parameters are loaded
      fetchParameterInfo()
    }
  }, [lastMessage, fetchParameterInfo])

  return {
    parameters,
    parameterConfig,
    isLoading,
    lastError,
    fetchAllParameters,
    updateParameters,
    // Convenience getters for specific parameter types
    sessionParams: parameters.session,
    monitorParams: parameters.monitor,
    stimulusParams: parameters.stimulus,
    cameraParams: parameters.camera,
    acquisitionParams: parameters.acquisition,
    analysisParams: parameters.analysis,
    // Hardware lists
    availableCameras: parameters.camera?.available_cameras || [],
    availableDisplays: parameters.monitor?.available_displays || []
  }
}