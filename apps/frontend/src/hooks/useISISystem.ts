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

    // Listen for main process messages
    window.electronAPI.onMainMessage((message: string) => {
      console.log('Main process message:', message)
      setIsReady(true)
    })

    // Listen for Python backend messages
    window.electronAPI.onPythonMessage((message: ISIMessage) => {
      console.log('Python backend message:', message)
      setLastMessage(message)
    })

    // Listen for backend errors
    window.electronAPI.onBackendError((error: string) => {
      console.error('Backend error:', error)
      setConnectionError(error)
      setIsReady(false)
    })

    // Request initial system status
    window.electronAPI.getSystemStatus()
      .then(() => {
        console.log('System status requested')
      })
      .catch((error) => {
        console.error('Failed to get system status:', error)
        setConnectionError('Failed to connect to system')
      })

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

    if (!isReady) {
      throw new Error('System not ready')
    }

    try {
      const result = await window.electronAPI.sendToPython(command)
      if (!result.success) {
        throw new Error('Command failed')
      }
      return result
    } catch (error) {
      console.error('Failed to send command:', error)
      throw error
    }
  }, [isReady])

  // Emergency stop function
  const emergencyStop = useCallback(async () => {
    if (!window.electronAPI) {
      throw new Error('Electron API not available')
    }

    try {
      const result = await window.electronAPI.emergencyStop()
      return result
    } catch (error) {
      console.error('Emergency stop failed:', error)
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