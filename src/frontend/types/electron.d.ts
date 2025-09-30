/**
 * Type definitions for Electron API exposed to renderer process
 * These types define the multi-channel IPC interface between Electron main process and React renderer
 */

export interface ElectronAPI {
  // Python backend communication via CONTROL channel
  sendToPython: (message: any) => Promise<{ success: boolean }>
  onPythonMessage: (callback: (message: any) => void) => void
  removeAllPythonListeners: () => void

  // Multi-channel IPC event listeners
  onControlMessage: (callback: (message: any) => void) => void
  onSyncMessage: (callback: (message: any) => void) => void
  onHealthMessage: (callback: (message: any) => void) => void
  onSharedMemoryFrame: (callback: (frameData: SharedMemoryFrameData) => void) => void
  removeSharedMemoryListener: () => void

  // System control
  getSystemStatus: () => Promise<{ success: boolean }>
  emergencyStop: () => Promise<{ success: boolean }>

  // General IPC
  onMainMessage: (callback: (message: string) => void) => void
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
    ipcRenderer: {
      on: (channel: string, listener: (...args: any[]) => void) => void
      off: (channel: string, listener: (...args: any[]) => void) => void
      send: (channel: string, ...args: unknown[]) => void
      invoke: (channel: string, ...args: unknown[]) => Promise<any>
    }
  }
}