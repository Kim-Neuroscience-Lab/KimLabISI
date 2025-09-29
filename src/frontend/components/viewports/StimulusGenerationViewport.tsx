import React, { useEffect, useState } from 'react'

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

interface StimulusGenerationViewportProps {
  className?: string
  stimulusParams?: StimulusParameters
  monitorParams?: MonitorParameters
  acquisitionParams?: AcquisitionParameters
  sendCommand?: (command: any) => Promise<any>
  systemState?: SystemState
  lastMessage?: any
}

const StimulusGenerationViewport: React.FC<StimulusGenerationViewportProps> = ({
  className = '',
  stimulusParams,
  monitorParams,
  acquisitionParams,
  sendCommand,
  systemState,
  lastMessage
}) => {
  const [backendParams, setBackendParams] = useState<StimulusParameters | null>(null)
  const [stimulusStatus, setStimulusStatus] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Frame explorer state
  const [direction, setDirection] = useState<'LR' | 'RL' | 'TB' | 'BT'>('LR')
  const [currentFrameIndex, setCurrentFrameIndex] = useState(0)
  const [showBarMask, setShowBarMask] = useState(false)
  const [totalFrames, setTotalFrames] = useState(0)
  const [frameImageData, setFrameImageData] = useState<string | null>(null)
  const [datasetInfo, setDatasetInfo] = useState<any>(null)

  // Fetch initial stimulus data and dataset info
  useEffect(() => {
    const initializeStimulus = async () => {
      // Component is only rendered when system is ready, so we can proceed
      if (!sendCommand) {
        return
      }

      try {
        setIsLoading(true)

        // Get parameters from backend
        const paramsResponse = await sendCommand({ type: 'get_stimulus_parameters' })
        if (paramsResponse?.success && paramsResponse?.parameters) {
          setBackendParams(paramsResponse.parameters)
        } else {
          console.warn('StimulusGenerationViewport: Failed to get parameters:', paramsResponse)
        }

        // Get status from backend
        try {
          const statusResponse = await sendCommand({ type: 'get_stimulus_status' })
          if (statusResponse?.success) {
            setStimulusStatus(statusResponse.status)
          } else {
            console.warn('StimulusGenerationViewport: Failed to get status:', statusResponse)
          }
        } catch (error) {
          console.warn('StimulusGenerationViewport: Status request failed:', error.message)
        }

        // Get dataset info for default direction
        try {
          await loadDatasetInfo('LR')
        } catch (error) {
          console.warn('StimulusGenerationViewport: Dataset loading failed:', error.message)
        }
      } catch (error) {
        console.error('StimulusGenerationViewport: Failed to initialize stimulus:', error)
      } finally {
        setIsLoading(false)
      }
    }

    initializeStimulus()
  }, [sendCommand])

  // Listen for stimulus parameter updates from backend
  useEffect(() => {
    if (lastMessage?.type === 'stimulus_parameters_updated') {
      setBackendParams(lastMessage.parameters)
      // Reload dataset info and current frame when parameters change
      loadDatasetInfo(direction)
    }
    if (lastMessage?.type === 'stimulus_status') {
      setStimulusStatus(lastMessage)
    }
  }, [lastMessage, direction])

  // Send monitor parameters to backend when they change
  useEffect(() => {
    if (monitorParams && sendCommand) {
      sendCommand({
        type: 'update_spatial_configuration',
        spatial_config: {
          monitor_distance_cm: monitorParams.monitor_distance_cm,
          monitor_lateral_angle_deg: monitorParams.monitor_lateral_angle_deg,
          monitor_tilt_angle_deg: monitorParams.monitor_tilt_angle_deg,
          monitor_width_cm: monitorParams.monitor_width_cm,
          monitor_height_cm: monitorParams.monitor_height_cm,
          monitor_width_px: monitorParams.monitor_width_px,
          monitor_height_px: monitorParams.monitor_height_px,
          monitor_fps: monitorParams.monitor_fps
        }
      }).then(() => {
        // Regenerate stimulus when monitor parameters change
        loadDatasetInfo(direction)
      }).catch(error => {
        console.error('Failed to update spatial configuration:', error)
      })
    }
  }, [monitorParams, sendCommand, direction])

  // Send stimulus parameters to backend when they change
  useEffect(() => {
    if (stimulusParams && sendCommand) {
      sendCommand({
        type: 'update_stimulus_parameters',
        parameters: stimulusParams
      }).then(() => {
        // Regenerate stimulus when stimulus parameters change
        loadDatasetInfo(direction)
      }).catch(error => {
        console.error('Failed to update stimulus parameters:', error)
      })
    }
  }, [stimulusParams, sendCommand, direction])

  // Use backend parameters if available, fallback to frontend parameters
  const displayParams = backendParams || stimulusParams

  // Load dataset info for a direction
  const loadDatasetInfo = async (dir: string) => {
    if (!sendCommand) {
      return
    }

    try {
      const infoResponse = await sendCommand({
        type: 'get_stimulus_info',
        direction: dir,
        num_cycles: 3
      })

      if (infoResponse?.success) {
        setDatasetInfo(infoResponse)
        setTotalFrames(infoResponse.total_frames)
        // Reset to frame 0 and load default frame (LR, frame 0, no bar mask)
        setCurrentFrameIndex(0)
        await loadFrame(dir, 0, false)
      } else {
        console.error('StimulusGenerationViewport: Failed to load dataset info:', infoResponse)
      }
    } catch (error) {
      console.error('StimulusGenerationViewport: Exception loading dataset info:', error)
    }
  }

  // Load a specific frame
  const loadFrame = async (dir: string, frameIndex: number, showMask: boolean) => {
    if (!sendCommand) {
      return
    }

    try {
      const frameResponse = await sendCommand({
        type: 'get_stimulus_frame',
        direction: dir,
        frame_index: frameIndex,
        show_bar_mask: showMask,
        num_cycles: 3
      })

      if (frameResponse?.success && frameResponse.frame_data) {
        setFrameImageData(frameResponse.frame_data)
      } else {
        console.error('StimulusGenerationViewport: Failed to load frame:', frameResponse)
      }
    } catch (error) {
      console.error('StimulusGenerationViewport: Exception loading frame:', error)
    }
  }

  // Load frame when controls change
  useEffect(() => {
    if (totalFrames > 0) {
      loadFrame(direction, currentFrameIndex, showBarMask)
    }
  }, [direction, currentFrameIndex, showBarMask, totalFrames])

  // Direction change handler
  const handleDirectionChange = (newDirection: 'LR' | 'RL' | 'TB' | 'BT') => {
    setDirection(newDirection)
    loadDatasetInfo(newDirection) // This will reset frame index to 0
  }

  const startStimulus = async () => {
    if (!sendCommand) return

    try {
      await sendCommand({ type: 'start_stimulus', session_name: `session_${Date.now()}` })
    } catch (error) {
      console.error('Failed to start stimulus:', error)
    }
  }

  const stopStimulus = async () => {
    if (!sendCommand) return

    try {
      await sendCommand({ type: 'stop_stimulus' })
    } catch (error) {
      console.error('Failed to stop stimulus:', error)
    }
  }

  return (
    <div className={`flex flex-col h-full max-h-full ${className}`}>
      {/* Stimulus Display Container */}
      <div className="flex-1 relative bg-black border border-sci-secondary-600 rounded-lg overflow-hidden min-h-0 w-full h-0">
        {isLoading ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center text-sci-secondary-400">
              <div className="text-lg">Loading Stimulus</div>
              <div className="text-sm mt-2">Initializing parameters...</div>
            </div>
          </div>
        ) : frameImageData ? (
          <img
            src={frameImageData}
            alt={`Stimulus frame ${currentFrameIndex}`}
            className="absolute inset-0 w-full h-full object-contain"
            style={{
              maxWidth: '100%',
              maxHeight: '100%',
              width: '100%',
              height: '100%'
            }}
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center text-sci-secondary-400">
              <div className="text-4xl mb-4">⚠️</div>
              <div className="text-lg">No Frame Data</div>
              <div className="text-sm mt-2">Check backend connection</div>
            </div>
          </div>
        )}
      </div>

      {/* Frame Explorer Controls - Grid Layout */}
      <div className="grid grid-cols-3 items-center gap-4 mt-4">
        {/* Left Column - Direction and Bar Mask Controls */}
        <div className="flex items-center gap-4 justify-start">
          {/* Direction Controls */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-sci-secondary-400">Direction:</span>
            {(['LR', 'RL', 'TB', 'BT']).map((dir) => (
              <button
                key={dir}
                onClick={() => handleDirectionChange(dir as 'LR' | 'RL' | 'TB' | 'BT')}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  direction === dir
                    ? 'bg-sci-primary-600 text-white'
                    : 'bg-sci-secondary-700 text-sci-secondary-300 hover:bg-sci-secondary-600'
                }`}
              >
                {dir}
              </button>
            ))}
          </div>

          {/* Bar Mask Toggle */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-sci-secondary-400">Bar Mask:</span>
            <button
              onClick={() => setShowBarMask(!showBarMask)}
              className={`px-3 py-1 text-xs rounded transition-colors ${
                showBarMask
                  ? 'bg-sci-accent-600 text-white'
                  : 'bg-sci-secondary-700 text-sci-secondary-300 hover:bg-sci-secondary-600'
              }`}
            >
              {showBarMask ? 'ON' : 'OFF'}
            </button>
          </div>
        </div>

        {/* Center Column - Frame Slider */}
        {totalFrames > 0 && (
          <div className="flex items-center gap-4 justify-center">
            <span className="text-xs text-sci-secondary-400">Frame:</span>
            <input
              type="range"
              min={0}
              max={totalFrames - 1}
              value={currentFrameIndex}
              onChange={(e) => setCurrentFrameIndex(parseInt(e.target.value))}
              className="flex-1 max-w-48"
            />
            <span className="text-xs text-sci-secondary-300 w-20 text-right">
              {currentFrameIndex}/{totalFrames - 1}
              {datasetInfo && (
                <span className="text-sci-secondary-500 ml-2">
                  ({((datasetInfo.start_angle || 0) + (currentFrameIndex / (totalFrames - 1)) * ((datasetInfo.end_angle || 0) - (datasetInfo.start_angle || 0))).toFixed(1)}°)
                </span>
              )}
            </span>
          </div>
        )}

        {/* Right Column - Generate Stimulus Button */}
        <div className="flex justify-end">
          {!stimulusStatus?.is_presenting ? (
            <button
              onClick={startStimulus}
              disabled={!displayParams}
              className="px-4 py-2 bg-sci-primary-600 text-white rounded text-sm font-medium hover:bg-sci-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Generate Stimulus
            </button>
          ) : (
            <button
              onClick={stopStimulus}
              className="px-4 py-2 bg-red-600 text-white rounded text-sm font-medium hover:bg-red-700 transition-colors"
            >
              Stop Stimulus
            </button>
          )}
        </div>
      </div>

    </div>
  )
}

export default StimulusGenerationViewport