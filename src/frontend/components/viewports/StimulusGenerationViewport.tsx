import React, { useEffect, useState } from 'react'
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
  console.log('[STIMULUS-DEBUG] Component mounted/rendered, sendCommand:', !!sendCommand)

  const [backendParams, setBackendParams] = useState<StimulusParameters | null>(null)
  const [backendMonitorParams, setBackendMonitorParams] = useState<MonitorParameters | null>(null)
  const [stimulusStatus, setStimulusStatus] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Frame explorer state
  const [direction, setDirection] = useState<'LR' | 'RL' | 'TB' | 'BT'>('LR')
  const [currentFrameIndex, setCurrentFrameIndex] = useState(0)
  const [showBarMask, setShowBarMask] = useState(false)
  const [totalFrames, setTotalFrames] = useState(0)
  const [datasetInfo, setDatasetInfo] = useState<any>(null)
  const [hasFrameData, setHasFrameData] = useState(false)

  // Canvas-based frame rendering
  const { canvasRef, renderFrame } = useFrameRenderer()

  // Listen for shared memory frames from main process
  useEffect(() => {
    const handleSharedMemoryFrame = (frameData: any) => {
      console.log('Received shared memory frame:', frameData.frame_id, frameData.timestamp_us)

      // Extract dataset info from frame metadata
      if (frameData.total_frames && frameData.total_frames > 0) {
        setTotalFrames(frameData.total_frames)
        setDatasetInfo({
          total_frames: frameData.total_frames,
          start_angle: frameData.start_angle,
          end_angle: frameData.end_angle,
          direction: frameData.direction
        })
      }

      // Update current frame index
      if (frameData.frame_index !== undefined) {
        setCurrentFrameIndex(frameData.frame_index)
      }

      // Render raw binary frame data directly to canvas
      renderFrame(frameData)
      setHasFrameData(true)
    }

    // Register IPC listener for shared memory frames via electronAPI
    if (window.electronAPI?.onSharedMemoryFrame) {
      window.electronAPI.onSharedMemoryFrame(handleSharedMemoryFrame)
    }

    return () => {
      if (window.electronAPI?.removeSharedMemoryListener) {
        window.electronAPI.removeSharedMemoryListener()
      }
    }
  }, [renderFrame])

  // Stop loading once we have frame data
  useEffect(() => {
    if (hasFrameData) {
      setIsLoading(false)
    }
  }, [hasFrameData])

  // Use backend parameters if available, fallback to frontend parameters
  const displayParams = backendParams || stimulusParams

  // Request a frame from the backend
  const loadFrame = async (dir: string, frameIndex: number, showMask: boolean) => {
    console.log('[STIMULUS-DEBUG] loadFrame called:', { dir, frameIndex, showMask, hasSendCommand: !!sendCommand })

    if (!sendCommand) {
      console.error('[STIMULUS-DEBUG] sendCommand is not available')
      return
    }

    try {
      console.log('[STIMULUS-DEBUG] Sending get_stimulus_frame command...')
      await sendCommand({
        type: 'get_stimulus_frame',
        direction: dir,
        frame_index: frameIndex,
        show_bar_mask: showMask,
        num_cycles: 3
      })
      console.log('[STIMULUS-DEBUG] get_stimulus_frame command sent successfully')
      // Frame will arrive via shared memory with metadata
    } catch (error) {
      console.error('[STIMULUS-DEBUG] Failed to request frame:', error)
    }
  }

  // Request initial frame on mount
  useEffect(() => {
    console.log('[STIMULUS-DEBUG] Initial frame useEffect triggered:', { hasSendCommand: !!sendCommand, direction, showBarMask })
    if (sendCommand) {
      console.log('[STIMULUS-DEBUG] Calling loadFrame for initial frame')
      loadFrame(direction, 0, showBarMask)
    } else {
      console.warn('[STIMULUS-DEBUG] sendCommand not available in initial frame useEffect')
    }
  }, [sendCommand])

  // Request frame when controls change
  useEffect(() => {
    if (totalFrames > 0 && sendCommand) {
      loadFrame(direction, currentFrameIndex, showBarMask)
    }
  }, [direction, currentFrameIndex, showBarMask, totalFrames, sendCommand])

  // Direction change handler
  const handleDirectionChange = (newDirection: 'LR' | 'RL' | 'TB' | 'BT') => {
    setDirection(newDirection)
    setCurrentFrameIndex(0)
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

  console.log('[STIMULUS-DEBUG] render: totalFrames =', totalFrames, 'hasFrameData =', hasFrameData, 'hasSendCommand =', !!sendCommand)

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
        ) : (
          <>
            <canvas
              ref={canvasRef}
              className="absolute inset-0 w-full h-full"
              style={{
                maxWidth: '100%',
                maxHeight: '100%',
                objectFit: 'contain'
              }}
            />
            {!hasFrameData && (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-center text-sci-secondary-400">
                  <div className="text-4xl mb-4">⚠️</div>
                  <div className="text-lg">No Frame Data</div>
                  <div className="text-sm mt-2">Check backend connection</div>
                </div>
              </div>
            )}
          </>
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