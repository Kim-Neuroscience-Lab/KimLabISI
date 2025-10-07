import React, { useState } from 'react'
import { componentLogger } from '../../utils/logger'
import type { ISIMessage, ControlMessage, SyncMessage } from '../../types/ipc-messages'
import type { SystemState } from '../../types/shared'
import type { AnalysisParameters } from '../../hooks/useParameterManager'

interface AnalysisViewportProps {
  className?: string
  analysisParams?: AnalysisParameters
  sendCommand?: (command: ISIMessage) => Promise<{ success: boolean; error?: string }>
  lastMessage?: ControlMessage | SyncMessage | null
  systemState?: SystemState
}

interface AnalysisResult {
  timestamp: number
  metrics: {
    [key: string]: number
  }
}

const AnalysisViewport: React.FC<AnalysisViewportProps> = ({
  className = '',
  analysisParams,
  sendCommand,
  lastMessage,
  systemState
}) => {
  const [analysisResults, setAnalysisResults] = useState<AnalysisResult[]>([])
  const [isAnalysisActive, setIsAnalysisActive] = useState(false)

  // Listen for analysis results from backend
  React.useEffect(() => {
    if (lastMessage?.type === 'analysis_result') {
      const newResult: AnalysisResult = {
        timestamp: lastMessage.timestamp || Date.now(),
        metrics: lastMessage.metrics || {}
      }

      setAnalysisResults(prev => {
        const updated = [...prev, newResult]
        // Keep only last 100 results
        if (updated.length > 100) {
          updated.shift()
        }
        return updated
      })
    }

    if (lastMessage?.type === 'analysis_started') {
      setIsAnalysisActive(true)
    }

    if (lastMessage?.type === 'analysis_stopped') {
      setIsAnalysisActive(false)
    }
  }, [lastMessage])

  const startAnalysis = async () => {
    if (!sendCommand) return

    try {
      await sendCommand({ type: 'start_analysis' })
      setIsAnalysisActive(true)
    } catch (error) {
      componentLogger.error('Failed to start analysis:', error)
    }
  }

  const stopAnalysis = async () => {
    if (!sendCommand) return

    try {
      await sendCommand({ type: 'stop_analysis' })
      setIsAnalysisActive(false)
    } catch (error) {
      componentLogger.error('Failed to stop analysis:', error)
    }
  }

  const clearResults = () => {
    setAnalysisResults([])
  }

  const exportResults = () => {
    if (analysisResults.length === 0) return

    const csvHeader = ['Timestamp', ...Object.keys(analysisResults[0].metrics)].join(',')
    const csvRows = analysisResults.map(result => [
      result.timestamp,
      ...Object.values(result.metrics)
    ].join(','))

    const csvContent = [csvHeader, ...csvRows].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `analysis_results_${new Date().toISOString().replace(/[:.]/g, '-')}.csv`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  // Get latest metrics from most recent analysis result
  const latestMetrics = analysisResults.length > 0
    ? analysisResults[analysisResults.length - 1].metrics
    : {}


  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Metrics Display */}
      {Object.keys(latestMetrics).length > 0 && (
        <div className="mb-4 p-3 bg-sci-secondary-800 rounded-lg border border-sci-secondary-600">
          <h3 className="text-sm font-medium text-sci-secondary-200 mb-3">Latest Analysis Metrics</h3>
          <div className="grid grid-cols-2 gap-4">
            {Object.entries(latestMetrics).map(([key, value]) => (
              <div key={key} className="text-center">
                <div className="text-xs text-sci-secondary-400 mb-1">
                  {key.replace(/_/g, ' ').toUpperCase()}
                </div>
                <div className="text-lg font-mono font-bold text-sci-primary-400">
                  {typeof value === 'number' ? value.toFixed(2) : value}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Analysis Results Container */}
      <div className="flex-1 relative bg-sci-secondary-900 border border-sci-secondary-600 rounded-lg overflow-hidden">
        {analysisResults.length > 0 ? (
          <div className="p-4 h-full overflow-y-auto">
            <h3 className="text-lg font-medium text-sci-secondary-200 mb-4">Analysis Results</h3>
            <div className="space-y-2">
              {analysisResults.slice(-10).reverse().map((result, _index) => (
                <div key={result.timestamp} className="bg-sci-secondary-800 p-3 rounded border border-sci-secondary-700">
                  <div className="text-xs text-sci-secondary-400 mb-2">
                    {new Date(result.timestamp).toLocaleTimeString()}
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    {Object.entries(result.metrics).map(([key, value]) => (
                      <div key={key}>
                        <span className="text-sci-secondary-400">{key}:</span>
                        <span className="ml-1 text-white">
                          {typeof value === 'number' ? value.toFixed(2) : value}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center text-sci-secondary-400">
              <div className="text-6xl mb-4">📊</div>
              <div className="text-lg">Analysis Results</div>
              <div className="text-sm mt-2">
                {systemState?.isExperimentRunning
                  ? 'Analysis will appear when experiment data is processed'
                  : 'Start an experiment to see analysis results'
                }
              </div>
            </div>
          </div>
        )}

        {/* Status overlay */}
        <div className="absolute top-2 left-2 bg-black/70 text-white text-xs px-2 py-1 rounded">
          {isAnalysisActive ? (
            <span className="flex items-center gap-1">
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
              ACTIVE • {analysisResults.length} results
            </span>
          ) : (
            'IDLE'
          )}
        </div>
      </div>

      {/* Control Buttons */}
      <div className="flex gap-2 mt-4 justify-center">
        {!isAnalysisActive ? (
          <button
            onClick={startAnalysis}
            disabled={!systemState?.isConnected}
            className="px-4 py-2 bg-sci-primary-600 text-white rounded text-sm font-medium hover:bg-sci-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Start Analysis
          </button>
        ) : (
          <button
            onClick={stopAnalysis}
            className="px-4 py-2 bg-red-600 text-white rounded text-sm font-medium hover:bg-red-700 transition-colors"
          >
            Stop Analysis
          </button>
        )}

        <button
          onClick={clearResults}
          disabled={analysisResults.length === 0}
          className="px-4 py-2 bg-sci-secondary-600 text-white rounded text-sm font-medium hover:bg-sci-secondary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Clear Results
        </button>

        <button
          onClick={exportResults}
          disabled={analysisResults.length === 0}
          className="px-4 py-2 bg-sci-accent-600 text-white rounded text-sm font-medium hover:bg-sci-accent-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Export CSV
        </button>
      </div>

      {/* Status Info */}
      <div className="text-xs text-sci-secondary-400 text-center mt-2">
        {analysisResults.length > 0 ? (
          `${analysisResults.length} analysis results • Last: ${new Date(analysisResults[analysisResults.length - 1].timestamp).toLocaleTimeString()}`
        ) : (
          'No analysis results available'
        )}
      </div>
    </div>
  )
}

export default AnalysisViewport