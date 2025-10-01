import { contextBridge, ipcRenderer } from 'electron'

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
  sendToPython: (message: any) => Promise<{ success: boolean }>
  sendStartupCommand: (message: any) => Promise<{ success: boolean }>

  // Multi-channel IPC event listeners
  onControlMessage: (callback: (message: any) => void) => void
  onSyncMessage: (callback: (message: any) => void) => void
  onHealthMessage: (callback: (message: any) => void) => void
  onSharedMemoryFrame: (callback: (frameData: any) => void) => void
  removeSharedMemoryListener: () => void

  // System control
  getSystemStatus: () => Promise<{ success: boolean }>
  emergencyStop: () => Promise<{ success: boolean }>
  initializeZeroMQ: () => Promise<void>

  // General IPC
  onMainMessage: (callback: (message: string) => void) => void
  onBackendError: (callback: (error: string) => void) => void
}

const electronAPI: ElectronAPI = {
  sendToPython: (message: any) => ipcRenderer.invoke('send-to-python', message),
  sendStartupCommand: (message: any) => ipcRenderer.invoke('send-startup-command', message),
  onControlMessage: (callback: (message: any) => void) => {
    ipcRenderer.on('control-message', (_event, message) => callback(message))
  },
  onSyncMessage: (callback: (message: any) => void) => {
    ipcRenderer.on('sync-message', (_event, message) => callback(message))
  },
  onHealthMessage: (callback: (message: any) => void) => {
    ipcRenderer.on('health-message', (_event, message) => callback(message))
  },
  onSharedMemoryFrame: (callback: (frameData: any) => void) => {
    ipcRenderer.on('shared-memory-frame', (_event, frameData) => callback(frameData))
  },
  removeSharedMemoryListener: () => {
    ipcRenderer.removeAllListeners('shared-memory-frame')
  },
  getSystemStatus: () => ipcRenderer.invoke('get-system-status'),
  emergencyStop: () => ipcRenderer.invoke('emergency-stop'),
  initializeZeroMQ: () => ipcRenderer.invoke('initialize-zeromq'),
  onMainMessage: (callback: (message: string) => void) => {
    ipcRenderer.on('main-process-message', (_event, message) => callback(message))
  },
  onBackendError: (callback: (error: string) => void) => {
    ipcRenderer.on('backend-error', (_event, error) => callback(error))
  }
}

contextBridge.exposeInMainWorld('electronAPI', electronAPI)

// Types for the renderer process
declare global {
  interface Window {
    electronAPI: ElectronAPI
  }
}