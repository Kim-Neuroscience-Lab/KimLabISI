const { contextBridge, ipcRenderer } = require('electron')

// --------- Expose some API to the Renderer process ---------
contextBridge.exposeInMainWorld('ipcRenderer', {
  on(...args: Parameters<typeof ipcRenderer.on>) {
    const [channel, listener] = args
    return ipcRenderer.on(channel, (event, ...args) => listener(event, ...args))
  },
  off(...args: Parameters<typeof ipcRenderer.off>) {
    const [channel, ...omit] = args
    return ipcRenderer.off(channel, ...omit)
  },
  send(...args: Parameters<typeof ipcRenderer.send>) {
    const [channel, ...omit] = args
    return ipcRenderer.send(channel, ...omit)
  },
  invoke(...args: Parameters<typeof ipcRenderer.invoke>) {
    const [channel, ...omit] = args
    return ipcRenderer.invoke(channel, ...omit)
  },
})

// Type-safe API for the renderer process
export interface ElectronAPI {
  // Python backend communication
  sendToPython: (message: any) => Promise<{ success: boolean }>
  onPythonMessage: (callback: (message: any) => void) => void
  removeAllPythonListeners: () => void

  // System control
  getSystemStatus: () => Promise<{ success: boolean }>
  emergencyStop: () => Promise<{ success: boolean }>

  // General IPC
  onMainMessage: (callback: (message: string) => void) => void
  onBackendError: (callback: (error: string) => void) => void
}

const electronAPI: ElectronAPI = {
  // Python backend communication
  sendToPython: (message: any) => ipcRenderer.invoke('send-to-python', message),

  onPythonMessage: (callback: (message: any) => void) => {
    ipcRenderer.on('python-message', (_event, message) => callback(message))
  },

  removeAllPythonListeners: () => {
    ipcRenderer.removeAllListeners('python-message')
    ipcRenderer.removeAllListeners('main-process-message')
    ipcRenderer.removeAllListeners('backend-error')
  },

  // System control
  getSystemStatus: () => ipcRenderer.invoke('get-system-status'),
  emergencyStop: () => ipcRenderer.invoke('emergency-stop'),

  // General IPC
  onMainMessage: (callback: (message: string) => void) => {
    ipcRenderer.on('main-process-message', (_event, message) => callback(message))
  },

  onBackendError: (callback: (error: string) => void) => {
    ipcRenderer.on('backend-error', (_event, error) => callback(error))
  }
}

// Expose the API to the renderer process
contextBridge.exposeInMainWorld('electronAPI', electronAPI)

// Types for the renderer process
declare global {
  interface Window {
    electronAPI: ElectronAPI
  }
}