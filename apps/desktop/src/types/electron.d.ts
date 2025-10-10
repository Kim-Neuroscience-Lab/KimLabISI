/**
 * Type definitions for Electron API exposed to renderer process
 * These types define the multi-channel IPC interface between Electron main process and React renderer
 */

import type { ControlMessage, SyncMessage, ISIMessage } from './ipc-messages'

export interface ElectronAPI {
  // Multi-channel IPC event listeners - return unsubscribe functions
  onControlMessage: (callback: (message: ControlMessage) => void) => () => void
  onSyncMessage: (callback: (message: SyncMessage) => void) => () => void
  onHealthMessage: (callback: (message: HealthMessage) => void) => () => void
  onSharedMemoryFrame: (callback: (frameData: SharedMemoryFrameData) => void) => () => void
  readSharedMemoryFrame: (offset: number, size: number, shmPath: string) => Promise<ArrayBuffer>
  removeSharedMemoryListener: () => void
  onBackendError: (callback: (error: string) => void) => () => void
  onMainMessage: (callback: (message: string) => void) => () => void

  // Commands
  sendToPython: (message: ISIMessage) => Promise<{ success: boolean; error?: string }>
  sendStartupCommand: (message: ISIMessage) => Promise<{ success: boolean }>
  emergencyStop: () => Promise<{ success: boolean; error?: string }>
  initializeZeroMQ: () => Promise<void>
  getSystemStatus: () => Promise<{ success: boolean; error?: string }>
}

export interface SharedMemoryFrameMetadata {
  frame_id: number
  timestamp_us: number
  frame_index: number
  direction: string
  angle_degrees: number
  width_px: number
  height_px: number
  total_frames: number
  start_angle: number
  end_angle: number
  offset_bytes: number
  data_size_bytes: number
  shm_path: string
}

export interface SharedMemoryFrameData extends SharedMemoryFrameMetadata {
  frame_data: ArrayBuffer | Buffer
}

export interface HealthMetricsMessage {
  timestamp_us: number
  backend_fps: number
  frame_buffer_usage_percent: number
  memory_usage_mb: number
  cpu_usage_percent: number
  active_threads: number
  stimulus_active: boolean
  camera_active: boolean
}

export interface SystemHealthMessage {
  type: 'system_health'
  hardware_status: {
    multi_channel_ipc?: 'online' | 'offline' | 'error' | 'degraded'
    parameters?: 'online' | 'offline' | 'error' | 'degraded'
    display?: 'online' | 'offline' | 'error' | 'degraded'
    camera?: 'online' | 'offline' | 'error' | 'degraded'
    realtime_streaming?: 'online' | 'offline' | 'error' | 'degraded'
  }
  details?: {
    [key: string]: string
  }
}

export type HealthMessage = HealthMetricsMessage | SystemHealthMessage

declare global {
  interface Window {
    electronAPI: ElectronAPI
  }
}