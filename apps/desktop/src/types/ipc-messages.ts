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
