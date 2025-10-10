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
import { componentLogger } from '../../utils/logger'


const acquisitionModes = ['preview', 'record', 'playback'] as const
type AcquisitionMode = typeof acquisitionModes[number]

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

const modeControls: Record<AcquisitionMode, { icon: LucideIcon; key: string; label: string }[]> = {
  preview: [
    { key: 'skipBack', icon: SkipBack, label: 'Skip Back' },
    { key: 'stepBack', icon: StepBack, label: 'Step Back' },
    { key: 'playPause', icon: Play, label: 'Play/Pause' },
    { key: 'stop', icon: Square, label: 'Stop' },
    { key: 'stepForward', icon: StepForward, label: 'Step Forward' },
    { key: 'skipForward', icon: SkipForward, label: 'Skip Forward' },
  ],
  record: [
    { key: 'record', icon: Circle, label: 'Record' },
    { key: 'stop', icon: Square, label: 'Stop' },
  ],
  playback: [
    { key: 'skipBack', icon: SkipBack, label: 'Skip Back' },
    { key: 'stepBack', icon: StepBack, label: 'Step Back' },
    { key: 'playPause', icon: Play, label: 'Play/Pause' },
    { key: 'stop', icon: Square, label: 'Stop' },
    { key: 'stepForward', icon: StepForward, label: 'Step Forward' },
    { key: 'skipForward', icon: SkipForward, label: 'Skip Forward' },
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

  // Playback state
  const [availableSessions, setAvailableSessions] = useState<any[]>([])
  const [selectedSession, setSelectedSession] = useState<string | null>(null)
  const [loadedSessionData, setLoadedSessionData] = useState<any>(null)
  const [playbackFrameIndex, setPlaybackFrameIndex] = useState(0)
  const [isPlayingBack, setIsPlayingBack] = useState(false)
  const [currentPlaybackFrame, setCurrentPlaybackFrame] = useState<any>(null)
  const [isLoadingFrame, setIsLoadingFrame] = useState(false)

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
    componentLogger.debug('startAcquisition() called', { sendCommandAvailable: !!sendCommand, isPreviewing })

    // Record start time for elapsed time calculation
    setAcquisitionStartTime(Date.now())
    setFrameCount(0)

    // If already previewing, switch to acquisition mode
    if (isPreviewing) {
      // Start orchestrated acquisition sequence
      if (!sendCommand) {
        componentLogger.error('sendCommand is undefined!')
        return
      }

      // Stop the preview stimulus so baseline starts clean
      componentLogger.debug('Stopping preview stimulus before acquisition...')
      try {
        await sendCommand({ type: 'stop_stimulus' })
      } catch (error) {
        componentLogger.error('Error stopping preview stimulus:', error)
      }

      // Stop any existing acquisition first (safety check)
      componentLogger.debug('Stopping any existing acquisition...')
      try {
        await sendCommand({ type: 'stop_acquisition' })
      } catch (error) {
        // Ignore error if no acquisition was running
        componentLogger.debug('No existing acquisition to stop')
      }

      // Switch modes: preview OFF, acquisition ON
      setIsPreviewing(false)
      setIsAcquiring(true)

      componentLogger.debug('Sending start_acquisition command...')
      try {
        const result = await sendCommand({ type: 'start_acquisition' })
        componentLogger.debug('Received response:', result)
        if (result?.success) {
          componentLogger.info('Acquisition sequence started', {
            directions: result.total_directions,
            cycles: result.total_cycles
          })
        } else {
          componentLogger.error('Failed to start acquisition:', result?.error)
        }
      } catch (error) {
        componentLogger.error('Error starting acquisition:', error)
      }

      return
    }

    // Otherwise start from scratch
    componentLogger.debug('Starting preview first...')
    await startPreview()
    setIsAcquiring(true)

    // Start orchestrated acquisition sequence
    if (!sendCommand) {
      componentLogger.error('sendCommand is undefined!')
      return
    }

    componentLogger.debug('Sending start_acquisition command...')
    try {
      const result = await sendCommand({ type: 'start_acquisition' })
      componentLogger.debug('Received response:', result)
      if (result?.success) {
        componentLogger.info('Acquisition sequence started', {
          directions: result.total_directions,
          cycles: result.total_cycles
        })
      } else {
        componentLogger.error('Failed to start acquisition:', result?.error)
      }
    } catch (error) {
      componentLogger.error('Error starting acquisition:', error)
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
        componentLogger.info('Acquisition stopped')
      } else if (result?.error && !result.error.includes('not running')) {
        componentLogger.error('Failed to stop acquisition:', result?.error)
      }
    } catch (error: any) {
      if (!error.message?.includes('not running')) {
        componentLogger.error('Error stopping acquisition:', error)
      }
    }

    // Switch modes: acquisition OFF, preview ON
    setIsAcquiring(false)
    setIsPreviewing(true)

    // Restart preview stimulus
    componentLogger.debug('Restarting preview stimulus...')
    try {
      await sendCommand?.({ type: 'start_stimulus' })
    } catch (error) {
      componentLogger.error('Error restarting preview stimulus:', error)
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
      componentLogger.error('Error stopping preview:', error)
    }
  }

  // Load available sessions for playback
  const loadAvailableSessions = async () => {
    try {
      const result = await sendCommand?.({ type: 'list_sessions' })
      if (result?.success) {
        setAvailableSessions(result.sessions || [])
      }
    } catch (error) {
      componentLogger.error('Error loading sessions:', error)
    }
  }

  // Load a specific session for playback
  const loadSession = async (sessionPath: string) => {
    try {
      componentLogger.debug('Loading session', { sessionPath })
      const result = await sendCommand?.({ type: 'load_session', session_path: sessionPath })
      componentLogger.debug('Load session result', result)

      if (result?.success) {
        setSelectedSession(sessionPath)
        // Load session data for first available direction
        const dataResult = await sendCommand?.({ type: 'get_session_data' })
        componentLogger.debug('Get session data result', dataResult)

        if (dataResult?.success && dataResult.directions?.length > 0) {
          // Load data for first direction
          const firstDirection = dataResult.directions[0]
          componentLogger.debug('Loading direction', { firstDirection })

          const directionData = await sendCommand?.({
            type: 'get_session_data',
            direction: firstDirection
          })
          componentLogger.debug('Direction data result', directionData)
          componentLogger.debug('Camera frame info', {
            hasFrames: !!directionData?.camera_data?.has_frames,
            frameCount: directionData?.camera_data?.frame_count
          })

          if (directionData?.success) {
            setLoadedSessionData(directionData)
            setPlaybackFrameIndex(0)
            componentLogger.info('Session loaded successfully')
          } else {
            componentLogger.error('Failed to load direction data')
          }
        } else {
          componentLogger.error('No directions available in session')
        }
      } else {
        componentLogger.error('Failed to load session', { error: result?.error })
      }
    } catch (error) {
      componentLogger.error('Error loading session', error)
    }
  }

  // Play/pause playback
  const togglePlayback = () => {
    setIsPlayingBack(!isPlayingBack)
  }

  // Step forward one frame
  const stepForward = () => {
    if (loadedSessionData?.camera_data?.has_frames) {
      setPlaybackFrameIndex(prev =>
        Math.min(prev + 1, loadedSessionData.camera_data.frame_count - 1)
      )
    }
  }

  // Step backward one frame
  const stepBackward = () => {
    setPlaybackFrameIndex(prev => Math.max(prev - 1, 0))
  }

  // Skip to start
  const skipToStart = () => {
    setPlaybackFrameIndex(0)
  }

  // Skip to end
  const skipToEnd = () => {
    if (loadedSessionData?.camera_data?.has_frames) {
      setPlaybackFrameIndex(loadedSessionData.camera_data.frame_count - 1)
    }
  }

  // Listen for camera frames from camera-specific shared memory channel
  useEffect(() => {
    componentLogger.debug('Camera frame listener effect', {
      isPreviewing,
      isAcquiring,
      shouldListen: isPreviewing || isAcquiring
    })
    if (!isPreviewing && !isAcquiring) return

    const handleCameraFrame = async (metadata: any) => {
      try {
        componentLogger.debug('Received camera frame metadata', metadata)
        // Read actual frame data from shared memory using offset, size, and path
        const frameDataBuffer = await window.electronAPI.readSharedMemoryFrame(
          metadata.offset_bytes,
          metadata.data_size_bytes,
          metadata.shm_path
        )

        // Create ImageData from RGBA buffer
        const canvas = cameraCanvasRef.current
        if (!canvas) {
          componentLogger.warn('Canvas ref not available')
          return
        }

        const width = metadata.width_px
        const height = metadata.height_px

        // Set canvas dimensions
        if (canvas.width !== width || canvas.height !== height) {
          canvas.width = width
          canvas.height = height
          componentLogger.debug('Canvas resized', { width, height })
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
          timestamp_us: metadata.timestamp_us || metadata.capture_timestamp_us,
          timestamp_ms: (metadata.timestamp_us || metadata.capture_timestamp_us) / 1000,
          frame_id: metadata.frame_id || frameCount,
          camera_name: metadata.camera_name
        })
      } catch (error) {
        componentLogger.error('Failed to read camera frame from shared memory', error)
      }
    }

    componentLogger.debug('Setting up camera frame listener')
    let unsubscribe: (() => void) | undefined
    if (window.electronAPI?.onCameraFrame) {
      unsubscribe = window.electronAPI.onCameraFrame(handleCameraFrame)
      componentLogger.debug('Camera frame listener registered')
    } else {
      componentLogger.warn('window.electronAPI.onCameraFrame not available')
    }

    return () => {
      componentLogger.debug('Cleaning up camera frame listener')
      unsubscribe?.()
    }
  }, [isPreviewing, isAcquiring])

  // Listen for stimulus frames from stimulus-specific shared memory channel for mini preview
  // During acquisition: show live stimulus
  // During preview: show static frame from slider
  useEffect(() => {
    const handleStimulusFrame = async (metadata: any) => {
      try {
        // During acquisition: accept all stimulus frames (show live playback)
        // During preview: only accept frames matching slider position
        if (!isAcquiring && metadata.frame_index !== sharedFrameIndex) {
          return
        }

        // Read actual frame data from shared memory
        const frameDataBuffer = await window.electronAPI.readSharedMemoryFrame(
          metadata.offset_bytes,
          metadata.data_size_bytes,
          metadata.shm_path
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
        componentLogger.error('Failed to read stimulus frame from shared memory', error)
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

  // Update histogram chart data (backend now provides Chart.js-ready format)
  const updateHistogramChart = useCallback((data: any) => {
    if (!data?.labels || !data?.data) return

    setHistogramChartData({
      labels: data.labels,
      datasets: [{
        label: 'Pixel Count',
        data: data.data,
        backgroundColor: 'rgba(255, 255, 255, 0.8)',
        borderColor: 'rgba(255, 255, 255, 1)',
        borderWidth: 1,
      }]
    })

    setHistogramStats(data.statistics)
  }, [])

  // Update correlation chart data (backend now provides Chart.js-ready format)
  const updateCorrelationChart = useCallback((data: any) => {
    componentLogger.debug('Timing data received', data)

    // Backend sends empty arrays if no valid data
    if (!data?.labels || data.labels.length === 0) {
      componentLogger.warn('No timing data available')
      setCorrelationChartData({
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
      setCorrelationStats(null)
      return
    }

    componentLogger.debug('Plotting timing points', { count: data.labels.length })

    setCorrelationChartData({
      labels: data.labels,
      datasets: [{
        label: 'Timing Difference (ms)',
        data: data.data,
        borderColor: 'rgba(59, 130, 246, 1)',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        borderWidth: 2,
        pointRadius: 1,
        pointHoverRadius: 4,
        tension: 0.1,
      }]
    })

    setCorrelationStats(data.statistics)
  }, [])

  // Format elapsed time as HH:MM:SS:FF (frames at camera FPS)
  const formatElapsedTime = useCallback((startTime: number | null, currentFrameCount: number): string => {
    if (!startTime || !isAcquiring) {
      return '00:00:00:00'
    }

    const elapsedMs = Date.now() - startTime
    const hours = Math.floor(elapsedMs / 3600000)
    const minutes = Math.floor((elapsedMs % 3600000) / 60000)
    const seconds = Math.floor((elapsedMs % 60000) / 1000)

    // Use camera FPS from parameters, fallback to 30fps
    const cameraFps = cameraParams?.camera_fps || 30
    const frames = currentFrameCount % cameraFps

    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}:${frames.toString().padStart(2, '0')}`
  }, [isAcquiring, cameraParams?.camera_fps])

  // Poll for histogram (any time camera is active)
  useEffect(() => {
    if (!isPreviewing && !isAcquiring) return

    const pollInterval = setInterval(async () => {
      try {
        const result = await sendCommand?.({ type: 'get_camera_histogram' })

        if (result?.success && result.data) {
          updateHistogramChart(result.data)
        } else if (result?.error) {
          componentLogger.warn('Histogram not available', { error: result.error })
        }
      } catch (error) {
        componentLogger.error('Error polling histogram', error)
      }
    }, 100) // 10 Hz

    return () => clearInterval(pollInterval)
  }, [isPreviewing, isAcquiring, sendCommand, updateHistogramChart])

  // Poll for correlation data (only in acquisition mode)
  useEffect(() => {
    if (!isAcquiring) return

    componentLogger.debug('Starting correlation polling')
    const pollInterval = setInterval(async () => {
      try {
        const result = await sendCommand?.({ type: 'get_correlation_data' })
        componentLogger.debug('Correlation poll result', result)

        if (result?.success && result.data) {
          updateCorrelationChart(result.data)
        } else if (result?.error) {
          componentLogger.warn('Correlation not available', { error: result.error })
        } else {
          componentLogger.warn('Correlation result invalid', result)
        }
      } catch (error) {
        componentLogger.error('Error polling correlation', error)
      }
    }, 100) // 10 Hz

    return () => {
      componentLogger.debug('Stopping correlation polling')
      clearInterval(pollInterval)
    }
  }, [isAcquiring, sendCommand, updateCorrelationChart])

  // Listen for acquisition progress messages from backend
  useEffect(() => {
    if (!isAcquiring) return

    const handleSyncMessage = async (message: any) => {
      if (message.type === 'acquisition_progress') {
        componentLogger.debug('Acquisition progress update', message)
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
          componentLogger.info('Acquisition sequence completed')
          // Backend has already stopped acquisition, just restart preview
          setIsAcquiring(false)
          setIsPreviewing(true)
          setAcquisitionStatus(null)

          // Restart preview stimulus (camera is still running)
          componentLogger.debug('Restarting preview stimulus after acquisition')
          try {
            await sendCommand?.({ type: 'start_stimulus' })
          } catch (error) {
            componentLogger.error('Error restarting preview stimulus', error)
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

    componentLogger.debug('Starting acquisition status polling')
    const pollInterval = setInterval(async () => {
      try {
        const result = await sendCommand?.({ type: 'get_acquisition_status' })

        if (result?.success && result.status) {
          setAcquisitionStatus(result.status)

          // Skip - completion is handled by sync message listener
        }
      } catch (error) {
        componentLogger.error('Error polling acquisition status', error)
      }
    }, 500) // 2 Hz (slower since we have push messages)

    return () => {
      componentLogger.debug('Stopping acquisition status polling')
      clearInterval(pollInterval)
    }
  }, [isAcquiring, sendCommand])

  // Load available sessions when playback mode is selected
  useEffect(() => {
    if (acquisitionMode === 'playback' && systemState?.isConnected) {
      loadAvailableSessions()
    }
  }, [acquisitionMode, systemState?.isConnected])

  // Load playback frame on-demand when frame index changes
  useEffect(() => {
    if (!loadedSessionData?.camera_data?.has_frames || acquisitionMode !== 'playback') return

    const loadFrame = async () => {
      setIsLoadingFrame(true)
      try {
        const result = await sendCommand?.({
          type: 'get_playback_frame',
          direction: loadedSessionData.direction,
          frame_index: playbackFrameIndex
        })

        if (result?.success && result?.frame_data) {
          setCurrentPlaybackFrame(result)
        } else {
          componentLogger.error('Failed to load playback frame', { error: result?.error })
        }
      } catch (error) {
        componentLogger.error('Error loading playback frame', error)
      } finally {
        setIsLoadingFrame(false)
      }
    }

    loadFrame()
  }, [playbackFrameIndex, loadedSessionData, acquisitionMode, sendCommand])

  // Playback timer - auto-advance frames at session FPS (only when not loading)
  useEffect(() => {
    if (!isPlayingBack || !loadedSessionData?.camera_data?.has_frames) return

    // Get FPS from session metadata, fallback to 30fps
    const playbackFps = loadedSessionData?.metadata?.acquisition?.camera_fps ||
                        loadedSessionData?.metadata?.camera?.camera_fps ||
                        30

    const interval = setInterval(() => {
      // Only advance if not currently loading a frame (backpressure)
      if (!isLoadingFrame) {
        setPlaybackFrameIndex(prev => {
          const next = prev + 1
          if (next >= loadedSessionData.camera_data.frame_count) {
            setIsPlayingBack(false) // Stop at end
            return prev
          }
          return next
        })
      }
    }, 1000 / playbackFps)

    return () => clearInterval(interval)
  }, [isPlayingBack, loadedSessionData, isLoadingFrame])

  // Render playback frame to canvas
  useEffect(() => {
    if (!currentPlaybackFrame?.frame_data || acquisitionMode !== 'playback') return

    const canvas = cameraCanvasRef.current
    if (!canvas) return

    const frameData = currentPlaybackFrame.frame_data
    if (!frameData) return

    // Frame data is shape [height, width] grayscale
    const height = frameData.length
    const width = frameData[0]?.length || 0

    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width
      canvas.height = height
    }

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Convert grayscale to RGBA
    const imageData = ctx.createImageData(width, height)
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const idx = (y * width + x) * 4
        const value = frameData[y][x]
        imageData.data[idx] = value     // R
        imageData.data[idx + 1] = value // G
        imageData.data[idx + 2] = value // B
        imageData.data[idx + 3] = 255   // A
      }
    }

    ctx.putImageData(imageData, 0, 0)
  }, [currentPlaybackFrame, acquisitionMode])

  // Stop camera when entering playback mode
  useEffect(() => {
    if (acquisitionMode === 'playback' && (isPreviewing || isAcquiring)) {
      componentLogger.debug('Entering playback mode - stopping live camera')
      stopPreview()
    }
  }, [acquisitionMode, isPreviewing, isAcquiring])

  // Auto-start preview when camera is selected (not in playback mode)
  useEffect(() => {
    componentLogger.debug('Auto-start check', {
      acquisitionMode,
      selectedCamera: cameraParams?.selected_camera,
      isConnected: systemState?.isConnected,
      isPreviewing,
      isAcquiring,
      shouldStart: acquisitionMode !== 'playback' && cameraParams?.selected_camera && systemState?.isConnected && !isPreviewing && !isAcquiring
    })
    if (acquisitionMode !== 'playback' && cameraParams?.selected_camera && systemState?.isConnected && !isPreviewing && !isAcquiring) {
      componentLogger.debug('Auto-starting preview for camera', { camera: cameraParams.selected_camera })
      startPreview()
    }
  }, [cameraParams?.selected_camera, systemState?.isConnected, isPreviewing, isAcquiring, acquisitionMode])

  // Update mini stimulus preview when parameters or shared state change
  // This triggers backend to generate and write frame to shared memory
  // The shared memory listener above will then render it
  useEffect(() => {
    const fetchStimulusFrame = async () => {
      if (!stimulusParams || !monitorParams) return

      try {
        componentLogger.debug('Requesting stimulus frame', {
          direction: sharedDirection,
          frameIndex: sharedFrameIndex,
          showBarMask: sharedShowBarMask
        })
        await sendCommand?.({
          type: 'get_stimulus_frame',
          direction: sharedDirection,
          frame_index: sharedFrameIndex,
          show_bar_mask: sharedShowBarMask
        })
      } catch (error) {
        componentLogger.error('Error fetching stimulus frame', error)
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
          if (acquisitionMode === 'playback') {
            togglePlayback()
          } else {
            if (isAcquiring) {
              stopAcquisition()
            } else {
              startAcquisition()
            }
          }
          break
        }
        case 'stop': {
          if (acquisitionMode === 'playback') {
            setIsPlayingBack(false)
            setPlaybackFrameIndex(0)
          } else {
            stopAcquisition()
          }
          break
        }
        case 'record': {
          if (!isAcquiring) {
            startAcquisition()
          }
          break
        }
        case 'skipBack': {
          if (acquisitionMode === 'playback') {
            skipToStart()
          }
          break
        }
        case 'stepBack': {
          if (acquisitionMode === 'playback') {
            stepBackward()
          }
          break
        }
        case 'stepForward': {
          if (acquisitionMode === 'playback') {
            stepForward()
          }
          break
        }
        case 'skipForward': {
          if (acquisitionMode === 'playback') {
            skipToEnd()
          }
          break
        }
        default: {
          componentLogger.warn('Unknown control action', { action })
        }
      }
    },
    [isAcquiring, startAcquisition, stopAcquisition]
  )

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Main content area */}
      <div className="flex-1 flex flex-col gap-2 p-2 min-h-0 overflow-hidden">
        {/* Top row: Camera | Camera Status | Stimulus */}
        <div className="flex gap-2 min-h-0" style={{ height: '50%' }}>
          {/* Camera Feed */}
          {isCameraVisible ? (
            <div className="relative bg-black border border-sci-secondary-600 rounded-lg overflow-hidden" style={{ aspectRatio: `${cameraStats?.width || 640} / ${cameraStats?.height || 480}`, height: '100%', contain: 'layout size' }}>
              <canvas
                ref={cameraCanvasRef}
                className="absolute inset-0 w-full h-full"
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
            <div className="bg-sci-secondary-800 border border-dashed border-sci-secondary-600 rounded-lg flex items-center justify-center text-sci-secondary-400" style={{ aspectRatio: '4/3', height: '100%' }}>
              <div className="flex flex-col items-center gap-2">
                <ScanEye className="w-6 h-6" />
                <span className="text-sm">Camera view hidden</span>
              </div>
            </div>
          )}

          {/* Camera Information - Expands to fill center */}
          <div className="bg-sci-secondary-800 border border-sci-secondary-600 rounded-lg p-3 h-full overflow-auto flex-1 min-w-0">
            <div className="text-sm font-medium text-sci-secondary-200 mb-2">
              {acquisitionMode === 'playback' ? 'Playback Status' : isAcquiring ? 'Acquisition Status' : 'Camera Status'}
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              {acquisitionMode === 'playback' ? (
                <>
                  <div className="col-span-2">
                    <span className="text-sci-secondary-400">Session:</span>
                    <span className="ml-1 text-sci-secondary-200">
                      {loadedSessionData?.metadata?.session_name || 'None'}
                    </span>
                  </div>
                  <div>
                    <span className="text-sci-secondary-400">Frame:</span>
                    <span className="ml-1 text-sci-secondary-200 font-mono">
                      {playbackFrameIndex + 1}/{loadedSessionData?.camera_data?.frame_count || 0}
                    </span>
                  </div>
                  <div>
                    <span className="text-sci-secondary-400">Status:</span>
                    <span className={`ml-1 font-medium ${
                      isPlayingBack ? 'text-sci-success-400' : 'text-sci-secondary-500'
                    }`}>
                      {isPlayingBack ? 'PLAYING' : 'PAUSED'}
                    </span>
                  </div>
                  {loadedSessionData?.camera_data && (
                    <>
                      <div>
                        <span className="text-sci-secondary-400">Direction:</span>
                        <span className="ml-1 text-sci-secondary-200">
                          {loadedSessionData.direction || 'N/A'}
                        </span>
                      </div>
                      <div>
                        <span className="text-sci-secondary-400">Resolution:</span>
                        <span className="ml-1 text-sci-secondary-200 font-mono">
                          {currentPlaybackFrame?.frame_data?.[0]?.length || 0}×{currentPlaybackFrame?.frame_data?.length || 0}
                        </span>
                      </div>
                    </>
                  )}
                </>
              ) : (
                <>
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
                </>
              )}
              {acquisitionMode !== 'playback' && (isPreviewing || isAcquiring) && (
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

          {/* Stimulus Preview - Same height as camera */}
          <div className="relative bg-black border border-sci-secondary-600 rounded-lg overflow-hidden" style={{ aspectRatio: `${monitorParams?.monitor_width_px || 1728} / ${monitorParams?.monitor_height_px || 1117}`, height: '100%', contain: 'layout size' }}>
            <canvas
              ref={stimulusCanvasRef}
              className="absolute inset-0 w-full h-full"
            />
          </div>
        </div>

        {/* Bottom row: Two plots equally sized */}
        <div className="grid grid-cols-2 gap-2 flex-1 min-h-0">
            {/* Luminance Histogram */}
            <div className="bg-sci-secondary-800 border border-sci-secondary-600 rounded-lg p-2 flex flex-col h-full min-w-0">
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

            {/* Frame Timing Plot - Scrolling Line Chart (Last 5s) */}
            <div className="bg-sci-secondary-800 border border-sci-secondary-600 rounded-lg p-2 flex flex-col h-full min-w-0">
              <div className="text-xs text-sci-secondary-400 mb-1 flex-none">
                Frame Timing (Last 5s)
                {correlationStats && correlationStats.matched_count > 0 && (
                  <span className="ml-2 text-sci-secondary-500">
                    μ={correlationStats.mean_diff_ms.toFixed(2)}ms σ={correlationStats.std_diff_ms.toFixed(2)}ms
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

      {/* Control Buttons */}
      <div className="flex items-center gap-4 p-3 border-t border-sci-secondary-600 bg-sci-secondary-800/60 justify-center">
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

          {/* Session selector for playback mode */}
          {acquisitionMode === 'playback' && (
            <div className="flex items-center gap-2">
              <label className="text-xs uppercase tracking-wide text-sci-secondary-400">Session</label>
              <select
                value={selectedSession || ''}
                onChange={(event) => loadSession(event.target.value)}
                className="bg-sci-secondary-700 border border-sci-secondary-500 rounded px-2 py-1 text-sm text-sci-secondary-100 focus:outline-none focus:ring-2 focus:ring-sci-primary-600"
              >
                <option value="">Select a session...</option>
                {availableSessions.map((session) => (
                  <option key={session.session_path} value={session.session_path}>
                    {session.session_name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {acquisitionMode !== 'playback' && (
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
          )}

          {modeControls[acquisitionMode].map(({ key, icon }) => {
            const isPlayPause = key === 'playPause'
            const isRecord = key === 'record'
            const isStop = key === 'stop'

            const isDisabled =
              acquisitionMode === 'playback'
                ? !loadedSessionData?.camera_data?.has_frames // Disable if no frames loaded in playback mode
                : (!isPreviewing && !isAcquiring && key !== 'playPause' && key !== 'record')

            const baseButtonClasses =
              'w-9 h-9 flex items-center justify-center rounded-full border transition-colors focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-offset-sci-secondary-900'

            let buttonClasses =
              'bg-sci-secondary-700 border-sci-secondary-500 text-sci-secondary-200 hover:bg-sci-secondary-600'

            let IconComponent: LucideIcon = icon

            if (isPlayPause) {
              if (acquisitionMode === 'playback') {
                if (isPlayingBack) {
                  IconComponent = Pause
                  buttonClasses =
                    'bg-sci-accent-600 border-sci-accent-500 text-white hover:bg-sci-accent-500'
                } else {
                  IconComponent = Play
                  buttonClasses =
                    'bg-sci-primary-600 border-sci-primary-500 text-white hover:bg-sci-primary-500'
                }
              } else if (isAcquiring) {
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
  )
}

export default AcquisitionViewport
