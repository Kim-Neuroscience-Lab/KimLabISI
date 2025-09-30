import { useState, useEffect, useCallback } from 'react'

interface ISIMessage {
  type: string
  [key: string]: any
}

/**
 * System state tracking hook - PURE VIEW LAYER
 *
 * Architecture principles:
 * - Frontend displays backend state directly without interpretation
 * - No business logic in frontend
 * - Backend validates all commands and determines readiness
 * - Frontend can send commands anytime; backend rejects if not ready
 */
export const useISISystem = () => {
  // Display state directly from backend - no interpretation
  const [systemState, setSystemState] = useState<string>('initializing')
  const [displayText, setDisplayText] = useState<string>('Initializing system...')
  const [isReady, setIsReady] = useState<boolean>(false)
  const [isError, setIsError] = useState<boolean>(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [lastMessage, setLastMessage] = useState<ISIMessage | null>(null)
  const [connectionError, setConnectionError] = useState<string | null>(null)

  // Initialize multi-channel IPC communication
  useEffect(() => {
    if (!window.electronAPI) {
      setConnectionError('Electron API not available')
      setIsError(true)
      return
    }

    let mounted = true
    let zeromqInitialized = false

    // Listen for CONTROL channel messages (startup coordination, commands)
    const handleControlMessage = (message: ISIMessage) => {
      if (!mounted) return
      setLastMessage(message)

      // Handle unified system_state messages from backend
      if (message.type === 'system_state') {
        setSystemState(message.state)
        setDisplayText(message.display_text || message.state)
        setIsReady(message.is_ready || false)
        setIsError(message.is_error || false)
        if (message.error) {
          setErrorMessage(message.error)
        }

        // When backend signals "waiting_frontend", initialize ZeroMQ and send ready signal
        if (message.state === 'waiting_frontend' && !zeromqInitialized) {
          zeromqInitialized = true
          window.electronAPI.initializeZeroMQ?.().then(() => {
            const handshakeCommand = { type: 'frontend_ready' }
            window.electronAPI.sendToPython(handshakeCommand)
              .catch((err: Error) => {
                if (/Backend not ready/.test(err.message)) {
                  // Backend hasn't completed initialization yet. We will wait for the next
                  // system_state update (which will still be waiting_frontend) before retrying.
                  console.warn('Backend not ready for frontend_ready handshake yet. Awaiting next state update...')
                  zeromqInitialized = false
                } else {
                  console.error('Failed to send frontend_ready:', err)
                }
              })
          }).catch((err: Error) => {
            console.error('Failed to initialize ZeroMQ:', err)
            setConnectionError('Failed to establish backend connection')
            setIsError(true)
          })
        }
      }
    }

    // Listen for SYNC channel messages (system coordination after startup)
    const handleSyncMessage = (message: ISIMessage) => {
      if (!mounted) return
      setLastMessage(message)

      // SYNC channel also receives system_state broadcasts after handshake
      if (message.type === 'system_state') {
        setSystemState(message.state)
        setDisplayText(message.display_text || message.state)
        setIsReady(message.is_ready || false)
        setIsError(message.is_error || false)
        if (message.error) {
          setErrorMessage(message.error)
        }
      }
    }

    // Listen for HEALTH channel messages (continuous monitoring)
    const handleHealthMessage = (message: ISIMessage) => {
      if (!mounted) return
      // Health messages don't trigger state updates
    }

    // Listen for backend errors
    const handleBackendError = (error: string) => {
      if (!mounted) return
      setConnectionError(error)
      setIsError(true)
    }

    // Set up multi-channel listeners
    window.electronAPI.onControlMessage?.(handleControlMessage)
    window.electronAPI.onSyncMessage?.(handleSyncMessage)
    window.electronAPI.onHealthMessage?.(handleHealthMessage)
    window.electronAPI.onBackendError(handleBackendError)

    // Fallback: also listen to legacy python-message for backwards compatibility
    window.electronAPI.onPythonMessage?.(handleControlMessage)

    // Cleanup listeners on unmount
    return () => {
      mounted = false
      window.electronAPI.removeAllPythonListeners?.()
    }
  }, [])

  /**
   * Send command to backend - NO BLOCKING LOGIC
   *
   * Frontend can send commands anytime. Backend validates readiness
   * and returns proper error if system is not ready.
   */
  const sendCommand = useCallback(async (command: ISIMessage) => {
    if (!window.electronAPI) {
      throw new Error('Electron API not available')
    }

    try {
      const result = await window.electronAPI.sendToPython(command)
      if (!result.success) {
        throw new Error(result.error || 'Command failed')
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
    // System state (directly from backend)
    systemState,
    displayText,
    isReady,
    isError,
    errorMessage,
    connectionError,
    // Messages and commands
    lastMessage,
    sendCommand,
    emergencyStop
  }
}