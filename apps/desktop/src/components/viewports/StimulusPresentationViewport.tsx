import React, { useEffect, useState, useCallback } from 'react'
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

interface StimulusPresentationViewportProps {
  className?: string
  stimulusParams?: StimulusParameters
  monitorParams?: MonitorParameters
  acquisitionParams?: AcquisitionParameters
  sendCommand?: (command: ISIMessage) => Promise<{ success: boolean; error?: string }>
  systemState?: SystemState
  lastMessage?: ControlMessage | SyncMessage | null
  isPresenting?: boolean
  onClose?: () => void
}

const StimulusPresentationViewport: React.FC<StimulusPresentationViewportProps> = ({
  className = '',
  stimulusParams,
  monitorParams,
  acquisitionParams,
  sendCommand,
  systemState,
  lastMessage,
  isPresenting = false,
  onClose
}) => {
  const [hasFrameData, setHasFrameData] = useState(false)
  const [presentationEnabled, setPresentationEnabled] = useState(false)

  // Canvas-based frame rendering
  const { canvasRef, renderFrame } = useFrameRenderer()

  // Query presentation state on mount (in case we missed the broadcast)
  // This prevents race condition where viewport mounts after acquisition already started
  useEffect(() => {
    const queryPresentationState = async () => {
      try {
        if (window.electronAPI?.sendToPython) {
          console.log('[StimulusPresentationViewport] Querying presentation state on mount')
          const result: any = await window.electronAPI.sendToPython({
            type: 'get_presentation_state'
          })

          if (result.success && result.enabled !== undefined) {
            console.log('[StimulusPresentationViewport] Query result:', {
              enabled: result.enabled,
              is_running: result.is_running
            })
            setPresentationEnabled(result.enabled)
          }
        }
      } catch (error) {
        componentLogger.error('Failed to query presentation state:', error)
      }
    }

    queryPresentationState()
  }, [])

  // Listen for shared memory frame metadata from main process
  useEffect(() => {
    const handleSharedMemoryFrame = async (metadata: SharedMemoryFrameData) => {
      // DIAGNOSTIC: Log all received frames
      console.log('[StimulusPresentationViewport] Frame received:', {
        frame_id: metadata.frame_id,
        presentationEnabled,
        width: metadata.width_px,
        height: metadata.height_px,
        data_size: metadata.data_size_bytes
      })

      // Only render frames when presentation is enabled
      if (!presentationEnabled) {
        console.warn('[StimulusPresentationViewport] Frame DROPPED - presentation not enabled')
        return
      }

      try {
        // Read actual frame data from shared memory using offset and size
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

        renderFrame(completeFrameData)
        setHasFrameData(true)
      } catch (error) {
        componentLogger.error('Failed to read frame from shared memory:', error)
      }
    }

    let unsubscribe: (() => void) | undefined
    if (window.electronAPI?.onSharedMemoryFrame) {
      unsubscribe = window.electronAPI.onSharedMemoryFrame(handleSharedMemoryFrame)
    }

    return () => {
      unsubscribe?.()
    }
  }, [renderFrame, presentationEnabled])

  // Listen for presentation stimulus state changes
  useEffect(() => {
    const handleSyncMessage = (message: any) => {
      if (message.type === 'presentation_stimulus_state') {
        console.log('[StimulusPresentationViewport] Presentation state changed:', message.enabled)
        setPresentationEnabled(message.enabled)
        componentLogger.debug(`Presentation state changed: ${message.enabled}`)

        // Clear frame data when presentation is disabled
        if (!message.enabled) {
          setHasFrameData(false)
        }
      }
    }

    // Subscribe to sync channel for presentation state changes
    let unsubscribe: (() => void) | undefined
    if (window.electronAPI?.onSyncMessage) {
      unsubscribe = window.electronAPI.onSyncMessage(handleSyncMessage)
    }

    return () => {
      unsubscribe?.()
    }
  }, [])

  // Listen for stimulus presentation stop
  useEffect(() => {
    if (lastMessage?.type === 'stimulus_presentation_stop') {
      if (onClose) {
        onClose()
      }
    }
  }, [lastMessage, onClose])

  // Handle escape key to close presentation
  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && onClose) {
        onClose()
      }
    }

    document.addEventListener('keydown', handleKeyPress)
    return () => {
      document.removeEventListener('keydown', handleKeyPress)
    }
  }, [onClose])

  // Component mounted - no logging needed (would clutter console)

  // Always render in fullscreen mode for presentation - no UI controls needed
  return (
    <div
      className="fixed inset-0 z-50 bg-black cursor-none"
      style={{
        width: '100vw',
        height: '100vh',
        overflow: 'hidden'
      }}
    >
      {presentationEnabled ? (
        <canvas
          ref={canvasRef}
          className="w-full h-full"
          style={{
            maxWidth: '100vw',
            maxHeight: '100vh',
            objectFit: 'contain'
          }}
        />
      ) : (
        <div
          style={{
            width: '100%',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#666',
            fontSize: '24px',
            fontFamily: 'monospace'
          }}
        >
          Presentation Monitor (Standby)
        </div>
      )}
    </div>
  )
}

export default StimulusPresentationViewport