/**
 * ISI Macroscope Control System - Main Application Component
 *
 * Refactored thin client frontend using proper architecture.
 * Uses Zustand stores for state management and typed IPC communication.
 * Contains NO business logic - only displays backend state.
 */

import React, { useEffect } from 'react';
import { getIPCClient } from './services/ipc-client';
import { useConnectionStatus } from './stores/backend-mirror';
import { useInteraction, useInteractionActions } from './stores/ui-store';
import WorkflowContainer from './components/workflow/WorkflowContainer';
import './App.css';

// ============================================================================
// MAIN APPLICATION COMPONENT
// ============================================================================

const App: React.FC = () => {
  const connectionStatus = useConnectionStatus();
  const interaction = useInteraction();
  const interactionActions = useInteractionActions();

  // Initialize IPC client on mount
  useEffect(() => {
    const ipcClient = getIPCClient();

    // Set loading state while initializing
    interactionActions.setLoading(true, 'Connecting to backend...');

    // Check if connection is established after a short delay
    const connectionCheckTimeout = setTimeout(() => {
      if (!ipcClient.isConnected()) {
        interactionActions.setLoading(false);
      } else {
        interactionActions.setLoading(false);
      }
    }, 3000); // 3 second timeout

    // Monitor connection status changes
    const connectionMonitor = setInterval(() => {
      const isConnected = ipcClient.isConnected();
      if (isConnected && interaction.isLoading && interaction.loadingMessage.includes('Connecting')) {
        interactionActions.setLoading(false);
      }
    }, 1000);

    // Cleanup on unmount
    return () => {
      clearTimeout(connectionCheckTimeout);
      clearInterval(connectionMonitor);
      ipcClient.disconnect();
    };
  }, [interactionActions, interaction.isLoading, interaction.loadingMessage]);

  // Show connection error if not connected
  if (!connectionStatus.isConnected && !interaction.isLoading) {
    return (
      <div className="app">
        <header className="app-header">
          <h1>ISI Macroscope Control System</h1>
          <div className="connection-status disconnected">
            Backend Disconnected
          </div>
        </header>

        <main className="app-main">
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '60vh',
            textAlign: 'center',
            color: '#666'
          }}>
            <div style={{ fontSize: 18, marginBottom: 16 }}>
              Unable to connect to backend
            </div>
            <div style={{ fontSize: 14, marginBottom: 24, maxWidth: 400, lineHeight: 1.6 }}>
              Please ensure the Python backend is running and accessible.
              The connection will automatically retry when the backend becomes available.
            </div>
            <div style={{
              padding: 12,
              backgroundColor: '#f9f9f9',
              borderRadius: 4,
              border: '1px solid #ddd',
              fontSize: 12,
              fontFamily: 'monospace',
              color: '#666'
            }}>
              Health: {connectionStatus.health} | Last update: {
                connectionStatus.lastUpdate > 0
                  ? new Date(connectionStatus.lastUpdate).toLocaleTimeString()
                  : 'Never'
              }
            </div>
          </div>
        </main>
      </div>
    );
  }

  // Show loading screen during initialization
  if (interaction.isLoading) {
    return (
      <div className="app">
        <header className="app-header">
          <h1>ISI Macroscope Control System</h1>
          <div className="connection-status connecting">
            Initializing...
          </div>
        </header>

        <main className="app-main">
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '60vh',
            textAlign: 'center'
          }}>
            <div style={{
              width: 40,
              height: 40,
              border: '4px solid #e5e7eb',
              borderTop: '4px solid #3b82f6',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite',
              marginBottom: 16
            }} />
            <div style={{ fontSize: 16, color: '#374151', marginBottom: 8 }}>
              {interaction.loadingMessage || 'Loading...'}
            </div>
            <div style={{ fontSize: 12, color: '#6b7280' }}>
              Please wait while the system initializes
            </div>
          </div>
        </main>
      </div>
    );
  }

  // Main application interface
  return (
    <div className="app">
      {/* Header with connection status */}
      <header className="app-header">
        <h1>ISI Macroscope Control System</h1>
        <div className={`connection-status ${connectionStatus.isConnected ? 'connected' : 'disconnected'}`}>
          <span>{connectionStatus.isConnected ? 'Connected' : 'Disconnected'}</span>
          <span className="connection-health" style={{
            marginLeft: 8,
            fontSize: 12,
            opacity: 0.8,
            color: getHealthColor(connectionStatus.health)
          }}>
            {connectionStatus.health}
          </span>
        </div>
      </header>

      {/* Main workflow container */}
      <main className="app-main">
        <WorkflowContainer />
      </main>

      {/* Footer with system info */}
      <footer className="app-footer">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: 12, color: '#6b7280' }}>
            Last update: {
              connectionStatus.lastUpdate > 0
                ? new Date(connectionStatus.lastUpdate).toLocaleTimeString()
                : 'Never'
            }
          </div>
          <div style={{ fontSize: 12, color: '#6b7280' }}>
            ISI Macroscope Control System v1.0
          </div>
        </div>
      </footer>
    </div>
  );
};

// Helper function to get health indicator color
const getHealthColor = (health: string): string => {
  switch (health) {
    case 'EXCELLENT': return '#22c55e';
    case 'GOOD': return '#84cc16';
    case 'POOR': return '#f59e0b';
    case 'DISCONNECTED': return '#ef4444';
    default: return '#6b7280';
  }
};

export default App;