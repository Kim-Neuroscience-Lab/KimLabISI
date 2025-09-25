/**
 * ISI Macroscope Control System - Analysis Display
 *
 * Displays data analysis progress and results.
 */

import React from 'react';
import type { WorkflowStateDisplay } from '../../types/ipc-messages';
import { useProgress } from '../../stores/backend-mirror';
import { useIPCActions } from '../../services/ipc-client';
import ResultsDisplay from '../display/ResultsDisplay';

// ============================================================================
// ANALYSIS DISPLAY COMPONENT
// ============================================================================

interface AnalysisDisplayProps {
  workflowState: WorkflowStateDisplay | null;
}

export const AnalysisDisplay: React.FC<AnalysisDisplayProps> = ({ workflowState }) => {
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
          {workflowState?.stateTitle || 'Data Analysis'}
        </h1>
        <p style={{ color: '#666', marginTop: 8 }}>
          {workflowState?.stateDescription || 'Processing intrinsic signal data for retinotopic mapping'}
        </p>
      </div>

      {/* Progress Section - Only show during processing */}
      {progress && !progress.isIndeterminate && (
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
                backgroundColor: '#8b5cf6',
                transition: 'width 0.3s ease'
              }}
            />
          </div>

          {/* Analysis Status Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
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

            <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
              <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>Processing</div>
              <div style={{ fontWeight: 600, color: '#8b5cf6' }}>
                {progress.canCancel ? 'Active' : 'Finalizing'}
              </div>
            </div>
          </div>

          {/* Processing Details */}
          {progress.details && progress.details.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 14 }}>
                Processing Steps:
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

      {/* Analysis Parameters */}
      <div style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>
          Analysis Configuration
        </h2>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: 16
        }}>
          <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Preprocessing</div>
            <div style={{ fontSize: 14, color: '#666', lineHeight: 1.5 }}>
              <div>Temporal Filtering: Enabled</div>
              <div>Spatial Smoothing: 2px Gaussian</div>
              <div>Motion Correction: Enabled</div>
              <div>Artifact Removal: Active</div>
            </div>
          </div>

          <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Signal Analysis</div>
            <div style={{ fontSize: 14, color: '#666', lineHeight: 1.5 }}>
              <div>Method: Cross-correlation</div>
              <div>Frequency Domain: FFT</div>
              <div>Phase Detection: Enabled</div>
              <div>Amplitude Mapping: On</div>
            </div>
          </div>

          <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Retinotopic Mapping</div>
            <div style={{ fontSize: 14, color: '#666', lineHeight: 1.5 }}>
              <div>Azimuth Maps: 4 directions</div>
              <div>Elevation Maps: 4 directions</div>
              <div>Visual Field Sign: Calculated</div>
              <div>Area Boundaries: Auto-detect</div>
            </div>
          </div>

          <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Quality Control</div>
            <div style={{ fontSize: 14, color: '#666', lineHeight: 1.5 }}>
              <div>SNR Threshold: > 2.0</div>
              <div>Coherence: > 0.3</div>
              <div>Coverage: > 80%</div>
              <div>Validation: Enabled</div>
            </div>
          </div>
        </div>
      </div>

      {/* Results Section */}
      <div style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>
          Analysis Results
        </h2>

        <ResultsDisplay
          mapWidth={500}
          mapHeight={400}
        />
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
                  backgroundColor: action.displayText.toLowerCase().includes('cancel') ? '#ef4444' :
                                 action.displayText.toLowerCase().includes('restart') ? '#f59e0b' :
                                 action.displayText.toLowerCase().includes('export') ? '#22c55e' :
                                 action.isPrimary ? '#8b5cf6' : '#6b7280',
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

export default AnalysisDisplay;