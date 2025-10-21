import React, { useState, useRef, useEffect, useCallback } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { componentLogger } from '../../utils/logger'
import type { ISIMessage, ControlMessage, SyncMessage, ListSessionsResponse, GetAnalysisResultsResponse, GetAnalysisCompositeImageResponse } from '../../types/ipc-messages'
import type { SystemState, AnalysisParameters } from '../../types/shared'
import AnalysisProgress, { type AnalysisStage } from '../analysis/AnalysisProgress'
import { CalibrationCircleOverlay } from '../CalibrationCircleOverlay'

interface AnalysisViewportProps {
  className?: string
  sendCommand?: (command: ISIMessage) => Promise<{ success: boolean; error?: string }>
  lastMessage?: ControlMessage | SyncMessage | null
  systemState?: SystemState
  analysisParams?: AnalysisParameters
}

type SignalType =
  // Primary retinotopy maps (HSV colormap)
  | 'azimuth' | 'elevation'
  // VFS options (JET colormap) - 3 variants
  | 'raw_vfs_map' | 'magnitude_vfs_map' | 'statistical_vfs_map'
  // Individual direction phase maps (HSV colormap - cyclic hue for phase angle)
  | 'LR_phase_map' | 'RL_phase_map' | 'TB_phase_map' | 'BT_phase_map'
  // Individual direction magnitude maps (VIRIDIS colormap)
  | 'LR_magnitude_map' | 'RL_magnitude_map' | 'TB_magnitude_map' | 'BT_magnitude_map'
  // Individual direction coherence maps (VIRIDIS colormap)
  | 'LR_coherence_map' | 'RL_coherence_map' | 'TB_coherence_map' | 'BT_coherence_map'

type OverlayType = 'area_borders' | 'area_patches' | 'none'

// Analysis result metadata (no heavy arrays - only metadata)
interface AnalysisMetadata {
  session_path: string
  shape: [number, number]  // [height, width]
  num_areas: number
  primary_layers: string[]  // Main result layers (azimuth_map, elevation_map, etc.)
  advanced_layers: string[]  // Debug/intermediate layers (phase_LR, magnitude_LR, etc.)
  has_anatomical: boolean
}

/**
 * Utility function to convert base64 string to Blob URL.
 * Used for displaying images received from backend.
 */
const base64ToBlob = (base64: string, mimeType: string = 'image/png'): Blob => {
  const byteCharacters = atob(base64)
  const byteNumbers = new Array(byteCharacters.length)
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i)
  }
  const byteArray = new Uint8Array(byteNumbers)
  return new Blob([byteArray], { type: mimeType })
}

/**
 * Convert RGB24 data from shared memory to a blob URL for display.
 * RGB24 format has 3 bytes per pixel (R, G, B), no alpha channel.
 */
const rgb24ToBlob = async (data: ArrayBuffer, width: number, height: number): Promise<Blob> => {
  // Create a canvas
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Failed to get canvas context')

  // Create ImageData
  const imageData = ctx.createImageData(width, height)
  const rgb24Data = new Uint8Array(data)

  // Convert RGB24 to RGBA
  for (let i = 0; i < width * height; i++) {
    imageData.data[i * 4 + 0] = rgb24Data[i * 3 + 0]  // R
    imageData.data[i * 4 + 1] = rgb24Data[i * 3 + 1]  // G
    imageData.data[i * 4 + 2] = rgb24Data[i * 3 + 2]  // B
    imageData.data[i * 4 + 3] = 255                    // A (fully opaque)
  }

  // Put ImageData on canvas
  ctx.putImageData(imageData, 0, 0)

  // Convert canvas to blob
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob)
      else reject(new Error('Failed to convert canvas to blob'))
    }, 'image/png')
  })
}

