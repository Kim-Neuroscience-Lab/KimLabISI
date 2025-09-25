/**
 * ISI Macroscope Control System - IPC Message Types
 *
 * Strict typing for communication between frontend and backend.
 * Frontend sends only user actions, backend sends only display updates.
 * No business logic or validation in frontend.
 */

// ============================================================================
// USER ACTIONS: Frontend ’ Backend
// ============================================================================

export type UserActionType =
  | 'CLICK'           // User clicked a UI element
  | 'INPUT'           // User entered data
  | 'SELECT'          // User selected an option
  | 'NAVIGATION'      // User navigated to different view
  | 'FILE_OPERATION'  // User file operation (load, save)
  | 'SYSTEM_REQUEST'  // User requested system operation

export interface UserAction {
  readonly type: UserActionType;
  readonly element: string;           // UI element identifier
  readonly value?: string | number | boolean | object;
  readonly metadata?: {
    readonly timestamp: number;
    readonly sessionId?: string;
  };
}

// Specific user action types for better typing
export interface ClickAction extends UserAction {
  readonly type: 'CLICK';
  readonly element: string;
}

export interface InputAction extends UserAction {
  readonly type: 'INPUT';
  readonly element: string;
  readonly value: string | number;
}

export interface SelectAction extends UserAction {
  readonly type: 'SELECT';
  readonly element: string;
  readonly value: string | number;
}

export interface NavigationAction extends UserAction {
  readonly type: 'NAVIGATION';
  readonly element: string;
  readonly value?: string; // target page/view
}

// ============================================================================
// DISPLAY UPDATES: Backend ’ Frontend
// ============================================================================

export type DisplayUpdateType =
  | 'STATE_CHANGE'       // Workflow state changed
  | 'PROGRESS_UPDATE'    // Progress indication update
  | 'HARDWARE_STATUS'    // Hardware status changed
  | 'ERROR_STATE'        // Error conditions
  | 'DATA_PREVIEW'       // Preview data for display
  | 'RESULTS_READY'      // Analysis results available
  | 'SYSTEM_HEALTH'      // Overall system health

export interface DisplayUpdate {
  readonly type: DisplayUpdateType;
  readonly timestamp: number;
  readonly data: ReadonlyDisplayData;
}

// ============================================================================
// DISPLAY DATA: Read-only data for UI rendering
// ============================================================================

export interface ReadonlyDisplayData {
  readonly workflowState?: WorkflowStateDisplay;
  readonly progress?: ProgressDisplay;
  readonly hardware?: HardwareStatusDisplay;
  readonly errors?: ErrorDisplay[];
  readonly preview?: PreviewDisplay;
  readonly results?: ResultsDisplay;
  readonly systemHealth?: SystemHealthDisplay;
}

// Workflow state display information
export interface WorkflowStateDisplay {
  readonly currentState: WorkflowState;
  readonly availableActions: readonly UserActionDescriptor[];
  readonly stateTitle: string;
  readonly stateDescription: string;
  readonly canNavigateBack: boolean;
  readonly progressPercentage?: number;
}

export type WorkflowState =
  | 'STARTUP'
  | 'SETUP_READY'
  | 'SETUP'
  | 'GENERATION_READY'
  | 'GENERATION'
  | 'ACQUISITION_READY'
  | 'ACQUISITION'
  | 'ANALYSIS_READY'
  | 'ANALYSIS'
  | 'ERROR'
  | 'RECOVERY'
  | 'DEGRADED';

// Available actions that user can perform
export interface UserActionDescriptor {
  readonly actionElement: string;
  readonly actionType: UserActionType;
  readonly displayText: string;
  readonly isEnabled: boolean;
  readonly isPrimary?: boolean;
  readonly requiresConfirmation?: boolean;
  readonly confirmationText?: string;
}

// Progress display for long-running operations
export interface ProgressDisplay {
  readonly operationName: string;
  readonly currentStep: string;
  readonly totalSteps: number;
  readonly currentStepNumber: number;
  readonly overallProgress: number; // 0-100
  readonly stepProgress: number;    // 0-100
  readonly isIndeterminate: boolean;
  readonly estimatedTimeRemaining?: string;
  readonly canCancel: boolean;
  readonly details?: readonly string[];
}

