/**
 * ISI Macroscope Control System - IPC Client
 *
 * Electron IPC client for communication with Python backend.
 * Implements strict thin client pattern - only forwards user actions
 * and receives display updates. Contains NO business logic.
 */

import type {
  UserAction,
  DisplayUpdate,
  BinaryDataMetadata,
  IPCCommunication,
  ClickAction,
  InputAction,
  SelectAction,
  NavigationAction,
} from '../types/ipc-messages';
import { useBackendMirrorActions } from '../stores/backend-mirror';
import { useNotificationActions } from '../stores/ui-store';

// ============================================================================
// IPC CLIENT IMPLEMENTATION
// ============================================================================

class ISIIPCClient implements IPCCommunication {
  private isConnectedState = false;
  private displayUpdateCallbacks: Array<(update: DisplayUpdate) => void> = [];
  private binaryDataCallbacks: Array<(data: ArrayBuffer, metadata: BinaryDataMetadata) => void> = [];
  private connectionHealthTimer?: NodeJS.Timeout;

  constructor() {
    this.initializeIPC();
    this.startConnectionHealthMonitoring();
  }

  private initializeIPC(): void {
    // Initialize Electron IPC listeners
    if (typeof window !== 'undefined' && window.electronAPI) {
      // Listen for display updates from backend
      window.electronAPI.onDisplayUpdate((update: DisplayUpdate) => {
        this.handleDisplayUpdate(update);
      });

      // Listen for binary data streams (previews, results)
      window.electronAPI.onBinaryData((data: ArrayBuffer, metadata: BinaryDataMetadata) => {
        this.handleBinaryData(data, metadata);
      });

      // Listen for connection status changes
      window.electronAPI.onConnectionStatus((isConnected: boolean) => {
        this.isConnectedState = isConnected;
      });

      // Listen for IPC errors
      window.electronAPI.onIPCError((error: string) => {
        console.error('IPC Error:', error);
        // Notify UI of IPC errors
        const notifications = useNotificationActions();
        notifications.addToast({
          type: 'error',
          title: 'Communication Error',
          message: `IPC communication error: ${error}`,
          autoDismiss: true,
          dismissAfterMs: 5000,
        });
      });
    }
  }

  private startConnectionHealthMonitoring(): void {
    // Monitor connection health every 5 seconds
    this.connectionHealthTimer = setInterval(() => {
      this.checkConnectionHealth();
    }, 5000);
  }

  private checkConnectionHealth(): void {
    if (typeof window !== 'undefined' && window.electronAPI) {
      window.electronAPI.ping()
        .then(() => {
          if (!this.isConnectedState) {
            this.isConnectedState = true;
            const actions = useBackendMirrorActions();
            actions.setConnectionStatus(true, 'GOOD');
          }
        })
        .catch(() => {
          if (this.isConnectedState) {
            this.isConnectedState = false;
            const actions = useBackendMirrorActions();
            actions.setConnectionStatus(false, 'DISCONNECTED');
          }
        });
    }
  }

  private handleDisplayUpdate(update: DisplayUpdate): void {
    // Update backend mirror with display data
    const actions = useBackendMirrorActions();

    // Record IPC latency
    const latency = Date.now() - update.timestamp;
    actions.recordIPCLatency(latency);

    // Update display data based on update type
    actions.updateFromBackend(update.data);
    actions.updateLastContact();

    // Notify registered callbacks
    this.displayUpdateCallbacks.forEach(callback => {
      try {
        callback(update);
      } catch (error) {
        console.error('Error in display update callback:', error);
      }
    });
  }

  private handleBinaryData(data: ArrayBuffer, metadata: BinaryDataMetadata): void {
    // Handle binary data streams (preview frames, analysis results)
    this.binaryDataCallbacks.forEach(callback => {
      try {
        callback(data, metadata);
      } catch (error) {
        console.error('Error in binary data callback:', error);
      }
    });

    // Update performance metrics for preview frames
    if (metadata.type === 'PREVIEW_FRAME') {
      const actions = useBackendMirrorActions();
      actions.updateFrameTimestamp(Date.now());
    }
  }

  // ============================================================================
  // PUBLIC API IMPLEMENTATION
  // ============================================================================

