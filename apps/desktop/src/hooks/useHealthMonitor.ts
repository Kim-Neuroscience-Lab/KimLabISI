import { useState, useEffect } from 'react'
import type { HealthMessage } from '../types/electron'
import type { ControlMessage, SyncMessage } from '../types/ipc-messages'

export interface HealthStatus {
  system: string
  status: 'online' | 'offline' | 'error' | 'degraded'
  message?: string
  lastUpdate?: number
}

export interface SystemHealthState {
  multi_channel_ipc: HealthStatus
  parameters: HealthStatus
  display: HealthStatus
  camera: HealthStatus
  realtime_streaming: HealthStatus
  overall: {
    status: 'healthy' | 'degraded' | 'error' | 'initializing'
    message: string
  }
}

interface UseHealthMonitorOptions {
  lastMessage?: ControlMessage | SyncMessage | null
}

export const useHealthMonitor = ({ lastMessage }: UseHealthMonitorOptions) => {
  const [healthState, setHealthState] = useState<SystemHealthState>({
    multi_channel_ipc: { system: 'multi_channel_ipc', status: 'offline' },
    parameters: { system: 'parameters', status: 'offline' },
    display: { system: 'display', status: 'offline' },
    camera: { system: 'camera', status: 'offline' },
    realtime_streaming: { system: 'realtime_streaming', status: 'offline' },
    overall: {
      status: 'initializing',
      message: 'System initializing...'
    }
  })

  useEffect(() => {
    if (!window.electronAPI?.onHealthMessage) {
      return
    }

    const handleHealthMessage = (healthData: HealthMessage) => {
      // Type guard for SystemHealthMessage
      if (!('type' in healthData) || healthData.type !== 'system_health') {
        return
      }

      if (!healthData.hardware_status) {
        return
      }

      setHealthState(prev => {
        const next: SystemHealthState = {
          ...prev,
          multi_channel_ipc: { system: 'multi_channel_ipc', status: 'offline' },
          parameters: { system: 'parameters', status: 'offline' },
          display: { system: 'display', status: 'offline' },
          camera: { system: 'camera', status: 'offline' },
          realtime_streaming: { system: 'realtime_streaming', status: 'offline' },
          overall: prev.overall
        }

        const systems: Array<keyof SystemHealthState> = [
          'multi_channel_ipc',
          'parameters',
          'display',
          'camera',
          'realtime_streaming'
        ]

        systems.forEach(systemKey => {
          const status = healthData.hardware_status[systemKey as string]
          if (!status) {
            return
          }

          next[systemKey] = {
            system: systemKey as string,
            status,
            message: healthData.details?.[systemKey as string],
            lastUpdate: Date.now()
          }
        })

        const onlineCount = systems.filter(systemKey => next[systemKey].status === 'online').length
        const errorCount = systems.filter(systemKey => next[systemKey].status === 'error').length

        if (errorCount > 0) {
          next.overall = {
            status: 'error',
            message: `${errorCount} system${errorCount > 1 ? 's' : ''} in error state`
          }
        } else if (onlineCount === systems.length) {
          next.overall = {
            status: 'healthy',
            message: 'All systems operational'
          }
        } else if (onlineCount > 0) {
          next.overall = {
            status: 'degraded',
            message: `${onlineCount}/${systems.length} systems online`
          }
        } else {
          next.overall = {
            status: 'initializing',
            message: 'Systems starting up...'
          }
        }

        return next
      })
    }

    const unsubscribe = window.electronAPI.onHealthMessage(handleHealthMessage)

    return () => {
      unsubscribe()
    }
  }, [])

  return {
    healthState,
    isHealthy: healthState.overall.status === 'healthy',
    hasErrors: healthState.overall.status === 'error',
    isInitializing: healthState.overall.status === 'initializing'
  }
}