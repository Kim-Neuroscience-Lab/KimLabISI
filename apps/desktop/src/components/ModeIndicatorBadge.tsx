import React from 'react'

interface ModeIndicatorBadgeProps {
  mode: 'preview' | 'record' | 'playback'
  isPreviewing: boolean
  isAcquiring: boolean
  className?: string
}

/**
 * Large, prominent mode indicator badge that overlays the camera feed.
 * Shows clear visual indication of current mode to prevent accidental preview
 * when scientist thinks they're recording.
 */
export function ModeIndicatorBadge({
  mode,
  isPreviewing,
  isAcquiring,
  className = ''
}: ModeIndicatorBadgeProps) {
  // Determine badge appearance based on mode and state
  const getBadgeConfig = () => {
    if (mode === 'record' && isAcquiring) {
      return {
        text: '● RECORDING',
        bgColor: 'bg-red-600',
        textColor: 'text-white',
        borderColor: 'border-red-500',
        animate: true
      }
    } else if (mode === 'preview' && isPreviewing) {
      return {
        text: '⚠️ PREVIEW MODE - NOT RECORDING',
        bgColor: 'bg-yellow-500',
        textColor: 'text-gray-900',
        borderColor: 'border-yellow-400',
        animate: false
      }
    } else if (mode === 'playback') {
      return {
        text: '▶ PLAYBACK',
        bgColor: 'bg-blue-600',
        textColor: 'text-white',
        borderColor: 'border-blue-500',
        animate: false
      }
    } else {
      // Idle state - no badge
      return null
    }
  }

  const config = getBadgeConfig()

  // Don't show badge if idle
  if (!config) {
    return null
  }

  return (
    <div
      className={`absolute top-4 right-4 z-50 ${className}`}
      role="status"
      aria-live="polite"
    >
      <div
        className={`
          ${config.bgColor}
          ${config.textColor}
          ${config.borderColor}
          px-6 py-3
          rounded-lg
          border-2
          shadow-2xl
          font-bold
          text-lg
          backdrop-blur-sm
          bg-opacity-95
          ${config.animate ? 'animate-pulse' : ''}
        `}
      >
        {config.text}
      </div>
    </div>
  )
}
