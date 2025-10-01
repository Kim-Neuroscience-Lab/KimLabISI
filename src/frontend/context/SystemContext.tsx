import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'

interface ISIMessage {
  type: string
  [key: string]: any
}

interface ParametersSnapshot {
  timestamp: number
  parameters: Record<string, any>
  parameter_config: Record<string, any>
}

interface SystemContextValue {
  systemState: string
  displayText: string
  isReady: boolean
  isError: boolean
  errorMessage: string | null
  connectionError: string | null
  parametersSnapshot: ParametersSnapshot | null
  healthSnapshot: ISIMessage | null
  lastControlMessage: ISIMessage | null
  sendCommand: (command: ISIMessage) => Promise<any>
  emergencyStop: () => Promise<any>
}

const SystemContext = createContext<SystemContextValue | undefined>(undefined)

export const SystemProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [systemState, setSystemState] = useState<string>('initializing')
  const [displayText, setDisplayText] = useState<string>('Initializing backend systems...')
  const [isReady, setIsReady] = useState<boolean>(false)
  const [isError, setIsError] = useState<boolean>(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [connectionError, setConnectionError] = useState<string | null>(null)

  const [parametersSnapshot, setParametersSnapshot] = useState<ParametersSnapshot | null>(null)
  const [healthSnapshot, setHealthSnapshot] = useState<ISIMessage | null>(null)
  const [lastControlMessage, setLastControlMessage] = useState<ISIMessage | null>(null)

  const handshakeInProgress = useRef(false)

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

    return window.electronAPI.emergencyStop()
  }, [])

  useEffect(() => {
    if (!window.electronAPI) {
      setConnectionError('Electron API not available')
      setIsError(true)
      return
    }

    let mounted = true

    const performHandshake = async (pingId?: string) => {
      try {
        await window.electronAPI.initializeZeroMQ?.()

        if (pingId) {
          const readyPayload = { type: 'frontend_ready', ping_id: pingId }
          await window.electronAPI.sendStartupCommand?.(readyPayload)

          const responsePayload = {
            type: 'frontend_ready_response',
            ping_id: pingId,
            success: true,
          }
          await window.electronAPI.sendStartupCommand?.(responsePayload)
        } else {
          const readyPayload = { type: 'frontend_ready' }
          await window.electronAPI.sendStartupCommand?.(readyPayload)
        }
      } catch (error) {
        console.error('Frontend handshake failed:', error)
      } finally {
        handshakeInProgress.current = false
      }
    }

    const handleSystemState = (message: ISIMessage) => {
      setSystemState(message.state)
      setDisplayText(message.display_text || message.state)
      setIsReady(Boolean(message.is_ready))
      setIsError(Boolean(message.is_error))
      if (message.error) {
        setErrorMessage(message.error)
      }
    }

    const handleSyncMessage = (message: ISIMessage) => {
      if (!mounted) return

      if (message.type === 'system_state') {
        handleSystemState(message)
        if (message.state === 'waiting_frontend' && !handshakeInProgress.current) {
          handshakeInProgress.current = true
          performHandshake()
        }
      }

      if (message.type === 'parameters_snapshot') {
        setParametersSnapshot({
          timestamp: message.timestamp,
          parameters: message.parameters || {},
          parameter_config: message.parameter_config || {},
        })
      }

      if (message.type === 'system_health' || message.type === 'system_health_detailed') {
        setHealthSnapshot(message)
      }
    }

    const handleControlMessage = (message: ISIMessage) => {
      if (!mounted) return

      setLastControlMessage(message)

      if (message.type === 'parameters_snapshot') {
        setParametersSnapshot({
          timestamp: message.timestamp,
          parameters: message.parameters || {},
          parameter_config: message.parameter_config || {},
        })
      }

      if (message.type === 'parameter_info' && message.info?.parameter_config) {
        setParametersSnapshot(prev => {
          if (!prev) {
            return {
              timestamp: Date.now(),
              parameters: {},
              parameter_config: message.info.parameter_config,
            }
          }

          return {
            ...prev,
            parameter_config: message.info.parameter_config,
          }
        })
      }

      if (message.type === 'system_state') {
        handleSystemState(message)
      }

      if (message.type === 'startup_coordination' && message.command === 'check_frontend_ready') {
        if (!handshakeInProgress.current) {
          handshakeInProgress.current = true
          performHandshake(message.ping_id)
        }
      }
    }

    const handleHealthMessage = (message: ISIMessage) => {
      if (!mounted) return
      setHealthSnapshot(message)
    }

    const handleBackendError = (error: string) => {
      if (!mounted) return
      setConnectionError(error)
      setIsError(true)
    }

    window.electronAPI.onSyncMessage?.(handleSyncMessage)
    window.electronAPI.onControlMessage?.(handleControlMessage)
    window.electronAPI.onHealthMessage?.(handleHealthMessage)
    window.electronAPI.onBackendError(handleBackendError)

    return () => {
      mounted = false
      window.electronAPI.onSyncMessage?.(() => {})
      window.electronAPI.onControlMessage?.(() => {})
      window.electronAPI.onHealthMessage?.(() => {})
    }
  }, [])

  const value = useMemo<SystemContextValue>(() => ({
    systemState,
    displayText,
    isReady,
    isError,
    errorMessage,
    connectionError,
    parametersSnapshot,
    healthSnapshot,
    lastControlMessage,
    sendCommand,
    emergencyStop,
  }), [
    systemState,
    displayText,
    isReady,
    isError,
    errorMessage,
    connectionError,
    parametersSnapshot,
    healthSnapshot,
    lastControlMessage,
    sendCommand,
    emergencyStop,
  ])

  return <SystemContext.Provider value={value}>{children}</SystemContext.Provider>
}

export const useSystemContext = (): SystemContextValue => {
  const context = useContext(SystemContext)
  if (!context) {
    throw new Error('useSystemContext must be used within a SystemProvider')
  }
  return context
}

export const useParametersSnapshot = () => {
  const { parametersSnapshot } = useSystemContext()
  return parametersSnapshot
}

export const useHealthSnapshot = () => {
  const { healthSnapshot } = useSystemContext()
  return healthSnapshot
}
