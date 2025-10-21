/**
 * Shared type definitions used across multiple components
 * Consolidates duplicate interface definitions to maintain single source of truth
 */

export type SystemStatusValue = 'online' | 'offline' | 'error' | 'degraded'

export interface SystemStatus {
  camera: SystemStatusValue
  display: SystemStatusValue
  stimulus: SystemStatusValue
  parameters: SystemStatusValue
}

export interface SystemState {
  isConnected: boolean
  isExperimentRunning: boolean
  currentProgress: number
  systemStatus: SystemStatus
}

export interface CameraInfo {
  name: string
  capabilities?: {
    width: number
    height: number
    frameRate: number
  }
}

export interface DisplayInfo {
  name: string
  width: number
  height: number
  refresh_rate: number
  is_primary: boolean
  position_x: number
  position_y: number
  scale_factor: number
  identifier: string
}

// Parameter type definitions - should match backend dataclasses
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
  pixel_scale_mm_per_px: number
  vfs_threshold_sd: number
  smoothing_sigma: number
  magnitude_threshold: number
  coherence_threshold: number
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