const AnalysisViewport: React.FC<AnalysisViewportProps> = ({
  className = '',
  sendCommand,
  lastMessage,
  analysisParams
}) => {
  // Image ref (replaces canvas refs)
  const imageRef = useRef<HTMLImageElement>(null)

  // Analysis state
  const [analysisMetadata, setAnalysisMetadata] = useState<AnalysisMetadata | null>(null)
  const [isAnalysisRunning, setIsAnalysisRunning] = useState(false)
  const [analysisProgress, setAnalysisProgress] = useState(0)
  const [analysisStage, setAnalysisStage] = useState<string>('idle')
  const [selectedSession, setSelectedSession] = useState<string | null>(null)
  const [availableSessions, setAvailableSessions] = useState<any[]>([])
  const [currentSessionPath, setCurrentSessionPath] = useState<string | null>(null)

  // Calibration state
  const [isCalibrating, setIsCalibrating] = useState(false)
  const [calibrationMmPerPixel, setCalibrationMmPerPixel] = useState<number | null>(null)
  const [calibrationCircleDiameter, setCalibrationCircleDiameter] = useState<number>(100)
  const [calibrationImageDimensions, setCalibrationImageDimensions] = useState({ width: 640, height: 480 })
  const [calibrationImageUrl, setCalibrationImageUrl] = useState<string | null>(null)

  // Command submission state (prevents double-clicks, shows loading)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submissionError, setSubmissionError] = useState<string | null>(null)

  // Analysis progress stages with intermediate results
  const [analysisStages, setAnalysisStages] = useState<AnalysisStage[]>([
    { id: 'loading_data', label: 'Loading session data', progress: 0, status: 'pending' },
    { id: 'processing', label: 'Processing directions', progress: 0, status: 'pending' },
    { id: 'azimuth_map', label: 'Horizontal retinotopy', progress: 0, status: 'pending' },
    { id: 'elevation_map', label: 'Vertical retinotopy', progress: 0, status: 'pending' },
    { id: 'sign_map', label: 'Visual field sign', progress: 0, status: 'pending' },
    { id: 'boundary_map', label: 'Area boundaries', progress: 0, status: 'pending' },
    { id: 'saving', label: 'Saving results', progress: 0, status: 'pending' },
  ])

  // Image display
  const [compositeImageUrl, setCompositeImageUrl] = useState<string | null>(null)
  const [pendingFrameId, setPendingFrameId] = useState<number | null>(null)

  // Layer visibility and settings
  const [showAnatomical, setShowAnatomical] = useState(true)
  const [showSignal, setShowSignal] = useState(true)
  const [showOverlay, setShowOverlay] = useState(true)

  const [signalType, setSignalType] = useState<SignalType>('magnitude_vfs_map')
  const [overlayType, setOverlayType] = useState<OverlayType>('area_borders')

  const [anatomicalAlpha, setAnatomicalAlpha] = useState(0.5)
  const [signalAlpha, setSignalAlpha] = useState(0.8)
  const [overlayAlpha, setOverlayAlpha] = useState(1.0)

  // Store latest settings in a ref to avoid stale closures
  const settingsRef = useRef({
    showAnatomical,
    anatomicalAlpha,
    showSignal,
    signalType,
    signalAlpha,
    showOverlay,
    overlayType,
    overlayAlpha
  })

  // Update ref on every render
  useEffect(() => {
    settingsRef.current = {
      showAnatomical,
      anatomicalAlpha,
      showSignal,
      signalType,
      signalAlpha,
      showOverlay,
      overlayType,
      overlayAlpha
    }
  })

  // Load available sessions
  useEffect(() => {
    const loadSessions = async () => {
      if (!sendCommand) return

      try {
        const result = await sendCommand({ type: 'list_sessions' }) as ListSessionsResponse
        if (result.success && result.sessions) {
          setAvailableSessions(result.sessions)
          componentLogger.info('Loaded sessions:', result.sessions)
        }
      } catch (error) {
        componentLogger.error('Failed to load sessions:', error)
      }
    }

    loadSessions()
  }, [sendCommand])

  // Listen for analysis messages
  useEffect(() => {
    if (!lastMessage) return

    // Cancellation flag for async operations
    let cancelled = false

    // Async message handler
    const handleMessage = async () => {
      if (lastMessage.type === 'analysis_started') {
        setIsAnalysisRunning(true)
        setAnalysisProgress(0)
        setAnalysisStage('started')
        componentLogger.info('Analysis started')

        // Clear any submission errors (analysis successfully started)
        setSubmissionError(null)
        setIsSubmitting(false)

        // Reset all stages to pending
        setAnalysisStages(stages => stages.map(s => ({ ...s, progress: 0, status: 'pending', thumbnail: undefined })))

        // Clear existing metadata and image for new analysis
        setAnalysisMetadata(null)
        if (compositeImageUrl) {
          URL.revokeObjectURL(compositeImageUrl)
          setCompositeImageUrl(null)
        }
      }

      if (lastMessage.type === 'analysis_progress') {
        const progress = (lastMessage as any).progress ?? 0
        const stage = (lastMessage as any).stage ?? 'processing'
        setAnalysisProgress(progress)
        setAnalysisStage(stage)
        componentLogger.info(`Analysis progress: ${(progress * 100).toFixed(0)}%`)

        // Update stages based on progress
        setAnalysisStages(stages => {
          const updated = [...stages]

          // Map backend stage to frontend stage ID
          let stageId = 'processing'
          if (stage.includes('Loading') || stage.includes('loading')) {
            stageId = 'loading_data'
          } else if (stage.includes('Processing') || stage.includes('processing')) {
            stageId = 'processing'
          } else if (stage.includes('retinotopic')) {
            stageId = 'azimuth_map'  // Will be updated when layers arrive
          } else if (stage.includes('sign')) {
            stageId = 'sign_map'
          } else if (stage.includes('Saving') || stage.includes('saving')) {
            stageId = 'saving'
          }

          // Mark previous stages as completed
          let foundCurrent = false
          for (const s of updated) {
            if (s.id === stageId) {
              s.status = 'in_progress'
              s.progress = progress
              foundCurrent = true
            } else if (!foundCurrent && s.status !== 'completed') {
              s.status = 'completed'
              s.progress = 1.0
            }
          }

          return updated
        })
      }

      if (lastMessage.type === 'analysis_layer_ready') {
        // Intermediate layer is ready for visualization (PNG-rendered by backend)
        const layerName = (lastMessage as any).layer_name as string
        const imageBase64 = (lastMessage as any).image_base64 as string
        const sessionPath = (lastMessage as any).session_path as string

        componentLogger.info(`Intermediate layer ready: ${layerName}`)

        try {
          if (cancelled) return

          // Convert base64 PNG to blob URL
          const blob = base64ToBlob(imageBase64, 'image/png')
          const url = URL.createObjectURL(blob)

          // Create data URL for thumbnail
          const thumbnailDataUrl = `data:image/png;base64,${imageBase64}`

          // Update the corresponding stage with thumbnail and mark as completed
          setAnalysisStages(stages => {
            const updated = [...stages]
            const stage = updated.find(s => s.id === layerName)
            if (stage) {
              stage.thumbnail = thumbnailDataUrl
              stage.status = 'completed'
              stage.progress = 1.0
              componentLogger.info(`Added thumbnail for stage: ${layerName}`)
            }
            return updated
          })

          // Revoke old URL to prevent memory leak
          if (compositeImageUrl) {
            URL.revokeObjectURL(compositeImageUrl)
          }

          // Display the rendered image
          setCompositeImageUrl(url)

          // Initialize metadata if this is the first layer
          if (!analysisMetadata) {
            const height = (lastMessage as any).height ?? 0
            const width = (lastMessage as any).width ?? 0
            const metadata: AnalysisMetadata = {
              session_path: sessionPath,
              shape: [height, width],
              num_areas: 0,
              primary_layers: [layerName],
              advanced_layers: [],
              has_anatomical: false
            }
            setAnalysisMetadata(metadata)
            setCurrentSessionPath(sessionPath)
            componentLogger.info(`Analysis metadata initialized for incremental rendering`)
          } else {
            // Update existing metadata with new layer
            setAnalysisMetadata(prev => prev ? {
              ...prev,
              primary_layers: [...prev.primary_layers, layerName]
            } : prev)
          }

          componentLogger.info(`Displayed rendered layer: ${layerName}`)
        } catch (error) {
          if (!cancelled) {
            componentLogger.error(`Error displaying layer ${layerName}:`, error)
          }
        }
      }

      if (lastMessage.type === 'analysis_complete') {
        setIsAnalysisRunning(false)
        setAnalysisProgress(1.0)
        setAnalysisStage('complete')
        componentLogger.info('Analysis complete:', lastMessage)

        // Mark all stages as completed
        setAnalysisStages(stages => stages.map(s => ({
          ...s,
          status: s.status === 'in_progress' || s.status === 'pending' ? 'completed' : s.status,
          progress: 1.0
        })))

        // Load results metadata
        if ((lastMessage as any).output_path && !cancelled) {
          await loadAnalysisResults((lastMessage as any).output_path as string)
        }
      }

      if (lastMessage.type === 'analysis_error') {
        setIsAnalysisRunning(false)
        setAnalysisStage('error')
        componentLogger.error('Analysis error:', (lastMessage as any).error)
      }
    }

    // Execute the async handler
    handleMessage()

    // Cleanup function to cancel pending operations
    return () => {
      cancelled = true
    }
  }, [lastMessage, compositeImageUrl, analysisMetadata])

  // ========== CALIBRATION HANDLERS ==========

  const handleCalibrationChange = useCallback((mmPerPixel: number, circleDiameterPixels: number) => {
    setCalibrationMmPerPixel(mmPerPixel)
    setCalibrationCircleDiameter(circleDiameterPixels)
  }, [])

  const saveCalibration = async () => {
    if (!calibrationMmPerPixel || !sendCommand) {
      componentLogger.warn('Cannot save calibration - invalid scale or no command function')
      return
    }
    
    try {
      await sendCommand({
        type: 'update_parameter_group',
        group_name: 'analysis',
        parameters: { pixel_scale_mm_per_px: calibrationMmPerPixel }
      })
      
      setIsCalibrating(false)
      componentLogger.info('Calibration saved:', calibrationMmPerPixel, 'mm/px')
    } catch (error) {
      componentLogger.error('Failed to save calibration:', error)
    }
  }

  const startCalibration = async () => {
    if (!sendCommand) return

    try {
      // Try to load anatomical image first if available
      if (analysisMetadata?.has_anatomical && currentSessionPath) {
        componentLogger.info('Loading anatomical image for calibration')
        const result = await sendCommand({ 
          type: 'get_anatomical_image', 
          session_path: currentSessionPath 
        }) as any
        
        if (result?.image_data && result?.width && result?.height) {
          const blob = base64ToBlob(result.image_data)
          const url = URL.createObjectURL(blob)
          setCalibrationImageUrl(url)
          setCalibrationImageDimensions({ width: result.width, height: result.height })
          setIsCalibrating(true)
          componentLogger.info('Anatomical image loaded for calibration:', result.width, 'x', result.height)
          return
        }
      }
      
      // Fall back to current composite image
      if (compositeImageUrl && analysisMetadata) {
        setCalibrationImageUrl(compositeImageUrl)
        setCalibrationImageDimensions({ 
          width: analysisMetadata.shape[1] || 640, 
          height: analysisMetadata.shape[0] || 480 
        })
        setIsCalibrating(true)
        componentLogger.info('Using composite image for calibration')
        return
      }
      
      componentLogger.warn('No image available for calibration')
    } catch (error) {
      componentLogger.error('Failed to start calibration:', error)
    }
  }

  // ========== IMAGE LOADING ==========

  // Load analysis results metadata only (no heavy arrays)
  const loadAnalysisResults = async (outputPath: string) => {
    if (!sendCommand) return

    componentLogger.info('Loading analysis metadata from:', outputPath)

    try {
      // Extract session path from output path (remove /analysis_results)
      const sessionPath = outputPath.replace(/\/analysis_results$/, '')

      const result = await sendCommand({
        type: 'get_analysis_results',
        session_path: sessionPath
      } as any) as GetAnalysisResultsResponse

      if (result.success) {
        const metadata: AnalysisMetadata = {
          session_path: result.session_path || sessionPath,
          shape: result.shape as [number, number],
          num_areas: result.num_areas || 0,
          primary_layers: result.primary_layers || [],
          advanced_layers: result.advanced_layers || [],
          has_anatomical: result.has_anatomical || false
        }

        componentLogger.info('Analysis metadata loaded:', metadata)
        setAnalysisMetadata(metadata)
        setCurrentSessionPath(sessionPath)

        // Request initial composite image
        await requestCompositeImage(sessionPath)
      } else {
        componentLogger.error('Failed to load analysis metadata:', result.error)
      }
    } catch (error) {
      componentLogger.error('Error loading analysis metadata:', error)
    }
  }

  // Request composite image from backend
  const requestCompositeImage = useCallback(async (sessionPathOverride?: string) => {
    if (!sendCommand) return

    const sessionPath = sessionPathOverride || currentSessionPath
    if (!sessionPath) return

    // Use ref to get LATEST values (no stale closures)
    const settings = settingsRef.current

    componentLogger.info('Requesting composite image from backend...', settings)

    try {
      const result = await sendCommand({
        type: 'get_analysis_composite_image',
        session_path: sessionPath,
        layers: {
          anatomical: {
            visible: settings.showAnatomical,
            alpha: settings.anatomicalAlpha
          },
          signal: {
            visible: settings.showSignal,
            type: settings.signalType,
            alpha: settings.signalAlpha
          },
          overlay: {
            visible: settings.showOverlay,
            type: settings.overlayType,
            alpha: settings.overlayAlpha
          }
        }
      } as any) as GetAnalysisCompositeImageResponse

      if (result.success && result.frame_id !== undefined) {
        // Backend now sends frame via shared memory
        // Frame will arrive via onAnalysisFrame subscriber
        componentLogger.info(`Composite image requested, frame_id: ${result.frame_id}, dimensions: ${result.width}x${result.height}`)
        setPendingFrameId(result.frame_id)
      } else if (result.success && result.image_base64) {
        // Legacy fallback for base64 (backward compatibility during migration)
        componentLogger.warn('Received base64 image (legacy mode)')
        const blob = base64ToBlob(result.image_base64, 'image/png')
        const url = URL.createObjectURL(blob)

        setCompositeImageUrl(prevUrl => {
          if (prevUrl) {
            URL.revokeObjectURL(prevUrl)
          }
          return url
        })

        componentLogger.info(`Composite image loaded (base64): ${result.width}x${result.height}`)
      } else {
        componentLogger.error('Failed to get composite image:', result.error)
      }
    } catch (error) {
      componentLogger.error('Error requesting composite image:', error)
    }
  }, [sendCommand, currentSessionPath])

  // Request new image when settings change
  useEffect(() => {
    if (analysisMetadata && !isAnalysisRunning) {
      componentLogger.info('Settings changed, requesting composite image...')
      requestCompositeImage()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    showAnatomical,
    anatomicalAlpha,
    showSignal,
    signalType,
    signalAlpha,
    showOverlay,
    overlayType,
    overlayAlpha,
    analysisMetadata,
    isAnalysisRunning
    // NOTE: requestCompositeImage intentionally omitted to avoid dependency cycle
  ])

  // Subscribe to analysis frames from shared memory
  useEffect(() => {
    if (!window.electronAPI?.onAnalysisFrame) {
      componentLogger.warn('Analysis frame subscriber not available')
      return
    }

    const unsubscribe = window.electronAPI.onAnalysisFrame(async (frameData) => {
      try {
        componentLogger.info('Received analysis frame metadata:', frameData)

        // Read frame data from shared memory
        const arrayBuffer = await window.electronAPI.readSharedMemoryFrame(
          frameData.offset_bytes,
          frameData.data_size_bytes,
          frameData.shm_path
        )

        // Convert RGB24 to blob URL
        const blob = await rgb24ToBlob(arrayBuffer, frameData.width_px, frameData.height_px)
        const url = URL.createObjectURL(blob)

        // Revoke old URL to prevent memory leak
        setCompositeImageUrl(prevUrl => {
          if (prevUrl) {
            URL.revokeObjectURL(prevUrl)
          }
          return url
        })

        componentLogger.info(`Analysis composite displayed: ${frameData.width_px}x${frameData.height_px}`)
      } catch (error) {
        componentLogger.error('Error processing analysis frame:', error)
      }
    })

    return () => {
      unsubscribe()
    }
  }, [])

  // Cleanup blob URLs on unmount
  useEffect(() => {
    return () => {
      if (compositeImageUrl) {
        URL.revokeObjectURL(compositeImageUrl)
      }
    }
  }, [compositeImageUrl])

  // Start analysis on selected session with proper error handling and user feedback
  const startAnalysis = async () => {
    if (!sendCommand || !selectedSession || isSubmitting) {
      componentLogger.warn('Cannot start analysis', {
        hasSendCommand: !!sendCommand,
        hasSession: !!selectedSession,
        isSubmitting
      })
      return
    }

    // Clear any previous errors
    setSubmissionError(null)
    setIsSubmitting(true)

    // Determine if this is a re-analysis of the same session
    const isReanalysis = currentSessionPath === selectedSession && analysisMetadata !== null

    componentLogger.info(
      isReanalysis
        ? `[USER ACTION] Re-analyzing session: ${selectedSession}`
        : `[USER ACTION] Starting new analysis: ${selectedSession}`
    )

    try {
      const result = await sendCommand({
        type: 'start_analysis',
        session_path: selectedSession
      } as any)

      if (!result.success) {
        const errorMsg = result.error || 'Unknown error occurred'
        componentLogger.error('Failed to start analysis:', errorMsg)
        setSubmissionError(errorMsg)

        // Keep submitting state for a brief moment to show error, then reset
        setTimeout(() => {
          setIsSubmitting(false)
        }, 1000)
      } else {
        componentLogger.info('Analysis command sent successfully')

        // Reset submitting state after a brief delay to prevent rapid re-clicks
        // The analysis will update isAnalysisRunning via message listener
        setTimeout(() => {
          setIsSubmitting(false)
        }, 500)
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error)
      componentLogger.error('Error starting analysis:', error)
      setSubmissionError(`Failed to send command: ${errorMsg}`)

      // Reset after showing error
      setTimeout(() => {
        setIsSubmitting(false)
      }, 1000)
    }
  }

  // Stop running analysis
  const stopAnalysis = async () => {
    if (!sendCommand) return

    try {
      await sendCommand({ type: 'stop_analysis' })
    } catch (error) {
      componentLogger.error('Error stopping analysis:', error)
    }
  }

  // Handle thumbnail click - display in main viewer
  const handleThumbnailClick = (stageId: string, thumbnail: string) => {
    // Convert data URL back to blob URL for display
    fetch(thumbnail)
      .then(res => res.blob())
      .then(blob => {
        const url = URL.createObjectURL(blob)

        // Revoke old URL
        if (compositeImageUrl) {
          URL.revokeObjectURL(compositeImageUrl)
        }

        setCompositeImageUrl(url)
        componentLogger.info(`Displaying thumbnail from stage: ${stageId}`)
      })
      .catch(error => {
        componentLogger.error('Error displaying thumbnail:', error)
      })
  }

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Main Content Area: Square visualization on left, controls on right */}
      <div className="flex-1 flex gap-4 min-h-0">
        {/* Visualization Area - Fixed square container that never changes size */}
        <div
          className="flex-shrink-0 bg-black rounded-lg border border-sci-secondary-600 overflow-hidden flex items-center justify-center relative"
          style={{
            width: 'min(100vh - 2rem, 50vw)',  // Square sized to fit viewport
            height: 'min(100vh - 2rem, 50vw)', // Match width for perfect square
            minWidth: '300px',  // Minimum usable size
            minHeight: '300px'
          }}
        >
          {compositeImageUrl ? (
            <>
              <img
                ref={imageRef}
                src={compositeImageUrl}
                alt="Analysis Composite"
                className="w-full h-full object-contain"
                style={{ imageRendering: 'pixelated' }}
              />
              
              {/* Calibration Circle Overlay */}
              {isCalibrating && calibrationImageUrl && (
                <CalibrationCircleOverlay
                  visible={isCalibrating}
                  canvasWidth={calibrationImageDimensions.width}
                  canvasHeight={calibrationImageDimensions.height}
                  actualCameraWidth={calibrationImageDimensions.width}
                  actualCameraHeight={calibrationImageDimensions.height}
                  headFrameDiameterMm={analysisParams?.ring_size_mm || 10}
                  onCalibrationChange={handleCalibrationChange}
                />
              )}
            </>
          ) : (
            <div className="text-sci-secondary-500 text-sm text-center px-4">
              {isAnalysisRunning ? 'Analysis in progress...' : 'No analysis results to display'}
            </div>
          )}
        </div>

        {/* Right Panel: Session Selection + Layer Controls */}
        <div className="flex-1 flex flex-col gap-4 min-w-0 overflow-y-auto max-h-full pb-4">
          {/* Session Selection and Analysis Controls */}
          <div className="p-3 bg-sci-secondary-800 rounded-lg border border-sci-secondary-600 flex-shrink-0">
            <h3 className="text-sm font-medium text-sci-secondary-200 mb-3">Analysis Session</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-sci-secondary-400 mb-1">Session</label>
                <select
                  value={selectedSession || ''}
                  onChange={(e) => setSelectedSession(e.target.value)}
                  className="w-full px-2 py-1 bg-sci-secondary-900 text-white text-sm rounded border border-sci-secondary-600"
                  disabled={isAnalysisRunning}
                >
                  <option value="">Select session...</option>
                  {availableSessions.map((session) => (
                    <option key={session.session_path} value={session.session_path}>
                      {session.session_name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Error feedback */}
              {submissionError && !isAnalysisRunning && (
                <div className="px-3 py-2 bg-red-900/30 border border-red-600/50 rounded text-xs text-red-300">
                  <div className="font-medium mb-1">Analysis Failed</div>
                  <div>{submissionError}</div>
                </div>
              )}

              {/* Action buttons */}
              <div className="space-y-2">
                {!isAnalysisRunning ? (
                  <>
                    {/* Primary Analyze button */}
                    <button
                      onClick={startAnalysis}
                      disabled={!selectedSession || isSubmitting}
                      className="w-full px-4 py-2 bg-sci-primary-600 text-white text-sm rounded hover:bg-sci-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {isSubmitting ? (
                        <>
                          <span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                          <span>Starting...</span>
                        </>
                      ) : (
                        'Analyze'
                      )}
                    </button>

                    {/* Re-Analyze button (only shown when viewing results of selected session) */}
                    {selectedSession &&
                     currentSessionPath === selectedSession &&
                     analysisMetadata !== null &&
                     !isSubmitting && (
                      <button
                        onClick={startAnalysis}
                        className="w-full px-3 py-1.5 bg-sci-secondary-600 text-white text-xs rounded hover:bg-sci-secondary-700 transition-colors border border-sci-secondary-500"
                        title="Run analysis again on the same session"
                      >
                        Re-Analyze Current Session
                      </button>
                    )}
                  </>
                ) : (
                  <button
                    onClick={stopAnalysis}
                    className="w-full px-4 py-2 bg-red-600 text-white text-sm rounded hover:bg-red-700 transition-colors"
                  >
                    Stop Analysis
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Analysis Progress - Persistent section with stage tracking */}
          <div className="flex-shrink-0">
            <AnalysisProgress
              stages={analysisStages}
              isRunning={isAnalysisRunning}
              onThumbnailClick={handleThumbnailClick}
            />
          </div>

          {/* Calibration Controls */}
          <div className="p-3 bg-sci-secondary-800 rounded-lg border border-sci-secondary-600 flex-shrink-0">
            <h3 className="text-sm font-medium text-sci-secondary-200 mb-3">Spatial Calibration</h3>
            <div className="space-y-2">
              <button
                onClick={isCalibrating ? () => setIsCalibrating(false) : startCalibration}
                disabled={!analysisMetadata && !compositeImageUrl}
                className={`w-full px-3 py-2 rounded text-sm font-medium border transition-colors ${
                  isCalibrating
                    ? 'bg-sci-primary-600 border-sci-primary-500 text-white hover:bg-sci-primary-500'
                    : 'bg-sci-secondary-700 border-sci-secondary-500 text-sci-secondary-200 hover:bg-sci-secondary-600 disabled:opacity-40 disabled:cursor-not-allowed'
                }`}
              >
                {isCalibrating ? 'Exit Calibration' : 'Start Calibration'}
              </button>

              {isCalibrating && (
                <div className="flex flex-col gap-2 mt-2">
                  <div className="text-xs text-sci-secondary-400 bg-sci-secondary-900 p-2 rounded">
                    <div>Reference Object: {analysisParams?.ring_size_mm || 10} mm</div>
                    <div className="text-sci-secondary-500 text-[10px] mt-1">
                      (Ring Size parameter)
                    </div>
                  </div>

                  {calibrationMmPerPixel && (
                    <div className="text-xs text-sci-secondary-300 bg-sci-secondary-900 p-2 rounded">
                      <div>Scale: {calibrationMmPerPixel.toFixed(4)} mm/pixel</div>
                      <div>Circle: {calibrationCircleDiameter.toFixed(1)} px = {analysisParams?.ring_size_mm || 10} mm</div>
                    </div>
                  )}

                  <div className="text-xs text-sci-secondary-500 bg-sci-secondary-900 p-2 rounded">
                    Drag and resize the circle to match the known reference object in the image.
                  </div>

                  <button
                    onClick={saveCalibration}
                    disabled={!calibrationMmPerPixel}
                    className="px-3 py-2 rounded text-sm font-medium border transition-colors bg-sci-success-600 border-sci-success-500 text-white hover:bg-sci-success-500 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    Save Calibration
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Anatomical Layer */}
          <div className="p-3 bg-sci-secondary-800 rounded-lg border border-sci-secondary-600 flex-shrink-0">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-sci-secondary-200">Anatomical</span>
              <button
                onClick={() => setShowAnatomical(!showAnatomical)}
                className="text-sci-secondary-400 hover:text-white transition-colors"
              >
                {showAnatomical ? <Eye size={16} /> : <EyeOff size={16} />}
              </button>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs text-sci-secondary-400 whitespace-nowrap flex-shrink-0 w-16">
                Opacity
              </label>
              <input
                type="range"
                min="0"
                max="100"
                value={anatomicalAlpha * 100}
                onChange={(e) => setAnatomicalAlpha(Number(e.target.value) / 100)}
                className="flex-1"
                disabled={!showAnatomical}
              />
              <span className="text-xs text-sci-secondary-400 flex-shrink-0 w-10 text-right">
                {(anatomicalAlpha * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          {/* Signal Layer */}
          <div className="p-3 bg-sci-secondary-800 rounded-lg border border-sci-secondary-600 flex-shrink-0">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-sci-secondary-200">Signal</span>
              <button
                onClick={() => setShowSignal(!showSignal)}
                className="text-sci-secondary-400 hover:text-white transition-colors"
              >
                {showSignal ? <Eye size={16} /> : <EyeOff size={16} />}
              </button>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <label className="text-xs text-sci-secondary-400 whitespace-nowrap flex-shrink-0 w-16">Type</label>
                <select
                  value={signalType}
                  onChange={(e) => setSignalType(e.target.value as SignalType)}
                  className="flex-1 px-2 py-1 bg-sci-secondary-900 text-white text-sm rounded border border-sci-secondary-600"
                  disabled={!showSignal}
                >
                  {/* Primary Results */}
                  <optgroup label="Primary Results">
                    <option value="azimuth">Horizontal Retinotopy</option>
                    <option value="elevation">Vertical Retinotopy</option>
                  </optgroup>

                  {/* VFS Options - 3 variants */}
                  <optgroup label="Visual Field Sign">
                    <option value="raw_vfs_map">Raw VFS</option>
                    <option value="magnitude_vfs_map">Magnitude Threshold VFS</option>
                    <option value="statistical_vfs_map">Statistical Threshold VFS</option>
                  </optgroup>

                  {/* Phase Maps */}
                  <optgroup label="Phase Maps">
                    <option value="LR_phase_map">LR Phase</option>
                    <option value="RL_phase_map">RL Phase</option>
                    <option value="TB_phase_map">TB Phase</option>
                    <option value="BT_phase_map">BT Phase</option>
                  </optgroup>

                  {/* Quality Metrics (Literature Standard) */}
                  <optgroup label="Quality Metrics">
                    <option value="LR_coherence_map">LR Coherence</option>
                    <option value="RL_coherence_map">RL Coherence</option>
                    <option value="TB_coherence_map">TB Coherence</option>
                    <option value="BT_coherence_map">BT Coherence</option>
                  </optgroup>

                  {/* Response Strength */}
                  <optgroup label="Response Strength">
                    <option value="LR_magnitude_map">LR Magnitude</option>
                    <option value="RL_magnitude_map">RL Magnitude</option>
                    <option value="TB_magnitude_map">TB Magnitude</option>
                    <option value="BT_magnitude_map">BT Magnitude</option>
                  </optgroup>
                </select>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-xs text-sci-secondary-400 whitespace-nowrap flex-shrink-0 w-16">
                  Opacity
                </label>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={signalAlpha * 100}
                  onChange={(e) => setSignalAlpha(Number(e.target.value) / 100)}
                  className="flex-1"
                  disabled={!showSignal}
                />
                <span className="text-xs text-sci-secondary-400 flex-shrink-0 w-10 text-right">
                  {(signalAlpha * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </div>

          {/* Overlay Layer */}
          <div className="p-3 bg-sci-secondary-800 rounded-lg border border-sci-secondary-600 flex-shrink-0">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-sci-secondary-200">Overlay</span>
              <button
                onClick={() => setShowOverlay(!showOverlay)}
                className="text-sci-secondary-400 hover:text-white transition-colors"
              >
                {showOverlay ? <Eye size={16} /> : <EyeOff size={16} />}
              </button>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <label className="text-xs text-sci-secondary-400 whitespace-nowrap flex-shrink-0 w-16">Type</label>
                <select
                  value={overlayType}
                  onChange={(e) => setOverlayType(e.target.value as OverlayType)}
                  className="flex-1 px-2 py-1 bg-sci-secondary-900 text-white text-sm rounded border border-sci-secondary-600"
                  disabled={!showOverlay}
                >
                  <option value="none">None</option>
                  <option value="area_borders">Area Borders</option>
                  <option value="area_patches">Area Patches</option>
                </select>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-xs text-sci-secondary-400 whitespace-nowrap flex-shrink-0 w-16">
                  Opacity
                </label>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={overlayAlpha * 100}
                  onChange={(e) => setOverlayAlpha(Number(e.target.value) / 100)}
                  className="flex-1"
                  disabled={!showOverlay}
                />
                <span className="text-xs text-sci-secondary-400 flex-shrink-0 w-10 text-right">
                  {(overlayAlpha * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </div>

          {/* Results Info */}
          {analysisMetadata && (
            <div className="p-3 bg-sci-secondary-800 rounded-lg border border-sci-secondary-600 flex-shrink-0">
              <h3 className="text-sm font-medium text-sci-secondary-200 mb-2">Results</h3>
              <div className="space-y-1 text-xs text-sci-secondary-400">
                <div>Visual Areas: {analysisMetadata.num_areas || 0}</div>
                {analysisMetadata.shape && analysisMetadata.shape.length === 2 && (
                  <div>Resolution: {analysisMetadata.shape[1]} x {analysisMetadata.shape[0]}</div>
                )}
                <div>Primary Layers: {analysisMetadata.primary_layers?.length || 0}</div>
                <div>Advanced Layers: {analysisMetadata.advanced_layers?.length || 0}</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default AnalysisViewport
