import { contextBridge, ipcRenderer } from 'electron'
import type { ISIMessage, ControlMessage, SyncMessage } from '../types/ipc-messages'
import type { HealthMessage, SharedMemoryFrameData } from '../types/electron'

// --------- Expose some API to the Renderer process ---------
contextBridge.exposeInMainWorld('ipcRenderer', {
  on(channel: string, listener: Parameters<typeof ipcRenderer.on>[1]) {
    return ipcRenderer.on(channel, listener)
  },
  off(channel: string, listener: Parameters<typeof ipcRenderer.off>[1]) {
    return ipcRenderer.off(channel, listener)
  },
  send(channel: string, ...args: unknown[]) {
    return ipcRenderer.send(channel, ...args)
  },
  invoke(channel: string, ...args: unknown[]) {
    return ipcRenderer.invoke(channel, ...args)
  },
})

// Type-safe API for the renderer process
export interface ElectronAPI {
  // Python backend communication
  sendToPython: (message: ISIMessage) => Promise<{ success: boolean; error?: string }>
  sendStartupCommand: (message: ISIMessage) => Promise<{ success: boolean }>

  // Multi-channel IPC event listeners - return unsubscribe functions
  onControlMessage: (callback: (message: ControlMessage) => void) => () => void
  onSyncMessage: (callback: (message: SyncMessage) => void) => () => void
  onHealthMessage: (callback: (message: HealthMessage) => void) => () => void
  onSharedMemoryFrame: (callback: (frameData: SharedMemoryFrameData) => void) => () => void
  readSharedMemoryFrame: (offset: number, size: number) => Promise<ArrayBuffer>
  removeSharedMemoryListener: () => void

  // System control
  getSystemStatus: () => Promise<{ success: boolean; error?: string }>
  emergencyStop: () => Promise<{ success: boolean; error?: string }>
  initializeZeroMQ: () => Promise<void>

  // General IPC - return unsubscribe functions
  onMainMessage: (callback: (message: string) => void) => () => void
  onBackendError: (callback: (error: string) => void) => () => void
}

const electronAPI: ElectronAPI = {
  sendToPython: (message: ISIMessage) => ipcRenderer.invoke('send-to-python', message),
  sendStartupCommand: (message: ISIMessage) => ipcRenderer.invoke('send-startup-command', message),
  onControlMessage: (callback: (message: ControlMessage) => void) => {
    const listener = (_event: Electron.IpcRendererEvent, message: ControlMessage) => callback(message)
    ipcRenderer.on('control-message', listener)
    return () => ipcRenderer.off('control-message', listener)
  },
  onSyncMessage: (callback: (message: SyncMessage) => void) => {
    const listener = (_event: Electron.IpcRendererEvent, message: SyncMessage) => callback(message)
    ipcRenderer.on('sync-message', listener)
    return () => ipcRenderer.off('sync-message', listener)
  },
  onHealthMessage: (callback: (message: HealthMessage) => void) => {
    const listener = (_event: Electron.IpcRendererEvent, message: HealthMessage) => callback(message)
    ipcRenderer.on('health-message', listener)
    return () => ipcRenderer.off('health-message', listener)
  },
  onSharedMemoryFrame: (callback: (frameData: SharedMemoryFrameData) => void) => {
    const listener = (_event: Electron.IpcRendererEvent, frameData: SharedMemoryFrameData) => callback(frameData)
    ipcRenderer.on('shared-memory-frame', listener)
    return () => ipcRenderer.off('shared-memory-frame', listener)
  },
  readSharedMemoryFrame: (offset: number, size: number) => ipcRenderer.invoke('read-shared-memory-frame', offset, size),
  removeSharedMemoryListener: () => {
    ipcRenderer.removeAllListeners('shared-memory-frame')
  },
  getSystemStatus: () => ipcRenderer.invoke('get-system-status'),
  emergencyStop: () => ipcRenderer.invoke('emergency-stop'),
  initializeZeroMQ: () => ipcRenderer.invoke('initialize-zeromq'),
  onMainMessage: (callback: (message: string) => void) => {
    const listener = (_event: Electron.IpcRendererEvent, message: string) => callback(message)
    ipcRenderer.on('main-process-message', listener)
    return () => ipcRenderer.off('main-process-message', listener)
  },
  onBackendError: (callback: (error: string) => void) => {
    const listener = (_event: Electron.IpcRendererEvent, error: string) => callback(error)
    ipcRenderer.on('backend-error', listener)
    return () => ipcRenderer.off('backend-error', listener)
  }
}

contextBridge.exposeInMainWorld('electronAPI', electronAPI)

// Types for the renderer process
declare global {
  interface Window {
    electronAPI: ElectronAPI
  }
}