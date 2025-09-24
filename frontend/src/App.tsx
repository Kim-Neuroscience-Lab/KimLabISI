/**
 * ISI Macroscope Control System - Main Application Component
 *
 * Thin client frontend that displays backend state and forwards user commands.
 * All business logic resides in the Python backend - this component only
 * handles display and user interaction routing.
 */

import React, { useEffect, useState } from 'react';
import './App.css';

// IPC types for communication with backend
interface BackendState {
  workflow_state: string;
  hardware_status: Record<string, boolean>;
  current_session?: string;
  errors: string[];
  system_health: string;
}

interface IPCMessage {
  type: string;
  command?: string;
  data?: any;
}

// Declare window.electronAPI for TypeScript
declare global {
  interface Window {
    electronAPI: {
      sendCommand: (command: string, data?: any) => Promise<any>;
      onStateUpdate: (callback: (state: BackendState) => void) => void;
      removeAllListeners: (channel: string) => void;
    };
  }
}

const App: React.FC = () => {
  // UI state - mirrors backend state for display only
  const [backendState, setBackendState] = useState<BackendState>({
    workflow_state: 'STARTUP',
    hardware_status: {},
    errors: [],
    system_health: 'UNKNOWN'
  });

  // UI-only state
  const [isConnected, setIsConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Initialize connection to backend
    initializeBackendConnection();

    // Cleanup on unmount
    return () => {
      if (window.electronAPI) {
        window.electronAPI.removeAllListeners('state-update');
      }
    };
  }, []);

  const initializeBackendConnection = async () => {
    try {
      if (!window.electronAPI) {
        setError('Electron IPC not available');
        return;
      }

      // Set up state update listener
      window.electronAPI.onStateUpdate((state: BackendState) => {
        setBackendState(state);
        setIsConnected(true);
        setError(null);
      });

      // Request initial state
      await sendCommand('get_system_status');

    } catch (err) {
      console.error('Failed to initialize backend connection:', err);
      setError('Failed to connect to backend');
      setIsConnected(false);
    }
  };

  const sendCommand = async (command: string, data?: any): Promise<any> => {
    try {
      setLoading(true);
      setError(null);

      if (!window.electronAPI) {
        throw new Error('Electron IPC not available');
      }

      const result = await window.electronAPI.sendCommand(command, data);

      if (result.success === false) {
        setError(result.error_message || 'Command failed');
      }

      return result;
    } catch (err) {
      console.error(`Command ${command} failed:`, err);
      setError(`Command failed: ${err}`);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  // Command handlers - forward user actions to backend
  const handleStartSystem = async () => {
    await sendCommand('start_system');
  };

  const handleStartSetup = async () => {
    await sendCommand('start_spatial_setup');
  };

  const handleStartGeneration = async () => {
    await sendCommand('start_stimulus_generation');
  };

  const handleStartAcquisition = async () => {
    await sendCommand('start_acquisition');
  };

  const handleStartAnalysis = async () => {
    const sessionId = backendState.current_session;
    if (sessionId) {
      await sendCommand('start_analysis', { session_id: sessionId });
    }
  };

  const handleEmergencyStop = async () => {
    await sendCommand('emergency_stop');
  };

  // Render current workflow state
  const renderWorkflowState = () => {
    const state = backendState.workflow_state;

    return (
      <div className="workflow-state">
        <h2>System Status: {state}</h2>

        <div className="workflow-actions">
          {state === 'STARTUP' && (
            <button onClick={handleStartSystem} disabled={loading}>
              Initialize System
            </button>
          )}

          {state === 'SETUP_READY' && (
            <button onClick={handleStartSetup} disabled={loading}>
              Start Spatial Setup
            </button>
          )}

          {state === 'GENERATION_READY' && (
            <button onClick={handleStartGeneration} disabled={loading}>
              Generate Stimuli
            </button>
          )}

          {state === 'ACQUISITION_READY' && (
            <button onClick={handleStartAcquisition} disabled={loading}>
              Start Acquisition
            </button>
          )}

          {state === 'ANALYSIS_READY' && (
            <button onClick={handleStartAnalysis} disabled={loading}>
              Analyze Data
            </button>
          )}

          {(state === 'SETUP' || state === 'GENERATION' || state === 'ACQUISITION' || state === 'ANALYSIS') && (
            <div className="active-workflow">
              <p>Workflow in progress: {state}</p>
              <button
                onClick={handleEmergencyStop}
                className="emergency-stop"
                disabled={loading}
              >
                Emergency Stop
              </button>
            </div>
          )}

          {state === 'ERROR' && (
            <div className="error-state">
              <p>System in error state. Check logs for details.</p>
              <button onClick={handleStartSystem} disabled={loading}>
                Retry Initialization
              </button>
            </div>
          )}

          {state === 'DEGRADED' && (
            <div className="degraded-state">
              <p>System running in degraded mode. Some hardware unavailable.</p>
            </div>
          )}
        </div>
      </div>
    );
  };

  // Render hardware status display
  const renderHardwareStatus = () => {
    return (
      <div className="hardware-status">
        <h3>Hardware Status</h3>
        <div className="hardware-grid">
          {Object.entries(backendState.hardware_status).map(([hardware, available]) => (
            <div
              key={hardware}
              className={`hardware-item ${available ? 'available' : 'unavailable'}`}
            >
              <span className="hardware-name">{hardware.replace('_', ' ').toUpperCase()}</span>
              <span className="hardware-indicator">
                {available ? '' : ''}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  // Render system errors
  const renderErrors = () => {
    if (backendState.errors.length === 0 && !error) return null;

    return (
      <div className="error-display">
        <h3>System Messages</h3>
        {error && (
          <div className="error-item frontend-error">
            Frontend Error: {error}
          </div>
        )}
        {backendState.errors.map((err, index) => (
          <div key={index} className="error-item backend-error">
            {err}
          </div>
        ))}
      </div>
    );
  };

  // Main render
  return (
    <div className="app">
      <header className="app-header">
        <h1>ISI Macroscope Control System</h1>
        <div className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
          {isConnected ? 'Connected to Backend' : 'Backend Disconnected'}
        </div>
      </header>

      <main className="app-main">
        {/* Connection error display */}
        {!isConnected && (
          <div className="connection-error">
            <p>Unable to connect to backend. Please ensure the Python backend is running.</p>
            <button onClick={initializeBackendConnection}>
              Retry Connection
            </button>
          </div>
        )}

        {/* Main application interface */}
        {isConnected && (
          <>
            {renderWorkflowState()}
            {renderHardwareStatus()}
            {renderErrors()}
          </>
        )}
      </main>

      {/* Loading overlay */}
      {loading && (
        <div className="loading-overlay">
          <div className="loading-spinner">
            <p>Processing command...</p>
          </div>
        </div>
      )}

      <footer className="app-footer">
        <p>System Health: <span className={`health-${backendState.system_health.toLowerCase()}`}>
          {backendState.system_health}
        </span></p>
        {backendState.current_session && (
          <p>Current Session: {backendState.current_session}</p>
        )}
      </footer>
    </div>
  );
};

export default App;