/**
 * ISI Macroscope Control System - Preload Script
 *
 * This preload script provides a secure bridge between the Electron main process
 * and the renderer process, following security best practices and thin client
 * architecture principles.
 *
 * Security Features:
 * - Context isolation enabled
 * - Node integration disabled
 * - Exposed APIs are minimal and controlled
 * - All backend communication proxied through main process
 *
 * Thin Client Architecture:
 * - No business logic in renderer
 * - All commands forwarded to Python backend
 * - Frontend only handles UI state and presentation
 */

const { contextBridge, ipcRenderer } = require('electron');

/**
 * Secure API exposed to renderer process
 * Following thin client principles - all business logic requests go to backend
 */
const isiMacroscopeAPI = {
    /**
     * Backend Communication APIs
     * These forward all business logic to the Python backend
     */
    backend: {
        /**
         * Send command to Python backend
         * @param {string} command - Command type (e.g., 'workflow.start')
         * @param {object} parameters - Command parameters
         * @returns {Promise<object>} Backend response
         */
        sendCommand: async (command, parameters = {}) => {
            try {
                console.log(`🎨 Frontend sending command: ${command}`, parameters);
                const response = await ipcRenderer.invoke('backend-command', command, parameters);
                console.log(`🎨 Frontend received response:`, response);
                return response;
            } catch (error) {
                console.error(`🎨 Command failed: ${command}`, error);
                return {
                    success: false,
                    error_message: error.message,
                    data: {}
                };
            }
        },

        /**
         * Send query to Python backend
         * @param {object} query - Query parameters
         * @returns {Promise<object>} Backend response
         */
        sendQuery: async (query = {}) => {
            try {
                console.log('🎨 Frontend sending query:', query);
                const response = await ipcRenderer.invoke('backend-query', query);
                console.log('🎨 Frontend received query response:', response);
                return response;
            } catch (error) {
                console.error('🎨 Query failed:', error);
                return {
                    success: false,
                    error_message: error.message,
                    data: {}
                };
            }
        },

        /**
         * Get backend connection status
         * @returns {Promise<object>} Connection status
         */
        getConnectionStatus: async () => {
            return await ipcRenderer.invoke('get-connection-status');
        },

        /**
         * Get system information from backend
         * @returns {Promise<object>} System info
         */
        getSystemInfo: async () => {
            return await ipcRenderer.invoke('get-system-info');
        }
    },

    /**
     * Workflow Management APIs (forwarded to backend)
     * Following thin client - no workflow logic in frontend
     */
    workflow: {
        /**
         * Start the workflow system
         */
        start: async () => {
            return await isiMacroscopeAPI.backend.sendCommand('workflow.start');
        },

        /**
         * Get current workflow state
         */
        getState: async () => {
            return await isiMacroscopeAPI.backend.sendCommand('workflow.get_state');
        },

        /**
         * Transition to a new workflow state
         * @param {string} targetState - Target state name
         */
        transitionTo: async (targetState) => {
            return await isiMacroscopeAPI.backend.sendCommand('workflow.transition', {
                target_state: targetState
            });
        },

        /**
         * Get workflow transition history
         */
        getHistory: async () => {
            return await isiMacroscopeAPI.backend.sendCommand('workflow.get_history');
        }
    },

    /**
     * Hardware Management APIs (forwarded to backend)
     * Following thin client - no hardware logic in frontend
     */
    hardware: {
        /**
         * Detect available hardware
         */
        detect: async () => {
            return await isiMacroscopeAPI.backend.sendCommand('hardware.detect');
        },

        /**
         * Get hardware status
         */
        getStatus: async () => {
            return await isiMacroscopeAPI.backend.sendCommand('hardware.get_status');
        }
    },

    /**
     * System Management APIs (forwarded to backend)
     */
    system: {
        /**
         * Perform system health check
         */
        healthCheck: async () => {
            return await isiMacroscopeAPI.backend.sendCommand('system.health_check');
        },

        /**
         * Get system information
         */
        getInfo: async () => {
            return await isiMacroscopeAPI.backend.sendCommand('system.get_info');
        }
    },

    /**
     * Event Subscription APIs
     * For receiving updates from backend
     */
    events: {
        /**
         * Subscribe to backend connection events
         * @param {function} callback - Event callback
         */
        onBackendConnected: (callback) => {
            ipcRenderer.on('backend-connected', callback);
        },

        /**
         * Subscribe to backend disconnection events
         * @param {function} callback - Event callback
         */
        onBackendDisconnected: (callback) => {
            ipcRenderer.on('backend-disconnected', callback);
        },

        /**
         * Subscribe to backend connection attempts
         * @param {function} callback - Event callback
         */
        onBackendConnecting: (callback) => {
            ipcRenderer.on('backend-connecting', callback);
        },

        /**
         * Remove event listeners
         * @param {string} event - Event name
         * @param {function} callback - Callback to remove
         */
        removeListener: (event, callback) => {
            ipcRenderer.removeListener(event, callback);
        },

        /**
         * Remove all listeners for an event
         * @param {string} event - Event name
         */
        removeAllListeners: (event) => {
            ipcRenderer.removeAllListeners(event);
        }
    },

    /**
     * Utility APIs
     */
    utils: {
        /**
         * Check if running in development mode
         * @returns {Promise<boolean>} Development mode status
         */
        isDevelopment: async () => {
            const status = await isiMacroscopeAPI.backend.getConnectionStatus();
            return status.isDevelopment;
        },

        /**
         * Get application version info
         * @returns {Promise<object>} Version information
         */
        getVersionInfo: async () => {
            const systemInfo = await isiMacroscopeAPI.system.getInfo();
            return {
                frontend_version: '1.0.0',
                backend_version: systemInfo.data?.backend_version || 'unknown',
                electron_version: process.versions.electron,
                node_version: process.versions.node
            };
        }
    }
};

/**
 * Expose secure API to renderer process
 * This is the ONLY interface between frontend and backend
 * All business logic goes through this API to the Python backend
 */
contextBridge.exposeInMainWorld('isiMacroscope', isiMacroscopeAPI);

/**
 * Console logging for development
 */
if (process.env.NODE_ENV === 'development') {
    console.log('🎨 ISI Macroscope preload script loaded');
    console.log('🎨 Thin client API exposed to renderer');
    console.log('🎨 All business logic will be handled by Python backend');
}

/**
 * Security validation
 * Ensure we're running in a secure context
 */
window.addEventListener('DOMContentLoaded', () => {
    // Verify context isolation
    if (typeof process !== 'undefined') {
        console.error('❌ Security violation: Node.js process exposed to renderer');
    }

    // Verify API exposure
    if (typeof window.isiMacroscope === 'undefined') {
        console.error('❌ API not properly exposed to renderer');
    } else {
        console.log('✅ ISI Macroscope API properly exposed to renderer');
        console.log('✅ Security context validated');
    }
});