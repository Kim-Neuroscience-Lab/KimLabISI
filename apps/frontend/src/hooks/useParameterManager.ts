import { useState, useCallback } from 'react'

/**
 * Generic parameter management hook that eliminates repetitive state patterns
 * Used for managing form parameters with type safety and consistent update patterns
 */
export const useParameterManager = <T extends Record<string, any>>(initialValues: T) => {
  const [parameters, setParameters] = useState<T>(initialValues)

  const updateParameter = useCallback((key: keyof T, value: any) => {
    setParameters(prev => ({ ...prev, [key]: value }))
  }, [])

  const setAllParameters = useCallback((newParameters: T) => {
    setParameters(newParameters)
  }, [])

  const resetParameters = useCallback(() => {
    setParameters(initialValues)
  }, [initialValues])

  return {
    parameters,
    updateParameter,
    setAllParameters,
    resetParameters
  }
}