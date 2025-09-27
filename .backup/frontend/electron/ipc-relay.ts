/**
 * ISI Macroscope Control System - IPC Relay
 *
 * Bridges Electron IPC with Python backend stdin/stdout communication.
 * Implements the unified launcher architecture pattern with proper
 * error handling, message validation, and performance monitoring.
 *
 * Architecture:
 * Renderer <-> Main Process <-> IPC Relay <-> Python Backend (stdin/stdout)
 */

import { ChildProcess } from 'child_process';
import { EventEmitter } from 'events';
import { Readable, Writable } from 'stream';

// Type definitions matching Python backend
interface IPCMessage {
  message_type: 'command' | 'query' | 'state_update' | 'notification' | 'response' | 'error';
  message_id: string;
  timestamp: number;
  payload: { [key: string]: any };
}

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
  data: { [key: string]: any };
}

interface BinaryDataMetadata {
  type: 'PREVIEW_FRAME' | 'ANALYSIS_RESULT' | 'CALIBRATION_DATA';
  format: string;
  size: number;
  timestamp: number;
  [key: string]: any;
}

/**
 * IPC Relay class for bridging Electron IPC with Python backend
 */
export class IPCRelay extends EventEmitter {
  private pythonProcess: ChildProcess;
  private stdin: Writable;
  private stdout: Readable;
  private stderr: Readable;
  private messageQueue: Map<string, { resolve: Function; reject: Function; timeout: NodeJS.Timeout }> = new Map();
  private isConnected = false;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 3;
  private messageBuffer = '';
  private performanceMetrics = {
    messagesSent: 0,
    messagesReceived: 0,
    averageLatency: 0,
    errors: 0,
  };

  constructor(pythonProcess: ChildProcess) {
    super();
    this.pythonProcess = pythonProcess;

    if (!pythonProcess.stdin || !pythonProcess.stdout || !pythonProcess.stderr) {
      throw new Error('Python process must have stdin, stdout, and stderr pipes');
    }

    this.stdin = pythonProcess.stdin;
    this.stdout = pythonProcess.stdout;
    this.stderr = pythonProcess.stderr;
  }

  /**
   * Initialize the IPC relay
   */
  async initialize(): Promise<void> {
    console.log('IPC Relay: Initializing connection to Python backend...');

    try {
      this.setupEventHandlers();
      await this.establishConnection();
      this.startHeartbeat();
      console.log('IPC Relay: Initialization complete');
    } catch (error) {
      console.error('IPC Relay: Initialization failed:', error);
      throw error;
    }
  }

  /**
   * Setup event handlers for Python process communication
   */
  private setupEventHandlers(): void {
    // Handle stdout messages from Python backend
    this.stdout.on('data', (data: Buffer) => {
      this.handleBackendData(data.toString());
    });

    // Handle stderr from Python backend
    this.stderr.on('data', (data: Buffer) => {
      console.error('Backend stderr:', data.toString());
    });

    // Handle process events
    this.pythonProcess.on('exit', (code, signal) => {
      console.log(`IPC Relay: Python process exited with code ${code}, signal ${signal}`);
      this.isConnected = false;
      this.emit('connection-status', false);
      this.handleProcessExit(code, signal);
    });

    this.pythonProcess.on('error', (error) => {
      console.error('IPC Relay: Python process error:', error);
      this.performanceMetrics.errors++;
      this.emit('ipc-error', `Backend process error: ${error.message}`);
    });

    // Handle stdin errors
    this.stdin.on('error', (error) => {
      console.error('IPC Relay: stdin error:', error);
      this.performanceMetrics.errors++;
      this.emit('ipc-error', `stdin error: ${error.message}`);
    });
  }

