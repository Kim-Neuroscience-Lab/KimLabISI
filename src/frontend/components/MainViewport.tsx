import React, { useState, useEffect } from 'react'
import Header from './Header'
import CameraViewport from './viewports/CameraViewport'
import StartupViewport from './viewports/StartupViewport'
import StimulusGenerationViewport from './viewports/StimulusGenerationViewport'
import { useParameterManager } from '../hooks/useParameterManager'

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
  lastMessage?: any
  initState?: string
  connectionError?: string
  startupProgress?: any
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
  lastMessage,
  initState,
  connectionError,
  startupProgress
}) => {
  const [activeTab, setActiveTab] = useState<'camera' | 'stimulus' | 'analysis'>('camera')
  const [showStartupPause, setShowStartupPause] = useState(false)

  // Use parameter manager to get all parameters
  const {
    cameraParams,
    stimulusParams,
    monitorParams,
    acquisitionParams
  } = useParameterManager(sendCommand, lastMessage)

  // Handle startup completion pause
  useEffect(() => {
    if (initState === 'system-ready' && !showStartupPause) {
      setShowStartupPause(true)

      // Show completed startup stages for 1 second before transitioning
      const pauseTimer = setTimeout(() => {
        setShowStartupPause(false)
      }, 1000)

      return () => clearTimeout(pauseTimer)
    }
  }, [initState])

  const renderCameraView = () => (
    <CameraViewport
      className="flex-1"
      cameraParams={cameraParams}
      sendCommand={sendCommand}
      systemState={systemState}
      lastMessage={lastMessage}
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
      lastMessage={lastMessage}
    />
  )

  const renderAnalysisView = () => (
    <div className="flex-1 flex items-center justify-center bg-sci-secondary-900 rounded-lg border border-sci-secondary-700">
      <div className="text-center">
        <div className="w-16 h-16 bg-sci-success-600 rounded-lg mx-auto mb-4 flex items-center justify-center">
          <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        </div>
        <h3 className="text-lg font-medium text-sci-secondary-200 mb-2">Analysis Results</h3>
        <p className="text-sci-secondary-400">Real-time signal analysis and retinotopic mapping</p>
      </div>
    </div>
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
        {initState !== 'system-ready' || showStartupPause ? (
          <StartupViewport
            className="flex-1"
            initState={showStartupPause ? 'system-ready' : initState}
            connectionError={connectionError}
            startupProgress={startupProgress}
          />
        ) : (
          <>
            {activeTab === 'camera' && renderCameraView()}
            {activeTab === 'stimulus' && renderStimulusPreview()}
            {activeTab === 'analysis' && renderAnalysisView()}
          </>
        )}
      </div>
    </div>
  )
}

export default MainViewport