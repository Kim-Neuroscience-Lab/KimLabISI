import React, { useRef, useEffect, useState, useCallback } from 'react'
import {
  SkipBack,
  StepBack,
  Play,
  Pause,
  Square,
  StepForward,
  SkipForward,
  Circle,
  ScanEye,
  type LucideIcon
} from 'lucide-react'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js'
import { Bar, Line } from 'react-chartjs-2'
import type { ISIMessage, ControlMessage, SyncMessage } from '../../types/ipc-messages'
import type { SystemState } from '../../types/shared'
import type { CameraParameters, StimulusParameters, MonitorParameters, AcquisitionParameters } from '../../hooks/useParameterManager'

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
)

const acquisitionModes = ["preview", "record", "playback"] as const
type AcquisitionMode = typeof acquisitionModes[number]

const modeControls: Record<AcquisitionMode, { icon: LucideIcon; key: string; label: string }[]> = {
  preview: [
    { key: "skipBack", icon: SkipBack, label: "Skip Back" },
    { key: "stepBack", icon: StepBack, label: "Step Back" },
    { key: "playPause", icon: Play, label: "Play/Pause" },
    { key: "stop", icon: Square, label: "Stop" },
    { key: "stepForward", icon: StepForward, label: "Step Forward" },
    { key: "skipForward", icon: SkipForward, label: "Skip Forward" },
  ],
  record: [
    { key: "record", icon: Circle, label: "Record" },
    { key: "stop", icon: Square, label: "Stop" },
  ],
  playback: [
    { key: "skipBack", icon: SkipBack, label: "Skip Back" },
    { key: "stepBack", icon: StepBack, label: "Step Back" },
    { key: "playPause", icon: Play, label: "Play/Pause" },
    { key: "stop", icon: Square, label: "Stop" },
    { key: "stepForward", icon: StepForward, label: "Step Forward" },
    { key: "skipForward", icon: SkipForward, label: "Skip Forward" },
  ],
}

interface AcquisitionViewportProps {
  className?: string
  cameraParams?: CameraParameters
  stimulusParams?: StimulusParameters
  monitorParams?: MonitorParameters
  acquisitionParams?: AcquisitionParameters
  sendCommand?: (command: ISIMessage) => Promise<{ success: boolean; error?: string }>
  systemState?: SystemState
  lastMessage?: ControlMessage | SyncMessage | null
  sharedDirection?: 'LR' | 'RL' | 'TB' | 'BT'
  sharedFrameIndex?: number
  sharedShowBarMask?: boolean
}

