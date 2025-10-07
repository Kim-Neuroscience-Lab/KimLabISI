import React from 'react'

interface StartupViewportProps {
  className?: string
  systemState: string
  displayText: string
  isReady: boolean
  isError: boolean
  errorMessage?: string | null
  connectionError?: string | null
}

/**
 * StartupViewport - PURE VIEW COMPONENT
 *
 * Displays backend state directly without interpretation.
 * All state comes from backend via system_state messages.
 */
const StartupViewport: React.FC<StartupViewportProps> = ({
  className = '',
  systemState,
  displayText,
  isReady,
  isError,
  errorMessage,
  connectionError
}) => {

  const getStatusMessage = () => {
    if (connectionError) {
      return `Connection Error: ${connectionError}`
    }

    if (errorMessage) {
      return errorMessage
    }

    return displayText
  }

  const hasError = isError || !!connectionError
  const isLoading = !hasError && !isReady

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Main Status Area */}
      <div className="flex-1 relative bg-sci-secondary-900 border border-sci-secondary-600 rounded-lg overflow-hidden">
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center max-w-lg">

            {/* ISI Logo/Icon */}
            <div className="mb-8">
              <div className={`w-20 h-20 mx-auto rounded-full flex items-center justify-center text-2xl font-bold transition-all duration-500 ${
                hasError
                  ? 'bg-red-600 text-white'
                  : isReady
                  ? 'bg-green-600 text-white'
                  : 'bg-sci-primary-600 text-white animate-pulse'
              }`}>
                {hasError ? '✗' : isReady ? '✓' : 'ISI'}
              </div>
            </div>

            {/* Status Message - directly from backend */}
            <div className={`text-3xl font-medium mb-6 transition-colors duration-300 ${
              hasError
                ? 'text-red-400'
                : isReady
                ? 'text-green-400'
                : 'text-sci-secondary-200'
            }`}>
              {getStatusMessage()}
            </div>

            {/* Loading Animation */}
            {isLoading && (
              <div className="flex items-center justify-center space-x-1">
                <div className="w-2 h-2 bg-sci-primary-600 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-sci-primary-600 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-2 h-2 bg-sci-primary-600 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              </div>
            )}

            {/* System State (for debugging) */}
            <div className="mt-4 text-xs text-sci-secondary-500">
              State: {systemState}
            </div>

          </div>
        </div>
      </div>

      {/* Status Info */}
      <div className="text-sm text-sci-secondary-400 text-center mt-4">
        ISI Control System • {displayText}
      </div>
    </div>
  )
}

export default StartupViewport