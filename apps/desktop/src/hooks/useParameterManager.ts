import { useState, useEffect, useCallback } from 'react'
import type { ISIMessage, ControlMessage, SyncMessage } from '../types/ipc-messages'
import { hookLogger } from '../utils/logger'

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

export function useParameterManager(
  lastSnapshot: ControlMessage | SyncMessage | null,
  sendCommand?: (command: ISIMessage) => Promise<{ success: boolean; error?: string }>
) {
  const [parameters, setParameters] = useState<AllParameters>({})
  const [parameterConfig, setParameterConfig] = useState<Record<string, unknown>>({})
  const updateParameters = useCallback(async (category: keyof AllParameters, newParams: Partial<AllParameters[typeof category]>) => {
    if (!sendCommand) return

    try {
      const response = await sendCommand({
        type: 'update_parameter_group',
        group_name: category,
        parameters: newParams
      })

      if (!response?.success) {
        hookLogger.error(`useParameterManager: Failed to update ${category} parameters`, response)
        return false
      }

      return true
    } catch (error) {
      hookLogger.error(`useParameterManager: Error updating ${category} parameters:`, error)
      return false
    }
  }, [sendCommand])

  useEffect(() => {
    if (!lastSnapshot || lastSnapshot.type !== 'parameters_snapshot') {
      return
    }

    if (lastSnapshot.parameters) {
      setParameters(lastSnapshot.parameters)
    }
    if (lastSnapshot.parameter_config) {
      setParameterConfig(lastSnapshot.parameter_config)
    }
  }, [lastSnapshot])

  return {
    parameters,
    parameterConfig,
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