const AcquisitionViewport: React.FC<AcquisitionViewportProps> = ({
  className = '',
  cameraParams,
  stimulusParams,
  monitorParams,
  acquisitionParams,
  sendCommand,
  systemState,
  lastMessage,
  sharedDirection = 'LR',
  sharedFrameIndex = 0,
  sharedShowBarMask = false
}) => {
  // Camera feed state
  const cameraCanvasRef = useRef<HTMLCanvasElement>(null)
  const [isPreviewing, setIsPreviewing] = useState(false)
  const [isAcquiring, setIsAcquiring] = useState(false)
  const [acquisitionMode, setAcquisitionMode] = useState<AcquisitionMode>('preview')
  const [isCameraVisible, setIsCameraVisible] = useState(true)
  const [cameraError, setCameraError] = useState<string | null>(null)

  // Mini stimulus preview
  const stimulusCanvasRef = useRef<HTMLCanvasElement>(null)

  // Statistics
  const [cameraStats, setCameraStats] = useState<any>(null)
  const [frameCount, setFrameCount] = useState(0)
  const [currentStimulus, setCurrentStimulus] = useState<any>(null)

  // Acquisition status
  const [acquisitionStatus, setAcquisitionStatus] = useState<any>(null)

  // Chart.js data state
  const [histogramChartData, setHistogramChartData] = useState<any>({
    labels: [],
    datasets: [{
      label: 'Luminance Distribution',
      data: [],
      backgroundColor: 'rgba(255, 255, 255, 0.8)',
      borderColor: 'rgba(255, 255, 255, 1)',
      borderWidth: 1,
    }]
  })
  const [histogramStats, setHistogramStats] = useState<any>(null)
  const [acquisitionStartTime, setAcquisitionStartTime] = useState<number | null>(null)

  const [correlationChartData, setCorrelationChartData] = useState<any>({
    labels: [],
    datasets: [{
      label: 'Timing Difference (ms)',
      data: [],
      borderColor: 'rgba(59, 130, 246, 1)',
      backgroundColor: 'rgba(59, 130, 246, 0.1)',
      borderWidth: 2,
      pointRadius: 1,
      pointHoverRadius: 4,
      tension: 0.1,
    }]
  })
  const [correlationStats, setCorrelationStats] = useState<any>(null)

  // Start camera preview (just camera feed, no analysis)
  const startPreview = async () => {
    if (!cameraParams?.selected_camera) {
      setCameraError('No camera selected')
      return
    }

    try {
      setCameraError(null)
      const result = await sendCommand?.({
        type: 'start_camera_acquisition',
        camera_name: cameraParams.selected_camera
      })

      if (result?.success) {
        setIsPreviewing(true)
      } else {
        setCameraError(result?.error || 'Failed to start preview')
      }
    } catch (error) {
      setCameraError(`Error: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  // Start full acquisition (camera + histogram + correlation)
  const startAcquisition = async () => {
    console.log('🎬 startAcquisition() called')
    console.log('   sendCommand available?', !!sendCommand)
    console.log('   isPreviewing?', isPreviewing)

    // Record start time for elapsed time calculation
    setAcquisitionStartTime(Date.now())
    setFrameCount(0)

    // If already previewing, switch to acquisition mode
    if (isPreviewing) {
      // Start orchestrated acquisition sequence
      if (!sendCommand) {
        console.error('❌ sendCommand is undefined!')
        return
      }

      // Stop the preview stimulus so baseline starts clean
      console.log('📤 Stopping preview stimulus before acquisition...')
      try {
        await sendCommand({ type: 'stop_stimulus' })
      } catch (error) {
        console.error('❌ Error stopping preview stimulus:', error)
      }

      // Stop any existing acquisition first (safety check)
      console.log('📤 Stopping any existing acquisition...')
      try {
        await sendCommand({ type: 'stop_acquisition' })
      } catch (error) {
        // Ignore error if no acquisition was running
        console.log('   No existing acquisition to stop')
      }

      // Switch modes: preview OFF, acquisition ON
      setIsPreviewing(false)
      setIsAcquiring(true)

      console.log('📤 Sending start_acquisition command...')
      try {
        const result = await sendCommand({ type: 'start_acquisition' })
        console.log('📥 Received response:', result)
        if (result?.success) {
          console.log('✅ Acquisition sequence started')
          console.log(`   Directions: ${result.total_directions}, Cycles: ${result.total_cycles}`)
        } else {
          console.error('❌ Failed to start acquisition:', result?.error)
        }
      } catch (error) {
        console.error('❌ Error starting acquisition:', error)
      }

      return
    }

    // Otherwise start from scratch
    console.log('📤 Starting preview first...')
    await startPreview()
    setIsAcquiring(true)

    // Start orchestrated acquisition sequence
    if (!sendCommand) {
      console.error('❌ sendCommand is undefined!')
      return
    }

    console.log('📤 Sending start_acquisition command...')
    try {
      const result = await sendCommand({ type: 'start_acquisition' })
      console.log('📥 Received response:', result)
      if (result?.success) {
        console.log('✅ Acquisition sequence started')
        console.log(`   Directions: ${result.total_directions}, Cycles: ${result.total_cycles}`)
      } else {
        console.error('❌ Failed to start acquisition:', result?.error)
      }
    } catch (error) {
      console.error('❌ Error starting acquisition:', error)
    }
  }

  // Stop acquisition and return to preview mode
  const stopAcquisition = async () => {
    setAcquisitionStartTime(null)
    setAcquisitionStatus(null)

    // Stop acquisition sequence (ignore error if already stopped)
    try {
      const result = await sendCommand?.({ type: 'stop_acquisition' })
      if (result?.success) {
        console.log('✅ Acquisition stopped')
      } else if (result?.error && !result.error.includes('not running')) {
        console.error('❌ Failed to stop acquisition:', result?.error)
      }
    } catch (error: any) {
      if (!error.message?.includes('not running')) {
        console.error('❌ Error stopping acquisition:', error)
      }
    }

    // Switch modes: acquisition OFF, preview ON
    setIsAcquiring(false)
    setIsPreviewing(true)

    // Restart preview stimulus
    console.log('📤 Restarting preview stimulus...')
    try {
      await sendCommand?.({ type: 'start_stimulus' })
    } catch (error) {
      console.error('❌ Error restarting preview stimulus:', error)
    }
  }

  // Stop preview (and acquisition if running)
  const stopPreview = async () => {
    try {
      // Stop acquisition if running
      if (isAcquiring) {
        await sendCommand?.({ type: 'stop_acquisition' })
      }

      await sendCommand?.({ type: 'stop_camera_acquisition' })
      setIsPreviewing(false)
      setIsAcquiring(false)
      setAcquisitionStartTime(null)
      setAcquisitionStatus(null)
    } catch (error) {
      console.error('Error stopping preview:', error)
    }
  }

  // Listen for camera frames from shared memory (works in both preview and acquisition mode)
  useEffect(() => {
    if (!isPreviewing && !isAcquiring) return

    const handleSharedMemoryFrame = async (metadata: any) => {
      try {
        // Only process camera frames (direction === 'CAMERA')
        if (metadata.direction !== 'CAMERA') return

        // Read actual frame data from shared memory using offset and size
        const frameDataBuffer = await window.electronAPI.readSharedMemoryFrame(
          metadata.offset_bytes,
          metadata.data_size_bytes
        )

        // Create ImageData from RGBA buffer
        const canvas = cameraCanvasRef.current
        if (!canvas) return

        const width = metadata.width_px
        const height = metadata.height_px

        // Set canvas dimensions
        if (canvas.width !== width || canvas.height !== height) {
          canvas.width = width
          canvas.height = height
        }

        const ctx = canvas.getContext('2d')
        if (!ctx) return

        // Create ImageData directly from RGBA bytes
        const imageData = new ImageData(
          new Uint8ClampedArray(frameDataBuffer),
          width,
          height
        )

        // Render to canvas
        ctx.putImageData(imageData, 0, 0)

        // Update frame count
        setFrameCount(prev => prev + 1)

        setCameraStats({
          width,
          height,
          timestamp_us: metadata.timestamp_us,
          timestamp_ms: metadata.timestamp_us / 1000,
          frame_id: metadata.frame_id || frameCount
        })
      } catch (error) {
        console.error('Failed to read camera frame from shared memory:', error)
      }
    }

    let unsubscribe: (() => void) | undefined
    if (window.electronAPI?.onSharedMemoryFrame) {
      unsubscribe = window.electronAPI.onSharedMemoryFrame(handleSharedMemoryFrame)
    }

    return () => {
      unsubscribe?.()
    }
  }, [isPreviewing, isAcquiring])

  // Listen for stimulus frames from shared memory for mini preview
  // During acquisition: show live stimulus
  // During preview: show static frame from slider
  useEffect(() => {
    const handleStimulusFrame = async (metadata: any) => {
      try {
        // Only process stimulus frames (direction !== 'CAMERA')
        if (metadata.direction === 'CAMERA') return

        // During acquisition: accept all stimulus frames (show live playback)
        // During preview: only accept frames matching slider position
        if (!isAcquiring && metadata.frame_index !== sharedFrameIndex) {
          return
        }

        // Read actual frame data from shared memory
        const frameDataBuffer = await window.electronAPI.readSharedMemoryFrame(
          metadata.offset_bytes,
          metadata.data_size_bytes
        )

        // Render to stimulus canvas
        const canvas = stimulusCanvasRef.current
        if (!canvas) return

        const width = metadata.width_px
        const height = metadata.height_px

        // Set canvas dimensions
        if (canvas.width !== width || canvas.height !== height) {
          canvas.width = width
          canvas.height = height
        }

        const ctx = canvas.getContext('2d')
        if (!ctx) return

        // Create ImageData directly from RGBA bytes
        const imageData = new ImageData(
          new Uint8ClampedArray(frameDataBuffer),
          width,
          height
        )

        // Render to canvas
        ctx.putImageData(imageData, 0, 0)

        // Update current stimulus info
        setCurrentStimulus({
          direction: metadata.direction,
          angle: metadata.angle_degrees,
          frame_index: metadata.frame_index
        })
      } catch (error) {
        console.error('Failed to read stimulus frame from shared memory:', error)
      }
    }

    let unsubscribe: (() => void) | undefined
    if (window.electronAPI?.onSharedMemoryFrame) {
      unsubscribe = window.electronAPI.onSharedMemoryFrame(handleStimulusFrame)
    }

    return () => {
      unsubscribe?.()
    }
  }, [sharedFrameIndex, isAcquiring])

  // Update histogram chart data
  const updateHistogramChart = useCallback((data: any) => {
    if (!data?.histogram || !data?.bin_edges) return

    const { histogram, bin_edges, statistics } = data

    // Create labels from bin edges (show every 32nd bin for readability)
    const labels = bin_edges.slice(0, -1).map((_: number, i: number) =>
      i % 32 === 0 ? Math.round(bin_edges[i]).toString() : ''
    )

    setHistogramChartData({
      labels,
      datasets: [{
        label: 'Pixel Count',
        data: histogram,
        backgroundColor: 'rgba(255, 255, 255, 0.8)',
        borderColor: 'rgba(255, 255, 255, 1)',
        borderWidth: 1,
      }]
    })

    setHistogramStats(statistics)
  }, [])

  // Update correlation chart data - scrolling line chart of last 5 seconds
  const updateCorrelationChart = useCallback((data: any) => {
    console.log('📈 Correlation data received:', data)

    // Check if we have correlation data
    if (!data?.correlations || data.correlations.length === 0) {
      console.warn('📈 No correlation data yet')
      return
    }

    const { correlations, statistics } = data
    const currentTime = Date.now() * 1000 // Convert to microseconds
    const fiveSecondsAgo = currentTime - (5 * 1_000_000) // 5 seconds in microseconds

    // Filter to only show last 5 seconds and valid correlations
    const recentCorrelations = correlations
      .filter((c: any) =>
        c.camera_timestamp >= fiveSecondsAgo &&
        c.time_difference_us !== null &&
        c.time_difference_us !== undefined
      )

    if (recentCorrelations.length === 0) {
      console.warn('📈 No recent correlations in last 5 seconds')
      return
    }

    // Get the earliest timestamp for relative time calculation
    const earliestTimestamp = Math.min(...recentCorrelations.map((c: any) => c.camera_timestamp))

    // Convert to relative time (seconds from start) and time difference (milliseconds)
    const timePoints = recentCorrelations.map((c: any) =>
      (c.camera_timestamp - earliestTimestamp) / 1_000_000 // Convert to seconds
    )
    const timeDiffs = recentCorrelations.map((c: any) =>
      c.time_difference_us / 1000 // Convert to milliseconds
    )

    console.log('📈 Plotting', recentCorrelations.length, 'correlations from last 5 seconds')

    setCorrelationChartData({
      labels: timePoints.map((t: number) => t.toFixed(2)),
      datasets: [{
        label: 'Timing Difference (ms)',
        data: timeDiffs,
        borderColor: 'rgba(59, 130, 246, 1)',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        borderWidth: 2,
        pointRadius: 1,
        pointHoverRadius: 4,
        tension: 0.1, // Slight smoothing
      }]
    })

    setCorrelationStats(statistics)
  }, [])

  // Format elapsed time as HH:MM:SS:FF (frames at 30fps)
  const formatElapsedTime = useCallback((startTime: number | null, currentFrameCount: number): string => {
    if (!startTime || !isAcquiring) {
      return '00:00:00:00'
    }

    const elapsedMs = Date.now() - startTime
    const hours = Math.floor(elapsedMs / 3600000)
    const minutes = Math.floor((elapsedMs % 3600000) / 60000)
    const seconds = Math.floor((elapsedMs % 60000) / 1000)
    const frames = currentFrameCount % 30 // Assuming 30fps

    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}:${frames.toString().padStart(2, '0')}`
  }, [isAcquiring])

  // Poll for histogram (any time camera is active)
  useEffect(() => {
    if (!isPreviewing && !isAcquiring) return

    const pollInterval = setInterval(async () => {
      try {
        const result = await sendCommand?.({ type: 'get_camera_histogram' })

        if (result?.success && result.data) {
          updateHistogramChart(result.data)
        } else if (result?.error) {
          console.warn('Histogram not available:', result.error)
        }
      } catch (error) {
        console.error('Error polling histogram:', error)
      }
    }, 100) // 10 Hz

    return () => clearInterval(pollInterval)
  }, [isPreviewing, isAcquiring, sendCommand, updateHistogramChart])

  // Poll for correlation data (only in acquisition mode)
  useEffect(() => {
    if (!isAcquiring) return

    console.log('📈 Starting correlation polling...')
    const pollInterval = setInterval(async () => {
      try {
        const result = await sendCommand?.({ type: 'get_correlation_data' })
        console.log('📈 Correlation poll result:', result)

        if (result?.success && result.data) {
          updateCorrelationChart(result.data)
        } else if (result?.error) {
          console.warn('📈 Correlation not available:', result.error)
        } else {
          console.warn('📈 Correlation result invalid:', result)
        }
      } catch (error) {
        console.error('📈 Error polling correlation:', error)
      }
    }, 100) // 10 Hz

    return () => {
      console.log('📈 Stopping correlation polling')
      clearInterval(pollInterval)
    }
  }, [isAcquiring, sendCommand, updateCorrelationChart])

  // Listen for acquisition progress messages from backend
  useEffect(() => {
    if (!isAcquiring) return

    const handleSyncMessage = async (message: any) => {
      if (message.type === 'acquisition_progress') {
        console.log('🔄 Acquisition progress update:', message)
        setAcquisitionStatus({
          is_running: message.is_running,
          phase: message.phase,
          current_direction: message.current_direction,
          current_direction_index: message.current_direction_index,
          total_directions: message.total_directions,
          current_cycle: message.current_cycle,
          total_cycles: message.total_cycles,
          elapsed_time: message.elapsed_time,
          phase_start_time: message.phase_start_time
        })

        // Check if acquisition completed
        if (message.phase === 'complete') {
          console.log('✅ Acquisition sequence completed!')
          // Backend has already stopped acquisition, just restart preview
          setIsAcquiring(false)
          setIsPreviewing(true)
          setAcquisitionStatus(null)

          // Restart preview stimulus (camera is still running)
          console.log('📤 Restarting preview stimulus after acquisition...')
          try {
            await sendCommand?.({ type: 'start_stimulus' })
          } catch (error) {
            console.error('❌ Error restarting preview stimulus:', error)
          }
        }
      }
    }

    let unsubscribe: (() => void) | undefined
    if (window.electronAPI?.onSyncMessage) {
      unsubscribe = window.electronAPI.onSyncMessage(handleSyncMessage)
    }

    return () => {
      unsubscribe?.()
    }
  }, [isAcquiring])

  // Poll for acquisition status (only in acquisition mode) - fallback if push messages fail
  useEffect(() => {
    if (!isAcquiring) return

    console.log('🔄 Starting acquisition status polling...')
    const pollInterval = setInterval(async () => {
      try {
        const result = await sendCommand?.({ type: 'get_acquisition_status' })

        if (result?.success && result.status) {
          setAcquisitionStatus(result.status)

          // Skip - completion is handled by sync message listener
        }
      } catch (error) {
        console.error('🔄 Error polling acquisition status:', error)
      }
    }, 500) // 2 Hz (slower since we have push messages)

    return () => {
      console.log('🔄 Stopping acquisition status polling')
      clearInterval(pollInterval)
    }
  }, [isAcquiring, sendCommand])

  // Auto-start preview when camera is selected
  useEffect(() => {
    if (cameraParams?.selected_camera && systemState?.isConnected && !isPreviewing && !isAcquiring) {
      startPreview()
    }
  }, [cameraParams?.selected_camera, systemState?.isConnected, isPreviewing, isAcquiring])

  // Update mini stimulus preview when parameters or shared state change
  // This triggers backend to generate and write frame to shared memory
  // The shared memory listener above will then render it
  useEffect(() => {
    const fetchStimulusFrame = async () => {
      if (!stimulusParams || !monitorParams) return

      try {
        console.log(`📐 Requesting stimulus frame: direction=${sharedDirection}, frame=${sharedFrameIndex}, mask=${sharedShowBarMask}`)
        await sendCommand?.({
          type: 'get_stimulus_frame',
          direction: sharedDirection,
          frame_index: sharedFrameIndex,
          show_bar_mask: sharedShowBarMask
        })
      } catch (error) {
        console.error('Error fetching stimulus frame:', error)
      }
    }

    fetchStimulusFrame()
  }, [stimulusParams, monitorParams, sendCommand, sharedDirection, sharedFrameIndex, sharedShowBarMask])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (isPreviewing || isAcquiring) {
        stopPreview()
      }
    }
  }, [])

  const handleControlAction = useCallback(
    (action: string) => {
      switch (action) {
        case 'playPause': {
          if (isAcquiring) {
            stopAcquisition()
          } else {
            startAcquisition()
          }
          break
        }
        case 'stop': {
          stopAcquisition()
          break
        }
        case 'record': {
          if (!isAcquiring) {
            startAcquisition()
          }
          break
        }
        case 'skipBack':
        case 'stepBack':
        case 'stepForward':
        case 'skipForward': {
          console.debug(`[AcquisitionViewport] Control '${action}' not yet implemented`)
          break
        }
        default: {
          console.warn(`[AcquisitionViewport] Unknown control '${action}'`)
        }
      }
    },
    [isAcquiring, startAcquisition, stopAcquisition]
  )

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Two-column layout: Camera+Info | Stimulus+Plots */}
      <div className="flex-1 flex gap-2 p-2 min-h-0 items-start">
        {/* Left Column - Camera + Info */}
        <div className="flex flex-col gap-2 h-full">
          {/* Camera Feed - Square Aspect Ratio */}
          {isCameraVisible ? (
            <div className="flex-1 aspect-square bg-black border border-sci-secondary-600 rounded-lg overflow-hidden relative min-h-0">
              <canvas
                ref={cameraCanvasRef}
                style={{ width: '100%', height: '100%', display: 'block', objectFit: 'contain' }}
              />

              {/* Error State */}
              {cameraError && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/80">
                  <div className="text-center text-red-400">
                    <div className="text-4xl mb-2">⚠️</div>
                    <div className="text-lg mb-2">Camera Error</div>
                    <div className="text-sm">{cameraError}</div>
                  </div>
                </div>
              )}

              {/* No Camera State */}
              {!cameraParams?.selected_camera && !cameraError && (
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center text-sci-secondary-400">
                    <div className="text-6xl mb-4">📷</div>
                    <div className="text-lg">No Camera Selected</div>
                    <div className="text-sm mt-2">Select a camera in the control panel</div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex-1 aspect-square bg-sci-secondary-800 border border-dashed border-sci-secondary-600 rounded-lg flex items-center justify-center text-sci-secondary-400">
              <div className="flex flex-col items-center gap-2">
                <ScanEye className="w-6 h-6" />
                <span className="text-sm">Camera view hidden</span>
              </div>
            </div>
          )}

          {/* Camera Information */}
          <div className="bg-sci-secondary-800 border border-sci-secondary-600 rounded-lg p-3">
            <div className="text-sm font-medium text-sci-secondary-200 mb-2">
              {isAcquiring ? 'Acquisition Status' : 'Camera Status'}
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              <div>
                <span className="text-sci-secondary-400">Camera:</span>
                <span className="ml-1 text-sci-secondary-200">
                  {cameraParams?.selected_camera || 'None'}
                </span>
              </div>
              <div>
                <span className="text-sci-secondary-400">Status:</span>
                <span className={`ml-1 font-medium ${
                  isAcquiring ? 'text-sci-success-400' : isPreviewing ? 'text-sci-accent-400' : 'text-sci-secondary-500'
                }`}>
                  {isAcquiring ? 'ACQUIRING' : isPreviewing ? 'PREVIEW' : 'STOPPED'}
                </span>
              </div>
              {(isPreviewing || isAcquiring) && (
                <>
                  <div>
                    <span className="text-sci-secondary-400">Frame:</span>
                    <span className="ml-1 text-sci-secondary-200 font-mono">
                      {isAcquiring ? frameCount : 0}
                    </span>
                  </div>
                  <div>
                    <span className="text-sci-secondary-400">Time:</span>
                    <span className="ml-1 text-sci-secondary-200 font-mono">
                      {formatElapsedTime(acquisitionStartTime, frameCount)}
                    </span>
                  </div>
                  {isAcquiring && acquisitionStatus ? (
                    <>
                      <div>
                        <span className="text-sci-secondary-400">Phase:</span>
                        <span className="ml-1 text-sci-secondary-200 capitalize">
                          {acquisitionStatus.phase.replace(/_/g, ' ')}
                        </span>
                      </div>
                      <div>
                        <span className="text-sci-secondary-400">Direction:</span>
                        <span className="ml-1 text-sci-secondary-200">
                          {acquisitionStatus.current_direction || 'N/A'}
                        </span>
                      </div>
                      <div>
                        <span className="text-sci-secondary-400">Cycle:</span>
                        <span className="ml-1 text-sci-secondary-200 font-mono">
                          {acquisitionStatus.current_cycle}/{acquisitionStatus.total_cycles}
                        </span>
                      </div>
                      <div>
                        <span className="text-sci-secondary-400">Progress:</span>
                        <span className="ml-1 text-sci-secondary-200 font-mono">
                          {acquisitionStatus.current_direction_index + 1}/{acquisitionStatus.total_directions}
                        </span>
                      </div>
                    </>
                  ) : (
                    <>
                      <div>
                        <span className="text-sci-secondary-400">Direction:</span>
                        <span className="ml-1 text-sci-secondary-200">
                          {currentStimulus?.direction || sharedDirection}
                        </span>
                      </div>
                      <div>
                        <span className="text-sci-secondary-400">Angle:</span>
                        <span className="ml-1 text-sci-secondary-200 font-mono">
                          {currentStimulus?.angle?.toFixed(1) || '87.4'}°
                        </span>
                      </div>
                    </>
                  )}
                </>
              )}
              {cameraStats && (
                <div className={(isPreviewing || isAcquiring) ? '' : 'col-span-2'}>
                  <span className="text-sci-secondary-400">Resolution:</span>
                  <span className="ml-1 text-sci-secondary-200 font-mono">
                    {cameraStats.width}×{cameraStats.height}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column - Stimulus + Plots */}
        <div className="flex flex-col gap-2 h-full">
          {/* Stimulus Preview - Monitor Aspect Ratio */}
          <div className="flex-1 bg-black border border-sci-secondary-600 rounded-lg overflow-hidden min-h-0" style={{ aspectRatio: `${monitorParams?.monitor_width_px || 1728} / ${monitorParams?.monitor_height_px || 1117}` }}>
            <canvas
              ref={stimulusCanvasRef}
              style={{ width: '100%', height: '100%', display: 'block', objectFit: 'contain' }}
            />
          </div>

          {/* Plots Row */}
          <div className="grid grid-cols-2 gap-2">
            {/* Luminance Histogram */}
            <div className="bg-sci-secondary-800 border border-sci-secondary-600 rounded-lg p-2 flex flex-col h-48">
              <div className="text-xs text-sci-secondary-400 mb-1 flex-none">
                Luminance
                {histogramStats && (
                  <span className="ml-2 text-sci-secondary-500">
                    μ={histogramStats.mean.toFixed(1)} σ={histogramStats.std.toFixed(1)}
                  </span>
                )}
              </div>
              <div className="flex-1 min-h-0">
                <Bar
                  data={histogramChartData}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                      legend: { display: false },
                      tooltip: { enabled: true },
                    },
                    scales: {
                      x: {
                        display: true,
                        ticks: { color: '#9ca3af', font: { size: 8 } },
                        grid: { display: false }
                      },
                      y: {
                        display: true,
                        ticks: { color: '#9ca3af', font: { size: 8 } },
                        grid: { color: 'rgba(156, 163, 175, 0.1)' }
                      }
                    },
                    animation: false,
                  }}
                />
              </div>
            </div>

            {/* Timing Correlation Plot - Scrolling Line Chart (Last 5s) */}
            <div className="bg-sci-secondary-800 border border-sci-secondary-600 rounded-lg p-2 flex flex-col h-48">
              <div className="text-xs text-sci-secondary-400 mb-1 flex-none">
                Timing Correlation (Last 5s)
                {correlationStats && (
                  <span className="ml-2 text-sci-secondary-500">
                    μ={(correlationStats.mean_diff_ms || 0).toFixed(2)}ms σ={(correlationStats.std_diff_ms || 0).toFixed(2)}ms
                  </span>
                )}
              </div>
              <div className="flex-1 min-h-0">
                <Line
                  data={correlationChartData}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                      legend: { display: false },
                      tooltip: { enabled: true },
                    },
                    scales: {
                      x: {
                        display: true,
                        ticks: { color: '#9ca3af', font: { size: 8 }, maxTicksLimit: 6 },
                        grid: { color: 'rgba(156, 163, 175, 0.1)' },
                        title: { display: true, text: 'Time (s)', color: '#9ca3af', font: { size: 8 } }
                      },
                      y: {
                        display: true,
                        ticks: { color: '#9ca3af', font: { size: 8 } },
                        grid: { color: 'rgba(156, 163, 175, 0.1)' },
                        title: { display: true, text: 'Δt (ms)', color: '#9ca3af', font: { size: 8 } }
                      }
                    },
                    animation: false,
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Control Buttons */}
      <div className="flex flex-col gap-2 p-3 border-t border-sci-secondary-600 bg-sci-secondary-800/60">
        <div className="flex items-center gap-3 justify-center">
          <div className="flex items-center gap-2">
            <label className="text-xs uppercase tracking-wide text-sci-secondary-400">Mode</label>
            <select
              value={acquisitionMode}
              onChange={(event) => setAcquisitionMode(event.target.value as AcquisitionMode)}
              className="bg-sci-secondary-700 border border-sci-secondary-500 rounded px-2 py-1 text-sm text-sci-secondary-100 focus:outline-none focus:ring-2 focus:ring-sci-primary-600"
            >
              {acquisitionModes.map((mode) => (
                <option key={mode} value={mode} className="capitalize">
                  {mode}
                </option>
              ))}
            </select>
          </div>

          <button
            type="button"
            onClick={() => setIsCameraVisible((value) => !value)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded text-sm font-medium border transition-colors ${
              isCameraVisible
                ? 'bg-sci-primary-600 border-sci-primary-500 text-white hover:bg-sci-primary-500'
                : 'bg-sci-secondary-700 border-sci-secondary-500 text-sci-secondary-200 hover:bg-sci-secondary-600'
            }`}
          >
            <ScanEye className="w-4 h-4" />
            Camera {isCameraVisible ? 'On' : 'Off'}
          </button>
        </div>

        <div className="flex items-center justify-center gap-2">
          {modeControls[acquisitionMode].map(({ key, icon }) => {
            const isPlayPause = key === 'playPause'
            const isRecord = key === 'record'
            const isStop = key === 'stop'

            const isDisabled =
              !isPreviewing && !isAcquiring && key !== 'playPause' && key !== 'record'

            const baseButtonClasses =
              'w-9 h-9 flex items-center justify-center rounded-full border transition-colors focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-offset-sci-secondary-900'

            let buttonClasses =
              'bg-sci-secondary-700 border-sci-secondary-500 text-sci-secondary-200 hover:bg-sci-secondary-600'

            let IconComponent: LucideIcon = icon

            if (isPlayPause) {
              if (isAcquiring) {
                IconComponent = Pause
                buttonClasses =
                  'bg-sci-accent-600 border-sci-accent-500 text-white hover:bg-sci-accent-500'
              } else {
                IconComponent = Play
                buttonClasses =
                  'bg-sci-primary-600 border-sci-primary-500 text-white hover:bg-sci-primary-500'
              }
            }

            if (isRecord) {
              buttonClasses = 'bg-red-600 border-red-500 text-white hover:bg-red-500'
            }

            if (isStop) {
              buttonClasses =
                'bg-sci-secondary-700 border-sci-secondary-500 text-sci-secondary-100 hover:bg-sci-secondary-600'
            }

            return (
              <button
                key={key}
                type="button"
                disabled={isDisabled}
                className={`${baseButtonClasses} ${buttonClasses} ${
                  isDisabled ? 'opacity-40 cursor-not-allowed' : ''
                }`}
                onClick={() => handleControlAction(key)}
                title={key}
              >
                <IconComponent className="w-4 h-4" />
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default AcquisitionViewport
