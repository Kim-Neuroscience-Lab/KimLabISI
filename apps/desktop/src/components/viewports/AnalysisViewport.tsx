import React, { useState, useRef, useEffect, useCallback } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { componentLogger } from '../../utils/logger'
import type { ISIMessage, ControlMessage, SyncMessage, ListSessionsResponse, GetAnalysisResultsResponse, GetAnalysisCompositeImageResponse } from '../../types/ipc-messages'
import type { SystemState } from '../../types/shared'

interface AnalysisViewportProps {
  className?: string
  sendCommand?: (command: ISIMessage) => Promise<{ success: boolean; error?: string }>
  lastMessage?: ControlMessage | SyncMessage | null
  systemState?: SystemState
}

type SignalType = 'azimuth' | 'elevation' | 'sign' | 'magnitude' | 'phase'
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

const AnalysisViewport: React.FC<AnalysisViewportProps> = ({
  className = '',
  sendCommand,
  lastMessage
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

  // Image display
  const [compositeImageUrl, setCompositeImageUrl] = useState<string | null>(null)

  // Layer visibility and settings
  const [showAnatomical, setShowAnatomical] = useState(true)
  const [showSignal, setShowSignal] = useState(true)
  const [showOverlay, setShowOverlay] = useState(true)

  const [signalType, setSignalType] = useState<SignalType>('azimuth')
  const [overlayType, setOverlayType] = useState<OverlayType>('area_borders')

  const [anatomicalAlpha, setAnatomicalAlpha] = useState(0.5)
  const [signalAlpha, setSignalAlpha] = useState(0.8)
  const [overlayAlpha, setOverlayAlpha] = useState(1.0)

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

    componentLogger.info('Requesting composite image from backend...')

    try {
      const result = await sendCommand({
        type: 'get_analysis_composite_image',
        session_path: sessionPath,
        layers: {
          anatomical: {
            visible: showAnatomical,
            alpha: anatomicalAlpha
          },
          signal: {
            visible: showSignal,
            type: signalType,
            alpha: signalAlpha
          },
          overlay: {
            visible: showOverlay,
            type: overlayType,
            alpha: overlayAlpha
          }
        }
      } as any) as GetAnalysisCompositeImageResponse

      if (result.success && result.image_base64) {
        // Convert base64 to blob URL
        const blob = base64ToBlob(result.image_base64, 'image/png')
        const url = URL.createObjectURL(blob)

        // Revoke old URL to prevent memory leak
        if (compositeImageUrl) {
          URL.revokeObjectURL(compositeImageUrl)
        }

        setCompositeImageUrl(url)
        componentLogger.info(`Composite image loaded: ${result.width}x${result.height}`)
      } else {
        componentLogger.error('Failed to get composite image:', result.error)
      }
    } catch (error) {
      componentLogger.error('Error requesting composite image:', error)
    }
  }, [
    sendCommand,
    currentSessionPath,
    showAnatomical,
    anatomicalAlpha,
    showSignal,
    signalType,
    signalAlpha,
    showOverlay,
    overlayType,
    overlayAlpha,
    compositeImageUrl
  ])

  // Request new image when settings change
  useEffect(() => {
    if (analysisMetadata && !isAnalysisRunning) {
      requestCompositeImage()
    }
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
  ])

  // Cleanup blob URLs on unmount
  useEffect(() => {
    return () => {
      if (compositeImageUrl) {
        URL.revokeObjectURL(compositeImageUrl)
      }
    }
  }, [compositeImageUrl])

  // Start analysis on selected session
  const startAnalysis = async () => {
    if (!sendCommand || !selectedSession) return

    try {
      const result = await sendCommand({
        type: 'start_analysis',
        session_path: selectedSession
      } as any)

      if (!result.success) {
        componentLogger.error('Failed to start analysis:', result.error)
      }
    } catch (error) {
      componentLogger.error('Error starting analysis:', error)
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

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Top Controls Bar */}
      <div className="flex gap-4 mb-4 p-3 bg-sci-secondary-800 rounded-lg border border-sci-secondary-600">
        {/* Session Selection */}
        <div className="flex-1">
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

        {/* Start/Stop Analysis */}
        <div className="flex items-end">
          {!isAnalysisRunning ? (
            <button
              onClick={startAnalysis}
              disabled={!selectedSession}
              className="px-4 py-1 bg-sci-primary-600 text-white text-sm rounded hover:bg-sci-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Analyze
            </button>
          ) : (
            <button
              onClick={stopAnalysis}
              className="px-4 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700 transition-colors"
            >
              Stop
            </button>
          )}
        </div>
      </div>

      {/* Progress Bar */}
      {isAnalysisRunning && (
        <div className="mb-4 p-3 bg-sci-secondary-800 rounded-lg border border-sci-secondary-600">
          <div className="flex justify-between text-xs text-sci-secondary-400 mb-2">
            <span>{analysisStage}</span>
            <span>{(analysisProgress * 100).toFixed(0)}%</span>
          </div>
          <div className="w-full bg-sci-secondary-900 rounded-full h-2">
            <div
              className="bg-sci-primary-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${analysisProgress * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex gap-4">
        {/* Visualization Area - Now uses <img> instead of <canvas> */}
        <div className="flex-1 relative bg-black rounded-lg border border-sci-secondary-600 overflow-hidden flex items-center justify-center">
          {compositeImageUrl ? (
            <img
              ref={imageRef}
              src={compositeImageUrl}
              alt="Analysis Composite"
              className="max-w-full max-h-full object-contain"
              style={{ imageRendering: 'pixelated' }}
            />
          ) : (
            <div className="text-sci-secondary-500 text-sm">
              {isAnalysisRunning ? 'Analysis in progress...' : 'No analysis results to display'}
            </div>
          )}
        </div>

        {/* Layer Controls Panel */}
        <div className="w-64 space-y-4">
          {/* Anatomical Layer */}
          <div className="p-3 bg-sci-secondary-800 rounded-lg border border-sci-secondary-600">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-sci-secondary-200">Anatomical</span>
              <button
                onClick={() => setShowAnatomical(!showAnatomical)}
                className="text-sci-secondary-400 hover:text-white transition-colors"
              >
                {showAnatomical ? <Eye size={16} /> : <EyeOff size={16} />}
              </button>
            </div>
            <div>
              <label className="block text-xs text-sci-secondary-400 mb-1">
                Opacity: {(anatomicalAlpha * 100).toFixed(0)}%
              </label>
              <input
                type="range"
                min="0"
                max="100"
                value={anatomicalAlpha * 100}
                onChange={(e) => setAnatomicalAlpha(Number(e.target.value) / 100)}
                className="w-full"
                disabled={!showAnatomical}
              />
            </div>
          </div>

          {/* Signal Layer */}
          <div className="p-3 bg-sci-secondary-800 rounded-lg border border-sci-secondary-600">
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
              <div>
                <label className="block text-xs text-sci-secondary-400 mb-1">Type</label>
                <select
                  value={signalType}
                  onChange={(e) => setSignalType(e.target.value as SignalType)}
                  className="w-full px-2 py-1 bg-sci-secondary-900 text-white text-sm rounded border border-sci-secondary-600"
                  disabled={!showSignal}
                >
                  {/* Primary Layers */}
                  <optgroup label="Primary Results">
                    <option value="azimuth">Horizontal Retinotopy</option>
                    <option value="elevation">Vertical Retinotopy</option>
                    <option value="sign">Visual Field Sign</option>
                  </optgroup>

                  {/* Advanced Layers */}
                  {analysisMetadata && analysisMetadata.advanced_layers.length > 0 && (
                    <optgroup label="Advanced (Debug)">
                      <option value="magnitude">Response Magnitude</option>
                      <option value="phase">Phase Map</option>
                    </optgroup>
                  )}
                </select>
              </div>
              <div>
                <label className="block text-xs text-sci-secondary-400 mb-1">
                  Opacity: {(signalAlpha * 100).toFixed(0)}%
                </label>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={signalAlpha * 100}
                  onChange={(e) => setSignalAlpha(Number(e.target.value) / 100)}
                  className="w-full"
                  disabled={!showSignal}
                />
              </div>
            </div>
          </div>

          {/* Overlay Layer */}
          <div className="p-3 bg-sci-secondary-800 rounded-lg border border-sci-secondary-600">
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
              <div>
                <label className="block text-xs text-sci-secondary-400 mb-1">Type</label>
                <select
                  value={overlayType}
                  onChange={(e) => setOverlayType(e.target.value as OverlayType)}
                  className="w-full px-2 py-1 bg-sci-secondary-900 text-white text-sm rounded border border-sci-secondary-600"
                  disabled={!showOverlay}
                >
                  <option value="none">None</option>
                  <option value="area_borders">Area Borders</option>
                  <option value="area_patches">Area Patches</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-sci-secondary-400 mb-1">
                  Opacity: {(overlayAlpha * 100).toFixed(0)}%
                </label>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={overlayAlpha * 100}
                  onChange={(e) => setOverlayAlpha(Number(e.target.value) / 100)}
                  className="w-full"
                  disabled={!showOverlay}
                />
              </div>
            </div>
          </div>

          {/* Results Info */}
          {analysisMetadata && (
            <div className="p-3 bg-sci-secondary-800 rounded-lg border border-sci-secondary-600">
              <h3 className="text-sm font-medium text-sci-secondary-200 mb-2">Results</h3>
              <div className="space-y-1 text-xs text-sci-secondary-400">
                <div>Visual Areas: {analysisMetadata.num_areas}</div>
                <div>Resolution: {analysisMetadata.shape[1]} x {analysisMetadata.shape[0]}</div>
                <div>Primary Layers: {analysisMetadata.primary_layers.length}</div>
                <div>Advanced Layers: {analysisMetadata.advanced_layers.length}</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default AnalysisViewport
