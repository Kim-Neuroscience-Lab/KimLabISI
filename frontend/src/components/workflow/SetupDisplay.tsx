/**
 * ISI Macroscope Control System - Setup Display
 *
 * Displays parameter configuration interface for experimental setup.
 * Follows thin client pattern - only displays data and forwards user input.
 */

import React from 'react';
import type { WorkflowStateDisplay } from '../../types/ipc-messages';
import { useIPCActions } from '../../services/ipc-client';
import { useProgress } from '../../stores/backend-mirror';

// ============================================================================
// SETUP DISPLAY COMPONENT
// ============================================================================

interface SetupDisplayProps {
  workflowState: WorkflowStateDisplay | null;
}

export const SetupDisplay: React.FC<SetupDisplayProps> = ({ workflowState }) => {
  const ipcActions = useIPCActions();
  const progress = useProgress();

  const handleInput = async (element: string, value: string | number) => {
    try {
      await ipcActions.sendInput(element, value);
    } catch (error) {
      console.error('Failed to send input:', error);
    }
  };

  const handleSelect = async (element: string, value: string | number) => {
    try {
      await ipcActions.sendSelect(element, value);
    } catch (error) {
      console.error('Failed to send selection:', error);
    }
  };

  const handleAction = async (actionElement: string) => {
    try {
      await ipcActions.sendClick(actionElement);
    } catch (error) {
      console.error('Failed to send action:', error);
    }
  };

  return (
    <div style={{ padding: 40, maxWidth: 1000, margin: '0 auto' }}>
      {/* Title */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 24, fontWeight: 600, margin: 0 }}>
          {workflowState?.stateTitle || 'Experimental Setup'}
        </h1>
        <p style={{ color: '#666', marginTop: 8 }}>
          {workflowState?.stateDescription || 'Configure parameters for ISI experiment'}
        </p>
      </div>

      {/* Progress Indicator */}
      {progress && (
        <div style={{ marginBottom: 32 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontWeight: 600 }}>{progress.operationName}</span>
            <span>{progress.overallProgress.toFixed(0)}%</span>
          </div>
          <div style={{
            width: '100%',
            height: 8,
            backgroundColor: '#e5e7eb',
            borderRadius: 4,
            overflow: 'hidden'
          }}>
            <div
              style={{
                width: `${progress.overallProgress}%`,
                height: '100%',
                backgroundColor: '#3b82f6',
                transition: 'width 0.3s ease'
              }}
            />
          </div>
          <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
            {progress.currentStep}
          </div>
        </div>
      )}

      {/* Parameter Configuration */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32, marginBottom: 32 }}>

        {/* Spatial Configuration */}
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>
            Spatial Configuration
          </h2>

          <div style={{ display: 'grid', gap: 16 }}>
            <div>
              <label style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>
                Monitor Distance (cm)
              </label>
              <input
                type="number"
                step="0.1"
                min="5"
                max="50"
                defaultValue="10.0"
                onChange={(e) => handleInput('monitor_distance_cm', parseFloat(e.target.value))}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 4,
                  border: '1px solid #ccc',
                  fontSize: 14
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>
                Monitor Angle (degrees)
              </label>
              <input
                type="number"
                step="1"
                min="-45"
                max="45"
                defaultValue="20"
                onChange={(e) => handleInput('monitor_angle_degrees', parseInt(e.target.value))}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 4,
                  border: '1px solid #ccc',
                  fontSize: 14
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>
                Field of View (degrees)
              </label>
              <input
                type="number"
                step="1"
                min="10"
                max="60"
                defaultValue="30"
                onChange={(e) => handleInput('monitor_height_degrees', parseInt(e.target.value))}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 4,
                  border: '1px solid #ccc',
                  fontSize: 14
                }}
              />
            </div>
          </div>
        </div>

        {/* Stimulus Parameters */}
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>
            Stimulus Parameters
          </h2>

          <div style={{ display: 'grid', gap: 16 }}>
            <div>
              <label style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>
                Bar Width (degrees)
              </label>
              <input
                type="number"
                step="1"
                min="5"
                max="40"
                defaultValue="20"
                onChange={(e) => handleInput('bar_width_degrees', parseInt(e.target.value))}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 4,
                  border: '1px solid #ccc',
                  fontSize: 14
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>
                Drift Speed (deg/sec)
              </label>
              <input
                type="number"
                step="0.1"
                min="1"
                max="20"
                defaultValue="9"
                onChange={(e) => handleInput('drift_speed_degrees_per_sec', parseFloat(e.target.value))}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 4,
                  border: '1px solid #ccc',
                  fontSize: 14
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>
                Checkerboard Size (degrees)
              </label>
              <input
                type="number"
                step="1"
                min="5"
                max="50"
                defaultValue="25"
                onChange={(e) => handleInput('checkerboard_size_degrees', parseInt(e.target.value))}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 4,
                  border: '1px solid #ccc',
                  fontSize: 14
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>
                Flicker Frequency (Hz)
              </label>
              <input
                type="number"
                step="0.1"
                min="1"
                max="12"
                defaultValue="6"
                onChange={(e) => handleInput('flicker_frequency_hz', parseFloat(e.target.value))}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 4,
                  border: '1px solid #ccc',
                  fontSize: 14
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>
                Frame Rate (FPS)
              </label>
              <select
                defaultValue="60"
                onChange={(e) => handleSelect('frame_rate_fps', parseInt(e.target.value))}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 4,
                  border: '1px solid #ccc',
                  fontSize: 14
                }}
              >
                <option value="30">30 FPS</option>
                <option value="60">60 FPS</option>
                <option value="120">120 FPS</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Available Actions */}
      {workflowState?.availableActions && workflowState.availableActions.length > 0 && (
        <div style={{ textAlign: 'center', borderTop: '1px solid #e5e7eb', paddingTop: 32 }}>
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

export default SetupDisplay;