import React, { useState } from 'react'
import { SquareChevronRight, Github } from 'lucide-react'

interface ConsoleProps {
  logMessages: string[]
}


const Console: React.FC<ConsoleProps> = ({
  logMessages
}) => {
  const [isCollapsed, setIsCollapsed] = useState(true)

  const toggleConsole = () => {
    setIsCollapsed(!isCollapsed)
  }

  const openGitHub = () => {
    window.open('https://github.com/Kim-Neuroscience-Lab/KimLabISI.git', '_blank')
  }

  const mostRecentMessage = logMessages.length > 0 ? logMessages[logMessages.length - 1] : null

  if (isCollapsed) {
    return (
      <div className="h-12 bg-sci-secondary-800 border-t border-sci-secondary-700 flex items-center">
        {/* Console Icon */}
        <div className="h-12 w-12 flex items-center justify-center border-r border-sci-secondary-700">
          <SquareChevronRight
            className="w-6 h-6 cursor-pointer text-sci-secondary-200 hover:text-sci-primary-400 transition-colors"
            onClick={toggleConsole}
          />
        </div>
        {/* Most recent message */}
        <div className="flex-1 mx-4 overflow-hidden">
          {mostRecentMessage ? (
            <div className="text-xs font-mono text-sci-secondary-300 truncate">
              {mostRecentMessage}
            </div>
          ) : (
            <div className="text-xs text-sci-secondary-500 italic">
              No messages
            </div>
          )}
        </div>
        {/* GitHub Icon */}
        <div className="h-12 w-12 flex items-center justify-center">
          <Github
            className="w-6 h-6 cursor-pointer text-sci-secondary-200 hover:text-sci-primary-400 transition-colors"
            onClick={openGitHub}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="bg-sci-secondary-800 border-t border-sci-secondary-700 flex flex-col" style={{ height: '256px', minHeight: '256px', maxHeight: '256px' }}>
      {/* Console Header */}
      <div className="h-12 flex items-center justify-between border-b border-sci-secondary-700 flex-shrink-0">
        <div className="w-12 flex items-center justify-center">
          <SquareChevronRight
            className="w-6 h-6 cursor-pointer text-sci-secondary-200 hover:text-sci-primary-400 transition-colors"
            onClick={toggleConsole}
          />
        </div>
        {/* Most recent message */}
        <div className="flex-1 mx-4 overflow-hidden">
          {mostRecentMessage ? (
            <div className="text-xs font-mono text-sci-secondary-300 truncate">
              {mostRecentMessage}
            </div>
          ) : (
            <div className="text-xs text-sci-secondary-500 italic">
              No messages
            </div>
          )}
        </div>
        <div className="w-12 flex items-center justify-center">
          <Github
            className="w-6 h-6 cursor-pointer text-sci-secondary-200 hover:text-sci-primary-400 transition-colors"
            onClick={openGitHub}
          />
        </div>
      </div>

      {/* Console Content */}
      <div className="flex-1 p-4 min-h-0 overflow-hidden">
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