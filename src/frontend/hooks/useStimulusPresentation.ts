import { useCallback, useMemo } from 'react'
import { useSystemContext } from '../context/SystemContext'

interface PresentationState {
  isPresenting: boolean
  isPresentationAvailable: boolean
  presentationStatus: 'disabled' | 'ready' | 'active' | 'error'
  statusMessage?: string
}

export const useStimulusPresentation = () => {
  const { lastControlMessage, sendCommand } = useSystemContext()

  const state: PresentationState = useMemo(() => {
    if (!lastControlMessage) {
      return {
        isPresenting: false,
        isPresentationAvailable: false,
        presentationStatus: 'disabled',
        statusMessage: 'Initializing presentation system...'
      }
    }

    switch (lastControlMessage.type) {
      case 'presentation_status':
        return {
          isPresenting: lastControlMessage.status === 'active',
          isPresentationAvailable: lastControlMessage.status === 'ready' || lastControlMessage.status === 'active',
          presentationStatus: lastControlMessage.status,
          statusMessage: lastControlMessage.message
        }

      case 'presentation_started':
        return {
          isPresenting: true,
          isPresentationAvailable: true,
          presentationStatus: 'active',
          statusMessage: 'Presentation active'
        }

      case 'presentation_stopped':
        return {
          isPresenting: false,
          isPresentationAvailable: true,
          presentationStatus: 'ready',
          statusMessage: 'Presentation stopped'
        }

      case 'presentation_error':
        return {
          isPresenting: false,
          isPresentationAvailable: false,
          presentationStatus: 'error',
          statusMessage: lastControlMessage.error || 'Presentation error occurred'
        }

      default:
        return {
          isPresenting: false,
          isPresentationAvailable: false,
          presentationStatus: 'disabled',
          statusMessage: 'Initializing presentation system...'
        }
    }
  }, [lastControlMessage])

  const startPresentation = useCallback(async () => {
    await sendCommand({ type: 'start_presentation' })
  }, [sendCommand])

  const stopPresentation = useCallback(async () => {
    await sendCommand({ type: 'stop_presentation' })
  }, [sendCommand])

  const togglePresentation = useCallback(async () => {
    if (state.isPresenting) {
      await stopPresentation()
    } else {
      await startPresentation()
    }
  }, [startPresentation, stopPresentation, state.isPresenting])

  return {
    ...state,
    startPresentation,
    stopPresentation,
    togglePresentation
  }
}

export default useStimulusPresentation