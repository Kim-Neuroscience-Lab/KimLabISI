import React, { useEffect, useState } from 'react'
import { useFrameRenderer } from '../../hooks/useFrameRenderer'
import { componentLogger } from '../../utils/logger'
import type { ISIMessage, ControlMessage, SyncMessage } from '../../types/ipc-messages'
import type { SharedMemoryFrameData } from '../../types/electron'
import type { SystemState } from '../../types/shared'
import type {
  MonitorParameters,
  StimulusParameters,
  AcquisitionParameters
} from '../../hooks/useParameterManager'

interface StimulusGenerationViewportProps {
  className?: string
  stimulusParams?: StimulusParameters
  monitorParams?: MonitorParameters
  acquisitionParams?: AcquisitionParameters
  sendCommand?: (command: ISIMessage) => Promise<{ success: boolean; error?: string }>
  systemState?: SystemState
  lastMessage?: ControlMessage | SyncMessage | null
  sharedDirection?: 'LR' | 'RL' | 'TB' | 'BT'
  sharedFrameIndex?: number
  sharedShowBarMask?: boolean
  onDirectionChange?: (dir: 'LR' | 'RL' | 'TB' | 'BT') => void
  onFrameIndexChange?: (index: number) => void
  onShowBarMaskChange?: (show: boolean) => void
}

const StimulusGenerationViewport: React.FC<StimulusGenerationViewportProps> = ({
  className = '',
  stimulusParams,
  monitorParams,
  acquisitionParams,
  sendCommand,
  systemState,
  lastMessage,
  sharedDirection = 'LR',
  sharedFrameIndex = 0,
  sharedShowBarMask = false,
  onDirectionChange,
  onFrameIndexChange,
  onShowBarMaskChange
}) => {
  const [isLoading, setIsLoading] = useState(true)

  // Use shared state from parent (synced across viewports)
  const direction = sharedDirection
  const currentFrameIndex = sharedFrameIndex
  const showBarMask = sharedShowBarMask
  const setDirection = onDirectionChange || (() => {})
  const setCurrentFrameIndex = onFrameIndexChange || (() => {})
  const setShowBarMask = onShowBarMaskChange || (() => {})
  const [totalFrames, setTotalFrames] = useState(0)
  const [datasetInfo, setDatasetInfo] = useState<any>(null)
  const [hasFrameData, setHasFrameData] = useState(false)

  // Canvas-based frame rendering
  const { canvasRef, renderFrame } = useFrameRenderer()

  // Listen for shared memory frame metadata ONLY (not frame data)
  useEffect(() => {
    let lastFrameId: number | null = null

    const handleSharedMemoryFrame = async (metadata: SharedMemoryFrameData) => {
      // Only process if this is a NEW frame (prevents duplicate renders)
      if (lastFrameId !== null && metadata.frame_id === lastFrameId) {
        return
      }
      lastFrameId = metadata.frame_id

      // Extract dataset info from frame metadata
      if (metadata.total_frames && metadata.total_frames > 0) {
        setTotalFrames(metadata.total_frames)
        setDatasetInfo({
          total_frames: metadata.total_frames,
          start_angle: metadata.start_angle,
          end_angle: metadata.end_angle,
          direction: metadata.direction
        })
      }

      // Read actual frame data from shared memory using offset and size
      try {
        const frameDataBuffer = await window.electronAPI.readSharedMemoryFrame(
          metadata.offset_bytes,
          metadata.data_size_bytes
        )

        // Combine metadata with frame data for rendering
        const completeFrameData = {
          ...metadata,
          frame_data: frameDataBuffer
        }

        // Render the single frame (preview mode - not continuous playback)
        renderFrame(completeFrameData)
        setHasFrameData(true)
      } catch (error) {
        componentLogger.error('Failed to read frame from shared memory:', error)
      }
    }

    // Register IPC listener for shared memory frame metadata via electronAPI
    let unsubscribe: (() => void) | undefined
    if (window.electronAPI?.onSharedMemoryFrame) {
      unsubscribe = window.electronAPI.onSharedMemoryFrame(handleSharedMemoryFrame)
    }

    return () => {
      unsubscribe?.()
    }
  }, [renderFrame])

  // Stop loading once we have frame data
  useEffect(() => {
    if (hasFrameData) {
      setIsLoading(false)
    }
  }, [hasFrameData])

  // Load initial frame on mount
  useEffect(() => {
    if (!hasFrameData && systemState?.isConnected && sendCommand) {
      loadFrame(direction, 0, showBarMask)
    }
  }, [hasFrameData, systemState?.isConnected, sendCommand])

  // Request a frame from the backend
  const loadFrame = async (dir: string, frameIndex: number, showMask: boolean) => {
    if (!sendCommand) {
      componentLogger.error('Stimulus frame request failed: sendCommand is unavailable')
      return
    }

    try {
      await sendCommand({
        type: 'get_stimulus_frame',
        direction: dir,
        frame_index: frameIndex,
        show_bar_mask: showMask
      })
      // Frame will arrive via shared memory with metadata
    } catch (error) {
      componentLogger.error('Failed to request stimulus frame:', error)
    }
  }

  // Request frame when controls change
  useEffect(() => {
    if (!hasFrameData) {
      return
    }

    if (totalFrames > 0 && sendCommand) {
      loadFrame(direction, currentFrameIndex, showBarMask)
    }
  }, [direction, currentFrameIndex, showBarMask, totalFrames, sendCommand, hasFrameData])

  // Direction change handler
  const handleDirectionChange = (newDirection: 'LR' | 'RL' | 'TB' | 'BT') => {
    setDirection(newDirection)
    setCurrentFrameIndex(0)
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

        {/* Right Column - Info Text */}
        <div className="flex justify-end">
          <span className="text-xs text-sci-secondary-400 italic">
            Real-time preview - Adjust controls to see different frames
          </span>
        </div>
      </div>

    </div>
  )
}

export default StimulusGenerationViewport