/**
 * Type definitions for IPC messages between Electron and Python backend
 * Replaces 'any' types with proper TypeScript interfaces for type safety
 */

// Base message interface
export interface ISIMessage {
  type: string
  messageId?: string
  timestamp?: number
}

// System state message from backend
export interface SystemStateMessage extends ISIMessage {
  type: 'system_state'
  state:
    | 'initializing'
    | 'waiting_frontend'
    | 'ipc_ready'
    | 'parameters_loaded'
    | 'hardware_detected'
    | 'systems_validated'
    | 'ready'
    | 'error'
  display_text: string
  is_ready: boolean
  is_error: boolean
  details?: Record<string, unknown>
}

// ZeroMQ connection ready message
export interface ZeroMQReadyMessage extends ISIMessage {
  type: 'zeromq_ready'
  health_port: number
  sync_port: number
}

// Frontend ready message
export interface FrontendReadyMessage extends ISIMessage {
  type: 'frontend_ready'
  ping_id?: string
}

// Frontend ready response
export interface FrontendReadyResponse extends ISIMessage {
  type: 'frontend_ready_response'
  success: boolean
  message: string
}

// Parameter update message
export interface ParameterUpdateMessage extends ISIMessage {
  type: 'parameter_update'
  group: string
  parameters: Record<string, unknown>
}

// Hardware status message
export interface HardwareStatusMessage extends ISIMessage {
  type: 'hardware_status'
  cameras?: Array<{
    index: number
    name: string
    resolution: [number, number]
  }>
  displays?: Array<{
    name: string
    width: number
    height: number
    is_primary: boolean
  }>
}

// Command response
export interface CommandResponse {
  success: boolean
  error?: string
  message?: string
  data?: unknown
}

// Startup command
export interface StartupCommand {
  type: string
  [key: string]: unknown
}

// Analysis message types
export interface AnalysisStartedMessage extends ISIMessage {
  type: 'analysis_started'
  session_path: string
}

export interface AnalysisProgressMessage extends ISIMessage {
  type: 'analysis_progress'
  progress: number
  stage: string
}

export interface AnalysisLayerReadyMessage extends ISIMessage {
  type: 'analysis_layer_ready'
  layer_name: string
  shape: number[]
  dtype: string
  data_min: number
  data_max: number
  shm_path: string
  session_path: string
  // PNG-based rendering fields
  image_base64?: string
  width?: number
  height?: number
  format?: string
}

export interface AnalysisCompleteMessage extends ISIMessage {
  type: 'analysis_complete'
  session_path: string
  output_path: string
  num_areas: number
  success: boolean
}

export interface AnalysisErrorMessage extends ISIMessage {
  type: 'analysis_error'
  error: string
  session_path: string
}

// Session information
export interface SessionInfo {
  session_name: string
  session_path: string
  created_at: string
  last_modified: string
}

// Command types
export interface ListSessionsCommand extends ISIMessage {
  type: 'list_sessions'
}

export interface ListSessionsResponse extends CommandResponse {
  sessions?: SessionInfo[]
}

export interface GetAnalysisResultsCommand extends ISIMessage {
  type: 'get_analysis_results'
  session_path: string
}

export interface GetAnalysisResultsResponse extends CommandResponse {
  session_path?: string
  shape?: [number, number]
  num_areas?: number
  primary_layers?: string[]
  advanced_layers?: string[]
  has_anatomical?: boolean
}

export interface GetAnalysisCompositeImageCommand extends ISIMessage {
  type: 'get_analysis_composite_image'
  session_path: string
  layers: {
    anatomical?: { visible: boolean; alpha: number }
    signal?: { visible: boolean; type: string; alpha: number }
    overlay?: { visible: boolean; type: string; alpha: number }
  }
  width?: number
  height?: number
}

export interface GetAnalysisCompositeImageResponse extends CommandResponse {
  image_base64?: string
  width?: number
  height?: number
  format?: string
}

export interface StartAnalysisCommand extends ISIMessage {
  type: 'start_analysis'
  session_path: string
}

// Generic message type for untyped messages
export interface GenericMessage extends ISIMessage {
  type: string
  [key: string]: unknown
}

// Discriminated union of all control messages
export type ControlMessage =
  | SystemStateMessage
  | ZeroMQReadyMessage
  | FrontendReadyResponse
  | HardwareStatusMessage
  | ParameterUpdateMessage
  | GenericMessage

// Discriminated union of all sync messages
export type SyncMessage =
  | SystemStateMessage
  | ParameterUpdateMessage
  | HardwareStatusMessage
  | AnalysisStartedMessage
  | AnalysisProgressMessage
  | AnalysisLayerReadyMessage
  | AnalysisCompleteMessage
  | AnalysisErrorMessage
  | GenericMessage

// Type guards
export function isSystemStateMessage(msg: ISIMessage): msg is SystemStateMessage {
  return msg.type === 'system_state'
}

export function isZeroMQReadyMessage(msg: ISIMessage): msg is ZeroMQReadyMessage {
  return msg.type === 'zeromq_ready'
}

export function isFrontendReadyMessage(msg: ISIMessage): msg is FrontendReadyMessage {
  return msg.type === 'frontend_ready'
}

export function isParameterUpdateMessage(msg: ISIMessage): msg is ParameterUpdateMessage {
  return msg.type === 'parameter_update'
}

export function isHardwareStatusMessage(msg: ISIMessage): msg is HardwareStatusMessage {
  return msg.type === 'hardware_status'
}
