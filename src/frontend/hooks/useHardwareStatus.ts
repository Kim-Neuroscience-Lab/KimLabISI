import { useState, useEffect, useCallback, useRef } from 'react'

export type HardwareStatusValue = 'online' | 'offline' | 'error'

export interface HardwareStatus {
  camera: HardwareStatusValue
  display: HardwareStatusValue
  stimulus: HardwareStatusValue
  parameters: HardwareStatusValue
}

export interface CameraInfo {
  name: string
  capabilities?: {
    width: number
    height: number
    frameRate: number
  }
}

export interface DisplayInfo {
  name: string
  width: number
  height: number
  refresh_rate: number
  is_primary: boolean
  position_x: number
  position_y: number
  scale_factor: number
  identifier: string
}

export interface UseHardwareStatusProps {
  sendCommand?: (command: any) => Promise<any>
  isConnected: boolean
  isReady: boolean
  lastMessage?: any
  onStatusChange?: (status: HardwareStatus) => void
}

export interface UseHardwareStatusReturn {
  hardwareStatus: HardwareStatus
  availableCameras: CameraInfo[]
  availableDisplays: DisplayInfo[]
  isInitializing: boolean
  refreshStatus: () => Promise<void>
  selectCamera: (cameraName: string) => Promise<void>
  selectDisplay: (displayId: string) => Promise<void>
}

export const useHardwareStatus = ({
  sendCommand,
  isConnected,
  isReady,
  lastMessage,
  onStatusChange
}: UseHardwareStatusProps): UseHardwareStatusReturn => {
  const [hardwareStatus, setHardwareStatus] = useState<HardwareStatus>({
    camera: 'offline',
    display: 'offline',
    stimulus: 'offline',
    parameters: 'offline'
  })

  const [availableCameras, setAvailableCameras] = useState<CameraInfo[]>([])
  const [availableDisplays, setAvailableDisplays] = useState<DisplayInfo[]>([])
  const [isInitializing, setIsInitializing] = useState(false)

  // Track which systems have been tested to avoid duplicate requests
  const testedSystems = useRef<Set<string>>(new Set())

  // Update hardware status and notify parent
  const updateHardwareStatus = useCallback((updates: Partial<HardwareStatus>) => {
    setHardwareStatus(prev => {
      const newStatus = { ...prev, ...updates }
      onStatusChange?.(newStatus)
      return newStatus
    })
  }, [onStatusChange])

  // Centralized system health check using backend health monitor
  const testAllSystems = useCallback(async (force: boolean = false) => {
    if (!sendCommand) return
    if (!force && testedSystems.current.has('all_systems')) return

    testedSystems.current.add('all_systems')
    setIsInitializing(true)

    try {
      // Use centralized health checking from backend
      const response = await sendCommand({
        type: 'get_system_health',
        use_cache: false, // Force fresh check
        include_details: true
      })

      if (response?.success && response?.hardware_status) {
        // Update hardware status from centralized backend check
        updateHardwareStatus(response.hardware_status)

        // Update camera and display lists if available in detailed response
        if (response.detailed_results) {
          const cameraDetails = response.detailed_results.camera
          const displayDetails = response.detailed_results.display

          if (cameraDetails?.metrics?.camera_names) {
            const cameras: CameraInfo[] = cameraDetails.metrics.camera_names.map((name: string) => ({ name }))
            setAvailableCameras(cameras)
          }

          if (displayDetails?.metrics?.display_info) {
            setAvailableDisplays(displayDetails.metrics.display_info)
          }
        }

      } else {
        console.error('Health check failed:', response?.error || 'Unknown error')
        // Fallback to offline status if health check fails
        updateHardwareStatus({
          camera: 'error',
          display: 'error',
          stimulus: 'error',
          parameters: 'error'
        })
      }
    } catch (error) {
      console.error('Centralized health check failed:', error)
      updateHardwareStatus({
        camera: 'error',
        display: 'error',
        stimulus: 'error',
        parameters: 'error'
      })
    } finally {
      setIsInitializing(false)
    }
  }, [sendCommand, updateHardwareStatus])

  // Refresh status - clears cache and retests all systems
  const refreshStatus = useCallback(async () => {
    testedSystems.current.clear()
    setHardwareStatus({
      camera: 'offline',
      display: 'offline',
      stimulus: 'offline',
      parameters: 'offline'
    })
    await testAllSystems(true) // Force refresh
  }, [testAllSystems])

  // Initialize hardware status when backend becomes ready
  useEffect(() => {
    if (isConnected && isReady && sendCommand) {
      // Clear any previous test state and start fresh
      testedSystems.current.clear()
      // Use setTimeout to ensure this runs after the current execution stack
      setTimeout(() => testAllSystems(true), 100)
    }
  }, [isConnected, isReady, sendCommand, testAllSystems])

  // Handle incoming messages from backend - standardized health only
  useEffect(() => {
    if (!lastMessage) return

    switch (lastMessage.type) {
      case 'system_health':
      case 'system_health_detailed':
        if (lastMessage.hardware_status) {
          updateHardwareStatus(lastMessage.hardware_status)

          // Update camera and display info if available in detailed response
          if (lastMessage.detailed_results) {
            const cameraDetails = lastMessage.detailed_results.camera
            const displayDetails = lastMessage.detailed_results.display

            if (cameraDetails?.metrics?.camera_names) {
              const cameras: CameraInfo[] = cameraDetails.metrics.camera_names.map((name: string) => ({ name }))
              setAvailableCameras(cameras)
            }

            if (displayDetails?.metrics?.display_info) {
              setAvailableDisplays(displayDetails.metrics.display_info)
            }
          }
        }
        break

      case 'get_camera_capabilities':
        if (lastMessage.success && lastMessage.capabilities) {
          // Update camera info with capabilities
          setAvailableCameras(prev =>
            prev.map(camera =>
              camera.name === lastMessage.camera_name
                ? { ...camera, capabilities: lastMessage.capabilities }
                : camera
            )
          )
        }
        break
    }
  }, [lastMessage, updateHardwareStatus])

  // Reset status when connection is lost
  useEffect(() => {
    if (!isConnected) {
      setHardwareStatus({
        camera: 'offline',
        display: 'offline',
        stimulus: 'offline',
        parameters: 'offline'
      })
      testedSystems.current.clear()
    }
  }, [isConnected])

  // Camera selection
  const selectCamera = useCallback(async (cameraName: string) => {
    if (!sendCommand) return

    try {
      const response = await sendCommand({
        type: 'get_camera_capabilities',
        camera_name: cameraName
      })

      if (response?.success) {
        // Update camera info with capabilities
        setAvailableCameras(prev =>
          prev.map(camera =>
            camera.name === cameraName
              ? { ...camera, capabilities: response.capabilities }
              : camera
          )
        )
      }
    } catch (error) {
      console.error('Failed to select camera:', error)
    }
  }, [sendCommand])

  // Display selection
  const selectDisplay = useCallback(async (displayId: string) => {
    if (!sendCommand) return

    try {
      await sendCommand({
        type: 'select_display',
        display_id: displayId
      })
    } catch (error) {
      console.error('Failed to select display:', error)
    }
  }, [sendCommand])

  return {
    hardwareStatus,
    availableCameras,
    availableDisplays,
    isInitializing,
    refreshStatus,
    selectCamera,
    selectDisplay
  }
}