  /**
   * Establish connection with Python backend
   */
  private async establishConnection(): Promise<void> {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Connection timeout'));
      }, 10000); // 10 second timeout

      // Send initial handshake
      const handshakeMessage: IPCMessage = {
        message_type: 'command',
        message_id: this.generateMessageId(),
        timestamp: Date.now(),
        payload: {
          handler: 'command_handler',
          command: 'handshake',
          parameters: {
            client_type: 'electron',
            client_version: '1.0.0',
          },
        },
      };

      // Wait for successful handshake response
      const handshakeHandler = (message: IPCMessage) => {
        if (message.message_type === 'response' && message.payload.success) {
          this.isConnected = true;
          clearTimeout(timeout);
          this.emit('connection-status', true);
          resolve();
        }
      };

      this.once('backend-message', handshakeHandler);
      this.sendToBackend(handshakeMessage);
    });
  }

  /**
   * Handle incoming data from Python backend
   */
  private handleBackendData(data: string): void {
    // Append to buffer (handle partial messages)
    this.messageBuffer += data;

    // Process complete lines (messages)
    const lines = this.messageBuffer.split('\n');
    this.messageBuffer = lines.pop() || ''; // Keep incomplete line in buffer

    for (const line of lines) {
      if (line.trim()) {
        this.processBackendMessage(line.trim());
      }
    }
  }

  /**
   * Process a complete message from Python backend
   */
  private processBackendMessage(messageJson: string): void {
    try {
      const message: IPCMessage = JSON.parse(messageJson);
      this.performanceMetrics.messagesReceived++;

      // Calculate latency if timestamp is available
      if (message.timestamp) {
        const latency = Date.now() - message.timestamp;
        this.updateAverageLatency(latency);
      }

      // Emit generic backend message event
      this.emit('backend-message', message);

      // Handle specific message types
      switch (message.message_type) {
        case 'state_update':
          this.handleStateUpdate(message);
          break;

        case 'notification':
          this.handleNotification(message);
          break;

        case 'response':
          this.handleResponse(message);
          break;

        case 'error':
          this.handleError(message);
          break;

        default:
          console.warn('IPC Relay: Unknown message type:', message.message_type);
      }
    } catch (error) {
      console.error('IPC Relay: Failed to parse backend message:', error);
      this.performanceMetrics.errors++;
      this.emit('ipc-error', `Message parsing error: ${error}`);
    }
  }

  /**
   * Handle state update from backend
   */
  private handleStateUpdate(message: IPCMessage): void {
    const displayUpdate: DisplayUpdate = {
      timestamp: message.timestamp,
      data: message.payload.state_data || {},
    };

    this.emit('display-update', displayUpdate);
  }

  /**
   * Handle notification from backend
   */
  private handleNotification(message: IPCMessage): void {
    console.log('Backend notification:', message.payload);
    // Could emit specific notification events here
  }

  /**
   * Handle response from backend
   */
  private handleResponse(message: IPCMessage): void {
    const pendingMessage = this.messageQueue.get(message.message_id);
    if (pendingMessage) {
      clearTimeout(pendingMessage.timeout);
      this.messageQueue.delete(message.message_id);

      if (message.payload.success) {
        pendingMessage.resolve(message.payload.result);
      } else {
        pendingMessage.reject(new Error(message.payload.error || 'Unknown error'));
      }
    }
  }

  /**
   * Handle error from backend
   */
  private handleError(message: IPCMessage): void {
    console.error('Backend error:', message.payload);
    this.performanceMetrics.errors++;
    this.emit('ipc-error', message.payload.error || 'Unknown backend error');

    // Also handle as response if there's a pending message
    const pendingMessage = this.messageQueue.get(message.message_id);
    if (pendingMessage) {
      clearTimeout(pendingMessage.timeout);
      this.messageQueue.delete(message.message_id);
      pendingMessage.reject(new Error(message.payload.error || 'Backend error'));
    }
  }

  /**
   * Handle Python process exit
   */
  private handleProcessExit(code: number | null, signal: string | null): void {
    // Reject all pending messages
    for (const [messageId, pendingMessage] of this.messageQueue) {
      clearTimeout(pendingMessage.timeout);
      pendingMessage.reject(new Error('Backend process exited'));
    }
    this.messageQueue.clear();

    // Attempt reconnection if not intentional shutdown
    if (code !== 0 && this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(`IPC Relay: Attempting reconnection (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
      // Note: Actual reconnection would require respawning the Python process
      // This should be handled by the main process
    }
  }

  /**
   * Send user action to Python backend
   */
  async sendUserAction(action: UserAction): Promise<void> {
    if (!this.isConnected) {
      throw new Error('Not connected to backend');
    }

    const message: IPCMessage = {
      message_type: 'command',
      message_id: this.generateMessageId(),
      timestamp: Date.now(),
      payload: {
        handler: 'command_handler',
        command: 'user_action',
        parameters: {
          action_type: action.type.toLowerCase(),
          element: action.element,
          value: action.value,
          metadata: action.metadata,
        },
      },
    };

    return this.sendMessageWithResponse(message);
  }

  /**
   * Send message to backend and wait for response
   */
  private async sendMessageWithResponse(message: IPCMessage, timeoutMs: number = 5000): Promise<any> {
    return new Promise((resolve, reject) => {
      // Set up timeout
      const timeout = setTimeout(() => {
        this.messageQueue.delete(message.message_id);
        reject(new Error(`Message timeout: ${message.message_id}`));
      }, timeoutMs);

      // Store pending message
      this.messageQueue.set(message.message_id, { resolve, reject, timeout });

      // Send message
      try {
        this.sendToBackend(message);
      } catch (error) {
        clearTimeout(timeout);
        this.messageQueue.delete(message.message_id);
        reject(error);
      }
    });
  }

  /**
   * Send message to Python backend via stdin
   */
  private sendToBackend(message: IPCMessage): void {
    try {
      const messageJson = JSON.stringify(message) + '\n';
      this.stdin.write(messageJson);
      this.performanceMetrics.messagesSent++;
      console.debug('IPC Relay: Sent message to backend:', message.message_type);
    } catch (error) {
      console.error('IPC Relay: Failed to send message to backend:', error);
      this.performanceMetrics.errors++;
      throw error;
    }
  }

  /**
   * Start heartbeat to monitor connection health
   */
  private startHeartbeat(): void {
    setInterval(async () => {
      if (!this.isConnected) {
        return;
      }

      try {
        const heartbeatMessage: IPCMessage = {
          message_type: 'query',
          message_id: this.generateMessageId(),
          timestamp: Date.now(),
          payload: {
            handler: 'query_handler',
            query_type: 'health_check',
          },
        };

        await this.sendMessageWithResponse(heartbeatMessage, 3000);
      } catch (error) {
        console.warn('IPC Relay: Heartbeat failed:', error);
        this.isConnected = false;
        this.emit('connection-status', false);
      }
    }, 10000); // Every 10 seconds
  }

  /**
   * Update average latency metric
   */
  private updateAverageLatency(latency: number): void {
    const alpha = 0.1; // Exponential moving average factor
    this.performanceMetrics.averageLatency =
      this.performanceMetrics.averageLatency * (1 - alpha) + latency * alpha;
  }

  /**
   * Generate unique message ID
   */
  private generateMessageId(): string {
    return `electron_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  // ============================================================================
  // PUBLIC API
  // ============================================================================

  /**
   * Check if connected to backend
   */
  isBackendConnected(): boolean {
    return this.isConnected;
  }

  /**
   * Get performance metrics
   */
  getPerformanceMetrics() {
    return { ...this.performanceMetrics };
  }

  /**
   * Register display update handler
   */
  onDisplayUpdate(callback: (update: DisplayUpdate) => void): void {
    this.on('display-update', callback);
  }

  /**
   * Register binary data handler
   */
  onBinaryData(callback: (data: ArrayBuffer, metadata: BinaryDataMetadata) => void): void {
    this.on('binary-data', callback);
  }

  /**
   * Register connection status handler
   */
  onConnectionStatus(callback: (isConnected: boolean) => void): void {
    this.on('connection-status', callback);
  }

  /**
   * Register IPC error handler
   */
  onIPCError(callback: (error: string) => void): void {
    this.on('ipc-error', callback);
  }

  /**
   * Cleanup resources
   */
  async cleanup(): Promise<void> {
    console.log('IPC Relay: Cleaning up resources...');

    // Clear all pending messages
    for (const [messageId, pendingMessage] of this.messageQueue) {
      clearTimeout(pendingMessage.timeout);
      pendingMessage.reject(new Error('IPC relay shutting down'));
    }
    this.messageQueue.clear();

    // Remove all listeners
    this.removeAllListeners();

    // Close stdin
    if (this.stdin && !this.stdin.destroyed) {
      this.stdin.end();
    }

    this.isConnected = false;
    console.log('IPC Relay: Cleanup complete');
  }
}
