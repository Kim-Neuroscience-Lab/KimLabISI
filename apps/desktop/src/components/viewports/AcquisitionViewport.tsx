import React, { useRef, useEffect, useState, useCallback } from 'react'
import {
  Play,
  Square,
  Circle,
  ScanEye,
  Monitor,
  Camera,
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
import type { ISIMessage } from '../../types/ipc-messages'
import type { SystemState } from '../../types/shared'
import type { CameraParameters, StimulusParameters, MonitorParameters, AcquisitionParameters } from '../../hooks/useParameterManager'
import { componentLogger } from '../../utils/logger'
import { ModeIndicatorBadge } from '../ModeIndicatorBadge'
import { FilterWarningModal } from '../FilterWarningModal'
import { useFrameRenderer } from '../../hooks/useFrameRenderer'


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

// Simplified controls - single toggle button per mode
const modeControls: Record<AcquisitionMode, { icon: LucideIcon; key: string; label: string }[]> = {
  preview: [
    { key: 'playPause', icon: Play, label: 'Preview' },
  ],
  record: [
    { key: 'recordToggle', icon: Circle, label: 'Record' },
  ],
  playback: [
    { key: 'playPause', icon: Play, label: 'Playback' },
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
  sharedDirection = 'LR',
  sharedFrameIndex = 0,
  sharedShowBarMask = false
}) => {
  // Camera feed state
  const cameraCanvasRef = useRef<HTMLCanvasElement>(null)
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

  // Mini stimulus preview - use hook for grayscale frame support
  const { canvasRef: stimulusCanvasRef, renderFrame: renderStimulusFrame } = useFrameRenderer()

  // Statistics
  const [cameraStats, setCameraStats] = useState<any>(null)
  const [frameCount, setFrameCount] = useState(0) // Camera frames captured
  const [stimulusFrameInfo, setStimulusFrameInfo] = useState<{
    current: number
    total: number
    direction?: string
    angle?: number
  } | null>(null)

  // Acquisition status
  const [acquisitionStatus, setAcquisitionStatus] = useState<any>(null)

  // Anatomical capture state
  const [showFilterWarning, setShowFilterWarning] = useState(false)
  const [filterWarningType, setFilterWarningType] = useState<'anatomical' | 'functional'>('anatomical')
  const [isCapturingAnatomical, setIsCapturingAnatomical] = useState(false)

  // Pre-recording filter warning state
  const [showPreRecordingWarning, setShowPreRecordingWarning] = useState(false)
  const [acquisitionError, setAcquisitionError] = useState<string | null>(null)

  // Monitor test state
  const [isTestingMonitor, setIsTestingMonitor] = useState(false)

  // Preview state tracking (user explicitly started preview)
  const [isPreviewActive, setIsPreviewActive] = useState(false)

  // Stimulus library status (tracks if stimulus is pre-generated and ready)
  const [stimulusLibraryStatus, setStimulusLibraryStatus] = useState<{
    library_loaded: boolean
    is_playing: boolean
  } | null>(null)

  // Track if stimulus is currently being pre-generated (async)
  const [isPreGeneratingStimulus, setIsPreGeneratingStimulus] = useState(false)

  // Derive isPreviewing and isAcquiring from backend state (Single Source of Truth)
  // isPreviewing = user explicitly started preview (not just idle camera)
  // isAcquiring = acquisition IS running
  const isPreviewing = isPreviewActive && cameraStats !== null && !(acquisitionStatus?.is_running ?? false)
  const isAcquiring = acquisitionStatus?.is_running ?? false

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
      setFrameCount(0) // Reset frame counter when starting preview
      setIsPreviewActive(true) // Mark preview as explicitly active

      // Start camera first
      const cameraResult = await sendCommand?.({
        type: 'start_camera_acquisition',
        camera_name: cameraParams.selected_camera
      })

      if (!cameraResult?.success) {
        setCameraError(cameraResult?.error || 'Failed to start camera')
        setIsPreviewActive(false)
        return
      }

      // Start preview mode with user-selected direction (proper integration!)
      const previewResult = await sendCommand?.({
        type: 'start_preview',
        direction: sharedDirection  // Use actual user selection, not hardcoded "LR"
      })

      if (!previewResult?.success) {
        setCameraError(previewResult?.error || 'Failed to start preview')
        setIsPreviewActive(false)
        return
      }

      componentLogger.info('Preview started successfully', {
        direction: sharedDirection,
        fps: previewResult.fps
      })
      // Note: isPreviewing is now derived from isPreviewActive && cameraStats !== null
    } catch (error) {
      setCameraError(`Error: ${error instanceof Error ? error.message : String(error)}`)
      setIsPreviewActive(false)
    }
  }

  // Start full acquisition (camera + histogram + correlation)
  // Backend reads all parameters from param_manager (Single Source of Truth)
  // Frontend validation provides fast UX feedback before calling backend
  // Returns true on success, false on failure
  const startAcquisition = async (): Promise<boolean> => {
    // Frontend validation provides fast UX feedback (optional - backend also validates)
    if (!acquisitionParams) {
      const errorMsg = 'Acquisition parameters not configured'
      setAcquisitionError(errorMsg)
      componentLogger.error(errorMsg)
      return false
    }

    if (!cameraParams?.camera_fps) {
      const errorMsg = 'Camera FPS not configured'
      setAcquisitionError(errorMsg)
      componentLogger.error(errorMsg)
      return false
    }

    try {
      // Clear previous errors
      setAcquisitionError(null)

      // Reset frontend display state
      setAcquisitionStartTime(Date.now())
      setFrameCount(0)

      // Send simple command - backend reads params from param_manager
      const result = await sendCommand?.({
        type: 'start_acquisition'
      })

      if (!result?.success) {
        const errorMsg = result?.error || 'Failed to start acquisition'
        setAcquisitionError(errorMsg)
        componentLogger.error('Backend failed to start acquisition:', errorMsg)
        return false
      }

      componentLogger.info('Acquisition started by backend', {
        directions: result.total_directions,
        cycles: result.total_cycles
      })
      return true
    } catch (error) {
      const errorMsg = `Error: ${error instanceof Error ? error.message : String(error)}`
      setAcquisitionError(errorMsg)
      componentLogger.error('Error sending start_acquisition command:', error)
      return false
    }
  }

  // Stop acquisition (fully stop, don't restart preview)
  const stopAcquisition = async () => {
    setAcquisitionStartTime(null)
    setAcquisitionStatus(null)
    setFrameCount(0)

    // Stop acquisition sequence (this also stops camera-triggered stimulus)
    try {
      const result = await sendCommand?.({ type: 'stop_acquisition' })
      if (result?.success) {
        componentLogger.info('Acquisition stopped - camera-triggered stimulus should be stopped')
      } else if (result?.error && !result.error.includes('not running')) {
        componentLogger.error('Failed to stop acquisition:', result?.error)
      }
    } catch (error: any) {
      if (!error.message?.includes('not running')) {
        componentLogger.error('Error stopping acquisition:', error)
      }
    }

    // CRITICAL FIX: Stop preview stimulus loop if it's somehow still running
    // This ensures stimulus stops even if there was a race condition
    try {
      await sendCommand?.({
        type: 'set_presentation_stimulus_enabled',
        enabled: false
      })
      componentLogger.info('Ensured preview stimulus is stopped')
    } catch (error) {
      componentLogger.error('Error ensuring preview stimulus stopped:', error)
    }

    // Stop camera completely
    try {
      await sendCommand?.({ type: 'stop_camera_acquisition' })
      componentLogger.info('Camera acquisition stopped')
    } catch (error) {
      componentLogger.error('Error stopping camera:', error)
    }

    // Note: isAcquiring and isPreviewing are now derived from backend state
  }

  // Stop preview (and acquisition if running)
  const stopPreview = async () => {
    try {
      setIsPreviewActive(false) // Mark preview as no longer active

      // Stop acquisition if running
      if (isAcquiring) {
        await sendCommand?.({ type: 'stop_acquisition' })
      }

      // Stop preview mode (proper integration!)
      const stopResult = await sendCommand?.({
        type: 'stop_preview'
      })

      if (stopResult?.success) {
        componentLogger.info('Preview stopped successfully')
      } else {
        componentLogger.error('Failed to stop preview:', stopResult?.error)
      }

      // Note: Don't stop camera - let it keep running for idle live view
      // await sendCommand?.({ type: 'stop_camera_acquisition' })

      setAcquisitionStartTime(null)
      setAcquisitionStatus(null)
      setFrameCount(0)
      // Note: isPreviewing is now derived from isPreviewActive state
    } catch (error) {
      componentLogger.error('Error stopping preview:', error)
    }
  }

  // Anatomical capture - show filter warning first
  const captureAnatomical = () => {
    setFilterWarningType('anatomical')
    setShowFilterWarning(true)
  }

  const confirmAnatomicalCapture = async () => {
    try {
      setShowFilterWarning(false)
      setIsCapturingAnatomical(true)

      const result = await sendCommand?.({ type: 'capture_anatomical' })

      if (result?.success) {
        componentLogger.info('Anatomical image captured', { path: result.path })
      } else {
        componentLogger.error('Failed to capture anatomical image:', result?.error)
      }
    } catch (error) {
      componentLogger.error('Error capturing anatomical image:', error)
    } finally {
      setIsCapturingAnatomical(false)
    }
  }

  const cancelAnatomicalCapture = () => {
    setShowFilterWarning(false)
  }

  // Pre-recording warning for acquisition start
  const initiateAcquisition = () => {
    setFilterWarningType('functional')
    setShowPreRecordingWarning(true)
  }

  const confirmStartAcquisition = async () => {
    // Clear previous errors
    setAcquisitionError(null)

    // Start acquisition and wait for result
    const success = await startAcquisition()

    // Only close modal if acquisition started successfully
    if (success) {
      setShowPreRecordingWarning(false)
    }
    // If there was an error, modal stays open showing the error
  }

  const cancelStartAcquisition = () => {
    setShowPreRecordingWarning(false)
  }

  // Monitor test handlers
  const testPresentationMonitor = async () => {
    try {
      if (isTestingMonitor) {
        // Stop test
        const result = await sendCommand?.({ type: 'stop_monitor_test' })
        if (result?.success) {
          setIsTestingMonitor(false)
          componentLogger.info('Monitor test stopped')
        }
      } else {
        // Start test
        const result = await sendCommand?.({ type: 'test_presentation_monitor' })
        if (result?.success) {
          setIsTestingMonitor(true)
          componentLogger.info('Monitor test started', {
            monitor: result.monitor_name,
            resolution: result.resolution,
            refreshRate: result.refresh_rate
          })
        } else {
          componentLogger.error('Failed to start monitor test:', result?.error)
        }
      }
    } catch (error) {
      componentLogger.error('Error testing monitor:', error)
    }
  }

  // Load available sessions for playback
  const loadAvailableSessions = async () => {
    if (!sendCommand) {
      componentLogger.error('loadAvailableSessions: sendCommand is not available')
      return
    }

    try {
      componentLogger.info('Loading available sessions...')
      const result = await sendCommand({ type: 'list_sessions' })
      componentLogger.info('List sessions result:', result)
      
      if (result?.success) {
        const sessions = result.sessions || []
        setAvailableSessions(sessions)
        componentLogger.info('Available sessions loaded:', { count: sessions.length, sessions })
      } else {
        componentLogger.error('Failed to list sessions:', result?.error)
      }
    } catch (error) {
      componentLogger.error('Exception loading sessions:', error)
    }
  }

  // Load a specific session for playback
  const loadSession = async (sessionPath: string) => {
    if (!sessionPath || sessionPath === '') {
      componentLogger.warn('loadSession called with empty sessionPath, ignoring')
      return
    }

    if (!sendCommand) {
      componentLogger.error('loadSession: sendCommand is not available')
      return
    }

    try {
      componentLogger.info('=== Starting session load ===', { sessionPath })
      
      // Step 1: Load session metadata
      const result = await sendCommand({ type: 'load_session', session_path: sessionPath })
      componentLogger.info('Step 1 - Load session result:', result)

      if (!result?.success) {
        componentLogger.error('Failed to load session', { error: result?.error, result })
        return
      }

      setSelectedSession(sessionPath)
      
      // Step 2: Get available directions
      const dataResult = await sendCommand({ type: 'get_session_data' })
      componentLogger.info('Step 2 - Get session data result:', dataResult)

      if (!dataResult?.success) {
        componentLogger.error('Failed to get session data', { error: dataResult?.error, dataResult })
        return
      }

      if (!dataResult.directions || dataResult.directions.length === 0) {
        componentLogger.error('No directions available in session', { dataResult })
        return
      }

      // Step 3: Load data for first direction
      const firstDirection = dataResult.directions[0]
      componentLogger.info('Step 3 - Loading first direction:', { firstDirection })

      const directionData = await sendCommand({
        type: 'get_session_data',
        direction: firstDirection
      })
      componentLogger.info('Step 3 - Direction data result:', directionData)
      
      if (!directionData?.success) {
        componentLogger.error('Failed to load direction data', { error: directionData?.error, directionData })
        return
      }

      // Check camera data
      const hasFrames = !!directionData?.camera_data?.has_frames
      const frameCount = directionData?.camera_data?.frame_count
      componentLogger.info('Camera frame info:', {
        hasFrames,
        frameCount,
        camera_data: directionData?.camera_data
      })

      if (!hasFrames) {
        componentLogger.warn('Session loaded but has no camera frames', { directionData })
      }

      setLoadedSessionData(directionData)
      setPlaybackFrameIndex(0)
      componentLogger.info('=== Session loaded successfully ===', {
        session: sessionPath,
        direction: firstDirection,
        hasFrames,
        frameCount
      })
    } catch (error) {
      componentLogger.error('=== Exception loading session ===', { error, sessionPath })
    }
  }

  // Toggle playback (play/stop)
  const togglePlayback = async () => {
    if (!sendCommand) return
    
    try {
      if (isPlayingBack) {
        // Stop playback
        const result = await sendCommand({ type: 'stop_playback_sequence' })
        if (result.success) {
          setIsPlayingBack(false)
          setPlaybackFrameIndex(0) // Reset to start
          componentLogger.info('Playback stopped')
        }
      } else {
        // Start playback from beginning
        const result = await sendCommand({ type: 'start_playback_sequence' })
        if (result.success) {
          setIsPlayingBack(true)
          componentLogger.info('Playback started')
        } else {
          componentLogger.error('Failed to start playback:', result.error)
        }
      }
    } catch (error) {
      componentLogger.error('Error toggling playback:', error)
    }
  }

  // Note: Standalone stop and frame stepping functions removed
  // Playback uses togglePlayback for play/stop control (no pause/resume)
  // Frame stepping can be re-added later if needed

  // Query stimulus library status on mount to show readiness indicator
  useEffect(() => {
    if (systemState?.isConnected && sendCommand) {
      componentLogger.debug('Querying stimulus library status...')
      sendCommand({ type: 'unified_stimulus_get_status' })
        .then(result => {
          if (result.success) {
            componentLogger.debug('Stimulus library status received', {
              library_loaded: result.library_loaded,
              is_playing: result.is_playing
            })
            setStimulusLibraryStatus({
              library_loaded: result.library_loaded,
              is_playing: result.is_playing
            })
          } else {
            componentLogger.error('Failed to get stimulus status:', result.error)
          }
        })
        .catch(err => {
          componentLogger.error('Error querying stimulus status:', err)
        })
    }
  }, [systemState?.isConnected, sendCommand])

  // REMOVED: Direction changes during preview mode
  // Preview mode now runs the full acquisition sequence (all directions)
  // If user wants to change direction, they must stop and restart preview
  // This matches the documented architecture: preview = full protocol test

  // Listen for stimulus library state changes (pre-generation complete)
  useEffect(() => {
    const handleSyncMessage = (message: any) => {
      if (message.type === 'unified_stimulus_pregeneration_started') {
        componentLogger.info('Stimulus pre-generation started (async)')
        setIsPreGeneratingStimulus(true)
      } else if (message.type === 'unified_stimulus_pregeneration_complete') {
        componentLogger.info('Stimulus pre-generation complete - updating status')
        setIsPreGeneratingStimulus(false)
        setStimulusLibraryStatus({
          library_loaded: true,
          is_playing: false
        })
      } else if (message.type === 'unified_stimulus_pregeneration_failed') {
        componentLogger.error('Stimulus pre-generation failed', message.error)
        setIsPreGeneratingStimulus(false)
      } else if (message.type === 'unified_stimulus_library_invalidated') {
        componentLogger.info('Stimulus library invalidated - updating status')
        setStimulusLibraryStatus({
          library_loaded: false,
          is_playing: false
        })
      }
    }

    let unsubscribe: (() => void) | undefined
    if (window.electronAPI?.onSyncMessage) {
      unsubscribe = window.electronAPI.onSyncMessage(handleSyncMessage)
    }

    return () => {
      unsubscribe?.()
    }
  }, [])

  // Listen for camera frames from camera-specific shared memory channel
  // ALWAYS listen (no dependencies) to avoid circular dependency:
  // - isPreviewing depends on cameraStats !== null
  // - But cameraStats is only set when frames are received
  // - So listener must be active from the start
  useEffect(() => {
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

        // Update frame count during active preview or acquisition (not idle streaming)
        // Note: Playback frame counting is handled separately in playback rendering effect
        if (isPreviewing || isAcquiring) {
          setFrameCount(prev => {
            const newCount = prev + 1
            // DIAGNOSTIC: Log camera frame updates during acquisition (every 60 frames to avoid spam)
            if (isAcquiring && newCount % 60 === 0) {
              console.log('[AcquisitionViewport] Camera frames:', {
                frameCount: newCount,
                isAcquiring,
                isPreviewing,
                timestamp_us: metadata.timestamp_us || metadata.capture_timestamp_us
              })
            }
            return newCount
          })
        }

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
  }, []) // Always listen, no dependencies (breaks circular dependency)

  // Listen for stimulus frames for mini preview
  // Uses useFrameRenderer hook which handles grayscale→RGBA conversion
  useEffect(() => {
    const handleStimulusFrame = async (metadata: any) => {
      try {
        componentLogger.debug('Received stimulus frame metadata for mini preview', metadata)

        // Read actual frame data from shared memory
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

        // Use hook's renderFrame - handles grayscale (1 channel) → RGBA conversion
        renderStimulusFrame(completeFrameData)

        // Update stimulus frame info for display in info panel
        if (metadata.frame_index !== undefined && metadata.total_frames) {
          setStimulusFrameInfo({
            current: metadata.frame_index,
            total: metadata.total_frames,
            direction: metadata.direction,
            angle: metadata.angle_degrees
          })

          // DIAGNOSTIC: Log stimulus frame updates during acquisition
          if (isAcquiring) {
            console.log('[AcquisitionViewport] Stimulus frame:', {
              frame_index: metadata.frame_index,
              total_frames: metadata.total_frames,
              direction: metadata.direction,
              angle: metadata.angle_degrees
            })
          }
        }
      } catch (error) {
        componentLogger.error('Failed to render stimulus frame', error)
      }
    }

    componentLogger.debug('Setting up stimulus frame listener')
    let unsubscribe: (() => void) | undefined
    if (window.electronAPI?.onSharedMemoryFrame) {
      unsubscribe = window.electronAPI.onSharedMemoryFrame(handleStimulusFrame)
      componentLogger.debug('Stimulus frame listener registered')
    } else {
      componentLogger.warn('window.electronAPI.onSharedMemoryFrame not available')
    }

    return () => {
      componentLogger.debug('Cleaning up stimulus frame listener')
      unsubscribe?.()
    }
  }, [renderStimulusFrame, isAcquiring]) // Re-subscribe when renderFrame or isAcquiring changes

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
  // CRITICAL FIX: Calculate time from frame count, not wall clock
  // This ensures smooth per-frame updates instead of jumpy per-second updates
  const formatElapsedTime = useCallback((startTime: number | null, currentFrameCount: number): string => {
    if (!startTime || !isAcquiring) {
      return '00:00:00:00'
    }

    // Use camera FPS from parameters, fallback to 30fps
    const cameraFps = cameraParams?.camera_fps || 30

    // Calculate elapsed time from frame count (frame-accurate, updates smoothly)
    const elapsedSeconds = currentFrameCount / cameraFps
    const hours = Math.floor(elapsedSeconds / 3600)
    const minutes = Math.floor((elapsedSeconds % 3600) / 60)
    const seconds = Math.floor(elapsedSeconds % 60)
    const frames = currentFrameCount % cameraFps

    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}:${frames.toString().padStart(2, '0')}`
  }, [isAcquiring, cameraParams?.camera_fps])

  // Histogram data is now pushed via ZeroMQ sync channel - no polling needed
  // Backend sends 'camera_histogram_update' messages via sync channel

  // Correlation data is now pushed via ZeroMQ sync channel - no polling needed
  // Backend sends 'correlation_update' messages via sync channel

  // Listen for all sync messages from backend (acquisition progress, histogram, correlation)
  useEffect(() => {
    const handleSyncMessage = async (message: any) => {
      // Acquisition progress updates
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
          // Backend has already stopped acquisition, fully stop camera
          setAcquisitionStatus(null)
          setAcquisitionStartTime(null)
          setFrameCount(0)
          // Note: isAcquiring and isPreviewing are now derived from backend state

          // Stop camera completely
          try {
            await sendCommand?.({ type: 'stop_camera_acquisition' })
          } catch (error) {
            componentLogger.error('Error stopping camera after acquisition', error)
          }
        }
      }

      // Histogram updates (pushed whenever camera is active)
      if (message.type === 'camera_histogram_update' && message.data) {
        updateHistogramChart(message.data)
      }

      // Correlation updates (pushed during acquisition)
      if (message.type === 'correlation_update' && message.data) {
        updateCorrelationChart(message.data)
      }

      // Playback progress updates
      if (message.type === 'playback_progress') {
        componentLogger.debug('Playback progress update', message)
        setAcquisitionStatus({
          is_running: true,
          phase: message.phase,
          current_direction: message.direction,
          current_cycle: message.cycle,
          total_cycles: message.total_cycles,
          elapsed_time: 0,
          phase_start_time: Date.now()
        })
      }

      // Playback complete
      if (message.type === 'playback_complete') {
        componentLogger.info('Playback sequence completed')
        setIsPlayingBack(false)
        setAcquisitionStatus(null)
      }

      // Playback error
      if (message.type === 'playback_error') {
        componentLogger.error('Playback error:', message.error)
        setIsPlayingBack(false)
        setAcquisitionStatus(null)
      }
    }

    let unsubscribe: (() => void) | undefined
    if (window.electronAPI?.onSyncMessage) {
      unsubscribe = window.electronAPI.onSyncMessage(handleSyncMessage)
    }

    return () => {
      unsubscribe?.()
    }
  }, [updateHistogramChart, updateCorrelationChart, sendCommand])

  // Poll for acquisition status (always, not just when acquiring) - shows current phase even when idle
  useEffect(() => {
    if (acquisitionMode === 'playback') return // Don't poll in playback mode

    componentLogger.debug('Starting acquisition status polling')
    const pollInterval = setInterval(async () => {
      try {
        const result = await sendCommand?.({ type: 'get_acquisition_status' })

        if (result?.success && result.phase !== undefined) {
          // Backend spreads status fields directly into response, not under 'status' key
          setAcquisitionStatus({
            is_running: result.is_running,
            phase: result.phase,
            current_direction: result.current_direction,
            current_direction_index: result.current_direction_index,
            total_directions: result.total_directions,
            current_cycle: result.current_cycle,
            total_cycles: result.total_cycles,
            elapsed_time: result.elapsed_time,
            phase_start_time: result.phase_start_time
          })

          // DIAGNOSTIC: Log acquisition status when is_running changes or in STIMULUS phase
          if (result.is_running || result.phase === 'stimulus') {
            console.log('[AcquisitionViewport] Acquisition status:', {
              is_running: result.is_running,
              phase: result.phase,
              current_direction: result.current_direction,
              current_cycle: result.current_cycle,
              total_cycles: result.total_cycles,
              elapsed_time: result.elapsed_time
            })
          }

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
  }, [acquisitionMode, sendCommand])

  // Load available sessions when playback mode is selected
  useEffect(() => {
    if (acquisitionMode === 'playback' && systemState?.isConnected) {
      loadAvailableSessions()
    }
  }, [acquisitionMode, systemState?.isConnected])

  // Cleanup when switching away from playback mode - close HDF5 files
  const prevModeRef = useRef<AcquisitionMode>('preview')
  useEffect(() => {
    const prevMode = prevModeRef.current
    
    // If switching away from playback mode, unload session to close HDF5 files
    if (prevMode === 'playback' && acquisitionMode !== 'playback') {
      componentLogger.info('Switching away from playback mode - unloading session to close HDF5 files')
      sendCommand?.({ type: 'unload_session' }).catch(err => {
        componentLogger.error('Failed to unload session:', err)
      })
    }
    
    // Update previous mode for next comparison
    prevModeRef.current = acquisitionMode
  }, [acquisitionMode, sendCommand])

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
    
    // Increment frame count for playback
    if (isPlayingBack) {
      setFrameCount(prev => prev + 1)
    }
  }, [currentPlaybackFrame, acquisitionMode, isPlayingBack])

  // Stop camera when entering playback mode
  useEffect(() => {
    if (acquisitionMode === 'playback' && (isPreviewing || isAcquiring)) {
      componentLogger.debug('Entering playback mode - stopping live camera')
      stopPreview()
    }
  }, [acquisitionMode, isPreviewing, isAcquiring])

  // Auto-start preview when camera is selected (not in playback mode)
  // DISABLED: User must explicitly press play or record to start
  // Auto-restart camera stream when exiting playback mode or after acquisition stops
  const hasAutoStartedCamera = useRef(false)
  useEffect(() => {
    // Only auto-start if:
    // 1. Not in playback mode
    // 2. Camera is selected
    // 3. System is connected
    // 4. Not currently previewing or acquiring
    // 5. Haven't already auto-started for this camera
    const shouldAutoStart = 
      acquisitionMode !== 'playback' && 
      cameraParams?.selected_camera && 
      systemState?.isConnected && 
      !isPreviewing && 
      !isAcquiring &&
      !hasAutoStartedCamera.current

    if (shouldAutoStart) {
      componentLogger.info('Auto-starting camera stream for idle view', { 
        camera: cameraParams.selected_camera 
      })
      hasAutoStartedCamera.current = true
      // Ensure camera is streaming for idle live view
      sendCommand?.({ type: 'start_camera_acquisition' }).catch(err => {
        componentLogger.error('Failed to auto-start camera:', err)
        hasAutoStartedCamera.current = false // Allow retry on error
      })
    }
    
    // Reset flag when camera changes or mode changes to playback
    if (acquisitionMode === 'playback' || !cameraParams?.selected_camera) {
      hasAutoStartedCamera.current = false
    }
  }, [acquisitionMode, cameraParams?.selected_camera, systemState?.isConnected, isPreviewing, isAcquiring, sendCommand])

  // Update mini stimulus preview when parameters or shared state change
  // This triggers backend to generate and write frame to shared memory
  // The shared memory listener above will then render it
  // ONLY request static frames when NOT previewing (PreviewStimulusLoop not running)
  useEffect(() => {
    const fetchStimulusFrame = async () => {
      if (!stimulusParams || !monitorParams) return

      // Skip if preview is running - PreviewStimulusLoop handles continuous frames
      if (isPreviewing || isAcquiring) {
        componentLogger.debug('Skipping static frame request - preview/acquisition running')
        return
      }

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
  }, [stimulusParams, monitorParams, sendCommand, sharedDirection, sharedFrameIndex, sharedShowBarMask, isPreviewing, isAcquiring])

  // Backend controls stimulus lifecycle via acquisition state machine
  // Frontend should NOT interfere with stimulus display - removed competing control logic

  // REMOVED: Automatic presentation stimulus control during record mode
  // The camera-triggered stimulus system handles presentation display during recording.
  // This useEffect was causing duplicate stimulus instances by starting PreviewStimulusLoop
  // while camera-triggered stimulus was also running, causing flickering.
  // Preview mode still controls presentation stimulus via the "Show on Presentation Monitor" checkbox.

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      // Stop any running acquisition/preview
      if (isPreviewing || isAcquiring) {
        stopPreview()
      }
      
      // Unload playback session to close HDF5 files
      if (acquisitionMode === 'playback' && loadedSessionData) {
        componentLogger.info('Component unmounting - unloading playback session')
        sendCommand?.({ type: 'unload_session' }).catch(err => {
          componentLogger.error('Failed to unload session on unmount:', err)
        })
      }
    }
  }, [])

  const handleControlAction = useCallback(
    (action: string) => {
      switch (action) {
        case 'playPause': {
          if (acquisitionMode === 'playback') {
            // Playback mode: toggle play/pause
            togglePlayback()
          } else if (acquisitionMode === 'preview') {
            // Preview mode: toggle preview on/off
            if (isPreviewing) {
              stopPreview()
            } else {
              startPreview()
            }
          }
          break
        }
        case 'recordToggle': {
          // Record mode: toggle recording on/off
          if (isAcquiring) {
            stopAcquisition()
          } else {
            initiateAcquisition()  // Show filter warning first, then start acquisition
          }
          break
        }
        default: {
          componentLogger.warn('Unknown control action', { action })
        }
      }
    },
    [
      acquisitionMode,
      isAcquiring,
      isPreviewing,
      stopAcquisition,
      startPreview,
      stopPreview,
      initiateAcquisition,
      togglePlayback
    ]
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

              {/* Mode Indicator Badge - Always visible for clear mode indication */}
              <div className="absolute top-2 left-2 pointer-events-none">
                <ModeIndicatorBadge
                  mode={acquisitionMode}
                  isPreviewing={isPreviewing}
                  isAcquiring={isAcquiring}
                />
              </div>

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

          {/* Camera Information - Expands to fill center (with calibration controls in preview mode) */}
          <div className="bg-sci-secondary-800 border border-sci-secondary-600 rounded-lg p-3 h-full overflow-auto flex-1 min-w-0 flex flex-col gap-2">
            <div className="text-sm font-medium text-sci-secondary-200 mb-2">
              {acquisitionMode === 'playback' ? 'Playback Status' : isAcquiring ? 'Acquisition Status' : 'System Status'}
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              {acquisitionMode === 'playback' ? (
                <>
                  <div>
                    <span className="text-sci-secondary-400">Session:</span>
                    <span className="ml-1 text-sci-secondary-200">
                      {loadedSessionData?.metadata?.session_name || 'None'}
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
                  <div>
                    <span className="text-sci-secondary-400">Phase:</span>
                    <span className="ml-1 text-sci-secondary-200">
                      Playback
                    </span>
                  </div>
                  <div>
                    <span className="text-sci-secondary-400">Direction:</span>
                    <span className="ml-1 text-sci-secondary-200">
                      {loadedSessionData?.direction || 'N/A'}
                    </span>
                  </div>
                  <div>
                    <span className="text-sci-secondary-400">Cycle:</span>
                    <span className="ml-1 text-sci-secondary-200 font-mono">
                      N/A
                    </span>
                  </div>
                  <div>
                    <span className="text-sci-secondary-400">Progress:</span>
                    <span className="ml-1 text-sci-secondary-200 font-mono">
                      {playbackFrameIndex + 1}/{loadedSessionData?.camera_data?.frame_count || 0}
                    </span>
                  </div>
                  <div>
                    <span className="text-sci-secondary-400">Frames:</span>
                    <span className="ml-1 text-sci-secondary-200 font-mono">
                      {loadedSessionData?.camera_data?.frame_count || 0}
                    </span>
                  </div>
                  <div>
                    <span className="text-sci-secondary-400">Time:</span>
                    <span className="ml-1 text-sci-secondary-200 font-mono">
                      00:00:00:00
                    </span>
                  </div>
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
                      isPreGeneratingStimulus ? 'text-yellow-400' : isAcquiring ? 'text-sci-success-400' : isPreviewing ? 'text-sci-accent-400' : 'text-sci-secondary-500'
                    }`}>
                      {isPreGeneratingStimulus ? 'PRE-GENERATING' : isAcquiring ? (acquisitionMode === 'record' ? 'RECORDING' : 'PREVIEWING') : isPreviewing ? 'PREVIEWING' : 'IDLE'}
                    </span>
                  </div>
                </>
              )}
              {acquisitionMode !== 'playback' && (
                <>
                  {/* Phase - always shown */}
                  <div>
                    <span className="text-sci-secondary-400">Phase:</span>
                    <span className="ml-1 text-sci-secondary-200 capitalize">
                      {acquisitionStatus?.phase === 'idle' ? 'Stopped' : (acquisitionStatus?.phase?.replace(/_/g, ' ') || 'Unknown')}
                    </span>
                  </div>

                  {/* Direction - always shown */}
                  <div>
                    <span className="text-sci-secondary-400">Direction:</span>
                    <span className="ml-1 text-sci-secondary-200">
                      {acquisitionStatus?.current_direction || (isAcquiring ? 'Waiting...' : 'N/A')}
                    </span>
                  </div>

                  {/* Cycle - always shown */}
                  <div>
                    <span className="text-sci-secondary-400">Cycle:</span>
                    <span className="ml-1 text-sci-secondary-200 font-mono">
                      {acquisitionStatus?.current_cycle || 0}/{acquisitionStatus?.total_cycles || 0}
                    </span>
                  </div>

                  {/* Progress - always shown */}
                  <div>
                    <span className="text-sci-secondary-400">Progress:</span>
                    <span className="ml-1 text-sci-secondary-200 font-mono">
                      {acquisitionStatus ? `${(acquisitionStatus.current_direction_index || 0) + 1}/${acquisitionStatus.total_directions || 0}` : '0/0'}
                    </span>
                  </div>

                  {/* Stimulus Frame Info - show during acquisition */}
                  {isAcquiring && stimulusFrameInfo && (
                    <div>
                      <span className="text-sci-secondary-400">Stimulus:</span>
                      <span className="ml-1 text-sci-secondary-200 font-mono">
                        {stimulusFrameInfo.current + 1}/{stimulusFrameInfo.total}
                      </span>
                    </div>
                  )}

                  {/* Camera Frames - always shown */}
                  <div>
                    <span className="text-sci-secondary-400">Frames:</span>
                    <span className="ml-1 text-sci-secondary-200 font-mono">
                      {frameCount.toLocaleString()}
                    </span>
                  </div>

                  {/* Time - compact in grid, unless record mode + acquiring */}
                  {!(acquisitionMode === 'record' && isAcquiring) && (
                    <div>
                      <span className="text-sci-secondary-400">Time:</span>
                      <span className="ml-1 text-sci-secondary-200 font-mono">
                        {formatElapsedTime(acquisitionStartTime, frameCount)}
                      </span>
                    </div>
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

            {/* Large Time Counter - ONLY in record mode while acquiring */}
            {acquisitionMode === 'record' && isAcquiring && (
              <div className="flex items-center justify-center p-4 bg-red-900/20 border border-red-700 rounded-lg">
                <div className="text-center">
                  <div className="text-xs uppercase tracking-wide text-red-400 mb-1">RECORDING TIME</div>
                  <div className="text-3xl font-mono font-bold text-red-300">
                    {formatElapsedTime(acquisitionStartTime, frameCount)}
                  </div>
                </div>
              </div>
            )}

            {/* Stimulus Library Status - always show in non-playback modes */}
            {acquisitionMode !== 'playback' && (
              <div className="border-t border-sci-secondary-600 pt-2 mt-2">
                <div className="text-xs font-medium text-sci-secondary-300 mb-2">
                  Stimulus Library
                </div>
                {stimulusLibraryStatus === null ? (
                  <div className="flex items-center gap-2 px-2 py-1 bg-sci-secondary-700 border border-sci-secondary-600 rounded text-xs">
                    <span className="text-sci-secondary-400">⋯</span>
                    <span className="text-sci-secondary-400">Checking status...</span>
                  </div>
                ) : stimulusLibraryStatus.library_loaded ? (
                  <div className="flex items-center gap-2 px-2 py-1 bg-green-900/30 border border-green-700 rounded text-xs">
                    <span className="text-green-400">✓</span>
                    <span className="text-green-300 font-medium">Stimulus Ready</span>
                  </div>
                ) : (
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-2 px-2 py-1 bg-yellow-900/30 border border-yellow-700 rounded text-xs">
                      <span className="text-yellow-400">⚠</span>
                      <span className="text-yellow-300 font-medium">Pre-generate Required</span>
                    </div>
                    <div className="text-xs text-sci-secondary-500 px-2">
                      Visit Stimulus Generation tab to pre-generate patterns
                    </div>
                  </div>
                )}
              </div>
            )}

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
              onChange={async (event) => {
                const newMode = event.target.value as AcquisitionMode
                
                // Call backend to properly cleanup old mode (close files, etc.)
                if (sendCommand) {
                  try {
                    const result = await sendCommand({ 
                      type: 'set_acquisition_mode',
                      mode: newMode
                    })
                    if (result.success) {
                      setAcquisitionMode(newMode)
                      componentLogger.info('Switched acquisition mode', { from: acquisitionMode, to: newMode })
                    } else {
                      componentLogger.error('Failed to switch mode:', result.error)
                    }
                  } catch (error) {
                    componentLogger.error('Error switching mode:', error)
                  }
                } else {
                  // Fallback if no sendCommand (shouldn't happen)
                  setAcquisitionMode(newMode)
                }
              }}
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
                onChange={(event) => {
                  const sessionPath = event.target.value
                  componentLogger.debug('Session dropdown changed', { sessionPath, hasValue: !!sessionPath })
                  if (sessionPath && sessionPath !== '') {
                    componentLogger.info('Loading session from dropdown', { sessionPath })
                    loadSession(sessionPath)
                  } else {
                    componentLogger.debug('Empty session selected, ignoring')
                  }
                }}
                className="bg-sci-secondary-700 border border-sci-secondary-500 rounded px-2 py-1 text-sm text-sci-secondary-100 focus:outline-none focus:ring-2 focus:ring-sci-primary-600"
              >
                <option value="">Select a session...</option>
                {availableSessions.map((session) => (
                  <option key={session.session_path} value={session.session_path}>
                    {session.session_name}
                  </option>
                ))}
              </select>
              {availableSessions.length === 0 && (
                <span className="text-xs text-sci-secondary-500">No sessions available</span>
              )}
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

          {/* Test Monitor Button - only when not acquiring/playing */}
          {acquisitionMode !== 'playback' && !isPreviewing && !isAcquiring && (
            <button
              type="button"
              onClick={testPresentationMonitor}
              className={`flex items-center gap-2 px-3 py-1.5 rounded text-sm font-medium border transition-colors ${
                isTestingMonitor
                  ? 'bg-sci-accent-600 border-sci-accent-500 text-white hover:bg-sci-accent-500'
                  : 'bg-sci-secondary-700 border-sci-secondary-500 text-sci-secondary-200 hover:bg-sci-secondary-600'
              }`}
            >
              <Monitor className="w-4 h-4" />
              {isTestingMonitor ? 'Stop Monitor Test' : 'Test Monitor'}
            </button>
          )}

          {/* Anatomical Capture Button - available in preview mode */}
          {acquisitionMode === 'preview' && (
            <button
              type="button"
              onClick={captureAnatomical}
              disabled={isCapturingAnatomical || !systemState?.isConnected || !cameraStats}
              className={`flex items-center gap-2 px-3 py-1.5 rounded text-sm font-medium border transition-colors ${
                isCapturingAnatomical || !systemState?.isConnected || !cameraStats
                  ? 'bg-sci-secondary-700 border-sci-secondary-500 text-sci-secondary-400 cursor-not-allowed opacity-50'
                  : 'bg-sci-accent-600 border-sci-accent-500 text-white hover:bg-sci-accent-500'
              }`}
            >
              <Camera className="w-4 h-4" />
              {isCapturingAnatomical ? 'Capturing...' : 'Capture Anatomical'}
            </button>
          )}

          {/* Show on Presentation Monitor Toggle - REMOVED
              Preview mode now automatically shows stimulus on presentation monitor.
              The UnifiedStimulusController handles presentation display via start_preview/stop_preview.
              No manual toggle needed - simpler UX, less architectural debt. */}

          {/* REMOVED: Record mode stimulus indicator
              Camera-triggered stimulus handles presentation automatically during recording */}


          {modeControls[acquisitionMode].map(({ key, icon, label }) => {
            // Determine button state and appearance based on mode and key
            let IconComponent: LucideIcon = icon
            let buttonClasses = ''
            let isDisabled = false

            if (key === 'playPause') {
              // Preview or Playback mode
              if (acquisitionMode === 'playback') {
                isDisabled = !loadedSessionData?.camera_data?.has_frames
                if (isPlayingBack) {
                  IconComponent = Square  // Stop icon when playing
                  buttonClasses = 'bg-sci-accent-600 border-sci-accent-500 text-white hover:bg-sci-accent-500'
                } else {
                  IconComponent = Play
                  buttonClasses = 'bg-sci-primary-600 border-sci-primary-500 text-white hover:bg-sci-primary-500'
                }
              } else if (acquisitionMode === 'preview') {
                if (isPreviewing) {
                  IconComponent = Square  // Stop icon when previewing
                  buttonClasses = 'bg-sci-accent-600 border-sci-accent-500 text-white hover:bg-sci-accent-500'
                } else {
                  IconComponent = Play
                  buttonClasses = 'bg-sci-primary-600 border-sci-primary-500 text-white hover:bg-sci-primary-500'
                }
              }
            } else if (key === 'recordToggle') {
              // Record mode
              if (isAcquiring) {
                IconComponent = Square  // Stop icon when recording
                buttonClasses = 'bg-red-700 border-red-600 text-white hover:bg-red-600'
              } else {
                IconComponent = Circle  // Record icon when stopped
                buttonClasses = 'bg-red-600 border-red-500 text-white hover:bg-red-500'
              }
            }

            return (
              <button
                key={key}
                type="button"
                disabled={isDisabled}
                className={`w-9 h-9 flex items-center justify-center rounded-full border transition-colors focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-offset-sci-secondary-900 ${buttonClasses} ${
                  isDisabled ? 'opacity-40 cursor-not-allowed' : ''
                }`}
                onClick={() => handleControlAction(key)}
                title={label}
              >
                <IconComponent className="w-4 h-4" />
              </button>
            )
          })}
      </div>

      {/* Filter Warning Modals */}
      {showFilterWarning && (
        <FilterWarningModal
          isOpen={showFilterWarning}
          onClose={cancelAnatomicalCapture}
          onConfirm={confirmAnatomicalCapture}
          filterType={filterWarningType}
        />
      )}

      {showPreRecordingWarning && (
        <FilterWarningModal
          isOpen={showPreRecordingWarning}
          onClose={cancelStartAcquisition}
          onConfirm={confirmStartAcquisition}
          filterType="functional"
          error={acquisitionError}
        />
      )}
    </div>
  )
}

export default AcquisitionViewport
