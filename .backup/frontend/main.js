/**
 * ISI Macroscope Control System - Frontend Main Entry Point
 *
 * This is the main Electron process for the ISI Macroscope Control System frontend.
 * Following ADR-0003 (Thin Client Architecture), this frontend contains ZERO business
 * logic and only handles UI presentation and communication with the Python backend.
 *
 * ZERO BUSINESS LOGIC PRINCIPLE:
 * - All workflow decisions made by Python backend
 * - All hardware control handled by Python backend
 * - All data processing performed by Python backend
 * - Frontend only sends commands and displays results
 *
 * Architecture Responsibilities:
 * - Initialize Electron application window
 * - Establish IPC connection to Python backend
 * - Route UI commands to backend for processing
 * - Display results received from backend
 * - Maintain thin client principles (no business logic)
 *
 * The backend (Python) contains ALL business logic, workflow state management,
 * hardware control, and data processing. The frontend only sends commands and
 * displays the responses.
 */

const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const WebSocket = require('ws');

// Development mode detection
const isDevelopment = process.env.NODE_ENV === 'development' || process.argv.includes('--dev');

// Backend connection configuration
const BACKEND_CONFIG = {
    host: 'localhost',
    port: 8765,
    maxReconnectAttempts: 5,
    reconnectDelay: 2000
};

/**
 * ISI Macroscope Frontend Application
 *
 * Manages the Electron application lifecycle and communication with the Python backend.
 * Strictly follows thin client architecture - contains no business logic.
 */
class ISIMacroscopeFrontend {
    constructor() {
        this.mainWindow = null;
        this.backendProcess = null;
        this.backendConnection = null;
        this.reconnectAttempts = 0;
        this.connectionStatus = 'disconnected';

        console.log('🎨 ISI Macroscope Frontend initializing...');
        console.log(`🎨 Development mode: ${isDevelopment}`);
    }

    /**
     * Initialize the Electron application
     */
    async initialize() {
        // Handle app ready event
        app.whenReady().then(() => {
            this.createMainWindow();
            this.setupIPC();
            this.startBackend();
        });

        // Handle window close events
        app.on('window-all-closed', () => {
            if (process.platform !== 'darwin') {
                this.cleanup();
                app.quit();
            }
        });

        // Handle app activation (macOS)
        app.on('activate', () => {
            if (BrowserWindow.getAllWindows().length === 0) {
                this.createMainWindow();
            }
        });

        // Handle app quit
        app.on('before-quit', () => {
            this.cleanup();
        });

        console.log('🎨 Frontend initialization complete');
    }

    /**
     * Create the main application window following thin client principles
     */
    createMainWindow() {
        console.log('🪟 Creating main application window...');

        this.mainWindow = new BrowserWindow({
            width: 1200,
            height: 800,
            minWidth: 800,
            minHeight: 600,
            title: 'ISI Macroscope Control System',
            icon: path.join(__dirname, 'assets', 'icon.png'), // Add icon if available
            webPreferences: {
                nodeIntegration: false,
                contextIsolation: true,
                enableRemoteModule: false,
                preload: path.join(__dirname, 'preload.js'),
                webSecurity: !isDevelopment
            },
            show: false // Don't show until ready
        });

        // Load the main HTML file
        const htmlPath = isDevelopment
            ? path.join(__dirname, 'src', 'index.html')
            : path.join(__dirname, 'dist', 'index.html');

        this.mainWindow.loadFile(htmlPath);

        // Show window when ready
        this.mainWindow.once('ready-to-show', () => {
            this.mainWindow.show();

            if (isDevelopment) {
                this.mainWindow.webContents.openDevTools();
            }

            console.log('🪟 Main window ready and displayed');
        });

        // Handle window closed
        this.mainWindow.on('closed', () => {
            this.mainWindow = null;
        });
    }

    /**
     * Setup IPC communication between renderer and main process
     * All business logic requests are forwarded to Python backend
     */
    setupIPC() {
        console.log('📡 Setting up IPC communication...');

        // Handle backend command requests from renderer
        ipcMain.handle('backend-command', async (event, command, parameters = {}) => {
            return await this.sendBackendCommand(command, parameters);
        });

        // Handle backend query requests from renderer
        ipcMain.handle('backend-query', async (event, query) => {
            return await this.sendBackendQuery(query);
        });

        // Handle connection status requests
        ipcMain.handle('get-connection-status', () => {
            return {
                status: this.connectionStatus,
                isDevelopment: isDevelopment,
                backendConfig: BACKEND_CONFIG
            };
        });

        // Handle system info requests
        ipcMain.handle('get-system-info', async () => {
            if (this.connectionStatus === 'connected') {
                return await this.sendBackendCommand('system.get_info');
            } else {
                return {
                    success: false,
                    error_message: 'Backend not connected',
                    data: {}
                };
            }
        });

        console.log('📡 IPC communication setup complete');
    }

