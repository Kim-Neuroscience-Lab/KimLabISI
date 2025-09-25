/**
 * ISI Macroscope Control System - Generation Display
 *
 * Displays stimulus generation progress and preview.
 */

import React from 'react';
import type { WorkflowStateDisplay } from '../../types/ipc-messages';
import { useProgress } from '../../stores/backend-mirror';
import { useIPCActions } from '../../services/ipc-client';
import PreviewMonitor from '../display/PreviewMonitor';

// ============================================================================
// GENERATION DISPLAY COMPONENT
// ============================================================================

interface GenerationDisplayProps {
  workflowState: WorkflowStateDisplay | null;
}

export const GenerationDisplay: React.FC<GenerationDisplayProps> = ({ workflowState }) => {
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
    <div style={{ padding: 40, maxWidth: 1200, margin: '0 auto' }}>
      {/* Title */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 24, fontWeight: 600, margin: 0 }}>
          {workflowState?.stateTitle || 'Stimulus Generation'}
        </h1>
        <p style={{ color: '#666', marginTop: 8 }}>
          {workflowState?.stateDescription || 'Generating retinotopic mapping stimuli'}
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
                backgroundColor: '#3b82f6',
                transition: 'width 0.3s ease'
              }}
            />
          </div>

          {/* Progress Details */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
            <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
              <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>Current Step</div>
              <div style={{ fontWeight: 600 }}>{progress.currentStep}</div>
            </div>

            <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
              <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>Progress</div>
              <div style={{ fontWeight: 600 }}>
                Step {progress.currentStepNumber} of {progress.totalSteps}
              </div>
            </div>

            <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
              <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>Time Remaining</div>
              <div style={{ fontWeight: 600 }}>
                {progress.estimatedTimeRemaining || 'Calculating...'}
              </div>
            </div>
          </div>

          {/* Progress Details */}
          {progress.details && progress.details.length > 0 && (
            <div style={{ marginTop: 16, fontSize: 12, color: '#666' }}>
              {progress.details.map((detail, index) => (
                <div key={index}>• {detail}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Preview Section */}
      <div style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>
          Stimulus Preview
        </h2>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 16 }}>
          <PreviewMonitor
            width={640}
            height={480}
            showStats={false}
          />
        </div>
      </div>

      {/* Generation Parameters Summary */}
      <div style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>
          Generation Parameters
        </h2>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 16
        }}>
          <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Stimulus Pattern</div>
            <div style={{ fontSize: 14, color: '#666' }}>
              Drifting bar with counter-phase checkerboard
            </div>
          </div>

          <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Directions</div>
            <div style={{ fontSize: 14, color: '#666' }}>
              4 directions: LR, RL, TB, BT
            </div>
          </div>

          <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Frame Rate</div>
            <div style={{ fontSize: 14, color: '#666' }}>
              60 FPS
            </div>
          </div>

          <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Resolution</div>
            <div style={{ fontSize: 14, color: '#666' }}>
              2560 × 1440
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
                  backgroundColor: action.isPrimary ? '#3b82f6' :
                                 action.displayText.toLowerCase().includes('cancel') ? '#ef4444' : '#6b7280',
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

export default GenerationDisplay;