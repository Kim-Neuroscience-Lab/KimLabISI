import React, { useState } from 'react'
import { X } from 'lucide-react'

export interface FilterWarningModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  filterType: 'anatomical' | 'functional'
  title?: string
  showDontShowAgain?: boolean
  error?: string | null
}

/**
 * Modal dialog for filter verification before critical operations.
 * Prevents scientists from capturing data with wrong filters installed.
 */
export function FilterWarningModal({
  isOpen,
  onClose,
  onConfirm,
  filterType,
  title,
  showDontShowAgain = true,
  error = null
}: FilterWarningModalProps) {
  const [confirmed, setConfirmed] = useState(false)
  const [dontShowAgain, setDontShowAgain] = useState(false)

  if (!isOpen) return null

  const filterSpecs =
    filterType === 'anatomical'
      ? {
          title: title || 'Anatomical Image Capture - Filter Check',
          message: 'Please verify the GREEN illumination filter is installed',
          specs: '510-590nm excitation filter',
          details: 'Anatomical imaging requires green illumination without emission filter for maximum brightness.',
          icon: '📷',
          confirmButton: 'Capture Anatomical Image',
          iconColor: 'text-green-600'
        }
      : {
          title: title || 'Start Recording - Filter Check',
          message: 'Please verify the RED BANDPASS filter is installed on the camera',
          specs: '~630nm (700nm emission bandpass) for hemoglobin imaging',
          details:
            'Functional imaging requires the red bandpass filter to isolate the hemoglobin absorption signal at ~630nm.',
          icon: '🔴',
          confirmButton: 'Start Recording',
          iconColor: 'text-red-600'
        }

  const handleConfirm = () => {
    if (confirmed) {
      onConfirm()
      // Reset state
      setConfirmed(false)
      setDontShowAgain(false)

      // Store preference if requested
      if (dontShowAgain && showDontShowAgain) {
        const prefKey = `filterWarning_${filterType}_disabled`
        localStorage.setItem(prefKey, 'true')
      }
    }
  }

  const handleClose = () => {
    onClose()
    // Reset state
    setConfirmed(false)
    setDontShowAgain(false)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="filter-warning-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black bg-opacity-50 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-2xl max-w-lg w-full mx-4 p-6">
        {/* Close button */}
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          aria-label="Close"
        >
          <X size={24} />
        </button>

        {/* Icon and Title */}
        <div className="flex items-start space-x-4 mb-4">
          <div className={`text-4xl ${filterSpecs.iconColor}`}>
            {filterSpecs.icon}
          </div>
          <div className="flex-1">
            <h2
              id="filter-warning-title"
              className="text-xl font-bold text-gray-900 dark:text-white mb-2"
            >
              {filterSpecs.title}
            </h2>
          </div>
        </div>

        {/* Warning Message */}
        <div className="mb-6 space-y-3">
          <div className="flex items-center space-x-2 text-yellow-700 dark:text-yellow-500 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-3">
            <span className="text-xl">⚠️</span>
            <p className="font-semibold">{filterSpecs.message}</p>
          </div>

          {/* Equipment Specs */}
          <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
            <p className="text-sm font-mono text-gray-700 dark:text-gray-300 mb-2">
              <span className="font-bold">Required Filter:</span> {filterSpecs.specs}
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {filterSpecs.details}
            </p>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-6">
            <div className="flex items-start space-x-2 text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
              <span className="text-xl">❌</span>
              <div className="flex-1">
                <p className="font-semibold mb-1">Failed to start acquisition</p>
                <p className="text-sm">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Confirmation Checkbox */}
        <div className="mb-6">
          <label className="flex items-center space-x-3 cursor-pointer">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              className="w-5 h-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              I confirm the correct filter is installed
            </span>
          </label>
        </div>

        {/* Don't Show Again (Optional) */}
        {showDontShowAgain && (
          <div className="mb-6">
            <label className="flex items-center space-x-3 cursor-pointer">
              <input
                type="checkbox"
                checked={dontShowAgain}
                onChange={(e) => setDontShowAgain(e.target.checked)}
                className="w-4 h-4 rounded border-gray-300 text-gray-600 focus:ring-gray-500"
              />
              <span className="text-xs text-gray-500 dark:text-gray-400">
                Don't show this warning again (not recommended)
              </span>
            </label>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex justify-end space-x-3">
          <button
            onClick={handleClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={!confirmed}
            className={`
              px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors
              ${
                confirmed
                  ? filterType === 'anatomical'
                    ? 'bg-green-600 hover:bg-green-700'
                    : 'bg-red-600 hover:bg-red-700'
                  : 'bg-gray-300 dark:bg-gray-600 cursor-not-allowed'
              }
            `}
          >
            {filterSpecs.confirmButton}
          </button>
        </div>
      </div>
    </div>
  )
}
