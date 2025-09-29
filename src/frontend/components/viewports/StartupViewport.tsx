import React from 'react'
import type { InitializationState } from '../../hooks/useISISystem'

interface StartupViewportProps {
  className?: string
  initState: InitializationState
  connectionError?: string | null
  startupProgress?: {
    phase: string
    message: string
    error?: boolean
  }
}

const StartupViewport: React.FC<StartupViewportProps> = ({
  className = '',
  initState,
  connectionError,
  startupProgress
}) => {

  const getStatusMessage = () => {
    if (startupProgress?.error || initState === 'error') {
      return startupProgress?.message || 'System Error'
    }

    if (initState === 'system-ready') {
      return 'System Ready'
    }

    // Use backend's startup message directly
    return startupProgress?.message || ''
  }


  const getProgressSteps = () => {
    const steps = [
      { key: 'initializing', label: 'Start' },
      { key: 'health_checks', label: 'Systems' },
      { key: 'hardware_detection', label: 'Hardware' },
      { key: 'system_ready', label: 'Ready' }
    ]

    const currentPhase = startupProgress?.phase || 'initializing'
    const hasError = startupProgress?.error || initState === 'error'

    return (
      <div className="flex items-center justify-center space-x-6">
        {steps.map((step, index) => {
          let status: 'completed' | 'active' | 'pending' | 'error' = 'pending'

          if (hasError) {
            // If there's an error, show error for current phase
            if (step.key === currentPhase) {
              status = 'error'
            } else {
              status = 'pending'
            }
          } else if (currentPhase === 'system_ready') {
            // When system is ready, mark all stages as completed including Ready
            status = 'completed'
          } else if (step.key === currentPhase) {
            status = 'active'
          } else {
            // Check if this step is completed based on phase order
            const stepIndex = steps.findIndex(s => s.key === step.key)
            const currentIndex = steps.findIndex(s => s.key === currentPhase)
            if (stepIndex < currentIndex) {
              status = 'completed'
            }
          }

          return (
            <React.Fragment key={step.key}>
              <div className="flex flex-col items-center">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium transition-all duration-300 ${
                  status === 'completed'
                    ? 'bg-green-600 text-white'
                    : status === 'active'
                    ? 'bg-sci-primary-600 text-white animate-pulse'
                    : status === 'error'
                    ? 'bg-red-600 text-white'
                    : 'bg-sci-secondary-700 text-sci-secondary-400'
                }`}>
                  {status === 'completed' ? '✓' : status === 'error' ? '✗' : index + 1}
                </div>
                <div className={`mt-2 text-xs font-medium transition-all duration-300 ${
                  status === 'completed'
                    ? 'text-green-400'
                    : status === 'active'
                    ? 'text-sci-primary-400'
                    : status === 'error'
                    ? 'text-red-400'
                    : 'text-sci-secondary-400'
                }`}>
                  {step.label}
                </div>
              </div>
              {index < steps.length - 1 && (
                <div className={`w-16 h-0.5 transition-all duration-300 ${
                  status === 'completed' ? 'bg-green-600' : 'bg-sci-secondary-700'
                }`} />
              )}
            </React.Fragment>
          )
        })}
      </div>
    )
  }

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Main Status Area */}
      <div className="flex-1 relative bg-sci-secondary-900 border border-sci-secondary-600 rounded-lg overflow-hidden">
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center max-w-md">

            {/* Status Message */}
            <div className="text-2xl font-medium text-sci-secondary-200 mb-8">
              {getStatusMessage()}
            </div>

            {/* Progress Steps */}
            <div className="flex items-center justify-center space-x-4 mb-8">
              {getProgressSteps()}
            </div>

            {/* Loading Animation for Active States */}
            {initState !== 'error' && initState !== 'system-ready' && (
              <div className="flex items-center justify-center space-x-1">
                <div className="w-2 h-2 bg-sci-primary-600 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-sci-primary-600 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-2 h-2 bg-sci-primary-600 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Status Info */}
      <div className="text-xs text-sci-secondary-400 text-center mt-4">
        ISI Control System • Initialization in progress
      </div>
    </div>
  )
}

export default StartupViewport