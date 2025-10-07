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
