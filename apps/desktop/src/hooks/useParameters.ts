import { useCallback, useMemo } from 'react'
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

export const useParameters = (): ParametersViewModel => {
  const { parametersSnapshot, sendCommand } = useSystemContext()

  const parameters = parametersSnapshot?.parameters ?? {}
  const parameterConfig = parametersSnapshot?.parameter_config ?? {}

  const updateParameters = useCallback(
    async (group: string, updates: Record<string, unknown>) => {
      await sendCommand({
        type: 'update_parameter_group',
        group_name: group,
        parameters: updates,
      })
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