  async sendUserAction(action: UserAction): Promise<void> {
    if (!this.isConnected()) {
      throw new Error('IPC client not connected to backend');
    }

    // Add timestamp metadata
    const actionWithTimestamp: UserAction = {
      ...action,
      metadata: {
        timestamp: Date.now(),
        ...action.metadata,
      },
    };

    try {
      if (typeof window !== 'undefined' && window.electronAPI) {
        await window.electronAPI.sendUserAction(actionWithTimestamp);
      } else {
        throw new Error('Electron API not available');
      }
    } catch (error) {
      console.error('Failed to send user action:', error);

      // Notify UI of send failure
      const notifications = useNotificationActions();
      notifications.addToast({
        type: 'error',
        title: 'Action Failed',
        message: `Failed to send action: ${action.element}`,
        autoDismiss: true,
        dismissAfterMs: 3000,
      });

      throw error;
    }
  }

  onDisplayUpdate(callback: (update: DisplayUpdate) => void): void {
    this.displayUpdateCallbacks.push(callback);
  }

  onBinaryData(callback: (data: ArrayBuffer, metadata: BinaryDataMetadata) => void): void {
    this.binaryDataCallbacks.push(callback);
  }

  isConnected(): boolean {
    return this.isConnectedState;
  }

  disconnect(): void {
    // Clean up connection health monitoring
    if (this.connectionHealthTimer) {
      clearInterval(this.connectionHealthTimer);
      this.connectionHealthTimer = undefined;
    }

    // Clear callbacks
    this.displayUpdateCallbacks = [];
    this.binaryDataCallbacks = [];

    // Update connection state
    this.isConnectedState = false;
    const actions = useBackendMirrorActions();
    actions.setConnectionStatus(false, 'DISCONNECTED');
  }
}

// ============================================================================
// SINGLETON INSTANCE
// ============================================================================

let ipcClientInstance: ISIIPCClient | null = null;

export function getIPCClient(): ISIIPCClient {
  if (!ipcClientInstance) {
    ipcClientInstance = new ISIIPCClient();
  }
  return ipcClientInstance;
}

// ============================================================================
// TYPED ACTION HELPERS
// ============================================================================

/**
 * Helper functions for sending typed user actions
 * These provide better type safety and consistency
 */

export async function sendClickAction(element: string, sessionId?: string): Promise<void> {
  const action: ClickAction = {
    type: 'CLICK',
    element,
    metadata: { timestamp: Date.now(), sessionId },
  };

  return getIPCClient().sendUserAction(action);
}

export async function sendInputAction(
  element: string,
  value: string | number,
  sessionId?: string
): Promise<void> {
  const action: InputAction = {
    type: 'INPUT',
    element,
    value,
    metadata: { timestamp: Date.now(), sessionId },
  };

  return getIPCClient().sendUserAction(action);
}

export async function sendSelectAction(
  element: string,
  value: string | number,
  sessionId?: string
): Promise<void> {
  const action: SelectAction = {
    type: 'SELECT',
    element,
    value,
    metadata: { timestamp: Date.now(), sessionId },
  };

  return getIPCClient().sendUserAction(action);
}

export async function sendNavigationAction(
  element: string,
  targetView?: string,
  sessionId?: string
): Promise<void> {
  const action: NavigationAction = {
    type: 'NAVIGATION',
    element,
    value: targetView,
    metadata: { timestamp: Date.now(), sessionId },
  };

  return getIPCClient().sendUserAction(action);
}

// ============================================================================
// HOOKS FOR REACT INTEGRATION
// ============================================================================

export function useIPCActions() {
  return {
    sendClick: sendClickAction,
    sendInput: sendInputAction,
    sendSelect: sendSelectAction,
    sendNavigation: sendNavigationAction,
    isConnected: () => getIPCClient().isConnected(),
  };
}

// ============================================================================
// ELECTRON API TYPE DEFINITIONS
// ============================================================================

declare global {
  interface Window {
    electronAPI?: {
      // Send user action to backend
      sendUserAction: (action: UserAction) => Promise<void>;

      // Listen for display updates
      onDisplayUpdate: (callback: (update: DisplayUpdate) => void) => void;

      // Listen for binary data streams
      onBinaryData: (callback: (data: ArrayBuffer, metadata: BinaryDataMetadata) => void) => void;

      // Listen for connection status changes
      onConnectionStatus: (callback: (isConnected: boolean) => void) => void;

      // Listen for IPC errors
      onIPCError: (callback: (error: string) => void) => void;

      // Health check ping
      ping: () => Promise<void>;
    };
  }
}