    /**
     * Start the Python backend process
     */
    async startBackend() {
        console.log('🐍 Starting Python backend...');

        try {
            // Backend startup command
            const backendPath = path.join(__dirname, '..', 'backend');
            const command = isDevelopment ? 'poetry' : 'python';
            const args = isDevelopment
                ? ['run', 'python', 'main.py', '--dev', '--port', BACKEND_CONFIG.port.toString()]
                : ['main.py', '--port', BACKEND_CONFIG.port.toString()];

            this.backendProcess = spawn(command, args, {
                cwd: backendPath,
                stdio: ['pipe', 'pipe', 'pipe']
            });

            // Handle backend output
            this.backendProcess.stdout.on('data', (data) => {
                console.log(`🐍 Backend: ${data.toString().trim()}`);
            });

            this.backendProcess.stderr.on('data', (data) => {
                console.error(`🐍 Backend Error: ${data.toString().trim()}`);
            });

            this.backendProcess.on('close', (code) => {
                console.log(`🐍 Backend process exited with code ${code}`);
                this.connectionStatus = 'disconnected';
                this.notifyRenderer('backend-disconnected', { code });
            });

            // Wait for backend to start, then connect
            setTimeout(() => {
                this.connectToBackend();
            }, 3000); // Give backend time to start

        } catch (error) {
            console.error('🐍 Failed to start backend:', error);
            this.showErrorDialog('Backend Startup Failed', `Failed to start Python backend: ${error.message}`);
        }
    }

    /**
     * Connect to the Python backend via WebSocket
     */
    async connectToBackend() {
        console.log('🔌 Connecting to Python backend WebSocket...');

        try {
            this.connectionStatus = 'connecting';
            this.notifyRenderer('backend-connecting');

            // Create WebSocket connection to Python backend
            const wsUrl = `ws://${BACKEND_CONFIG.host}:${BACKEND_CONFIG.port}`;
            this.backendConnection = new WebSocket(wsUrl);

            // Setup WebSocket event handlers
            this.backendConnection.onopen = () => {
                console.log('🔌 WebSocket connected to Python backend');
                this.connectionStatus = 'connected';
                this.reconnectAttempts = 0;
                this.notifyRenderer('backend-connected');
            };

            this.backendConnection.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    this.handleBackendMessage(message);
                } catch (error) {
                    console.error('🔌 Error parsing backend message:', error);
                }
            };

            this.backendConnection.onclose = (event) => {
                console.log('🔌 WebSocket connection closed:', event.code, event.reason);
                this.connectionStatus = 'disconnected';
                this.notifyRenderer('backend-disconnected', { code: event.code, reason: event.reason });

                // Attempt reconnection if not intentional
                if (event.code !== 1000) { // 1000 = normal closure
                    this.handleConnectionError(new Error(`Connection closed: ${event.reason}`));
                }
            };

