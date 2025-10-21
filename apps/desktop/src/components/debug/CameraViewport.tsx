/**
 * CameraViewport - DEBUG/TEST Component
 *
 * This viewport uses browser WebRTC camera (navigator.mediaDevices) for manual testing
 * and debugging. It is NOT part of the production acquisition pipeline.
 *
 * The timing correlation logic here is intentionally frontend-only for development purposes.
 * Production acquisition uses AcquisitionViewport which interfaces with the backend
 * Python camera system.
 */

import React, { useRef, useEffect, useState } from 'react'
import { componentLogger } from '../../utils/logger'
import type { ISIMessage, ControlMessage, SyncMessage } from '../../types/ipc-messages'
import type { SystemState, CameraParameters } from '../../types/shared'

interface TimingCorrelation {
  cameraTimestamp: number
  stimulusFrameId?: number
  stimulusTimestamp?: number
  timeDifference?: number
  correlationStatus: 'pending' | 'matched' | 'timeout'
}

interface CameraViewportProps {
  className?: string
  cameraParams?: CameraParameters
  sendCommand?: (command: ISIMessage) => Promise<{ success: boolean; error?: string }>
  systemState?: SystemState
  lastMessage?: ControlMessage | SyncMessage | null
}

const CameraViewport: React.FC<CameraViewportProps> = ({
  className = '',
  cameraParams,
  sendCommand,
  systemState,
  lastMessage
}) => {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamError, setStreamError] = useState<string | null>(null)
  const [stream, setStream] = useState<MediaStream | null>(null)

  // Hardware timing correlation state
  const [recentStimulusFrames, setRecentStimulusFrames] = useState<Array<{
    frameId: number
    timestamp: number
    direction: string
    frameIndex: number
  }>>([])
  const [timingCorrelations, setTimingCorrelations] = useState<TimingCorrelation[]>([])
  const [lastCorrelation, setLastCorrelation] = useState<TimingCorrelation | null>(null)

  const startCameraStream = async () => {
    if (!cameraParams?.selected_camera) {
      setStreamError('No camera selected')
      return
    }

    try {
      setStreamError(null)

      // Get available camera devices and find the one that matches the selected camera name
      const devices = await navigator.mediaDevices.enumerateDevices()
      const videoDevices = devices.filter(device => device.kind === 'videoinput')

      // Find device by label matching the selected camera name
      const selectedDevice = videoDevices.find(device =>
        device.label.includes(cameraParams.selected_camera) ||
        cameraParams.selected_camera.includes(device.label)
      )

      // Request camera access with specified parameters
      const constraints: MediaStreamConstraints = {
        video: selectedDevice ? {
          deviceId: { exact: selectedDevice.deviceId },
          frameRate: cameraParams.camera_fps > 0 ? cameraParams.camera_fps : 30,
          width: cameraParams.camera_width_px > 0 ? cameraParams.camera_width_px : undefined,
          height: cameraParams.camera_height_px > 0 ? cameraParams.camera_height_px : undefined
        } : {
          // Fallback to any camera if we can't find the specific one
          frameRate: cameraParams.camera_fps > 0 ? cameraParams.camera_fps : 30
        }
      }

      const mediaStream = await navigator.mediaDevices.getUserMedia(constraints)

      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream


        videoRef.current.play()
        setStream(mediaStream)
        setIsStreaming(true)

        // Notify backend that camera stream started
        sendCommand?.({
          type: 'camera_stream_started',
          camera_name: cameraParams.selected_camera
        }).catch((error: unknown) => componentLogger.error('Error:', error))
      }
    } catch (error) {
      componentLogger.error('Failed to start camera stream:', error)
      setStreamError(`Failed to access camera: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  const stopCameraStream = () => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop())
      setStream(null)
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null
    }

    setIsStreaming(false)

    // Notify backend that camera stream stopped
    sendCommand?.({
      type: 'camera_stream_stopped',
      camera_name: cameraParams?.selected_camera
    }).catch((error: unknown) => componentLogger.error('Error:', error))
  }


  const captureFrame = () => {
    if (!videoRef.current || !isStreaming) return

    const video = videoRef.current
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight

    const ctx = canvas.getContext('2d')
    if (ctx) {
      ctx.drawImage(video, 0, 0)

      // Convert to blob and download
      canvas.toBlob((blob) => {
        if (blob) {
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = `camera_capture_${new Date().toISOString().replace(/[:.]/g, '-')}.png`
          document.body.appendChild(a)
          a.click()
          document.body.removeChild(a)
          URL.revokeObjectURL(url)
        }
      })

      // Also notify backend of capture
      sendCommand?.({
        type: 'camera_capture',
        camera_name: cameraParams?.selected_camera,
        timestamp: Date.now()
      }).catch((error: unknown) => componentLogger.error('Error:', error))
    }
  }


  // Cleanup on unmount
  // Restart camera stream when parameters change
  useEffect(() => {
    if (cameraParams?.selected_camera && systemState?.isConnected) {
      if (isStreaming) {
        // Stop current stream and restart with new parameters
        stopCameraStream()
        // Queue restart using microtask to ensure cleanup completes
        queueMicrotask(() => startCameraStream())
      }
    }
  }, [cameraParams?.selected_camera, cameraParams?.camera_fps, cameraParams?.camera_width_px, cameraParams?.camera_height_px, systemState?.isConnected])

  useEffect(() => {
    return () => {
      stopCameraStream()
    }
  }, [])

  // Listen for stimulus frame events to track timing correlation
  useEffect(() => {
    if (!lastMessage) return

    // Track stimulus frame events for timing correlation
    if (lastMessage.type === 'stimulus_frame_presented') {
      const frameData = {
        frameId: lastMessage.frame_id,
        timestamp: lastMessage.timestamp_us || Date.now() * 1000, // Convert to microseconds if needed
        direction: lastMessage.direction,
        frameIndex: lastMessage.frame_index
      }

      setRecentStimulusFrames(prev => {
        // Keep only recent frames (last 10 seconds worth)
        const cutoffTime = frameData.timestamp - 10_000_000 // 10 seconds in microseconds
        const filtered = prev.filter(frame => frame.timestamp > cutoffTime)
        return [...filtered, frameData].slice(-100) // Keep max 100 frames
      })

      componentLogger.debug('CameraViewport: Tracked stimulus frame for correlation:', frameData)
    }
  }, [lastMessage])

  // Capture frame with timing correlation
  const captureFrameWithCorrelation = () => {
    if (!videoRef.current || !isStreaming) return

    const captureTimestamp = performance.now() * 1000 // Convert to microseconds
    const video = videoRef.current
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight

    const ctx = canvas.getContext('2d')
    if (ctx) {
      ctx.drawImage(video, 0, 0)

      // Convert to blob and download
      canvas.toBlob((blob) => {
        if (blob) {
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = `camera_capture_${new Date().toISOString().replace(/[:.]/g, '-')}.png`
          document.body.appendChild(a)
          a.click()
          document.body.removeChild(a)
          URL.revokeObjectURL(url)
        }
      })

      // Find matching stimulus frame for correlation
      const correlationWindow = 50_000 // 50ms in microseconds
      const matchingFrame = recentStimulusFrames.find(frame =>
        Math.abs(frame.timestamp - captureTimestamp) < correlationWindow
      )

      const correlation: TimingCorrelation = {
        cameraTimestamp: captureTimestamp,
        stimulusFrameId: matchingFrame?.frameId,
        stimulusTimestamp: matchingFrame?.timestamp,
        timeDifference: matchingFrame ? captureTimestamp - matchingFrame.timestamp : undefined,
        correlationStatus: matchingFrame ? 'matched' : 'timeout'
      }

      setLastCorrelation(correlation)
      setTimingCorrelations(prev => [...prev.slice(-19), correlation]) // Keep last 20 correlations

      componentLogger.debug('CameraViewport: Frame capture correlation:', correlation)

      // Notify backend of capture with correlation data
      sendCommand?.({
        type: 'camera_capture',
        camera_name: cameraParams?.selected_camera,
        timestamp: captureTimestamp,
        correlation: correlation
      }).catch((error: unknown) => componentLogger.error('Error:', error))
    }
  }

  return (
    <div className={`flex flex-col h-full min-h-0 ${className}`}>
      {/* Camera Feed Container */}
      <div className="flex-1 relative bg-black border border-sci-secondary-600 rounded-lg overflow-hidden min-h-0 w-full h-0">
        <video
          ref={videoRef}
          className="absolute inset-0 w-full h-full object-contain"
          autoPlay
          muted
          playsInline
          style={{
            maxWidth: '100%',
            maxHeight: '100%',
            width: '100%',
            height: '100%'
          }}
        />


        {/* Error State */}
        {streamError && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/80">
            <div className="text-center text-red-400">
              <div className="text-4xl mb-2">⚠️</div>
              <div className="text-lg mb-2">Camera Error</div>
              <div className="text-sm">{streamError}</div>
            </div>
          </div>
        )}

        {/* No Camera State */}
        {!cameraParams?.selected_camera && !streamError && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center text-sci-secondary-400">
              <div className="text-6xl mb-4">📷</div>
              <div className="text-lg">No Camera Selected</div>
              <div className="text-sm mt-2">Select a camera in the control panel</div>
            </div>
          </div>
        )}
      </div>

      {/* Control Buttons */}
      <div className="flex gap-2 mt-4 justify-center">
        {!isStreaming ? (
          <button
            onClick={startCameraStream}
            disabled={!cameraParams?.selected_camera}
            className="px-4 py-2 bg-sci-primary-600 text-white rounded text-sm font-medium hover:bg-sci-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Start Camera
          </button>
        ) : (
          <>
            <button
              onClick={stopCameraStream}
              className="px-4 py-2 bg-red-600 text-white rounded text-sm font-medium hover:bg-red-700 transition-colors"
            >
              Stop Camera
            </button>
            <button
              onClick={captureFrameWithCorrelation}
              className="px-4 py-2 bg-sci-accent-600 text-white rounded text-sm font-medium hover:bg-sci-accent-700 transition-colors"
            >
              Capture Frame
            </button>
          </>
        )}
      </div>

      {/* Status Info */}
      <div className="text-xs text-sci-secondary-400 text-center mt-2">
        {cameraParams?.selected_camera ? (
          isStreaming ? (
            `Camera: ${cameraParams.selected_camera} • Active`
          ) : (
            `Camera: ${cameraParams.selected_camera} • Ready`
          )
        ) : (
          'No camera configured'
        )}
      </div>

      {/* Timing Correlation Display */}
      {isStreaming && (
        <div className="mt-4 p-3 bg-sci-secondary-800 border border-sci-secondary-600 rounded-lg">
          <div className="text-sm font-medium text-sci-secondary-200 mb-2">
            Hardware Timing Correlation
          </div>

          {/* Last Correlation */}
          {lastCorrelation && (
            <div className="mb-3 p-2 bg-sci-secondary-900 rounded">
              <div className="text-xs text-sci-secondary-300 mb-1">Last Capture:</div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-sci-secondary-400">Status:</span>
                  <span className={`ml-1 font-medium ${
                    lastCorrelation.correlationStatus === 'matched'
                      ? 'text-sci-success-400'
                      : 'text-sci-error-400'
                  }`}>
                    {lastCorrelation.correlationStatus.toUpperCase()}
                  </span>
                </div>
                <div>
                  <span className="text-sci-secondary-400">Frame ID:</span>
                  <span className="ml-1 text-sci-secondary-200">
                    {lastCorrelation.stimulusFrameId || 'N/A'}
                  </span>
                </div>
                {lastCorrelation.timeDifference !== undefined && (
                  <div className="col-span-2">
                    <span className="text-sci-secondary-400">Time Diff:</span>
                    <span className={`ml-1 font-medium ${
                      Math.abs(lastCorrelation.timeDifference) < 16_667 // < 1 frame at 60fps
                        ? 'text-sci-success-400'
                        : Math.abs(lastCorrelation.timeDifference) < 33_333 // < 2 frames at 60fps
                        ? 'text-yellow-400'
                        : 'text-sci-error-400'
                    }`}>
                      {(lastCorrelation.timeDifference / 1000).toFixed(2)}ms
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Recent Stimulus Frames */}
          <div className="mb-2">
            <div className="text-xs text-sci-secondary-400 mb-1">
              Recent Stimulus Frames: {recentStimulusFrames.length}
            </div>
            {recentStimulusFrames.length === 0 && (
              <div className="text-xs text-sci-secondary-500 italic">
                No stimulus frames detected
              </div>
            )}
            {recentStimulusFrames.slice(-3).map((frame, index) => (
              <div key={`${frame.frameId}-${frame.timestamp}`} className="text-xs text-sci-secondary-300">
                Frame {frame.frameId} ({frame.direction}) • {((Date.now() * 1000 - frame.timestamp) / 1000000).toFixed(1)}s ago
              </div>
            ))}
          </div>

          {/* Correlation Statistics - Debug only, intentionally frontend-calculated */}
          {timingCorrelations.length > 0 && (() => {
            const matched = timingCorrelations.filter(c => c.correlationStatus === 'matched').length
            const timeout = timingCorrelations.filter(c => c.correlationStatus === 'timeout').length
            const matchRate = ((matched / timingCorrelations.length) * 100).toFixed(0)

            return (
              <div className="text-xs">
                <div className="text-sci-secondary-400 mb-1">
                  Recent Correlations: {timingCorrelations.length}
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <span className="text-sci-success-400">{matched}</span>
                    <span className="text-sci-secondary-500 ml-1">matched</span>
                  </div>
                  <div>
                    <span className="text-sci-error-400">{timeout}</span>
                    <span className="text-sci-secondary-500 ml-1">timeout</span>
                  </div>
                  <div>
                    <span className="text-sci-secondary-300">{matchRate}%</span>
                    <span className="text-sci-secondary-500 ml-1">rate</span>
                  </div>
                </div>
              </div>
            )
          })()}
        </div>
      )}
    </div>
  )
}

export default CameraViewport