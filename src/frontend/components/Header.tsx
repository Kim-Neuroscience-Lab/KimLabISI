import React from 'react'
import { Video, Columns3, BrainCircuit, BookMarked, MonitorCheck, Settings, Cable, LucideIcon } from 'lucide-react'
import { useHealthMonitor } from '../hooks/useHealthMonitor'

interface TabConfig {
  id: 'camera' | 'stimulus' | 'analysis'
  label: string
  icon: LucideIcon
}

interface HeaderProps {
  activeTab: 'camera' | 'stimulus' | 'analysis' | 'startup'
  onTabChange?: (tab: 'camera' | 'stimulus' | 'analysis') => void
  lastMessage?: any
  isExperimentRunning?: boolean
}

const Header: React.FC<HeaderProps> = ({
  activeTab,
  onTabChange,
  lastMessage,
  isExperimentRunning = false
}) => {
  const { healthState, isHealthy, hasErrors, isInitializing } = useHealthMonitor({ lastMessage })

  const getIconColor = (status: string) => {
    switch (status) {
      case 'online': return 'text-sci-success-400'
      case 'error': return 'text-sci-error-400'
      case 'degraded': return 'text-yellow-400'
      default: return 'text-sci-secondary-500'
    }
  }

  const getOverallStatus = () => {
    switch (healthState.overall.status) {
      case 'healthy':
        return { text: 'OK', color: 'text-sci-success-400' }
      case 'error':
        return { text: 'ERROR', color: 'text-sci-error-400' }
      case 'degraded':
        return { text: 'DEGRADED', color: 'text-yellow-400' }
      case 'initializing':
        return { text: 'CONNECTING', color: 'text-sci-secondary-200' }
      default:
        return { text: 'UNKNOWN', color: 'text-sci-secondary-500' }
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
          title={`IPC Connection: ${healthState.multi_channel_ipc.status} - ${healthState.multi_channel_ipc.message || 'Multi-channel IPC system'}`}
        >
          <Cable className={`w-4 h-4 ${getIconColor(healthState.multi_channel_ipc.status)}`} />
        </div>
        <div
          className="h-12 px-3 flex items-center justify-center"
          title={`Parameters: ${healthState.parameters.status} - ${healthState.parameters.message || 'Parameter management system'}`}
        >
          <BookMarked className={`w-4 h-4 ${getIconColor(healthState.parameters.status)}`} />
        </div>
        <div
          className="h-12 px-3 flex items-center justify-center"
          title={`Display: ${healthState.display.status} - ${healthState.display.message || 'Display management system'}`}
        >
          <MonitorCheck className={`w-4 h-4 ${getIconColor(healthState.display.status)}`} />
        </div>
        <div
          className="h-12 px-3 flex items-center justify-center"
          title={`Camera: ${healthState.camera.status} - ${healthState.camera.message || 'Camera acquisition system'}`}
        >
          <Video className={`w-4 h-4 ${getIconColor(healthState.camera.status)}`} />
        </div>
        <div
          className="h-12 px-3 flex items-center justify-center"
          title={`Stimulus: ${healthState.realtime_streaming.status} - ${healthState.realtime_streaming.message || 'Realtime streaming system'}`}
        >
          <Columns3 className={`w-4 h-4 ${getIconColor(healthState.realtime_streaming.status)}`} />
        </div>

        {isExperimentRunning && (
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