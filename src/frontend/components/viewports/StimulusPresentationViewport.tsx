import React, { useEffect, useState, useCallback } from 'react'

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
  const [currentStimulus, setCurrentStimulus] = useState<any>(null)

  // Listen for stimulus presentation updates
  useEffect(() => {
    if (lastMessage?.type === 'stimulus_frame') {
      setCurrentStimulus(lastMessage)
    }
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

  // Stimulus display - shows frames sent from backend
  const renderStimulus = () => {
    if (currentStimulus?.frame_data) {
      return (
        <img
          src={currentStimulus.frame_data}
          alt="Stimulus Frame"
          className="w-full h-full object-contain"
          style={{
            maxWidth: '100vw',
            maxHeight: '100vh',
            width: '100%',
            height: '100%'
          }}
        />
      )
    }

    // Default presentation screen - completely black with no text or UI
    return (
      <div className="w-full h-full bg-black">
      </div>
    )
  }

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
      {renderStimulus()}
    </div>
  )
}

export default StimulusPresentationViewport