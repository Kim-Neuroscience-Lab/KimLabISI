import { useState, useEffect, useCallback } from 'react'

interface ISIMessage {
  type: string
  [key: string]: any
}

export const useISISystem = () => {
  const [isReady, setIsReady] = useState(false)
  const [lastMessage, setLastMessage] = useState<ISIMessage | null>(null)
  const [connectionError, setConnectionError] = useState<string | null>(null)

  // Initialize IPC communication
  useEffect(() => {
    if (!window.electronAPI) {
      setConnectionError('Electron API not available')
      return
    }

    // Listen for Python backend messages
    const handlePythonMessage = (message: ISIMessage) => {
      setLastMessage(message)

      // Set ready state when we receive a successful system status response
      if (message.success && message.status === 'ready') {
        setIsReady(true)
        setConnectionError(null)
      }
    }

    // Listen for backend errors
    const handleBackendError = (error: string) => {
      setConnectionError(error)
      setIsReady(false)
    }

    // Listen for main process signals (backend ready)
    const handleMainMessage = (message: string) => {

      // Request system status when backend is ready
      if (message.includes('Backend ready')) {
        window.electronAPI.getSystemStatus()
          .catch((error) => {
            setConnectionError('Failed to connect to system')
          })
      }
    }

    // Set up listeners
    window.electronAPI.onPythonMessage(handlePythonMessage)
    window.electronAPI.onBackendError(handleBackendError)
    window.electronAPI.onMainMessage(handleMainMessage)

    // Cleanup listeners on unmount
    return () => {
      window.electronAPI.removeAllPythonListeners()
    }
  }, [])

  // Send command to Python backend
  const sendCommand = useCallback(async (command: ISIMessage) => {
    if (!window.electronAPI) {
      throw new Error('Electron API not available')
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
  }, [])

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
    isReady,
    lastMessage,
    connectionError,
    sendCommand,
    emergencyStop
  }
}