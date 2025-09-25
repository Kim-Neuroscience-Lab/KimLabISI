/**
 * ISI Macroscope Control System - Acquisition Display
 *
 * Displays data acquisition progress with live preview and statistics.
 */

import React from 'react';
import type { WorkflowStateDisplay } from '../../types/ipc-messages';
import { useProgress } from '../../stores/backend-mirror';
import { useIPCActions } from '../../services/ipc-client';
import PreviewMonitor from '../display/PreviewMonitor';

// ============================================================================
// ACQUISITION DISPLAY COMPONENT
// ============================================================================

interface AcquisitionDisplayProps {
  workflowState: WorkflowStateDisplay | null;
}

export const AcquisitionDisplay: React.FC<AcquisitionDisplayProps> = ({ workflowState }) => {
  const progress = useProgress();
  const ipcActions = useIPCActions();

  const handleAction = async (actionElement: string) => {
    try {
      await ipcActions.sendClick(actionElement);
    } catch (error) {
      console.error('Failed to send action:', error);
    }
  };

  return (
    <div style={{ padding: 40, maxWidth: 1400, margin: '0 auto' }}>
      {/* Title */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 24, fontWeight: 600, margin: 0 }}>
          {workflowState?.stateTitle || 'Data Acquisition'}
        </h1>
        <p style={{ color: '#666', marginTop: 8 }}>
          {workflowState?.stateDescription || 'Acquiring intrinsic signal imaging data'}
        </p>
      </div>

      {/* Progress Section */}
      {progress && (
        <div style={{ marginBottom: 32 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontWeight: 600 }}>{progress.operationName}</span>
            <span>{progress.overallProgress.toFixed(1)}%</span>
          </div>

          {/* Progress Bar */}
          <div style={{
            width: '100%',
            height: 12,
            backgroundColor: '#e5e7eb',
            borderRadius: 6,
            overflow: 'hidden',
            marginBottom: 16
          }}>
            <div
              style={{
                width: `${progress.overallProgress}%`,
                height: '100%',
                backgroundColor: '#22c55e',
                transition: 'width 0.3s ease'
              }}
            />
          </div>

          {/* Acquisition Status Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
            <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
              <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>Current Trial</div>
              <div style={{ fontWeight: 600 }}>{progress.currentStep}</div>
            </div>

            <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
              <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>Progress</div>
              <div style={{ fontWeight: 600 }}>
                {progress.currentStepNumber} / {progress.totalSteps}
              </div>
            </div>

            <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
              <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>Time Remaining</div>
              <div style={{ fontWeight: 600 }}>
                {progress.estimatedTimeRemaining || 'Calculating...'}
              </div>
            </div>

            <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
              <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>Status</div>
              <div style={{ fontWeight: 600, color: progress.canCancel ? '#22c55e' : '#f59e0b' }}>
                {progress.isIndeterminate ? 'Processing' : 'Recording'}
              </div>
            </div>
          </div>

          {/* Detailed Progress */}
          {progress.details && progress.details.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 14 }}>
                Acquisition Details:
              </div>
              <div style={{ fontSize: 12, color: '#666' }}>
                {progress.details.map((detail, index) => (
                  <div key={index} style={{ marginBottom: 4 }}>• {detail}</div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Live Preview Section */}
      <div style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>
          Live Preview
        </h2>

        <PreviewMonitor
          width={800}
          height={600}
          showStats={true}
        />
      </div>

      {/* Acquisition Parameters */}
      <div style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>
          Acquisition Settings
        </h2>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: 16
        }}>
          <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Camera Settings</div>
            <div style={{ fontSize: 14, color: '#666', lineHeight: 1.5 }}>
              <div>Resolution: 2560 × 1440</div>
              <div>Frame Rate: 60 FPS</div>
              <div>Exposure: Auto</div>
              <div>Gain: Auto</div>
            </div>
          </div>

          <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Stimulus Settings</div>
            <div style={{ fontSize: 14, color: '#666', lineHeight: 1.5 }}>
              <div>Bar Width: 20°</div>
              <div>Drift Speed: 9°/s</div>
              <div>Flicker: 6 Hz</div>
              <div>Directions: 4 (LR, RL, TB, BT)</div>
            </div>
          </div>

          <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Data Storage</div>
            <div style={{ fontSize: 14, color: '#666', lineHeight: 1.5 }}>
              <div>Format: HDF5</div>
              <div>Compression: LZ4</div>
              <div>Location: /data/acquisitions/</div>
              <div>Estimated Size: ~2.5 GB</div>
            </div>
          </div>

          <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Quality Control</div>
            <div style={{ fontSize: 14, color: '#666', lineHeight: 1.5 }}>
              <div>Frame Sync: Enabled</div>
              <div>Buffer Monitoring: Active</div>
              <div>Error Detection: On</div>
              <div>Auto Recovery: Enabled</div>
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
                  backgroundColor: action.displayText.toLowerCase().includes('stop') ||
                                 action.displayText.toLowerCase().includes('cancel') ? '#ef4444' :
                                 action.displayText.toLowerCase().includes('pause') ? '#f59e0b' :
                                 action.isPrimary ? '#22c55e' : '#6b7280',
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

export default AcquisitionDisplay;