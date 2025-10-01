/**
 * Type definitions for Electron API exposed to renderer process
 * These types define the multi-channel IPC interface between Electron main process and React renderer
 */

export interface ElectronAPI {
  onControlMessage: (callback: (message: any) => void) => void
  onSyncMessage: (callback: (message: any) => void) => void
  onHealthMessage: (callback: (message: any) => void) => void
  sendToPython: (message: any) => Promise<{ success: boolean; error?: string }>
  sendStartupCommand: (message: any) => Promise<{ success: boolean }>
  emergencyStop: () => Promise<any>
  initializeZeroMQ: () => Promise<void>
  getSystemStatus: () => Promise<any>
  onBackendError: (callback: (error: string) => void) => void
}

export interface SharedMemoryFrameData {
  frame_id: number
  timestamp_us: number
  frame_index: number
  direction: string
  angle_degrees: number
  width_px: number
  height_px: number
  frame_data: ArrayBuffer | Buffer
}

export interface HealthMessage {
  timestamp_us: number
  backend_fps: number
  frame_buffer_usage_percent: number
  memory_usage_mb: number
  cpu_usage_percent: number
  active_threads: number
  stimulus_active: boolean
  camera_active: boolean
}

export interface SyncMessage {
  type: string
  [key: string]: any
}

export interface ControlMessage {
  type: string
  [key: string]: any
}

declare global {
  interface Window {
    electronAPI: ElectronAPI
  }
}