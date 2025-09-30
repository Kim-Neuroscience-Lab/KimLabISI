import React, { useEffect, useState, useCallback } from 'react'
import { useFrameRenderer } from '../../hooks/useFrameRenderer'

interface MonitorParameters {
  selected_display: string
  monitor_distance_cm: number
  monitor_lateral_angle_deg: number
  monitor_tilt_angle_deg: number
  monitor_width_cm: number
  monitor_height_cm: number
  monitor_width_px: number
  monitor_height_px: number
  monitor_fps: number
}

interface StimulusParameters {
  checker_size_deg: number
  bar_width_deg: number
  drift_speed_deg_per_sec: number
  strobe_rate_hz: number
  contrast: number
}

interface AcquisitionParameters {
  baseline_sec: number
  between_sec: number
  cycles: number
  directions: string[]
}

interface SystemState {
  isConnected: boolean
  isExperimentRunning: boolean
  currentProgress: number
  systemStatus: {
    camera: 'online' | 'offline' | 'error'
    display: 'online' | 'offline' | 'error'
    stimulus: 'online' | 'offline' | 'error'
    parameters: 'online' | 'offline' | 'error'
  }
}

interface StimulusPresentationViewportProps {
  className?: string
  stimulusParams?: StimulusParameters
  monitorParams?: MonitorParameters
  acquisitionParams?: AcquisitionParameters
  sendCommand?: (command: any) => Promise<any>
  systemState?: SystemState
  lastMessage?: any
  isPresenting?: boolean
  onClose?: () => void
}

const StimulusPresentationViewport: React.FC<StimulusPresentationViewportProps> = ({
  className = '',
  stimulusParams,
  monitorParams,
  acquisitionParams,
  sendCommand,
  systemState,
  lastMessage,
  isPresenting = false,
  onClose
}) => {
  const [hasFrameData, setHasFrameData] = useState(false)

  // Canvas-based frame rendering
  const { canvasRef, renderFrame } = useFrameRenderer()

  // Listen for shared memory frames from main process
  useEffect(() => {
    const handleSharedMemoryFrame = (frameData: any) => {
      renderFrame(frameData)
      setHasFrameData(true)
    }

    if (window.electronAPI?.onSharedMemoryFrame) {
      window.electronAPI.onSharedMemoryFrame(handleSharedMemoryFrame)
    }

    return () => {
      if (window.electronAPI?.removeSharedMemoryListener) {
        window.electronAPI.removeSharedMemoryListener()
      }
    }
  }, [renderFrame])

  // Listen for stimulus presentation stop
  useEffect(() => {
    if (lastMessage?.type === 'stimulus_presentation_stop') {
      if (onClose) {
        onClose()
      }
    }
  }, [lastMessage, onClose])

  // Handle escape key to close presentation
  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && onClose) {
        onClose()
      }
    }

    document.addEventListener('keydown', handleKeyPress)
    return () => {
      document.removeEventListener('keydown', handleKeyPress)
    }
  }, [onClose])

  // Always render in fullscreen mode for presentation - no UI controls needed
  return (
    <div
      className="fixed inset-0 z-50 bg-black cursor-none"
      style={{
        width: '100vw',
        height: '100vh',
        overflow: 'hidden'
      }}
    >
      <canvas
        ref={canvasRef}
        className="w-full h-full"
        style={{
          maxWidth: '100vw',
          maxHeight: '100vh',
          objectFit: 'contain'
        }}
      />
    </div>
  )
}

export default StimulusPresentationViewport