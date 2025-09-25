/**
 * ISI Macroscope Control System - Error Display
 *
 * Displays error states and recovery options.
 */

import React from 'react';
import type { ErrorDisplay as ErrorData } from '../../types/ipc-messages';
import { useIPCActions } from '../../services/ipc-client';

// ============================================================================
// ERROR DISPLAY COMPONENT
// ============================================================================

interface ErrorDisplayProps {
  errors: readonly ErrorData[];
}

export const ErrorDisplay: React.FC<ErrorDisplayProps> = ({ errors }) => {
  const ipcActions = useIPCActions();

  const handleAction = async (actionElement: string) => {
    try {
      await ipcActions.sendClick(actionElement);
    } catch (error) {
      console.error('Failed to send action:', error);
    }
  };

  const handleDismiss = async (errorId: string) => {
    try {
      await ipcActions.sendClick(`dismiss_error_${errorId}`);
    } catch (error) {
      console.error('Failed to dismiss error:', error);
    }
  };

  const getSeverityColor = (severity: string): string => {
    switch (severity) {
      case 'CRITICAL': return '#dc2626';
      case 'ERROR': return '#ef4444';
      case 'WARNING': return '#f59e0b';
      case 'INFO': return '#3b82f6';
      default: return '#6b7280';
    }
  };

  const getSeverityBackground = (severity: string): string => {
    switch (severity) {
      case 'CRITICAL': return '#fef2f2';
      case 'ERROR': return '#fef2f2';
      case 'WARNING': return '#fffbeb';
      case 'INFO': return '#eff6ff';
      default: return '#f9fafb';
    }
  };

  if (errors.length === 0) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: '#666' }}>
        <div>No errors to display</div>
      </div>
    );
  }

  return (
    <div style={{ padding: 40, maxWidth: 1000, margin: '0 auto' }}>
      {/* Title */}
      <div style={{ marginBottom: 32, textAlign: 'center' }}>
        <h1 style={{ fontSize: 24, fontWeight: 600, margin: 0, color: '#dc2626' }}>
          System Error
        </h1>
        <p style={{ color: '#666', marginTop: 8 }}>
          The following errors require attention before proceeding
        </p>
      </div>

      {/* Error List */}
      <div style={{ display: 'grid', gap: 16, marginBottom: 32 }}>
        {errors.map((error) => (
          <div
            key={error.id}
            style={{
              padding: 20,
              borderRadius: 8,
              border: `2px solid ${getSeverityColor(error.severity)}`,
              backgroundColor: getSeverityBackground(error.severity),
            }}
          >
            {/* Error Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
                  <span
                    style={{
                      display: 'inline-block',
                      padding: '2px 8px',
                      borderRadius: 12,
                      backgroundColor: getSeverityColor(error.severity),
                      color: 'white',
                      fontSize: 11,
                      fontWeight: 600,
                      marginRight: 12,
                    }}
                  >
                    {error.severity}
                  </span>
                  <span style={{ fontSize: 12, color: '#666' }}>
                    {new Date(error.timestamp).toLocaleString()}
                  </span>
                </div>
                <h3 style={{ fontSize: 18, fontWeight: 600, margin: 0, color: getSeverityColor(error.severity) }}>
                  {error.title}
                </h3>
              </div>

              {error.canDismiss && (
                <button
                  onClick={() => handleDismiss(error.id)}
                  style={{
                    padding: '4px 8px',
                    border: 'none',
                    backgroundColor: 'transparent',
                    color: '#6b7280',
                    cursor: 'pointer',
                    fontSize: 18,
                    borderRadius: 4,
                  }}
                  title="Dismiss error"
                >
                  ×
                </button>
              )}
            </div>

            {/* Error Message */}
            <div style={{ marginBottom: 16 }}>
              <p style={{ margin: 0, lineHeight: 1.6, color: '#374151' }}>
                {error.message}
              </p>
            </div>

            {/* Technical Details */}
            {error.technicalDetails && (
              <details style={{ marginBottom: 16 }}>
                <summary style={{ cursor: 'pointer', fontWeight: 600, marginBottom: 8 }}>
                  Technical Details
                </summary>
                <pre
                  style={{
                    backgroundColor: 'rgba(0, 0, 0, 0.05)',
                    padding: 12,
                    borderRadius: 4,
                    fontSize: 12,
                    fontFamily: 'monospace',
                    overflow: 'auto',
                    margin: 0,
                  }}
                >
                  {error.technicalDetails}
                </pre>
              </details>
            )}

            {/* Suggested Actions */}
            {error.suggestedActions && error.suggestedActions.length > 0 && (
              <div>
                <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 14 }}>
                  Suggested Actions:
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {error.suggestedActions.map((action, index) => (
                    <button
                      key={index}
                      onClick={() => handleAction(action.actionElement)}
                      disabled={!action.isEnabled}
                      style={{
                        padding: '8px 16px',
                        borderRadius: 4,
                        border: `1px solid ${getSeverityColor(error.severity)}`,
                        backgroundColor: action.isPrimary ? getSeverityColor(error.severity) : 'transparent',
                        color: action.isPrimary ? 'white' : getSeverityColor(error.severity),
                        fontWeight: 600,
                        cursor: action.isEnabled ? 'pointer' : 'not-allowed',
                        opacity: action.isEnabled ? 1 : 0.5,
                        fontSize: 12,
                      }}
                    >
                      {action.displayText}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* General Recovery Actions */}
      <div style={{ textAlign: 'center', padding: 20, backgroundColor: '#f9fafb', borderRadius: 8 }}>
        <div style={{ fontWeight: 600, marginBottom: 16 }}>
          System Recovery Options
        </div>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
          <button
            onClick={() => handleAction('restart_system')}
            style={{
              padding: '12px 24px',
              borderRadius: 4,
              border: 'none',
              backgroundColor: '#f59e0b',
              color: 'white',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Restart System
          </button>

          <button
            onClick={() => handleAction('reset_to_startup')}
            style={{
              padding: '12px 24px',
              borderRadius: 4,
              border: '1px solid #d1d5db',
              backgroundColor: 'white',
              color: '#374151',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Reset to Startup
          </button>

          <button
            onClick={() => handleAction('contact_support')}
            style={{
              padding: '12px 24px',
              borderRadius: 4,
              border: '1px solid #3b82f6',
              backgroundColor: 'transparent',
              color: '#3b82f6',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Contact Support
          </button>
        </div>
      </div>
    </div>
  );
};

export default ErrorDisplay;