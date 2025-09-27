import React from 'react'

interface TimelineProps {
  progress: number
  isRunning: boolean
  logMessages: string[]
}

const Timeline: React.FC<TimelineProps> = ({
  progress,
  isRunning,
  logMessages
}) => {
  const formatProgress = (progress: number) => {
    return `${Math.round(progress)}%`
  }

  return (
    <div className="h-24 bg-sci-secondary-800 border-t border-sci-secondary-700 flex">
      {/* Progress Section */}
      <div className="w-96 border-r border-sci-secondary-700 p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-sci-secondary-200">
            Experiment Progress
          </span>
          <span className="text-sm text-sci-secondary-400">
            {formatProgress(progress)}
          </span>
        </div>

        <div className="relative">
          <div className="w-full bg-sci-secondary-700 rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-all duration-300 ${
                isRunning
                  ? 'bg-gradient-to-r from-sci-primary-500 to-sci-primary-400'
                  : 'bg-sci-secondary-600'
              }`}
              style={{ width: `${progress}%` }}
            />
          </div>

          {isRunning && (
            <div className="absolute -top-1 -right-1">
              <div className="w-4 h-4 bg-sci-primary-400 rounded-full animate-pulse"></div>
            </div>
          )}
        </div>

        <div className="flex justify-between text-xs text-sci-secondary-400 mt-1">
          <span>Start</span>
          {isRunning && (
            <span className="flex items-center space-x-1">
              <div className="w-2 h-2 bg-sci-primary-500 rounded-full animate-pulse"></div>
              <span>Running</span>
            </span>
          )}
          <span>End</span>
        </div>
      </div>

      {/* Log Messages Section */}
      <div className="flex-1 p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-sci-secondary-200">
            System Log
          </span>
          <span className="text-xs text-sci-secondary-400">
            {logMessages.length} messages
          </span>
        </div>

        <div className="h-12 bg-sci-secondary-900 rounded border border-sci-secondary-700 p-2 overflow-hidden">
          <div className="h-full overflow-y-auto">
            {logMessages.length > 0 ? (
              <div className="space-y-0.5">
                {logMessages.slice(-3).map((message, index) => (
                  <div
                    key={index}
                    className={`text-xs font-mono transition-opacity duration-300 ${
                      index === logMessages.slice(-3).length - 1
                        ? 'text-sci-secondary-200'
                        : 'text-sci-secondary-400'
                    }`}
                  >
                    {message}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-sci-secondary-500 italic">
                No log messages
              </div>
            )}
          </div>

          {/* Data flow animation when running */}
          {isRunning && (
            <div className="data-stream absolute bottom-0 left-0 w-full h-0.5 bg-sci-primary-500 opacity-20"></div>
          )}
        </div>
      </div>

      {/* Quick Stats */}
      <div className="w-48 border-l border-sci-secondary-700 p-4">
        <div className="text-sm font-medium text-sci-secondary-200 mb-2">
          Session Stats
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <div className="text-sci-secondary-400">Duration</div>
            <div className="text-sci-secondary-200 font-mono">
              {isRunning ? '00:15:32' : '--:--:--'}
            </div>
          </div>

          <div>
            <div className="text-sci-secondary-400">Frames</div>
            <div className="text-sci-secondary-200 font-mono">
              {isRunning ? '27,840' : '0'}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Timeline