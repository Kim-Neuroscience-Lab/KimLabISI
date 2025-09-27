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
      // Listen for backend messages (including display updates)
      window.electronAPI.onBackendMessage((message: any) => {
        this.handleBackendMessage(message);
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
    // Connection health is now managed by the backend
    // Frontend only reacts to connection status updates from backend
    console.log('IPC Client: Connection monitoring delegated to backend');
  }

  private handleBackendMessage(message: any): void {
    // Handle different types of backend messages
    if (message.type === 'state_batch') {
      // Backend sends batched updates - process each update in the batch
      if (message.updates && Array.isArray(message.updates)) {
        message.updates.forEach((update: any) => {
          const displayUpdate: DisplayUpdate = {
            timestamp: update.timestamp || message.timestamp || Date.now(),
            data: update,
          };
          this.handleDisplayUpdate(displayUpdate);
        });
      }
    } else if (message.type === 'state_update' || message.type === 'system_health') {
      // Handle individual state updates
      const displayUpdate: DisplayUpdate = {
        timestamp: message.timestamp || Date.now(),
        data: message,
      };
      this.handleDisplayUpdate(displayUpdate);
    } else if (message.type === 'notification') {
      // Handle backend notifications
      const notifications = useNotificationActions();
      notifications.addToast({
        type: message.payload?.level || 'info',
        title: message.payload?.title || 'Backend Notification',
        message: message.payload?.message || 'Notification from backend',
        autoDismiss: true,
        dismissAfterMs: 5000,
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

    // Convert user action to backend command format
    const command = {
      message_type: 'command',
      message_id: `frontend_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: Date.now(),
      payload: {
        handler: 'command_handler',
        command: 'user_action',
        parameters: {
          action_type: action.type.toLowerCase(),
          element: action.element,
          value: action.value,
          metadata: {
            timestamp: Date.now(),
            ...action.metadata,
          }
        }
      }
    };

    try {
      if (typeof window !== 'undefined' && window.electronAPI) {
        await window.electronAPI.sendBackendCommand(command);
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
      // Send command to backend
      sendBackendCommand: (message: any) => Promise<any>;

      // Get backend status
      getBackendStatus: () => Promise<any>;

      // Get app info
      getAppInfo: () => Promise<any>;

      // Listen for backend messages
      onBackendMessage: (callback: (message: any) => void) => void;

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