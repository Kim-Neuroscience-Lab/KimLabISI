import React from 'react'
import { Check, Loader2 } from 'lucide-react'

export interface AnalysisStage {
  id: string
  label: string
  progress: number  // 0.0 - 1.0
  status: 'pending' | 'in_progress' | 'completed'
  thumbnail?: string  // base64 PNG data URL
}

interface AnalysisProgressProps {
  stages: AnalysisStage[]
  isRunning: boolean
  className?: string
  onThumbnailClick?: (stageId: string, thumbnail: string) => void
}

const AnalysisProgress: React.FC<AnalysisProgressProps> = ({
  stages,
  isRunning,
  className = '',
  onThumbnailClick
}) => {
  return (
    <div className={`p-3 bg-sci-secondary-800 rounded-lg border border-sci-secondary-600 ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-sci-secondary-200">Analysis Progress</h3>
        {isRunning && (
          <div className="flex items-center gap-2 text-xs text-sci-primary-400">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>Running...</span>
          </div>
        )}
        {!isRunning && stages.some(s => s.status === 'completed') && (
          <span className="text-xs text-green-400">Complete</span>
        )}
      </div>

      <div className="space-y-2">
        {stages.map((stage) => (
          <div key={stage.id} className="flex items-center gap-2">
            {/* Label on left */}
            <span className={`text-xs whitespace-nowrap flex-shrink-0 w-36 ${
              stage.status === 'completed' ? 'text-sci-secondary-300' :
              stage.status === 'in_progress' ? 'text-sci-primary-300 font-medium' :
              'text-sci-secondary-500'
            }`}>
              {stage.label}
            </span>
            {/* Progress Bar in middle - Always visible */}
            <div className="flex-1 bg-sci-secondary-900 rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all duration-300 ${
                  stage.status === 'completed' ? 'bg-green-600' :
                  stage.status === 'in_progress' ? 'bg-sci-primary-600' :
                  'bg-sci-secondary-700'
                }`}
                style={{ width: `${stage.progress * 100}%` }}
              />
            </div>
            {/* Percentage on right */}
            <span className="text-xs text-sci-secondary-400 flex-shrink-0 w-10 text-right">
              {(stage.progress * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>

      {!isRunning && stages.length === 0 && (
        <div className="text-xs text-sci-secondary-500 text-center py-2">
          No analysis running
        </div>
      )}
    </div>
  )
}

export default AnalysisProgress
