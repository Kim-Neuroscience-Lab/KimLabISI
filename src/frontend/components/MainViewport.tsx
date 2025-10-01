import React, { useState, useEffect } from 'react'
import Header from './Header'
import CameraViewport from './viewports/CameraViewport'
import StartupViewport from './viewports/StartupViewport'
import StimulusGenerationViewport from './viewports/StimulusGenerationViewport'
import AnalysisViewport from './viewports/AnalysisViewport'
import useStimulusPresentation from '../hooks/useStimulusPresentation'
import { useParameters } from '../hooks/useParameters'

interface SystemState {
  isConnected: boolean
  isExperimentRunning: boolean
  currentProgress: number
  hardwareStatus: {
    camera: 'online' | 'offline' | 'error'
    display: 'online' | 'offline' | 'error'
  }
}

interface MainViewportProps {
  systemState: SystemState
  sendCommand?: (command: any) => Promise<any>
  parameterState: ReturnType<typeof useParameters>
  // New unified state from useISISystem
  systemStateStr?: string
  displayText?: string
  isReady?: boolean
  isError?: boolean
  errorMessage?: string | null
  connectionError?: string
}

const MainViewport: React.FC<MainViewportProps> = ({
  systemState = {
    isConnected: false,
    isExperimentRunning: false,
    currentProgress: 0,
    hardwareStatus: {
      camera: 'offline',
      display: 'offline'
    }
  },
  sendCommand,
  parameterState,
  systemStateStr = 'initializing',
  displayText = 'Initializing...',
  isReady = false,
  isError = false,
  errorMessage = null,
  connectionError
}) => {
  const [activeTab, setActiveTab] = useState<'camera' | 'stimulus' | 'analysis'>('stimulus')
  const [showStartupPause, setShowStartupPause] = useState(false)

  // Use parameter manager to get all parameters
  const {
    cameraParams,
    stimulusParams,
    monitorParams,
    acquisitionParams
  } = parameterState

  // Use stimulus presentation hook for second window functionality
  const {
    isPresenting,
    isPresentationWindowOpen,
    hasSecondaryMonitor,
    openPresentationWindow,
    closePresentationWindow,
    togglePresentationWindow
  } = useStimulusPresentation({
    monitorParams,
    sendCommand,
    systemState
  })

  // Handle startup completion pause
  useEffect(() => {
    if (systemStateStr === 'system-ready' && !showStartupPause) {
      setShowStartupPause(true)

      // Show completed startup stages for 1 second before transitioning
      const pauseTimer = setTimeout(() => {
        setShowStartupPause(false)
      }, 1000)

      return () => clearTimeout(pauseTimer)
    }
  }, [systemStateStr, showStartupPause])

  const renderCameraView = () => (
    <CameraViewport
      className="flex-1"
      cameraParams={cameraParams}
      sendCommand={sendCommand}
      systemState={systemState}
    />
  )

  const renderStimulusGeneration = () => (
    <StimulusGenerationViewport
      className="flex-1"
      stimulusParams={stimulusParams}
      monitorParams={monitorParams}
      acquisitionParams={acquisitionParams}
      sendCommand={sendCommand}
      systemState={systemState}
    />
  )

  const renderAnalysisView = () => (
    <AnalysisViewport
      className="flex-1"
      systemState={systemState}
      sendCommand={sendCommand}
    />
  )

  return (
    <div className="flex-1 flex flex-col">
      {/* Header with Navigation and Status */}
      <Header
        systemState={systemState}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      {/* Tab Content */}
      <div className="flex-1 p-4">
        {!isReady || showStartupPause ? (
          <StartupViewport
            className="flex-1"
            systemState={systemStateStr}
            displayText={displayText}
            isReady={isReady}
            isError={isError}
            errorMessage={errorMessage}
            connectionError={connectionError}
          />
        ) : (
          <>
            {activeTab === 'camera' && renderCameraView()}
            {activeTab === 'stimulus' && renderStimulusGeneration()}
            {activeTab === 'analysis' && renderAnalysisView()}
          </>
        )}
      </div>
    </div>
  )
}

export default MainViewport