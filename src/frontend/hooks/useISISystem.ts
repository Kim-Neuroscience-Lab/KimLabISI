import { useState, useEffect, useCallback } from 'react'

interface ISIMessage {
  type: string
  [key: string]: any
}

export type InitializationState =
  | 'initializing'    // App starting up
  | 'system-ready'    // Backend is ready and operational
  | 'error'           // Initialization failed

export const useISISystem = () => {
  const [initState, setInitState] = useState<InitializationState>('initializing')
  const [lastMessage, setLastMessage] = useState<ISIMessage | null>(null)
  const [connectionError, setConnectionError] = useState<string | null>(null)

  // Initialize IPC communication - just listen to backend
  useEffect(() => {
    if (!window.electronAPI) {
      setConnectionError('Electron API not available')
      setInitState('error')
      return
    }

    let mounted = true

    // Listen for Python backend messages
    const handlePythonMessage = (message: ISIMessage) => {
      if (!mounted) return

      setLastMessage(message)

      // Don't set system-ready from health messages - wait for main process signal
    }

    // Listen for backend errors
    const handleBackendError = (error: string) => {
      if (!mounted) return
      setConnectionError(error)
      setInitState('error')
    }

    // Listen for main process signals - this drives our ready state
    const handleMainMessage = (message: string) => {
      if (!mounted) return

      // Set system ready when main process confirms backend is ready
      if (message === 'Backend ready') {
        setInitState('system-ready')
      }
    }

    // Set up listeners
    window.electronAPI.onPythonMessage(handlePythonMessage)
    window.electronAPI.onBackendError(handleBackendError)
    window.electronAPI.onMainMessage(handleMainMessage)

    // Cleanup listeners on unmount
    return () => {
      mounted = false
      window.electronAPI.removeAllPythonListeners()
    }
  }, [])

  // Send command to Python backend - only when system is ready
  const sendCommand = useCallback(async (command: ISIMessage) => {
    if (!window.electronAPI) {
      throw new Error('Electron API not available')
    }

    if (initState !== 'system-ready') {
      throw new Error(`System not ready (current state: ${initState})`)
    }

    try {
      const result = await window.electronAPI.sendToPython(command)
      if (!result.success) {
        throw new Error('Command failed')
      }
      return result
    } catch (error) {
      throw error
    }
  }, [initState])

  // Emergency stop function
  const emergencyStop = useCallback(async () => {
    if (!window.electronAPI) {
      throw new Error('Electron API not available')
    }

    try {
      const result = await window.electronAPI.emergencyStop()
      return result
    } catch (error) {
      throw error
    }
  }, [])

  return {
    initState,
    isReady: initState === 'system-ready',
    lastMessage,
    connectionError,
    sendCommand,
    emergencyStop
  }
}