import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import type { ISIMessage, ControlMessage, SyncMessage } from '../types/ipc-messages'
import type { HealthMessage } from '../types/electron'
import { hookLogger } from '../utils/logger'

interface ParametersSnapshot {
  timestamp: number
  parameters: Record<string, unknown>
  parameter_config: Record<string, unknown>
}

interface SystemContextValue {
  systemState: string
  displayText: string
  isReady: boolean
  isError: boolean
  errorMessage: string | null
  connectionError: string | null
  parametersSnapshot: ParametersSnapshot | null
  healthSnapshot: HealthMessage | null
  lastControlMessage: ControlMessage | null
  lastSyncMessage: SyncMessage | null
  sendCommand: (command: ISIMessage) => Promise<{ success: boolean; error?: string }>
  emergencyStop: () => Promise<{ success: boolean; error?: string }>
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
  const [lastSyncMessage, setLastSyncMessage] = useState<ISIMessage | null>(null)

  const handshakeInProgress = useRef(false)
  const lastHealthRequestAt = useRef<number>(0)
  const parametersReceived = useRef(false)
  const readyStateReceived = useRef(false)

  const sendCommand = useCallback(async (command: ISIMessage) => {
    if (!window.electronAPI) {
      throw new Error('Electron API not available')
    }

    if (!isReady) {
      throw new Error('Backend not ready')
    }

    const result = await window.electronAPI.sendToPython(command)
    if (!result.success) {
      throw new Error(result.error || 'Command failed')
    }
    return result
  }, [isReady])

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
        hookLogger.error('Frontend handshake failed:', error)
      } finally {
        handshakeInProgress.current = false
      }
    }

    const handleSystemState = (message: ISIMessage) => {
      setSystemState(message.state)
      setDisplayText(message.display_text || message.state)
      setIsError(Boolean(message.is_error))
      if (message.error) {
        setErrorMessage(message.error)
      }

      // DON'T set isReady yet - wait for parameters_snapshot
      // (handled in parameter snapshot handler below)
    }

    const handleSyncMessage = (message: ISIMessage) => {
      if (!mounted) return

      console.log('📊 [SYNC] Received message type:', message.type)

      // Store all sync messages for components to access
      setLastSyncMessage(message)

      if (message.type === 'system_state') {
        console.log('📊 [SYNC] System state:', message.state, 'is_ready:', message.is_ready)
        handleSystemState(message)
        if (message.state === 'waiting_frontend' && !handshakeInProgress.current) {
          handshakeInProgress.current = true
          performHandshake()
        }

        // Check if this is a ready state via SYNC channel
        if (message.is_ready && message.state === 'ready') {
          readyStateReceived.current = true
          console.log('📊 [SYNC] Received ready state, checking if parameters available...')
          console.log('📊 [SYNC] Parameters received?', parametersReceived.current)

          // Only enable UI if we've received parameters
          if (parametersReceived.current) {
            console.log('📊 [SYNC] Both ready state and parameters received - enabling UI')
            setIsReady(true)
          } else {
            console.log('📊 [SYNC] Waiting for parameters before enabling UI...')
          }
        }
      }

      if (message.type === 'parameters_snapshot') {
        console.log('📊 [SYNC] Received parameters_snapshot:', {
          timestamp: message.timestamp,
          parameterKeys: Object.keys(message.parameters || {}),
          hasParameters: !!message.parameters,
          parameterCount: Object.keys(message.parameters || {}).length
        })
        setParametersSnapshot({
          timestamp: message.timestamp,
          parameters: message.parameters || {},
          parameter_config: message.parameter_config || {},
        })
        parametersReceived.current = true
        console.log('📊 [SYNC] Set parametersReceived.current = true')

        // If ready state was already received, now we can enable UI
        if (readyStateReceived.current) {
          console.log('📊 [SYNC] Parameters received after ready state - enabling UI now')
          setIsReady(true)
        } else {
          console.log('📊 [SYNC] Parameters received, waiting for ready state...')
        }
      }

      if (message.type === 'system_health' || message.type === 'system_health_detailed') {
        if (message.hardware_status) {
          setHealthSnapshot(message)
        }
        lastHealthRequestAt.current = Date.now()
      }
    }

    const handleControlMessage = (message: ISIMessage) => {
      if (!mounted) return

      setLastControlMessage(message)

      if (message.type === 'parameters_snapshot') {
        console.log('📊 [CONTROL] Received parameters_snapshot:', {
          timestamp: message.timestamp,
          parameterKeys: Object.keys(message.parameters || {}),
          parameters: message.parameters
        })
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

      // NOTE: system_state messages are ONLY sent via SYNC channel
      // Removed duplicate handling here to avoid race conditions

      if (message.type === 'startup_status' && message.health) {
        setHealthSnapshot({
          type: 'system_health',
          hardware_status: message.health,
          timestamp: Date.now(),
        })
        lastHealthRequestAt.current = Date.now()
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
      if (message.hardware_status) {
        setHealthSnapshot(message)
        lastHealthRequestAt.current = Date.now()
      }
    }

    const handleBackendError = (error: string | Error) => {
      if (!mounted) return
      const message = error instanceof Error ? error.message : error
      hookLogger.error('Backend error received:', message)
      setConnectionError(message)
      setErrorMessage(message)
      setIsError(true)
    }

    const unsubscribeSync = window.electronAPI.onSyncMessage?.(handleSyncMessage)
    const unsubscribeControl = window.electronAPI.onControlMessage?.(handleControlMessage)
    const unsubscribeHealth = window.electronAPI.onHealthMessage?.(handleHealthMessage)
    const unsubscribeError = window.electronAPI.onBackendError(handleBackendError)

    return () => {
      mounted = false
      unsubscribeSync?.()
      unsubscribeControl?.()
      unsubscribeHealth?.()
      unsubscribeError?.()
    }
  }, [])

  return (
    <SystemContext.Provider
      value={{
        systemState,
        displayText,
        isReady,
        isError,
        errorMessage,
        connectionError,
        parametersSnapshot,
        healthSnapshot,
        lastControlMessage,
        lastSyncMessage,
        sendCommand,
        emergencyStop,
      }}
    >
      {children}
    </SystemContext.Provider>
  )
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
