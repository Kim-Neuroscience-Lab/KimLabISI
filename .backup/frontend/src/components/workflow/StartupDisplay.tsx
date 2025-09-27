/**
 * ISI Macroscope Control System - Startup Display
 *
 * Displays system startup state and initialization progress.
 */

import React from 'react';
import type { WorkflowStateDisplay } from '../../types/ipc-messages';
import { useSystemHealth, useHardwareStatus } from '../../stores/backend-mirror';
import { useIPCActions } from '../../services/ipc-client';

// ============================================================================
// STARTUP DISPLAY COMPONENT
// ============================================================================

interface StartupDisplayProps {
  workflowState: WorkflowStateDisplay | null;
}

export const StartupDisplay: React.FC<StartupDisplayProps> = ({ workflowState }) => {
  const systemHealth = useSystemHealth();
  const hardwareStatus = useHardwareStatus();
  const ipcActions = useIPCActions();

  const handleAction = async (actionElement: string) => {
    try {
      await ipcActions.sendClick(actionElement);
    } catch (error) {
      console.error('Failed to send action:', error);
    }
  };

  return (
    <div style={{ padding: 40, maxWidth: 800, margin: '0 auto' }}>
      {/* Title */}
      <div style={{ textAlign: 'center', marginBottom: 32 }}>
        <h1 style={{ fontSize: 24, fontWeight: 600, margin: 0 }}>
          {workflowState?.stateTitle || 'ISI Macroscope Control System'}
        </h1>
        <p style={{ color: '#666', marginTop: 8 }}>
          {workflowState?.stateDescription || 'System starting up...'}
        </p>
      </div>

      {/* System Health Overview */}
      {systemHealth && (
        <div style={{ marginBottom: 32 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>
            System Health
          </h2>

          <div style={{
            padding: 16,
            backgroundColor: '#f9f9f9',
            borderRadius: 4,
            border: `2px solid ${getHealthColor(systemHealth.overall)}`,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 600 }}>Overall Status:</span>
              <span style={{
                color: getHealthColor(systemHealth.overall),
                fontWeight: 600
              }}>
                {systemHealth.overall}
              </span>
            </div>

            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
              gap: 12,
              marginTop: 16
            }}>
              <div>
                <div style={{ fontSize: 12, color: '#666' }}>CPU Usage</div>
                <div>{(systemHealth.cpuUsage * 100).toFixed(1)}%</div>
              </div>
              <div>
                <div style={{ fontSize: 12, color: '#666' }}>Memory Usage</div>
                <div>{(systemHealth.memoryUsage * 100).toFixed(1)}%</div>
              </div>
              <div>
                <div style={{ fontSize: 12, color: '#666' }}>GPU Usage</div>
                <div>{(systemHealth.gpuUsage * 100).toFixed(1)}%</div>
              </div>
              <div>
                <div style={{ fontSize: 12, color: '#666' }}>Temperature</div>
                <div>{systemHealth.temperature}°C</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Hardware Status */}
      {hardwareStatus && (
        <div style={{ marginBottom: 32 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>
            Hardware Status
          </h2>

          <div style={{ display: 'grid', gap: 12 }}>
            {Object.entries(hardwareStatus).map(([key, component]) => {
              if (key === 'overallStatus') return null;

              return (
                <div
                  key={key}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: 12,
                    backgroundColor: '#f9f9f9',
                    borderRadius: 4,
                    border: `1px solid ${getStatusColor(component.status)}`,
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600 }}>{component.name}</div>
                    {component.details && (
                      <div style={{ fontSize: 12, color: '#666' }}>{component.details}</div>
                    )}
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{
                      color: getStatusColor(component.status),
                      fontWeight: 600,
                      fontSize: 12
                    }}>
                      {component.status}
                    </div>
                    {component.temperature && (
                      <div style={{ fontSize: 12, color: '#666' }}>
                        {component.temperature}°C
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Available Actions */}
      {workflowState?.availableActions && workflowState.availableActions.length > 0 && (
        <div style={{ textAlign: 'center' }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>
            Available Actions
          </h2>

          <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
            {workflowState.availableActions.map((action, index) => (
              <button
                key={index}
                onClick={() => handleAction(action.actionElement)}
                disabled={!action.isEnabled}
                style={{
                  padding: '12px 24px',
                  borderRadius: 4,
                  border: 'none',
                  backgroundColor: action.isPrimary ? '#3b82f6' : '#6b7280',
                  color: 'white',
                  fontWeight: 600,
                  cursor: action.isEnabled ? 'pointer' : 'not-allowed',
                  opacity: action.isEnabled ? 1 : 0.5,
                }}
              >
                {action.displayText}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// Helper functions
const getHealthColor = (health: string): string => {
  switch (health) {
    case 'EXCELLENT': return '#22c55e';
    case 'GOOD': return '#84cc16';
    case 'WARNING': return '#f59e0b';
    case 'CRITICAL': return '#ef4444';
    default: return '#6b7280';
  }
};

const getStatusColor = (status: string): string => {
  switch (status) {
    case 'CONNECTED': return '#22c55e';
    case 'DISCONNECTED': return '#ef4444';
    case 'ERROR': return '#ef4444';
    default: return '#6b7280';
  }
};

export default StartupDisplay;