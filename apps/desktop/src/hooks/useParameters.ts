import { useCallback, useMemo, useRef } from 'react'
import { useSystemContext } from '../context/SystemContext'

export interface ParametersViewModel {
  parameters: Record<string, any>
  parameterConfig: Record<string, any>
  updateParameters: (group: string, updates: Record<string, unknown>) => Promise<void>
  sessionParams?: Record<string, any>
  monitorParams?: Record<string, any>
  stimulusParams?: Record<string, any>
  cameraParams?: Record<string, any>
  acquisitionParams?: Record<string, any>
  analysisParams?: Record<string, any>
  availableCameras: string[]
  availableDisplays: string[]
}

// Debounce delays for different parameter groups
const DEBOUNCE_DELAYS: Record<string, number> = {
  analysis: 500,    // Analysis parameters need longer debounce (trigger re-analysis)
  stimulus: 200,    // Stimulus parameters (visual updates)
  monitor: 200,     // Monitor parameters (spatial config)
  session: 0,       // Session metadata (immediate)
  camera: 0,        // Camera settings (immediate)
  acquisition: 0,   // Acquisition settings (immediate)
}

export const useParameters = (): ParametersViewModel => {
  const { parametersSnapshot, sendCommand } = useSystemContext()

  const parameters = parametersSnapshot?.parameters ?? {}
  const parameterConfig = parametersSnapshot?.parameter_config ?? {}

  // Store debounce timers per parameter group
  const debounceTimers = useRef<Record<string, NodeJS.Timeout>>({})

  const updateParameters = useCallback(
    async (group: string, updates: Record<string, unknown>) => {
      const delay = DEBOUNCE_DELAYS[group] ?? 200

      if (delay > 0) {
        // Clear existing timer for this group
        if (debounceTimers.current[group]) {
          clearTimeout(debounceTimers.current[group])
        }

        // Set new debounced timer
        return new Promise<void>((resolve) => {
          debounceTimers.current[group] = setTimeout(async () => {
            await sendCommand({
              type: 'update_parameter_group',
              group_name: group,
              parameters: updates,
            })
            delete debounceTimers.current[group]
            resolve()
          }, delay)
        })
      } else {
        // No debounce - send immediately
        await sendCommand({
          type: 'update_parameter_group',
          group_name: group,
          parameters: updates,
        })
      }
    },
    [sendCommand],
  )

  return useMemo(
    () => ({
      parameters,
      parameterConfig,
      updateParameters,
      sessionParams: parameters.session,
      monitorParams: parameters.monitor,
      stimulusParams: parameters.stimulus,
      cameraParams: parameters.camera,
      acquisitionParams: parameters.acquisition,
      analysisParams: parameters.analysis,
      availableCameras: parameters.camera?.available_cameras ?? [],
      availableDisplays: parameters.monitor?.available_displays ?? [],
    }),
    [parameters, parameterConfig, updateParameters],
  )
}
