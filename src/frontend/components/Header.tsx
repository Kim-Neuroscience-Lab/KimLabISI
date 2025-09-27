import React from 'react'
import { Video, Columns3, BrainCircuit, Cable, MonitorCheck, LucideIcon } from 'lucide-react'

interface SystemState {
  isConnected: boolean
  isExperimentRunning: boolean
  currentProgress: number
  hardwareStatus: {
    camera: 'online' | 'offline' | 'error'
    display: 'online' | 'offline' | 'error'
  }
}

interface TabConfig {
  id: 'camera' | 'stimulus' | 'analysis'
  label: string
  icon: LucideIcon
}

interface HeaderProps {
  systemState: SystemState
  activeTab: 'camera' | 'stimulus' | 'analysis'
  onTabChange: (tab: 'camera' | 'stimulus' | 'analysis') => void
}

const Header: React.FC<HeaderProps> = ({
  systemState,
  activeTab,
  onTabChange
}) => {
  const getIconColor = (status: string) => {
    switch (status) {
      case 'online': return 'text-sci-success-400'
      case 'error': return 'text-sci-error-400'
      default: return 'text-sci-secondary-500'
    }
  }

  const getOverallStatus = () => {
    const backendOnline = systemState.isConnected
    const displayOnline = systemState.hardwareStatus.display === 'online'
    const cameraOnline = systemState.hardwareStatus.camera === 'online'

    const hasError = systemState.hardwareStatus.display === 'error' ||
                     systemState.hardwareStatus.camera === 'error'

    if (hasError) {
      return { text: 'ERROR', color: 'text-sci-error-400' }
    } else if (backendOnline && displayOnline && cameraOnline) {
      return { text: 'OK', color: 'text-sci-success-400' }
    } else {
      return { text: 'ERROR', color: 'text-sci-error-400' }
    }
  }

  const tabs: TabConfig[] = [
    { id: 'camera', label: 'Camera Feed', icon: Video },
    { id: 'stimulus', label: 'Stimulus Feed', icon: Columns3 },
    { id: 'analysis', label: 'Analysis', icon: BrainCircuit }
  ]

  return (
    <div className="h-12 bg-sci-secondary-800 border-b border-sci-secondary-700 flex items-center justify-between px-2">
      {/* Left Section - Tab Navigation */}
      <div className="flex items-center">
        {tabs.map(tab => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id

          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`h-12 px-3 flex items-center justify-center text-sm font-medium transition-colors ${
                isActive
                  ? 'text-sci-primary-400'
                  : 'text-sci-secondary-400 hover:text-sci-primary-400'
              }`}
            >
              <Icon className="w-4 h-4" />
            </button>
          )
        })}

        {/* Active Tab Label */}
        <div className="ml-4">
          <h3 className="text-sm font-semibold text-sci-secondary-200">
            {tabs.find(tab => tab.id === activeTab)?.label}
          </h3>
        </div>
      </div>

      {/* Spacer */}
      <div className="flex-1"></div>

      {/* Right Section - Status Icons */}
      <div className="flex items-center">
        {/* Status Label first - mirrored layout */}
        <div className="mr-4">
          <h3 className="text-sm font-semibold text-sci-secondary-200">
            {getOverallStatus().text}
          </h3>
        </div>

        {/* Status Icons - mirror the tab icon structure */}
        <div
          className="h-12 px-3 flex items-center justify-center"
          title={`Backend: ${systemState.isConnected ? 'Online' : 'Offline'}`}
        >
          <Cable className={`w-4 h-4 ${getIconColor(systemState.isConnected ? 'online' : 'offline')}`} />
        </div>
        <div
          className="h-12 px-3 flex items-center justify-center"
          title={`Display: ${systemState.hardwareStatus.display}`}
        >
          <MonitorCheck className={`w-4 h-4 ${getIconColor(systemState.hardwareStatus.display)}`} />
        </div>
        <div
          className="h-12 px-3 flex items-center justify-center"
          title={`Camera: ${systemState.hardwareStatus.camera}`}
        >
          <Video className={`w-4 h-4 ${getIconColor(systemState.hardwareStatus.camera)}`} />
        </div>

        {systemState.isExperimentRunning && (
          <div className="flex items-center space-x-2 ml-4">
            <div className="w-2 h-2 bg-sci-primary-500 rounded-full animate-pulse"></div>
            <span className="text-sm font-medium text-sci-primary-400">
              Experiment Running
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

export default Header