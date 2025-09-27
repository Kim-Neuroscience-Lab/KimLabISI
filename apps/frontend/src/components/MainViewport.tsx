import React, { useState } from 'react'
import Header from './Header'

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
  }
}) => {
  const [activeTab, setActiveTab] = useState<'camera' | 'stimulus' | 'analysis'>('camera')

  const renderCameraView = () => (
    <div className="flex-1 flex items-center justify-center bg-sci-secondary-900 rounded-lg border border-sci-secondary-700">
      {systemState.isConnected ? (
        <div className="text-center">
          <div className="w-16 h-16 bg-sci-primary-600 rounded-lg mx-auto mb-4 flex items-center justify-center">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-sci-secondary-200 mb-2">Camera Feed</h3>
          <p className="text-sci-secondary-400">Camera feed will appear here during experiments</p>
        </div>
      ) : (
        <div className="text-center">
          <div className="w-16 h-16 bg-sci-secondary-700 rounded-lg mx-auto mb-4 flex items-center justify-center">
            <svg className="w-8 h-8 text-sci-secondary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728L5.636 5.636m12.728 12.728L5.636 5.636" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-sci-secondary-400 mb-2">System Offline</h3>
          <p className="text-sci-secondary-500">Connect to system to view camera feed</p>
        </div>
      )}
    </div>
  )

  const renderStimulusPreview = () => (
    <div className="flex-1 flex items-center justify-center bg-sci-secondary-900 rounded-lg border border-sci-secondary-700">
      <div className="text-center">
        <div className="w-16 h-16 bg-sci-accent-600 rounded-lg mx-auto mb-4 flex items-center justify-center">
          <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
          </svg>
        </div>
        <h3 className="text-lg font-medium text-sci-secondary-200 mb-2">Stimulus Feed</h3>
        <p className="text-sci-secondary-400">
          {systemState.isExperimentRunning ? 'Live stimulus display' : 'Preview stimulus patterns'}
        </p>

        {systemState.isExperimentRunning && (
          <div className="mt-4 space-y-2">
            <div className="w-64 h-48 mx-auto bg-black rounded border border-sci-secondary-600 relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-r from-white to-black opacity-30 animate-pulse"></div>
              <div className="absolute bottom-2 left-2 text-xs text-white bg-black bg-opacity-50 px-2 py-1 rounded">
                Drifting Bar Stimulus
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
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
        {activeTab === 'camera' && renderCameraView()}
        {activeTab === 'stimulus' && renderStimulusPreview()}
        {activeTab === 'analysis' && renderAnalysisView()}
      </div>
    </div>
  )
}

export default MainViewport