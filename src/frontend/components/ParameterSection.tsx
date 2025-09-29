import React from 'react'
import { FormField } from './FormField'

export interface ParameterConfig {
  key: string
  label: string
  type: 'text' | 'number' | 'select' | 'range'
  options?: Array<{ value: string; label: string }>
  min?: number
  max?: number
  step?: number
  unit?: string
  placeholder?: string
  disabled?: boolean
}

interface ParameterSectionProps {
  title: string
  initialValues: Record<string, any>
  configs: ParameterConfig[]
  onParametersChange?: (parameters: Record<string, any>) => void
}

export const ParameterSection: React.FC<ParameterSectionProps> = ({
  title: _title,
  initialValues,
  configs,
  onParametersChange
}) => {
  const handleParameterChange = (key: string, value: string | number) => {
    // Send change directly to parent - no local state management
    onParametersChange?.({ ...initialValues, [key]: value })
  }

  return (
    <div className="space-y-4">
      {configs.map((config) => (
        <FormField
          key={config.key}
          label={config.label}
          value={initialValues[config.key] ?? ''}
          onChange={(value) => handleParameterChange(config.key, value)}
          type={config.type}
          options={config.options}
          min={config.min}
          max={config.max}
          step={config.step}
          unit={config.unit}
          placeholder={config.placeholder}
          disabled={config.disabled}
        />
      ))}
    </div>
  )
}