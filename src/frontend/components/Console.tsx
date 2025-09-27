import React, { useState } from 'react'
import { SquareChevronRight } from 'lucide-react'

interface ConsoleProps {
  logMessages: string[]
}

interface MessageCounts {
  errors: number
  warnings: number
}

const Console: React.FC<ConsoleProps> = ({
  logMessages
}) => {
  const [isCollapsed, setIsCollapsed] = useState(true)

  const toggleConsole = () => {
    setIsCollapsed(!isCollapsed)
  }

  const getMessageCounts = (): MessageCounts => {
    const counts = { errors: 0, warnings: 0 }
    logMessages.forEach(message => {
      const lowerMessage = message.toLowerCase()
      if (lowerMessage.includes('error') || lowerMessage.includes('failed') || lowerMessage.includes('fail')) {
        counts.errors++
      } else if (lowerMessage.includes('warning') || lowerMessage.includes('warn')) {
        counts.warnings++
      }
    })
    return counts
  }

  const counts = getMessageCounts()

  if (isCollapsed) {
    return (
      <div className="h-12 bg-sci-secondary-800 border-t border-sci-secondary-700 flex items-center px-4">
        {/* Collapsed Console - Bottom Bar */}
        <div className="flex items-center gap-3">
          <SquareChevronRight
            className="w-6 h-6 cursor-pointer text-sci-secondary-200 hover:text-sci-primary-400 transition-colors"
            onClick={toggleConsole}
          />
        </div>
        <div className="flex-1"></div>
        <div className="flex items-center gap-4">
          {counts.errors > 0 && (
            <span className="text-xs text-sci-error-400">
              {counts.errors} errors
            </span>
          )}
          {counts.warnings > 0 && (
            <span className="text-xs text-sci-warning-400">
              {counts.warnings} warnings
            </span>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="h-64 bg-sci-secondary-800 border-t border-sci-secondary-700 flex flex-col">
      {/* Console Header */}
      <div className="h-12 flex items-center justify-between px-4 border-b border-sci-secondary-700">
        <div className="flex items-center gap-3">
          <SquareChevronRight
            className="w-6 h-6 cursor-pointer text-sci-secondary-200 hover:text-sci-primary-400 transition-colors"
            onClick={toggleConsole}
          />
        </div>
        <div className="flex items-center gap-4">
          {counts.errors > 0 && (
            <span className="text-xs text-sci-error-400">
              {counts.errors} errors
            </span>
          )}
          {counts.warnings > 0 && (
            <span className="text-xs text-sci-warning-400">
              {counts.warnings} warnings
            </span>
          )}
        </div>
      </div>

      {/* Console Content */}
      <div className="flex-1 p-4">
        <div className="h-full bg-sci-secondary-900 rounded border border-sci-secondary-700 p-3 overflow-hidden">
          <div className="h-full overflow-y-auto">
            {logMessages.length > 0 ? (
              <div className="space-y-1">
                {logMessages.map((message, index) => (
                  <div
                    key={index}
                    className={`text-xs font-mono transition-opacity duration-300 ${
                      index === logMessages.length - 1
                        ? 'text-sci-secondary-100'
                        : 'text-sci-secondary-300'
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
        </div>
      </div>
    </div>
  )
}

export default Console