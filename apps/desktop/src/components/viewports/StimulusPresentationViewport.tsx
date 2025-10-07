import React, { useEffect, useState, useCallback } from 'react'
import { useFrameRenderer } from '../../hooks/useFrameRenderer'
import type { ISIMessage, ControlMessage, SyncMessage } from '../../types/ipc-messages'
import type { SharedMemoryFrameData } from '../../types/electron'
import type { SystemState } from '../../types/shared'
import type {
  MonitorParameters,
  StimulusParameters,
  AcquisitionParameters
} from '../../hooks/useParameterManager'

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

  // Canvas-based frame rendering
  const { canvasRef, renderFrame } = useFrameRenderer()

  // Listen for shared memory frame metadata from main process
  useEffect(() => {
    const handleSharedMemoryFrame = async (metadata: SharedMemoryFrameData) => {
      try {
        // Read actual frame data from shared memory using offset and size
        const frameDataBuffer = await window.electronAPI.readSharedMemoryFrame(
          metadata.offset_bytes,
          metadata.data_size_bytes
        )

        // Combine metadata with frame data for rendering
        const completeFrameData = {
          ...metadata,
          frame_data: frameDataBuffer
        }

        renderFrame(completeFrameData)
        setHasFrameData(true)
      } catch (error) {
        console.error('Failed to read frame from shared memory:', error)
      }
    }

    let unsubscribe: (() => void) | undefined
    if (window.electronAPI?.onSharedMemoryFrame) {
      unsubscribe = window.electronAPI.onSharedMemoryFrame(handleSharedMemoryFrame)
    }

    return () => {
      unsubscribe?.()
    }
  }, [renderFrame])

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
      <canvas
        ref={canvasRef}
        className="w-full h-full"
        style={{
          maxWidth: '100vw',
          maxHeight: '100vh',
          objectFit: 'contain'
        }}
      />
    </div>
  )
}

export default StimulusPresentationViewport