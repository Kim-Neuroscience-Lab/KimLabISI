import { useState, useEffect } from 'react'

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
  lastMessage?: any
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

  // Listen for health messages from the HEALTH channel
  useEffect(() => {
    if (!window.electronAPI?.onHealthMessage) return

    const handleHealthMessage = (healthData: any) => {
      if (healthData.type === 'system_health' || healthData.type === 'health_update') {
        setHealthState(prev => {
          const newState = { ...prev }

          // Update individual system statuses
          if (healthData.hardware_status) {
            Object.keys(healthData.hardware_status).forEach(system => {
              const status = healthData.hardware_status[system]
              if (newState[system as keyof SystemHealthState]) {
                (newState[system as keyof SystemHealthState] as HealthStatus) = {
                  system,
                  status: status === 'online' ? 'online' : status === 'error' ? 'error' : 'offline',
                  message: healthData.details?.[system],
                  lastUpdate: Date.now()
                }
              }
            })
          }

          // Calculate overall health
          const systems = [
            newState.multi_channel_ipc,
            newState.parameters,
            newState.display,
            newState.camera,
            newState.realtime_streaming
          ]

          const onlineCount = systems.filter(s => s.status === 'online').length
          const errorCount = systems.filter(s => s.status === 'error').length
          const totalSystems = systems.length

          if (errorCount > 0) {
            newState.overall = {
              status: 'error',
              message: `${errorCount} system${errorCount > 1 ? 's' : ''} in error state`
            }
          } else if (onlineCount === totalSystems) {
            newState.overall = {
              status: 'healthy',
              message: 'All systems operational'
            }
          } else if (onlineCount > 0) {
            newState.overall = {
              status: 'degraded',
              message: `${onlineCount}/${totalSystems} systems online`
            }
          } else {
            newState.overall = {
              status: 'initializing',
              message: 'Systems starting up...'
            }
          }

          return newState
        })
      }
    }

    window.electronAPI.onHealthMessage(handleHealthMessage)

    return () => {
      // Cleanup if needed
    }
  }, [])

  // Handle legacy messages for backwards compatibility
  useEffect(() => {
    if (!lastMessage) return

    if (lastMessage.type === 'system_health' || lastMessage.type === 'system_health_detailed') {
      if (lastMessage.hardware_status) {
        setHealthState(prev => {
          const newState = { ...prev }

          // Map legacy hardware_status to new format
          if (lastMessage.hardware_status.multi_channel_ipc) {
            newState.multi_channel_ipc = {
              system: 'multi_channel_ipc',
              status: lastMessage.hardware_status.multi_channel_ipc,
              lastUpdate: Date.now()
            }
          }

          if (lastMessage.hardware_status.parameters) {
            newState.parameters = {
              system: 'parameters',
              status: lastMessage.hardware_status.parameters,
              lastUpdate: Date.now()
            }
          }

          if (lastMessage.hardware_status.display) {
            newState.display = {
              system: 'display',
              status: lastMessage.hardware_status.display,
              lastUpdate: Date.now()
            }
          }

          if (lastMessage.hardware_status.camera) {
            newState.camera = {
              system: 'camera',
              status: lastMessage.hardware_status.camera,
              lastUpdate: Date.now()
            }
          }

          if (lastMessage.hardware_status.realtime_streaming) {
            newState.realtime_streaming = {
              system: 'realtime_streaming',
              status: lastMessage.hardware_status.realtime_streaming,
              lastUpdate: Date.now()
            }
          }

          return newState
        })
      }
    }
  }, [lastMessage])

  return {
    healthState,
    isHealthy: healthState.overall.status === 'healthy',
    hasErrors: healthState.overall.status === 'error',
    isInitializing: healthState.overall.status === 'initializing'
  }
}