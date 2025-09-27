import React from 'react'

interface SystemState {
  isConnected: boolean
  isExperimentRunning: boolean
  currentProgress: number
  hardwareStatus: {
    camera: 'online' | 'offline' | 'error'
    display: 'online' | 'offline' | 'error'
  }
}

interface StatusBarProps {
  systemState: SystemState
  currentSession: string | null
  onEmergencyStop: () => void
}

const StatusBar: React.FC<StatusBarProps> = ({
  systemState,
  currentSession,
  onEmergencyStop
}) => {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online': return 'status-indicator online'
      case 'error': return 'status-indicator error'
      default: return 'status-indicator offline'
    }
  }

  return (
    <div className="h-12 bg-sci-secondary-800 border-b border-sci-secondary-700 flex items-center justify-between px-4">
      {/* Left Section - System Status */}
      <div className="flex items-center space-x-6">
        <div className="flex items-center space-x-2">
          <span className={getStatusColor(systemState.isConnected ? 'online' : 'offline')}></span>
          <span className="text-sm font-medium">
            {systemState.isConnected ? 'System Online' : 'System Offline'}
          </span>
        </div>

        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-1">
            <span className={getStatusColor(systemState.hardwareStatus.camera)}></span>
            <span className="text-xs text-sci-secondary-300">Camera</span>
          </div>

          <div className="flex items-center space-x-1">
            <span className={getStatusColor(systemState.hardwareStatus.display)}></span>
            <span className="text-xs text-sci-secondary-300">Display</span>
          </div>
        </div>
      </div>

      {/* Center Section - Session Info */}
      <div className="flex items-center space-x-4">
        {currentSession ? (
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-sci-success-500 rounded-full animate-pulse"></div>
            <span className="text-sm font-medium text-sci-success-400">
              Session: {currentSession}
            </span>
          </div>
        ) : (
          <span className="text-sm text-sci-secondary-400">No active session</span>
        )}

        {systemState.isExperimentRunning && (
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-sci-primary-500 rounded-full animate-pulse"></div>
            <span className="text-sm font-medium text-sci-primary-400">
              Experiment Running
            </span>
          </div>
        )}
      </div>

      {/* Right Section - Emergency Stop */}
      <div className="flex items-center space-x-4">
        <div className="text-xs text-sci-secondary-400">
          {new Date().toLocaleTimeString()}
        </div>

        <button
          onClick={onEmergencyStop}
          className="emergency-stop text-sm px-4 py-1"
          title="Emergency Stop (Ctrl+E)"
        >
          EMERGENCY STOP
        </button>
      </div>
    </div>
  )
}

export default StatusBar