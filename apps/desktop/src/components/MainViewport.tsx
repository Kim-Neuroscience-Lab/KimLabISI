import React, { useState, useEffect, useMemo } from 'react'
import Header from './Header'
import AcquisitionViewport from './viewports/AcquisitionViewport'
import StartupViewport from './viewports/StartupViewport'
import StimulusGenerationViewport from './viewports/StimulusGenerationViewport'
import AnalysisViewport from './viewports/AnalysisViewport'
import useStimulusPresentation from '../hooks/useStimulusPresentation'
import { useParameters } from '../hooks/useParameters'
import type { ISIMessage } from '../types/ipc-messages'
import type { HealthMessage } from '../types/electron'

interface MainViewportProps {
  sendCommand?: (command: ISIMessage) => Promise<{ success: boolean; error?: string }>
  parameterState: ReturnType<typeof useParameters>
  systemStateStr?: string
  displayText?: string
  isReady?: boolean
  isError?: boolean
  errorMessage?: string | null
  connectionError?: string
  healthSnapshot?: HealthMessage | null
  isExperimentRunning?: boolean
  currentProgress?: number
}

const MainViewport: React.FC<MainViewportProps> = ({
  sendCommand,
  parameterState,
  systemStateStr = 'initializing',
  displayText = 'Initializing...',
  isReady = false,
  isError = false,
  errorMessage = null,
  connectionError,
  healthSnapshot,
  isExperimentRunning = false,
  currentProgress = 0
}) => {
  const [activeTab, setActiveTab] = useState<'camera' | 'stimulus' | 'analysis'>('stimulus')
  const [showStartupPause, setShowStartupPause] = useState(false)

  // Shared frame display state across all viewports
  const [sharedDirection, setSharedDirection] = useState<'LR' | 'RL' | 'TB' | 'BT'>('LR')
  const [sharedFrameIndex, setSharedFrameIndex] = useState(0)
  const [sharedShowBarMask, setSharedShowBarMask] = useState(false)

  // Use parameter manager to get all parameters
  const {
    cameraParams,
    stimulusParams,
    monitorParams,
    acquisitionParams
  } = parameterState

  const systemContext = useMemo(() => ({
    isConnected: isReady,
    isExperimentRunning,
    currentProgress,
    hardwareStatus: healthSnapshot?.hardware_status ?? {},
  }), [isReady, isExperimentRunning, healthSnapshot, currentProgress])

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
    systemState: systemContext
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
    <AcquisitionViewport
      className="flex-1"
      cameraParams={cameraParams}
      stimulusParams={stimulusParams}
      monitorParams={monitorParams}
      acquisitionParams={acquisitionParams}
      sendCommand={sendCommand}
      systemState={systemContext}
      sharedDirection={sharedDirection}
      sharedFrameIndex={sharedFrameIndex}
      sharedShowBarMask={sharedShowBarMask}
    />
  )

  const renderStimulusGeneration = () => (
    <StimulusGenerationViewport
      className="flex-1"
      stimulusParams={stimulusParams}
      monitorParams={monitorParams}
      acquisitionParams={acquisitionParams}
      sendCommand={sendCommand}
      systemState={systemContext}
      sharedDirection={sharedDirection}
      sharedFrameIndex={sharedFrameIndex}
      sharedShowBarMask={sharedShowBarMask}
      onDirectionChange={setSharedDirection}
      onFrameIndexChange={setSharedFrameIndex}
      onShowBarMaskChange={setSharedShowBarMask}
    />
  )

  const renderAnalysisView = () => (
    <AnalysisViewport
      className="flex-1"
      systemState={systemContext}
      sendCommand={sendCommand}
    />
  )

  return (
    <div className="flex-1 flex flex-col">
      {/* Header with Navigation and Status */}
      <Header
        activeTab={activeTab}
        onTabChange={setActiveTab}
        isExperimentRunning={isExperimentRunning}
        healthSnapshot={healthSnapshot}
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