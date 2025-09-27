/**
 * ISI Macroscope Control System - Preload Script
 *
 * Provides secure bridge between sandboxed renderer and main process.
 * Implements context isolation with minimal API surface area.
 *
 * Security Features:
 * - Context isolation enabled
 * - Minimal API exposure
 * - Type-safe IPC communication
 * - No direct Node.js access from renderer
 */

import { contextBridge, ipcRenderer } from 'electron';

// Type definitions for IPC messages (must match backend types)
interface UserAction {
  type: 'CLICK' | 'INPUT' | 'SELECT' | 'NAVIGATION';
  element: string;
  value?: string | number;
  metadata?: {
    timestamp: number;
    sessionId?: string;
    [key: string]: any;
  };
}

interface DisplayUpdate {
  timestamp: number;
  data: {
    [key: string]: any;
  };
}

interface BinaryDataMetadata {
  type: 'PREVIEW_FRAME' | 'ANALYSIS_RESULT' | 'CALIBRATION_DATA';
  format: string;
  size: number;
  timestamp: number;
  [key: string]: any;
}

/**
 * Secure API exposed to renderer process
 * This is the ONLY interface between renderer and main process
 */
const electronAPI = {
  // ============================================================================
  // OUTGOING MESSAGES (Renderer -> Main -> Python Backend)
  // ============================================================================

  /**
   * Send command to Python backend
   * @param message Command message data
   */
  sendBackendCommand: async (message: any): Promise<any> => {
    // Add security metadata
    const secureMessage = {
      ...message,
      timestamp: Date.now(),
      source: 'renderer'
    };

    return ipcRenderer.invoke('send-backend-command', secureMessage);
  },

  /**
   * Get backend status
   */
  getBackendStatus: async (): Promise<any> => {
    return ipcRenderer.invoke('get-backend-status');
  },

  /**
   * Get app info
   */
  getAppInfo: async (): Promise<any> => {
    return ipcRenderer.invoke('get-app-info');
  },

  /**
   * Ping main process for health check
   */
  ping: async (): Promise<void> => {
    return ipcRenderer.invoke('ping');
  },

  // ============================================================================
  // INCOMING MESSAGES (Python Backend -> Main -> Renderer)
  // ============================================================================

  /**
   * Listen for display updates from Python backend
   * @param callback Function to handle display updates
   */
  onDisplayUpdate: (callback: (update: DisplayUpdate) => void): void => {
    // Validate callback is a function
    if (typeof callback !== 'function') {
      throw new Error('Display update callback must be a function');
    }

    ipcRenderer.on('display-update', (event, update: DisplayUpdate) => {
      try {
        // Basic validation of update structure
        if (!update || typeof update.timestamp !== 'number' || !update.data) {
          console.error('Invalid display update received:', update);
          return;
        }

        callback(update);
      } catch (error) {
        console.error('Error processing display update:', error);
      }
    });
  },

  /**
   * Listen for binary data streams from Python backend
   * @param callback Function to handle binary data
   */
  onBinaryData: (callback: (data: ArrayBuffer, metadata: BinaryDataMetadata) => void): void => {
    // Validate callback is a function
    if (typeof callback !== 'function') {
      throw new Error('Binary data callback must be a function');
    }

    ipcRenderer.on('binary-data', (event, data: ArrayBuffer, metadata: BinaryDataMetadata) => {
      try {
        // Basic validation of binary data and metadata
        if (!data || !(data instanceof ArrayBuffer)) {
          console.error('Invalid binary data received');
          return;
        }

        if (!metadata || !metadata.type || !metadata.format) {
          console.error('Invalid binary data metadata received:', metadata);
          return;
        }

        callback(data, metadata);
      } catch (error) {
        console.error('Error processing binary data:', error);
      }
    });
  },

  /**
   * Listen for backend messages
   * @param callback Function to handle backend messages
   */
  onBackendMessage: (callback: (message: any) => void): void => {
    // Validate callback is a function
    if (typeof callback !== 'function') {
      throw new Error('Backend message callback must be a function');
    }

    ipcRenderer.on('backend-message', (event, message: any) => {
      try {
        callback(message);
      } catch (error) {
        console.error('Error processing backend message:', error);
      }
    });
  },

  /**
   * Listen for connection status changes
   * @param callback Function to handle connection status changes
   */
  onConnectionStatus: (callback: (isConnected: boolean) => void): void => {
    // Validate callback is a function
    if (typeof callback !== 'function') {
      throw new Error('Connection status callback must be a function');
    }

    ipcRenderer.on('connection-status', (event, isConnected: boolean) => {
      try {
        if (typeof isConnected !== 'boolean') {
          console.error('Invalid connection status received:', isConnected);
          return;
        }

        callback(isConnected);
      } catch (error) {
        console.error('Error processing connection status:', error);
      }
    });
  },

  /**
   * Listen for IPC communication errors
   * @param callback Function to handle IPC errors
   */
  onIPCError: (callback: (error: string) => void): void => {
    // Validate callback is a function
    if (typeof callback !== 'function') {
      throw new Error('IPC error callback must be a function');
    }

    ipcRenderer.on('ipc-error', (event, error: string) => {
      try {
        if (typeof error !== 'string') {
          console.error('Invalid IPC error received:', error);
          return;
        }

        callback(error);
      } catch (callbackError) {
        console.error('Error processing IPC error:', callbackError);
      }
    });
  },

  // ============================================================================
  // UTILITY METHODS
  // ============================================================================

  /**
   * Remove all listeners (cleanup utility)
   */
  removeAllListeners: (): void => {
    ipcRenderer.removeAllListeners('display-update');
    ipcRenderer.removeAllListeners('binary-data');
    ipcRenderer.removeAllListeners('connection-status');
    ipcRenderer.removeAllListeners('ipc-error');
  },

  /**
   * Get Electron version info for debugging
   */
  getVersionInfo: (): { electron: string; chrome: string; node: string } => {
    return {
      electron: process.versions.electron,
      chrome: process.versions.chrome,
      node: process.versions.node,
    };
  },
};

// ============================================================================
// CONTEXT BRIDGE EXPOSURE
// ============================================================================

/**
 * Securely expose API to renderer process using context bridge
 * This is the ONLY way renderer can communicate with main process
 */
try {
  contextBridge.exposeInMainWorld('electronAPI', electronAPI);
  console.log('ISI Macroscope: Electron API exposed securely to renderer');
} catch (error) {
  console.error('ISI Macroscope: Failed to expose Electron API:', error);
}

// ============================================================================
// SECURITY HARDENING
// ============================================================================

// Prevent access to Node.js APIs from renderer
// This should already be blocked by sandbox mode, but adding extra safety
if (typeof window !== 'undefined') {
  // Remove any potential Node.js globals that might leak through
  delete (window as any).require;
  delete (window as any).process;
  delete (window as any).global;
  delete (window as any).Buffer;
  delete (window as any).__dirname;
  delete (window as any).__filename;
  delete (window as any).module;
  delete (window as any).exports;

  // Freeze the electronAPI to prevent tampering
  Object.freeze(electronAPI);
  Object.freeze((window as any).electronAPI);
}

// Log successful preload execution
console.log('ISI Macroscope: Preload script loaded successfully with security hardening');

// Export types for TypeScript support (these won't be available at runtime)
export type { UserAction, DisplayUpdate, BinaryDataMetadata };
