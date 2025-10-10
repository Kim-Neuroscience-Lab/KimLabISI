import React from 'react'
import { Video, Columns3, BrainCircuit, BookMarked, MonitorCheck, LucideIcon, Cable } from 'lucide-react'
import { useHealthSnapshot } from '../context/SystemContext'
import type { HealthMessage } from '../types/electron'

interface TabConfig {
  id: 'camera' | 'stimulus' | 'analysis'
  label: string
  icon: LucideIcon
}

interface HeaderProps {
  activeTab: 'camera' | 'stimulus' | 'analysis' | 'startup'
  onTabChange?: (tab: 'camera' | 'stimulus' | 'analysis') => void
  isExperimentRunning?: boolean
  healthSnapshot?: HealthMessage | null
}

const Header: React.FC<HeaderProps> = ({
  activeTab,
  onTabChange,
  isExperimentRunning = false,
  healthSnapshot
}) => {
  const snapshot = healthSnapshot ?? useHealthSnapshot()

  const hardwareStatus = snapshot?.hardware_status ?? {}
  const mergedHardwareStatus = {
    multi_channel_ipc: hardwareStatus.multi_channel_ipc ?? 'offline',
    parameters: hardwareStatus.parameters ?? 'offline',
    display: hardwareStatus.display ?? 'offline',
    camera: hardwareStatus.camera ?? 'offline',
    realtime_streaming: hardwareStatus.realtime_streaming ?? 'offline',
    analysis: hardwareStatus.analysis ?? 'offline',
  }

  const calculateOverallStatus = () => {
    const statuses = Object.values(mergedHardwareStatus)

    if (statuses.includes('error')) {
      return { text: 'ERROR', color: 'text-sci-error-400' }
    }

    if (statuses.every(status => status === 'online')) {
      return { text: 'OK', color: 'text-sci-success-400' }
    }

    if (statuses.some(status => status === 'online')) {
      return { text: 'DEGRADED', color: 'text-yellow-400' }
    }

    return { text: 'CONNECTING', color: 'text-sci-secondary-200' }
  }

  const getIconColor = (status: string) => {
    switch (status) {
      case 'online': return 'text-sci-success-400'
      case 'error': return 'text-sci-error-400'
      case 'degraded': return 'text-yellow-400'
      default: return 'text-sci-secondary-500'
    }
  }
  const resolveIconColor = (status: string) => snapshot ? getIconColor(status) : 'text-sci-secondary-500'

  const overallStatus = calculateOverallStatus()
  const statusText = snapshot ? overallStatus.text : 'CONNECTING'

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
          <h3 className="text-sm font-semibold text-white">
            {statusText}
          </h3>
        </div>

        {/* Status Icons - mirror the tab icon structure */}
        <div
          className="h-12 px-3 flex items-center justify-center"
          title={`IPC Connection: ${mergedHardwareStatus.multi_channel_ipc}`}
        >
          <Cable className={`w-4 h-4 ${resolveIconColor(mergedHardwareStatus.multi_channel_ipc)}`} />
        </div>
        <div
          className="h-12 px-3 flex items-center justify-center"
          title={`Parameters: ${mergedHardwareStatus.parameters}`}
        >
          <BookMarked className={`w-4 h-4 ${resolveIconColor(mergedHardwareStatus.parameters)}`} />
        </div>
        <div
          className="h-12 px-3 flex items-center justify-center"
          title={`Display: ${mergedHardwareStatus.display}`}
        >
          <MonitorCheck className={`w-4 h-4 ${resolveIconColor(mergedHardwareStatus.display)}`} />
        </div>
        <div
          className="h-12 px-3 flex items-center justify-center"
          title={`Camera: ${mergedHardwareStatus.camera}`}
        >
          <Video className={`w-4 h-4 ${resolveIconColor(mergedHardwareStatus.camera)}`} />
        </div>
        <div
          className="h-12 px-3 flex items-center justify-center"
          title={`Stimulus: ${mergedHardwareStatus.realtime_streaming}`}
        >
          <Columns3 className={`w-4 h-4 ${resolveIconColor(mergedHardwareStatus.realtime_streaming)}`} />
        </div>
        <div
          className="h-12 px-3 flex items-center justify-center"
          title={`Analysis: ${mergedHardwareStatus.analysis}`}
        >
          <BrainCircuit className={`w-4 h-4 ${resolveIconColor(mergedHardwareStatus.analysis)}`} />
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