import React, { useState, useEffect } from 'react'

interface FormFieldProps {
  label: string
  value: string | number
  onChange: (value: string | number) => void
  type?: 'text' | 'number' | 'select' | 'range'
  options?: Array<{ value: string; label: string }>
  min?: number
  max?: number
  step?: number
  unit?: string
  placeholder?: string
  disabled?: boolean
  // Note: validationBounds removed - backend handles all validation
  // Frontend should receive validation errors from backend and display them
}

export const FormField: React.FC<FormFieldProps> = ({
  label,
  value,
  onChange,
  type = 'text',
  options = [],
  min,
  max,
  step,
  unit,
  placeholder,
  disabled = false
}) => {
  // For number inputs, track display value separately to allow temporary empty state
  const [displayValue, setDisplayValue] = useState(String(value))

  // Update display value when prop value changes
  useEffect(() => {
    setDisplayValue(String(value))
  }, [value])

  const renderInput = () => {
    // Pure UI styling - no business validation
    const baseClasses = "w-full px-3 py-2 bg-sci-secondary-700 text-sci-secondary-100 border border-sci-secondary-600 rounded focus:outline-none focus:border-sci-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"

    switch (type) {
      case 'select':
        return (
          <select
            value={value}
            onChange={(e) => onChange(e.target.value)}
            disabled={disabled}
            className={baseClasses}
          >
            {options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        )

      case 'range':
        return (
          <div className="space-y-2">
            <input
              type="range"
              value={value}
              onChange={(e) => onChange(Number(e.target.value))}
              min={min}
              max={max}
              step={step}
              disabled={disabled}
              className="w-full h-2 bg-sci-secondary-700 rounded-lg appearance-none cursor-pointer slider disabled:cursor-not-allowed"
            />
            <div className="flex justify-between text-xs text-sci-secondary-400">
              <span>{min}</span>
              <span className="font-medium text-sci-secondary-200">
                {value}{unit && ` ${unit}`}
              </span>
              <span>{max}</span>
            </div>
          </div>
        )

      case 'number':
        return (
          <div className="relative">
            <input
              type="text"
              inputMode="decimal"
              value={displayValue}
              onChange={(e) => {
                const inputValue = e.target.value
                setDisplayValue(inputValue)

                // Allow empty string for temporary deletion
                if (inputValue === '') {
                  return // Don't propagate empty values
                }

                // Allow only numbers, decimal points, and minus signs at the start
                if (!/^-?(\d+\.?\d*|\.\d+)$/.test(inputValue)) {
                  return // Don't update if invalid
                }

                // Convert to number and propagate valid values only
                const numValue = Number(inputValue)
                if (!isNaN(numValue)) {
                  onChange(numValue)
                }
              }}
              onBlur={() => {
                // If field is empty on blur, revert to current value
                if (displayValue === '') {
                  setDisplayValue(String(value))
                }
              }}
              placeholder={placeholder}
              disabled={disabled}
              className={baseClasses}
            />
            {unit && (
              <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-sci-secondary-400 text-sm">
                {unit}
              </span>
            )}
          </div>
        )

      default:
        return (
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            disabled={disabled}
            className={baseClasses}
          />
        )
    }
  }

  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-sci-secondary-300">
        {label}
      </label>
      {renderInput()}
      {/* Validation messages should come from backend, not computed in frontend */}
    </div>
  )
}