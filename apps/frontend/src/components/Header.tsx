import React from 'react'
import { Video, Columns3, BrainCircuit, LucideIcon } from 'lucide-react'

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
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online': return 'status-indicator online'
      case 'error': return 'status-indicator error'
      default: return 'status-indicator offline'
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

      {/* Right Section - Status Indicators */}
      <div className="flex items-center space-x-4">
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

        {systemState.isExperimentRunning && (
          <div className="flex items-center space-x-2">
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