// Hardware status display
export interface HardwareStatusDisplay {
  readonly rtx4070: HardwareComponentStatus;
  readonly pcoPanda: HardwareComponentStatus;
  readonly samsung990Pro: HardwareComponentStatus;
  readonly intel13700K: HardwareComponentStatus;
  readonly overallStatus: 'OPERATIONAL' | 'DEGRADED' | 'FAILED' | 'UNKNOWN';
}

export interface HardwareComponentStatus {
  readonly name: string;
  readonly status: 'CONNECTED' | 'DISCONNECTED' | 'ERROR' | 'UNKNOWN';
  readonly details?: string;
  readonly temperature?: number;
  readonly utilization?: number;
  readonly availableMemory?: string;
}

// Error display information
export interface ErrorDisplay {
  readonly id: string;
  readonly severity: 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  readonly title: string;
  readonly message: string;
  readonly timestamp: number;
  readonly canDismiss: boolean;
  readonly suggestedActions?: readonly UserActionDescriptor[];
  readonly technicalDetails?: string;
}

// Preview display for real-time monitoring
export interface PreviewDisplay {
  readonly stimulus?: PreviewFrameData;
  readonly camera?: PreviewFrameData;
  readonly acquisitionStats?: AcquisitionStatsDisplay;
}

export interface PreviewFrameData {
  readonly frameNumber: number;
  readonly timestamp: number;
  readonly imageData: ArrayBuffer; // Binary frame data
  readonly width: number;
  readonly height: number;
  readonly format: 'JPEG' | 'PNG' | 'RAW';
}

export interface AcquisitionStatsDisplay {
  readonly stimulusFps: number;
  readonly cameraFps: number;
  readonly droppedFrames: number;
  readonly bufferUtilization: number;
  readonly dataRateBytes: number;
  readonly currentDirection: 'LR' | 'RL' | 'TB' | 'BT';
  readonly currentTrial: number;
  readonly totalTrials: number;
}

// Results display for analysis output
export interface ResultsDisplay {
  readonly maps?: ResultsMapDisplay[];
  readonly statistics?: ResultsStatisticsDisplay;
  readonly exportOptions?: readonly ExportOptionDisplay[];
  readonly qualityMetrics?: QualityMetricsDisplay;
}

export interface ResultsMapDisplay {
  readonly name: string;
  readonly description: string;
  readonly imageData: ArrayBuffer;
  readonly width: number;
  readonly height: number;
  readonly colormap: string;
  readonly valueRange: readonly [number, number];
}

export interface ResultsStatisticsDisplay {
  readonly totalFramesProcessed: number;
  readonly correlationQuality: number;
  readonly signalToNoise: number;
  readonly coveragePercentage: number;
  readonly processingTimeSeconds: number;
}

export interface ExportOptionDisplay {
  readonly format: string;
  readonly description: string;
  readonly actionElement: string;
  readonly isAvailable: boolean;
}

export interface QualityMetricsDisplay {
  readonly overall: number; // 0-100
  readonly spatialCoverage: number;
  readonly temporalStability: number;
  readonly signalClarity: number;
  readonly recommendations?: readonly string[];
}

// System health display
export interface SystemHealthDisplay {
  readonly overall: 'EXCELLENT' | 'GOOD' | 'WARNING' | 'CRITICAL' | 'UNKNOWN';
  readonly cpuUsage: number;
  readonly memoryUsage: number;
  readonly gpuUsage: number;
  readonly storageUsage: number;
  readonly temperature: number;
  readonly uptime: string;
}

// ============================================================================
// IPC COMMUNICATION WRAPPER
// ============================================================================

export interface IPCCommunication {
  // Send user action to backend
  sendUserAction: (action: UserAction) => Promise<void>;

  // Subscribe to display updates from backend
  onDisplayUpdate: (callback: (update: DisplayUpdate) => void) => void;

  // Binary data streaming for previews
  onBinaryData: (callback: (data: ArrayBuffer, metadata: BinaryDataMetadata) => void) => void;

  // Connection management
  isConnected: () => boolean;
  disconnect: () => void;
}

export interface BinaryDataMetadata {
  readonly type: 'PREVIEW_FRAME' | 'ANALYSIS_RESULT';
  readonly frameNumber?: number;
  readonly timestamp: number;
  readonly format: string;
  readonly width?: number;
  readonly height?: number;
}