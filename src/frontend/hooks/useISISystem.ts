import { useState, useEffect, useCallback, useRef } from 'react'

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
  const [systemState, setSystemState] = useState<string>('initializing')
  const [displayText, setDisplayText] = useState<string>('Initializing system...')
  const [isReady, setIsReady] = useState<boolean>(false)
  const [isError, setIsError] = useState<boolean>(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [lastMessage, setLastMessage] = useState<ISIMessage | null>(null)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const handshakeInProgress = useRef(false)

  useEffect(() => {
    if (!window.electronAPI) {
      setConnectionError('Electron API not available')
      setIsError(true)
      return
    }

    let mounted = true

    const performHandshake = async (pingId?: string) => {
      try {
        if (!window.electronAPI) return

        await window.electronAPI.initializeZeroMQ?.()

        if (pingId) {
          const readyPayload = { type: 'frontend_ready', ping_id: pingId }
          await window.electronAPI.sendStartupCommand?.(readyPayload)
          console.log('frontend_ready sent via startup bridge', readyPayload)

          const responsePayload = {
            type: 'frontend_ready_response',
            ping_id: pingId,
            success: true
          }
          await window.electronAPI.sendStartupCommand?.(responsePayload)
          console.log('frontend_ready_response sent via startup bridge', responsePayload)
        } else {
          const readyPayload = { type: 'frontend_ready' }
          await window.electronAPI.sendStartupCommand?.(readyPayload)
          console.log('frontend_ready (no ping) sent via startup bridge', readyPayload)
        }

        handshakeInProgress.current = false
      } catch (err) {
        console.error('Failed to complete frontend handshake:', err)
        handshakeInProgress.current = false
      }
    }

    const handleSyncMessage = (message: ISIMessage) => {
      if (!mounted) return
      setLastMessage(message)

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

    const handleHealthMessage = (_message: ISIMessage) => {
      if (!mounted) return
    }

    const handleBackendError = (error: string) => {
      if (!mounted) return
      setConnectionError(error)
      setIsError(true)
    }

    const handleControlMessage = (message: ISIMessage) => {
      if (!mounted) return

      if (message.type === 'parameters_snapshot') {
        setLastMessage(message)
        return
      }

      if (message.type === 'parameter_info' && message.info?.parameter_config) {
        setLastMessage((prev) => ({
          ...(prev || {}),
          type: 'parameters_snapshot',
          parameter_config: message.info.parameter_config,
          parameters: (prev as any)?.parameters,
        }))
        return
      }

      if (message.type === 'system_state') {
        handleSyncMessage(message)
      }
    }

    window.electronAPI.onControlMessage?.(handleControlMessage)
    window.electronAPI.onSyncMessage?.(handleSyncMessage)
    window.electronAPI.onHealthMessage?.(handleHealthMessage)
    window.electronAPI.onBackendError(handleBackendError)

    return () => {
      mounted = false
      window.electronAPI.onControlMessage?.(() => {})
    }
  }, [])

  const sendCommand = useCallback(async (command: ISIMessage) => {
    if (!window.electronAPI) {
      throw new Error('Electron API not available')
    }

    const result = await window.electronAPI.sendToPython(command)
    if (!result.success) {
      throw new Error(result.error || 'Command failed')
    }
    return result
  }, [])

  const emergencyStop = useCallback(async () => {
    if (!window.electronAPI) {
      throw new Error('Electron API not available')
    }

    return await window.electronAPI.emergencyStop()
  }, [])

  return {
    systemState,
    displayText,
    isReady,
    isError,
    errorMessage,
    connectionError,
    lastMessage,
    lastParametersSnapshot: lastMessage?.type === 'parameters_snapshot' ? lastMessage : null,
    sendCommand,
    emergencyStop
  }
}