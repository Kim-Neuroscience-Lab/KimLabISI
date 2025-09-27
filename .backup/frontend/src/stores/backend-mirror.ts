/**
 * ISI Macroscope Control System - Backend Display Mirror
 *
 * Read-only mirror of backend state for display purposes.
 * Contains NO business logic - only display data from backend.
 * Updated exclusively by IPC messages from backend.
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import type {
  ReadonlyDisplayData,
  WorkflowStateDisplay,
  ProgressDisplay,
  HardwareStatusDisplay,
  ErrorDisplay,
  PreviewDisplay,
  ResultsDisplay,
  SystemHealthDisplay,
} from '../types/ipc-messages';

// ============================================================================
// BACKEND DISPLAY STATE INTERFACE
// ============================================================================

export interface BackendDisplayState {
  // Connection status
  readonly isConnected: boolean;
  readonly lastUpdateTimestamp: number;
  readonly connectionHealth: 'EXCELLENT' | 'GOOD' | 'POOR' | 'DISCONNECTED';

  // Current display data from backend
  readonly workflowState: WorkflowStateDisplay | null;
  readonly progress: ProgressDisplay | null;
  readonly hardware: HardwareStatusDisplay | null;
  readonly errors: readonly ErrorDisplay[];
  readonly preview: PreviewDisplay | null;
  readonly results: ResultsDisplay | null;
  readonly systemHealth: SystemHealthDisplay | null;

  // Session information
  readonly currentSessionId: string | null;
  readonly sessionStartTime: number | null;
  readonly sessionMetadata: Record<string, unknown> | null;

  // Performance metrics for display
  readonly performanceMetrics: {
    readonly ipcLatency: number;
    readonly updateFrequency: number;
    readonly lastFrameTimestamp: number;
    readonly droppedUpdates: number;
  };
}

// ============================================================================
// BACKEND MIRROR ACTIONS INTERFACE
// ============================================================================

export interface BackendMirrorActions {
  // Connection management
  setConnectionStatus: (isConnected: boolean, health?: BackendDisplayState['connectionHealth']) => void;
  updateLastContact: () => void;

  // Update display data from backend (read-only)
  updateWorkflowState: (workflowState: WorkflowStateDisplay | null) => void;
  updateProgress: (progress: ProgressDisplay | null) => void;
  updateHardwareStatus: (hardware: HardwareStatusDisplay | null) => void;
  updateErrors: (errors: readonly ErrorDisplay[]) => void;
  updatePreview: (preview: PreviewDisplay | null) => void;
  updateResults: (results: ResultsDisplay | null) => void;
  updateSystemHealth: (health: SystemHealthDisplay | null) => void;

  // Batch update from IPC message
  updateFromBackend: (data: ReadonlyDisplayData) => void;

  // Session management
  setCurrentSession: (sessionId: string | null, startTime?: number, metadata?: Record<string, unknown>) => void;

  // Performance tracking
  recordIPCLatency: (latencyMs: number) => void;
  incrementDroppedUpdates: () => void;
  updateFrameTimestamp: (timestamp: number) => void;

  // Utility
  resetDisplayState: () => void;
  getSnapshot: () => BackendDisplayState;
}

// ============================================================================
// INITIAL STATE
// ============================================================================

const initialState: BackendDisplayState = {
  isConnected: false,
  lastUpdateTimestamp: 0,
  connectionHealth: 'DISCONNECTED',

  workflowState: null,
  progress: null,
  hardware: null,
  errors: [],
  preview: null,
  results: null,
  systemHealth: null,

  currentSessionId: null,
  sessionStartTime: null,
  sessionMetadata: null,

  performanceMetrics: {
    ipcLatency: 0,
    updateFrequency: 0,
    lastFrameTimestamp: 0,
    droppedUpdates: 0,
  },
};

// ============================================================================
// ZUSTAND STORE
// ============================================================================

export const useBackendMirror = create<BackendDisplayState & BackendMirrorActions>()(
  devtools(
    (set, get) => ({
      ...initialState,

      // Connection management
      setConnectionStatus: (isConnected, health = 'GOOD') =>
        set((state) => ({
          ...state,
          isConnected,
          connectionHealth: isConnected ? health : 'DISCONNECTED',
          lastUpdateTimestamp: Date.now(),
        })),

      updateLastContact: () =>
        set((state) => ({
          ...state,
          lastUpdateTimestamp: Date.now(),
          connectionHealth: state.isConnected
            ? (Date.now() - state.lastUpdateTimestamp < 5000 ? 'GOOD' : 'POOR')
            : 'DISCONNECTED',
        })),

      // Update display data from backend (read-only)
      updateWorkflowState: (workflowState) =>
        set((state) => ({
          ...state,
          workflowState,
          lastUpdateTimestamp: Date.now(),
        })),

      updateProgress: (progress) =>
        set((state) => ({
          ...state,
          progress,
          lastUpdateTimestamp: Date.now(),
        })),

      updateHardwareStatus: (hardware) =>
        set((state) => ({
          ...state,
          hardware,
          lastUpdateTimestamp: Date.now(),
        })),

      updateErrors: (errors) =>
        set((state) => ({
          ...state,
          errors,
          lastUpdateTimestamp: Date.now(),
        })),

      updatePreview: (preview) => {
        const timestamp = Date.now();
        set((state) => ({
          ...state,
          preview,
          lastUpdateTimestamp: timestamp,
          performanceMetrics: {
            ...state.performanceMetrics,
            lastFrameTimestamp: timestamp,
          },
        }));
      },

      updateResults: (results) =>
        set((state) => ({
          ...state,
          results,
          lastUpdateTimestamp: Date.now(),
        })),

      updateSystemHealth: (systemHealth) =>
        set((state) => ({
          ...state,
          systemHealth,
          lastUpdateTimestamp: Date.now(),
        })),

      // Batch update from IPC message
      updateFromBackend: (data) => {
        const timestamp = Date.now();
        set((state) => {
          const newState = { ...state, lastUpdateTimestamp: timestamp };

          // Update only the fields that are provided
          if (data.workflowState !== undefined) {
            newState.workflowState = data.workflowState;
          }
          if (data.progress !== undefined) {
            newState.progress = data.progress;
          }
          if (data.hardware !== undefined) {
            newState.hardware = data.hardware;
          }
          if (data.errors !== undefined) {
            newState.errors = data.errors;
          }
          if (data.preview !== undefined) {
            newState.preview = data.preview;
            newState.performanceMetrics = {
              ...newState.performanceMetrics,
              lastFrameTimestamp: timestamp,
            };
          }
          if (data.results !== undefined) {
            newState.results = data.results;
          }
          if (data.systemHealth !== undefined) {
            newState.systemHealth = data.systemHealth;
          }

          return newState;
        });
      },

      // Session management
      setCurrentSession: (sessionId, startTime, metadata) =>
        set((state) => ({
          ...state,
          currentSessionId: sessionId,
          sessionStartTime: startTime || Date.now(),
          sessionMetadata: metadata || null,
        })),

      // Performance tracking
      recordIPCLatency: (latencyMs) => {
        set((state) => {
          // Calculate rolling average of update frequency
          const timeSinceLastUpdate = Date.now() - state.performanceMetrics.lastFrameTimestamp;
          const newFrequency = timeSinceLastUpdate > 0 ? 1000 / timeSinceLastUpdate : 0;
          const smoothedFrequency = state.performanceMetrics.updateFrequency * 0.9 + newFrequency * 0.1;

          return {
            ...state,
            performanceMetrics: {
              ...state.performanceMetrics,
              ipcLatency: latencyMs,
              updateFrequency: smoothedFrequency,
            },
          };
        });
      },

      incrementDroppedUpdates: () =>
        set((state) => ({
          ...state,
          performanceMetrics: {
            ...state.performanceMetrics,
            droppedUpdates: state.performanceMetrics.droppedUpdates + 1,
          },
        })),

      updateFrameTimestamp: (timestamp) =>
        set((state) => ({
          ...state,
          performanceMetrics: {
            ...state.performanceMetrics,
            lastFrameTimestamp: timestamp,
          },
        })),

      // Utility
      resetDisplayState: () => set(initialState),

      getSnapshot: () => get(),
    }),
    {
      name: 'backend-mirror',
      enabled: process.env.NODE_ENV === 'development',
    }
  )
);

// ============================================================================
// SELECTOR HOOKS FOR PERFORMANCE
// ============================================================================

// Connection selectors
export const useConnectionStatus = () => useBackendMirror((state) => ({
  isConnected: state.isConnected,
  lastUpdate: state.lastUpdateTimestamp,
  health: state.connectionHealth,
}));

// Workflow state selectors
export const useWorkflowState = () => useBackendMirror((state) => state.workflowState);
export const useWorkflowActions = () => useBackendMirror((state) => state.workflowState?.availableActions || []);

// Progress selectors
export const useProgress = () => useBackendMirror((state) => state.progress);
export const useProgressPercentage = () => useBackendMirror((state) => state.progress?.overallProgress || 0);

// Hardware status selectors
export const useHardwareStatus = () => useBackendMirror((state) => state.hardware);
export const useOverallHardwareStatus = () => useBackendMirror((state) => state.hardware?.overallStatus || 'UNKNOWN');

// Error selectors
export const useErrors = () => useBackendMirror((state) => state.errors);
export const useCriticalErrors = () => useBackendMirror((state) =>
  state.errors.filter(error => error.severity === 'CRITICAL' || error.severity === 'ERROR')
);

// Preview selectors
export const usePreview = () => useBackendMirror((state) => state.preview);
export const useStimulusPreview = () => useBackendMirror((state) => state.preview?.stimulus);
export const useCameraPreview = () => useBackendMirror((state) => state.preview?.camera);
export const useAcquisitionStats = () => useBackendMirror((state) => state.preview?.acquisitionStats);

// Results selectors
export const useResults = () => useBackendMirror((state) => state.results);
export const useResultsMaps = () => useBackendMirror((state) => state.results?.maps || []);
export const useResultsStatistics = () => useBackendMirror((state) => state.results?.statistics);

// System health selectors
export const useSystemHealth = () => useBackendMirror((state) => state.systemHealth);

// Session selectors
export const useCurrentSession = () => useBackendMirror((state) => ({
  sessionId: state.currentSessionId,
  startTime: state.sessionStartTime,
  metadata: state.sessionMetadata,
}));

// Performance selectors
export const usePerformanceMetrics = () => useBackendMirror((state) => state.performanceMetrics);

// Backend mirror actions
export const useBackendMirrorActions = () => useBackendMirror((state) => ({
  setConnectionStatus: state.setConnectionStatus,
  updateLastContact: state.updateLastContact,
  updateWorkflowState: state.updateWorkflowState,
  updateProgress: state.updateProgress,
  updateHardwareStatus: state.updateHardwareStatus,
  updateErrors: state.updateErrors,
  updatePreview: state.updatePreview,
  updateResults: state.updateResults,
  updateSystemHealth: state.updateSystemHealth,
  updateFromBackend: state.updateFromBackend,
  setCurrentSession: state.setCurrentSession,
  recordIPCLatency: state.recordIPCLatency,
  incrementDroppedUpdates: state.incrementDroppedUpdates,
  updateFrameTimestamp: state.updateFrameTimestamp,
  resetDisplayState: state.resetDisplayState,
}));