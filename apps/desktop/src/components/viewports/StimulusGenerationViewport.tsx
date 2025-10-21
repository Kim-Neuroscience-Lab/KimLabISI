import React, { useEffect, useState } from 'react'
import { useFrameRenderer } from '../../hooks/useFrameRenderer'
import { componentLogger } from '../../utils/logger'
import type { ISIMessage, ControlMessage, SyncMessage } from '../../types/ipc-messages'
import type { SharedMemoryFrameData } from '../../types/electron'
import type {
  SystemState,
  MonitorParameters,
  StimulusParameters,
  AcquisitionParameters
} from '../../types/shared'

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
  const [isPreGenerating, setIsPreGenerating] = useState(false)
  const [preGenStatus, setPreGenStatus] = useState<{
    success?: boolean
    error?: string
    statistics?: any
  } | null>(null)
  const [preGenProgress, setPreGenProgress] = useState<{
    phase?: string
    direction?: string
    currentFrame?: number
    totalFrames?: number
    percentComplete?: number
    memoryBytes?: number
  } | null>(null)
  const [isLoadingLibrary, setIsLoadingLibrary] = useState(false)
  const [loadStatus, setLoadStatus] = useState<{
    success?: boolean
    error?: string
    validation_failed?: boolean
    mismatches?: any
  } | null>(null)
  const [isSavingLibrary, setIsSavingLibrary] = useState(false)
  const [saveStatus, setSaveStatus] = useState<{
    success?: boolean
    error?: string
  } | null>(null)

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
          metadata.data_size_bytes,
          metadata.shm_path
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

  // Listen for pre-generation progress updates via sync channel
  useEffect(() => {
    const handleSyncMessage = (message: any) => {
      if (message.type === 'unified_stimulus_pregeneration_progress') {
        // Update progress state
        setPreGenProgress({
          phase: message.phase,
          direction: message.direction,
          currentFrame: message.current_frame,
          totalFrames: message.total_frames,
          percentComplete: message.percent_complete,
          memoryBytes: message.memory_bytes
        })
      } else if (message.type === 'unified_stimulus_pregeneration_complete') {
        // Pre-generation finished successfully
        setIsPreGenerating(false)
        setPreGenStatus({
          success: true,
          statistics: message.statistics
        })
        componentLogger.info('Pre-generation complete via sync message', message.statistics)
      } else if (message.type === 'unified_stimulus_pregeneration_failed') {
        // Pre-generation failed
        setIsPreGenerating(false)
        setPreGenStatus({
          success: false,
          error: message.error
        })
        componentLogger.error('Pre-generation failed via sync message', message.error)
      }
    }

    let unsubscribe: (() => void) | undefined
    if (window.electronAPI?.onSyncMessage) {
      unsubscribe = window.electronAPI.onSyncMessage(handleSyncMessage)
      componentLogger.debug('Pre-generation progress listener registered')
    }

    return () => {
      unsubscribe?.()
    }
  }, [])

  // Stop loading once we have frame data
  useEffect(() => {
    if (hasFrameData) {
      setIsLoading(false)
    }
  }, [hasFrameData])

  // Load initial frame on mount AND query backend status to restore badge state
  useEffect(() => {
    if (!hasFrameData && systemState?.isConnected && sendCommand) {
      loadFrame(direction, 0, showBarMask)

      // CRITICAL FIX: Query backend status to restore completion badge
      // This ensures badge persists across viewport navigation (component unmount/remount)
      sendCommand({ type: 'unified_stimulus_get_status' })
        .then(result => {
          if (result.success && result.library_loaded) {
            componentLogger.debug('Stimulus library already loaded - restoring badge state', result.library_status)
            setPreGenStatus({
              success: true,
              statistics: {
                total_frames: Object.values(result.library_status || {}).reduce((sum: number, dir: any) => sum + (dir.frames || 0), 0),
                total_memory_bytes: Object.values(result.library_status || {}).reduce((sum: number, dir: any) => sum + (dir.memory_mb || 0) * 1024 * 1024, 0),
                directions: result.library_status
              }
            })
          } else {
            componentLogger.debug('Stimulus library not loaded - badge will show pre-generate button')
          }
        })
        .catch(err => {
          componentLogger.error('Failed to query stimulus status:', err)
        })
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

  // Auto-refresh current frame when parameters change
  useEffect(() => {
    if (!hasFrameData || totalFrames === 0 || !sendCommand) {
      return
    }

    componentLogger.debug('Stimulus/monitor parameters changed - refreshing current frame')
    loadFrame(direction, currentFrameIndex, showBarMask)
  }, [stimulusParams, monitorParams])

  // Direction change handler
  const handleDirectionChange = (newDirection: 'LR' | 'RL' | 'TB' | 'BT') => {
    setDirection(newDirection)
    setCurrentFrameIndex(0)
  }

  // Pre-generate stimulus for all directions
  const handlePreGenerate = async () => {
    if (!sendCommand) {
      componentLogger.error('Pre-generation failed: sendCommand is unavailable')
      return
    }

    setIsPreGenerating(true)
    setPreGenStatus(null)

    try {
      componentLogger.info('Starting stimulus pre-generation for all directions...')
      const result = await sendCommand({
        type: 'unified_stimulus_pregenerate'
      })

      if (result.success) {
        componentLogger.info('Stimulus pre-generation complete:', result)
        setPreGenStatus({
          success: true,
          statistics: result.statistics || result
        })
      } else {
        componentLogger.error('Stimulus pre-generation failed:', result.error)
        setPreGenStatus({
          success: false,
          error: result.error || 'Unknown error'
        })
      }
    } catch (error) {
      componentLogger.error('Failed to pre-generate stimulus:', error)
      setPreGenStatus({
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      })
    } finally {
      setIsPreGenerating(false)
    }
  }

  // Load pre-generated library from disk with parameter validation
  const handleLoadLibrary = async () => {
    if (!sendCommand) {
      componentLogger.error('Load library failed: sendCommand is unavailable')
      return
    }

    setIsLoadingLibrary(true)
    setLoadStatus(null)

    try {
      componentLogger.info('Loading stimulus library from disk...')
      const result = await sendCommand({
        type: 'unified_stimulus_load_library'
      })

      if (result.success) {
        componentLogger.info('Stimulus library loaded successfully:', result)
        setLoadStatus({
          success: true
        })

        // Update pre-gen status to show library is loaded
        setPreGenStatus({
          success: true,
          statistics: {
            total_frames: Object.values(result.library_status || {}).reduce((sum: number, dir: any) => sum + (dir.frames || 0), 0),
            total_memory_bytes: Object.values(result.library_status || {}).reduce((sum: number, dir: any) => sum + (dir.memory_mb || 0) * 1024 * 1024, 0),
            directions: result.library_status
          }
        })
      } else if (result.validation_failed) {
        // Parameter mismatch - show detailed error
        componentLogger.warn('Library load failed - parameter mismatch:', result.mismatches)
        setLoadStatus({
          success: false,
          error: 'Parameters do not match',
          validation_failed: true,
          mismatches: result.mismatches
        })
      } else {
        componentLogger.error('Stimulus library load failed:', result.error)
        setLoadStatus({
          success: false,
          error: result.error || 'Unknown error'
        })
      }
    } catch (error) {
      componentLogger.error('Failed to load stimulus library:', error)
      setLoadStatus({
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      })
    } finally {
      setIsLoadingLibrary(false)
    }
  }

  // Save current library to disk
  const handleSaveLibrary = async () => {
    if (!sendCommand) {
      componentLogger.error('Save library failed: sendCommand is unavailable')
      return
    }

    setIsSavingLibrary(true)
    setSaveStatus(null)

    try {
      componentLogger.info('Saving stimulus library to disk...')
      const result = await sendCommand({
        type: 'unified_stimulus_save_library'
      })

      if (result.success) {
        componentLogger.info('Stimulus library saved successfully:', result)
        setSaveStatus({
          success: true
        })
      } else {
        componentLogger.error('Stimulus library save failed:', result.error)
        setSaveStatus({
          success: false,
          error: result.error || 'Unknown error'
        })
      }
    } catch (error) {
      componentLogger.error('Failed to save stimulus library:', error)
      setSaveStatus({
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      })
    } finally {
      setIsSavingLibrary(false)
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

      {/* Pre-Generation Controls - Below canvas, above frame controls */}
      <div className="flex flex-col gap-2 p-3 bg-sci-secondary-800/50 border border-sci-secondary-600 rounded-lg mt-3">
        <div className="flex items-center justify-between gap-2">
          {/* Left side: Generation buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={handlePreGenerate}
              disabled={isPreGenerating || !systemState?.isConnected}
              className={`px-4 py-2 rounded font-medium transition-colors ${
                isPreGenerating
                  ? 'bg-sci-secondary-700 text-sci-secondary-400 cursor-wait'
                  : systemState?.isConnected
                  ? 'bg-sci-primary-600 hover:bg-sci-primary-700 text-white'
                  : 'bg-sci-secondary-700 text-sci-secondary-500 cursor-not-allowed'
              }`}
            >
              {isPreGenerating ? 'Pre-Generating...' : 'Pre-Generate All Directions'}
            </button>

            <button
              onClick={handleLoadLibrary}
              disabled={isLoadingLibrary || !systemState?.isConnected}
              className={`px-4 py-2 rounded font-medium transition-colors ${
                isLoadingLibrary
                  ? 'bg-sci-secondary-700 text-sci-secondary-400 cursor-wait'
                  : systemState?.isConnected
                  ? 'bg-sci-accent-600 hover:bg-sci-accent-700 text-white'
                  : 'bg-sci-secondary-700 text-sci-secondary-500 cursor-not-allowed'
              }`}
            >
              {isLoadingLibrary ? 'Loading...' : 'Load from Disk'}
            </button>
          </div>

          {/* Right side: Status Display */}
          <div className="flex items-center gap-2">
            {/* Load status */}
            {loadStatus && !isLoadingLibrary && (
              <div className={`px-3 py-2 rounded text-sm ${
                loadStatus.success
                  ? 'bg-green-900/30 border border-green-700 text-green-300'
                  : 'bg-red-900/30 border border-red-700 text-red-300'
              }`}>
                {loadStatus.success ? (
                  <div className="flex items-center gap-2">
                    <span className="text-green-400">✓</span>
                    <span>Loaded from disk</span>
                  </div>
                ) : loadStatus.validation_failed ? (
                  <div className="flex items-center gap-2">
                    <span className="text-red-400">✗</span>
                    <span>Parameter mismatch - regenerate required</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <span className="text-red-400">✗</span>
                    <span>{loadStatus.error || 'Load failed'}</span>
                  </div>
                )}
              </div>
            )}

            {/* Pre-gen status */}
            {preGenStatus && !isPreGenerating && (
              <div className={`px-3 py-2 rounded text-sm ${
                preGenStatus.success
                  ? 'bg-green-900/30 border border-green-700 text-green-300'
                  : 'bg-red-900/30 border border-red-700 text-red-300'
              }`}>
                {preGenStatus.success ? (
                  <div className="flex items-center gap-2">
                    <span className="text-green-400">✓</span>
                    <div>
                      <div className="font-medium">Library Ready</div>
                      {preGenStatus.statistics && (
                        <div className="text-xs opacity-80">
                          {preGenStatus.statistics.total_frames || 0} frames,
                          {' '}{((preGenStatus.statistics.total_memory_bytes || 0) / 1024 / 1024).toFixed(0)} MB
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <span className="text-red-400">✗</span>
                    <div>
                      <div className="font-medium">Failed</div>
                      {preGenStatus.error && (
                        <div className="text-xs opacity-80">{preGenStatus.error}</div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Parameter mismatch details */}
        {loadStatus?.validation_failed && loadStatus.mismatches && (
          <div className="p-3 bg-red-900/20 border border-red-700 rounded text-sm text-red-300">
            <div className="font-medium mb-2">Parameter Mismatches Detected:</div>
            <div className="text-xs space-y-1 font-mono">
              {Object.entries(loadStatus.mismatches).map(([key, values]: [string, any]) => (
                <div key={key} className="flex items-start gap-2">
                  <span className="text-red-400">•</span>
                  <div>
                    <span className="text-sci-secondary-300">{key}:</span>
                    <div className="ml-4">
                      <div>Saved: <span className="text-yellow-300">{JSON.stringify(values.saved)}</span></div>
                      <div>Current: <span className="text-yellow-300">{JSON.stringify(values.current)}</span></div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-2 text-xs opacity-80">
              The saved library was generated with different parameters. You must regenerate the library with current parameters.
            </div>
          </div>
        )}

        {/* Progress indicator while pre-generating */}
        {isPreGenerating && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2 text-sci-secondary-300">
              <div className="animate-spin h-4 w-4 border-2 border-sci-primary-500 border-t-transparent rounded-full"></div>
              <span className="text-sm">
                {preGenProgress?.phase === 'generating'
                  ? `Generating ${preGenProgress.direction} frames...`
                  : preGenProgress?.phase === 'compressing'
                  ? `Compressing ${preGenProgress.direction}: ${preGenProgress.currentFrame}/${preGenProgress.totalFrames}`
                  : 'Initializing...'}
              </span>
            </div>
            <div className="w-full bg-sci-secondary-700 rounded-full h-2 overflow-hidden">
              <div
                className="h-full bg-sci-primary-500 rounded-full transition-all duration-300"
                style={{ width: `${preGenProgress?.percentComplete || 0}%` }}
              ></div>
            </div>
            {preGenProgress?.percentComplete !== undefined && (
              <div className="text-xs text-sci-secondary-400 text-right">
                {preGenProgress.percentComplete.toFixed(1)}% complete
                {preGenProgress.memoryBytes && ` (${(preGenProgress.memoryBytes / 1024 / 1024).toFixed(1)} MB)`}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Frame Explorer Controls - Consolidated Single Strip */}
      <div className="flex items-center gap-6 p-3 bg-sci-secondary-800 border border-sci-secondary-600 rounded-lg mt-4">
        {/* Left: Direction selection */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-sci-secondary-400 uppercase tracking-wide">Direction</span>
          <div className="flex gap-1">
            {(['LR', 'RL', 'TB', 'BT'] as const).map((dir) => (
              <button
                key={dir}
                onClick={() => handleDirectionChange(dir)}
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
        </div>

        {/* Center: Frame slider (flex-1 to take remaining space) */}
        {totalFrames > 0 && (
          <div className="flex-1 flex items-center gap-3">
            <span className="text-xs text-sci-secondary-400 uppercase tracking-wide">Frame</span>
            <input
              type="range"
              min={0}
              max={totalFrames - 1}
              value={currentFrameIndex}
              onChange={(e) => setCurrentFrameIndex(parseInt(e.target.value))}
              className="flex-1"
            />
            <span className="text-xs text-sci-secondary-200 font-mono w-32">
              {currentFrameIndex}/{totalFrames - 1}
              {datasetInfo && (
                <span className="text-sci-secondary-500 ml-2">
                  ({((datasetInfo.start_angle || 0) + (currentFrameIndex / (totalFrames - 1)) * ((datasetInfo.end_angle || 0) - (datasetInfo.start_angle || 0))).toFixed(1)}°)
                </span>
              )}
            </span>
          </div>
        )}

        {/* Right: Bar Mask toggle */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-sci-secondary-400 uppercase tracking-wide">Bar Mask</span>
          <button
            onClick={() => setShowBarMask(!showBarMask)}
            className={`px-3 py-1 text-xs rounded transition-colors font-medium ${
              showBarMask
                ? 'bg-sci-accent-600 text-white'
                : 'bg-sci-secondary-700 text-sci-secondary-300 hover:bg-sci-secondary-600'
            }`}
          >
            {showBarMask ? 'ON' : 'OFF'}
          </button>
        </div>
      </div>

    </div>
  )
}

export default StimulusGenerationViewport