            this.backendConnection.onerror = (error) => {
                console.error('🔌 WebSocket error:', error);
                this.connectionStatus = 'disconnected';
                this.handleConnectionError(error);
            };

        } catch (error) {
            console.error('🔌 Backend connection failed:', error);
            this.connectionStatus = 'disconnected';
            this.handleConnectionError(error);
        }
    }

    /**
     * Handle message received from Python backend
     */
    handleBackendMessage(message) {
        console.log('📥 Received backend message:', message);

        // Handle different message types
        switch (message.message_type) {
            case 'state_update':
                this.handleStateUpdate(message);
                break;
            case 'response':
                this.handleCommandResponse(message);
                break;
            case 'notification':
                this.handleNotification(message);
                break;
            case 'error':
                this.handleError(message);
                break;
            default:
                console.log('📥 Unknown message type:', message.message_type);
        }
    }

    /**
     * Handle state update from backend
     */
    handleStateUpdate(message) {
        const { state_type, state_data } = message.payload;
        console.log(`📊 State update: ${state_type}`, state_data);

        // Notify renderer of state updates
        this.notifyRenderer('backend-state-update', { state_type, state_data });
    }

    /**
     * Handle command response from backend
     */
    handleCommandResponse(message) {
        // Store response for pending requests
        this.pendingResponses = this.pendingResponses || new Map();
        this.pendingResponses.set(message.message_id, message.payload);
    }

    /**
     * Handle notification from backend
     */
    handleNotification(message) {
        const { level, title, message: notificationMessage, details } = message.payload;
        console.log(`📢 Backend notification [${level}]: ${title} - ${notificationMessage}`);

        this.notifyRenderer('backend-notification', { level, title, message: notificationMessage, details });
    }

    /**
     * Handle error from backend
     */
    handleError(message) {
        const { error, details } = message.payload;
        console.error('❌ Backend error:', error, details);

        this.notifyRenderer('backend-error', { error, details });
    }

    /**
     * Send command to Python backend via WebSocket (thin client - no business logic here)
     */
    async sendBackendCommand(command, parameters = {}) {
        if (this.connectionStatus !== 'connected' || !this.backendConnection) {
            return {
                success: false,
                error_message: 'Backend not connected',
                data: {}
            };
        }

        console.log(`📤 Sending backend command: ${command}`, parameters);

        try {
            // Generate unique request ID
            const requestId = this.generateRequestId();

            // Create command message
            const commandMessage = {
                command: command,
                parameters: parameters,
                request_id: requestId
            };

            // Send command via WebSocket
            this.backendConnection.send(JSON.stringify(commandMessage));

            // Wait for response
            const response = await this.waitForResponse(requestId);
            console.log(`📥 Backend response:`, response);
            return response;

        } catch (error) {
            console.error('📤 Backend command failed:', error);
            return {
                success: false,
                error_message: error.message,
                data: {}
            };
        }
    }

    /**
     * Send query to Python backend
     */
    async sendBackendQuery(query) {
        console.log('📤 Sending backend query:', query);
        return await this.sendBackendCommand('workflow.get_state', query);
    }

    /**
     * Generate unique request ID
     */
    generateRequestId() {
        return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * Wait for response from backend
     */
    async waitForResponse(requestId, timeout = 10000) {
        this.pendingResponses = this.pendingResponses || new Map();

        return new Promise((resolve, reject) => {
            const timeoutId = setTimeout(() => {
                reject(new Error(`Request timeout: ${requestId}`));
            }, timeout);

            const checkResponse = () => {
                if (this.pendingResponses.has(requestId)) {
                    clearTimeout(timeoutId);
                    const response = this.pendingResponses.get(requestId);
                    this.pendingResponses.delete(requestId);
                    resolve(response);
                } else {
                    setTimeout(checkResponse, 50); // Check every 50ms
                }
            };

            checkResponse();
        });
    }

    // Mock response methods removed - now using real WebSocket backend communication

    /**
     * Handle backend connection errors
     */
    handleConnectionError(error) {
        this.reconnectAttempts++;

        if (this.reconnectAttempts < BACKEND_CONFIG.maxReconnectAttempts) {
            console.log(`🔌 Reconnect attempt ${this.reconnectAttempts}/${BACKEND_CONFIG.maxReconnectAttempts}`);
            setTimeout(() => {
                this.connectToBackend();
            }, BACKEND_CONFIG.reconnectDelay);
        } else {
            console.error('🔌 Max reconnection attempts reached');
            this.showErrorDialog(
                'Backend Connection Failed',
                'Could not connect to Python backend. Please check that the backend is running.'
            );
        }
    }

    /**
     * Notify renderer process of events
     */
    notifyRenderer(event, data = {}) {
        if (this.mainWindow && this.mainWindow.webContents) {
            this.mainWindow.webContents.send(event, data);
        }
    }

    /**
     * Show error dialog to user
     */
    showErrorDialog(title, message) {
        dialog.showErrorBox(title, message);
    }

    /**
     * Cleanup resources on app exit
     */
    cleanup() {
        console.log('🧹 Cleaning up frontend resources...');

        // Close WebSocket connection
        if (this.backendConnection && this.backendConnection.readyState === WebSocket.OPEN) {
            console.log('🔌 Closing WebSocket connection...');
            this.backendConnection.close(1000, 'Frontend shutdown');
            this.backendConnection = null;
        }

        // Terminate backend process
        if (this.backendProcess) {
            console.log('🐍 Terminating backend process...');
            this.backendProcess.kill('SIGTERM');
            this.backendProcess = null;
        }

        // Clear pending responses
        if (this.pendingResponses) {
            this.pendingResponses.clear();
        }

        console.log('🧹 Frontend cleanup complete');
    }
}

// Initialize and start the frontend application
const frontend = new ISIMacroscopeFrontend();
frontend.initialize().catch(error => {
    console.error('🎨 Frontend initialization failed:', error);
    app.quit();
});

// Export for testing
module.exports = ISIMacroscopeFrontend;