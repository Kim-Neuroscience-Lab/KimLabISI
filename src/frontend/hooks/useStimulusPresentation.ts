import { useState, useCallback, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import React from 'react'

interface MonitorParameters {
  selected_display: string
  available_displays: string[]
  monitor_distance_cm: number
  monitor_lateral_angle_deg: number
  monitor_tilt_angle_deg: number
  monitor_width_cm: number
  monitor_height_cm: number
  monitor_width_px: number
  monitor_height_px: number
  monitor_fps: number
}

interface UseStimulusPresentationOptions {
  monitorParams?: MonitorParameters
  sendCommand?: (command: any) => Promise<any>
  systemState?: any
  lastMessage?: any
}

interface PresentationWindow {
  window: Window | null
  root: any | null
  isOpen: boolean
}

const useStimulusPresentation = ({
  monitorParams,
  sendCommand,
  systemState,
  lastMessage
}: UseStimulusPresentationOptions) => {
  const [presentationWindow, setPresentationWindow] = useState<PresentationWindow>({
    window: null,
    root: null,
    isOpen: false
  })
  const [isPresenting, setIsPresenting] = useState(false)
  const [autoOpenAttempted, setAutoOpenAttempted] = useState(false)

  // Check if secondary monitor is available
  const hasSecondaryMonitor = () => {

    // Check multiple ways to detect secondary monitors
    const checks = {
      backendDetection: false,
      screenAPI: false,
      extendedScreen: false
    }

    // Method 1: Backend detection via available_displays
    if (monitorParams?.available_displays && monitorParams.available_displays.length > 1) {
      checks.backendDetection = true
    }

    // Method 2: Browser Screen API - check if extended desktop is wider than a single screen
    const primaryScreenWidth = window.screen.width
    const primaryScreenHeight = window.screen.height

    // Method 3: Modern screen.isExtended API (if available)
    if ('isExtended' in window.screen) {
      const isExtended = (window.screen as any).isExtended
      checks.extendedScreen = isExtended
    }

    const hasSecondary = checks.backendDetection || checks.screenAPI || checks.extendedScreen

    return hasSecondary
  }

  // Get optimal window position for secondary display
  const getSecondaryDisplayPosition = () => {

    if (!monitorParams) {
      // Fallback position - assume secondary monitor is to the right
      return {
        left: window.screen.width,
        top: 0,
        width: 1920,
        height: 1080
      }
    }

    // Use detected monitor dimensions if available
    const width = monitorParams.monitor_width_px > 0 ? monitorParams.monitor_width_px : 1920
    const height = monitorParams.monitor_height_px > 0 ? monitorParams.monitor_height_px : 1080

    // Strategy 1: Use the screen properties to determine extended desktop
    const primaryWidth = window.screen.width
    const primaryHeight = window.screen.height

    // Strategy 2: For the selected secondary display, position it to the right
    // This assumes most common setup: secondary monitor to the right
    const position = {
      left: primaryWidth + 50, // Small offset to ensure it's on secondary
      top: 50,
      width,
      height
    }

    return position
  }

  // Open presentation window on secondary monitor
  const openPresentationWindow = useCallback(async () => {
    if (presentationWindow.isOpen) {
      return
    }

    try {
      const position = getSecondaryDisplayPosition()

      // Create window features string for positioning
      const features = [
        `left=${position.left}`,
        `top=${position.top}`,
        `width=${position.width}`,
        `height=${position.height}`,
        'menubar=no',
        'toolbar=no',
        'location=no',
        'status=no',
        'scrollbars=no',
        'resizable=yes',
        'fullscreen=yes'
      ].join(',')


      // Open new window
      const newWindow = window.open('', 'stimulusPresentation', features)

      if (!newWindow) {
        console.error('Failed to open presentation window - popup blocked?')
        alert('Popup blocked! Please allow popups for this site and try again.\n\nTo allow popups:\n1. Click the popup blocker icon in your address bar\n2. Select "Always allow popups from this site"\n3. Try opening the presentation window again')
        return
      }

      // Additional check for popup blocker detection
      try {
        newWindow.focus()
        if (newWindow.closed) {
          console.error('Window was opened but immediately closed - popup blocked')
          alert('Popup was blocked! Please allow popups for this site and try again.')
          return
        }
      } catch (error) {
        console.error('Error focusing new window:', error)
      }

      // Set up the window document
      newWindow.document.title = 'ISI Stimulus Presentation'
      newWindow.document.head.innerHTML = `
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ISI Stimulus Presentation</title>
        <style>
          body, html {
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            overflow: hidden;
            background: black;
            font-family: system-ui, -apple-system, sans-serif;
          }
          #stimulus-presentation-root {
            width: 100%;
            height: 100%;
          }
        </style>
      `

      // Create root element for React
      const rootElement = newWindow.document.createElement('div')
      rootElement.id = 'stimulus-presentation-root'
      newWindow.document.body.appendChild(rootElement)

      // Create React root and render the presentation component
      const root = createRoot(rootElement)

      // Dynamically import and render the component
      const StimulusPresentationViewport = (await import('../components/viewports/StimulusPresentationViewport')).default

      root.render(React.createElement(StimulusPresentationViewport, {
        monitorParams,
        sendCommand,
        systemState,
        lastMessage,
        isPresenting: true,
        onClose: () => closePresentationWindow()
      }))

      // Handle window close event
      newWindow.addEventListener('beforeunload', () => {
        setPresentationWindow({
          window: null,
          root: null,
          isOpen: false
        })
        setIsPresenting(false)
      })

      // Store window and root references
      setPresentationWindow({
        window: newWindow,
        root,
        isOpen: true
      })

      setIsPresenting(true)

    } catch (error) {
      console.error('Failed to open presentation window:', error)
    }
  }, [presentationWindow.isOpen, monitorParams, sendCommand, systemState, lastMessage])

  // Close presentation window
  const closePresentationWindow = useCallback(() => {
    if (presentationWindow.window && !presentationWindow.window.closed) {
      presentationWindow.window.close()
    }

    if (presentationWindow.root) {
      presentationWindow.root.unmount()
    }

    setPresentationWindow({
      window: null,
      root: null,
      isOpen: false
    })

    setIsPresenting(false)
  }, [presentationWindow])

  // Update presentation component with new props
  const updatePresentationWindow = useCallback(async () => {
    if (presentationWindow.isOpen && presentationWindow.root) {
      try {
        // Use dynamic import instead of require for browser compatibility
        const { default: StimulusPresentationViewport } = await import('../components/viewports/StimulusPresentationViewport')

        presentationWindow.root.render(React.createElement(StimulusPresentationViewport, {
          monitorParams,
          sendCommand,
          systemState,
          lastMessage,
          isPresenting: true,
          onClose: closePresentationWindow
        }))
      } catch (error) {
        console.error('Failed to update presentation window:', error)
      }
    }
  }, [presentationWindow, monitorParams, sendCommand, systemState, lastMessage, closePresentationWindow])

  // Update presentation when props change
  useEffect(() => {
    if (presentationWindow.isOpen) {
      updatePresentationWindow()
    }
  }, [lastMessage, systemState, updatePresentationWindow])

  // Toggle presentation window
  const togglePresentationWindow = useCallback(() => {
    if (presentationWindow.isOpen) {
      closePresentationWindow()
    } else {
      openPresentationWindow()
    }
  }, [presentationWindow.isOpen, openPresentationWindow, closePresentationWindow])

  // Automatically open presentation window when secondary monitor is detected
  useEffect(() => {
    const hasSecondary = hasSecondaryMonitor()

    if (hasSecondary && !autoOpenAttempted && !presentationWindow.isOpen) {
      setAutoOpenAttempted(true)
      openPresentationWindow()
    }
  }, [monitorParams, autoOpenAttempted, presentationWindow.isOpen, openPresentationWindow])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (presentationWindow.isOpen) {
        closePresentationWindow()
      }
    }
  }, [presentationWindow.isOpen, closePresentationWindow])

  return {
    // State
    isPresenting,
    isPresentationWindowOpen: presentationWindow.isOpen,
    hasSecondaryMonitor: hasSecondaryMonitor(),

    // Actions
    openPresentationWindow,
    closePresentationWindow,
    togglePresentationWindow,

    // Window reference
    presentationWindow: presentationWindow.window
  }
}

export default useStimulusPresentation