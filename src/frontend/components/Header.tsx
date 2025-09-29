import React, { useEffect } from 'react'
import { Video, Columns3, BrainCircuit, BookMarked, MonitorCheck, Settings, LucideIcon } from 'lucide-react'

interface SystemState {
  isConnected: boolean
  isExperimentRunning: boolean
  currentProgress: number
  systemStatus: {
    camera: 'online' | 'offline' | 'error'
    display: 'online' | 'offline' | 'error'
    stimulus: 'online' | 'offline' | 'error'
    parameters: 'online' | 'offline' | 'error'
  }
}

interface TabConfig {
  id: 'camera' | 'stimulus' | 'analysis'
  label: string
  icon: LucideIcon
}

interface HeaderProps {
  systemState: SystemState
  activeTab: 'camera' | 'stimulus' | 'analysis' | 'startup'
  onTabChange?: (tab: 'camera' | 'stimulus' | 'analysis') => void
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
    const parametersOnline = systemState.systemStatus.parameters === 'online'
    const displayOnline = systemState.systemStatus.display === 'online'
    const cameraOnline = systemState.systemStatus.camera === 'online'
    const stimulusOnline = systemState.systemStatus.stimulus === 'online'

    const hasError = systemState.systemStatus.parameters === 'error' ||
                     systemState.systemStatus.display === 'error' ||
                     systemState.systemStatus.camera === 'error' ||
                     systemState.systemStatus.stimulus === 'error'

    // All systems must be online for OK status
    const allSystemsOnline = parametersOnline && displayOnline && cameraOnline && stimulusOnline

    // Show connecting state when not everything is online but no explicit errors
    const isConnecting = !allSystemsOnline && !hasError

    if (hasError) {
      return { text: 'ERROR', color: 'text-sci-error-400' }
    } else if (allSystemsOnline) {
      return { text: 'OK', color: 'text-sci-success-400' }
    } else if (isConnecting) {
      return { text: 'CONNECTING', color: 'text-sci-secondary-200' }
    } else {
      return { text: 'ERROR', color: 'text-sci-error-400' }
    }
  }

  const tabs: TabConfig[] = [
    { id: 'stimulus', label: 'Stimulus Generation', icon: Columns3 },
    { id: 'camera', label: 'Acquisition', icon: Video },
    { id: 'analysis', label: 'Analysis', icon: BrainCircuit }
  ]

  return (
    <div className="h-12 bg-sci-secondary-800 border-b border-sci-secondary-700 flex items-center justify-between px-2">
      {/* Left Section - Tab Navigation */}
      <div className="flex items-center">
        {tabs.map(tab => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          const isDisabled = !onTabChange
          const isClickable = onTabChange

          return (
            <button
              key={tab.id}
              onClick={isClickable ? () => onTabChange(tab.id) : undefined}
              disabled={isDisabled}
              className={`h-12 px-3 flex items-center justify-center text-sm font-medium transition-colors ${
                isActive
                  ? 'text-sci-primary-400'
                  : isDisabled
                  ? 'text-sci-secondary-600 cursor-not-allowed'
                  : 'text-sci-secondary-400 hover:text-sci-primary-400 cursor-pointer'
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
          title={`Parameters: ${systemState.systemStatus.parameters}`}
        >
          <BookMarked className={`w-4 h-4 ${getIconColor(systemState.systemStatus.parameters)}`} />
        </div>
        <div
          className="h-12 px-3 flex items-center justify-center"
          title={`Display: ${systemState.systemStatus.display}`}
        >
          <MonitorCheck className={`w-4 h-4 ${getIconColor(systemState.systemStatus.display)}`} />
        </div>
        <div
          className="h-12 px-3 flex items-center justify-center"
          title={`Camera: ${systemState.systemStatus.camera}`}
        >
          <Video className={`w-4 h-4 ${getIconColor(systemState.systemStatus.camera)}`} />
        </div>
        <div
          className="h-12 px-3 flex items-center justify-center"
          title={`Stimulus: ${systemState.systemStatus.stimulus}`}
        >
          <Columns3 className={`w-4 h-4 ${getIconColor(systemState.systemStatus.stimulus)}`} />
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