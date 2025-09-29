import React, { useRef, useEffect, useState } from 'react'

interface CameraParameters {
  selected_camera: string
  camera_fps: number
  camera_width_px: number
  camera_height_px: number
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

interface CameraViewportProps {
  className?: string
  cameraParams?: CameraParameters
  sendCommand?: (command: any) => Promise<any>
  systemState?: SystemState
  lastMessage?: any
}

const CameraViewport: React.FC<CameraViewportProps> = ({
  className = '',
  cameraParams,
  sendCommand,
  systemState,
  lastMessage: _lastMessage
}) => {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamError, setStreamError] = useState<string | null>(null)
  const [stream, setStream] = useState<MediaStream | null>(null)

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
        }).catch(console.error)
      }
    } catch (error) {
      console.error('Failed to start camera stream:', error)
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
    }).catch(console.error)
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
      }).catch(console.error)
    }
  }


  // Cleanup on unmount
  // Restart camera stream when parameters change
  useEffect(() => {
    if (cameraParams?.selected_camera && systemState?.isConnected) {
      if (isStreaming) {
        // Stop current stream and restart with new parameters
        stopCameraStream()
        setTimeout(() => startCameraStream(), 100) // Small delay to ensure cleanup
      }
    }
  }, [cameraParams?.selected_camera, cameraParams?.camera_fps, cameraParams?.camera_width_px, cameraParams?.camera_height_px, systemState?.isConnected])

  useEffect(() => {
    return () => {
      stopCameraStream()
    }
  }, [])

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
              onClick={captureFrame}
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
    </div>
  )
}

export default CameraViewport