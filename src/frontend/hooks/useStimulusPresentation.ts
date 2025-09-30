import { useState, useEffect, useCallback } from 'react'

interface PresentationState {
  isPresenting: boolean
  isPresentationAvailable: boolean
  presentationStatus: 'disabled' | 'ready' | 'active' | 'error'
  statusMessage?: string
}

interface UseStimulusPresentationOptions {
  sendCommand?: (command: any) => Promise<any>
  lastMessage?: any
}

const useStimulusPresentation = ({
  sendCommand,
  lastMessage
}: UseStimulusPresentationOptions) => {
  const [presentationState, setPresentationState] = useState<PresentationState>({
    isPresenting: false,
    isPresentationAvailable: false,
    presentationStatus: 'disabled',
    statusMessage: 'Initializing presentation system...'
  })

  // Handle backend presentation messages
  useEffect(() => {
    if (!lastMessage) return

    switch (lastMessage.type) {
      case 'presentation_status':
        setPresentationState(prev => ({
          ...prev,
          presentationStatus: lastMessage.status,
          isPresentationAvailable: lastMessage.status === 'ready' || lastMessage.status === 'active',
          statusMessage: lastMessage.message
        }))
        break

      case 'presentation_started':
        setPresentationState(prev => ({
          ...prev,
          isPresenting: true,
          presentationStatus: 'active',
          statusMessage: 'Presentation active'
        }))
        break

      case 'presentation_stopped':
        setPresentationState(prev => ({
          ...prev,
          isPresenting: false,
          presentationStatus: 'ready',
          statusMessage: 'Presentation stopped'
        }))
        break

      case 'presentation_error':
        setPresentationState(prev => ({
          ...prev,
          isPresenting: false,
          presentationStatus: 'error',
          statusMessage: lastMessage.error || 'Presentation error occurred'
        }))
        break
    }
  }, [lastMessage])

  // Request presentation start from backend
  const startPresentation = useCallback(async () => {
    if (!sendCommand) {
      throw new Error('Send command function not available')
    }

    try {
      await sendCommand({
        type: 'start_presentation'
      })
    } catch (error) {
      console.error('Failed to start presentation:', error)
      throw error
    }
  }, [sendCommand])

  // Request presentation stop from backend
  const stopPresentation = useCallback(async () => {
    if (!sendCommand) {
      throw new Error('Send command function not available')
    }

    try {
      await sendCommand({
        type: 'stop_presentation'
      })
    } catch (error) {
      console.error('Failed to stop presentation:', error)
      throw error
    }
  }, [sendCommand])

  // Toggle presentation state
  const togglePresentation = useCallback(async () => {
    if (presentationState.isPresenting) {
      await stopPresentation()
    } else {
      await startPresentation()
    }
  }, [presentationState.isPresenting, startPresentation, stopPresentation])

  return {
    // State
    isPresenting: presentationState.isPresenting,
    isPresentationAvailable: presentationState.isPresentationAvailable,
    presentationStatus: presentationState.presentationStatus,
    statusMessage: presentationState.statusMessage,

    // Actions - backend coordinated
    startPresentation,
    stopPresentation,
    togglePresentation
  }
}

export default useStimulusPresentation