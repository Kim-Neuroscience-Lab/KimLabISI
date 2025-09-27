/**
 * ISI Macroscope Control System - Preview Monitor
 *
 * Displays live preview streams from stimulus and camera sources.
 * Uses WebGL canvas for efficient frame rendering.
 */

import React from 'react';
import { WebGLCanvas } from '../hardware/WebGLCanvas';
import { usePreview, useAcquisitionStats } from '../../stores/backend-mirror';
import { useDisplay } from '../../stores/ui-store';

// ============================================================================
// PREVIEW MONITOR COMPONENT
// ============================================================================

interface PreviewMonitorProps {
  /** Width of the preview display */
  width?: number;
  /** Height of the preview display */
  height?: number;
  /** Whether to show acquisition statistics overlay */
  showStats?: boolean;
  /** CSS class name */
  className?: string;
}

export const PreviewMonitor: React.FC<PreviewMonitorProps> = ({
  width = 640,
  height = 480,
  showStats = true,
  className = '',
}) => {
  const preview = usePreview();
  const acquisitionStats = useAcquisitionStats();
  const display = useDisplay();

  // Create stats overlay component
  const statsOverlay = showStats && acquisitionStats && (
    <div
      style={{
        position: 'absolute',
        bottom: 8,
        left: 8,
        background: 'rgba(0, 0, 0, 0.8)',
        color: 'white',
        padding: 12,
        borderRadius: 4,
        fontSize: 12,
        fontFamily: 'monospace',
        pointerEvents: 'none',
      }}
    >
      <div>Stimulus: {acquisitionStats.stimulusFps.toFixed(1)} FPS</div>
      <div>Camera: {acquisitionStats.cameraFps.toFixed(1)} FPS</div>
      <div>Dropped: {acquisitionStats.droppedFrames}</div>
      <div>Buffer: {(acquisitionStats.bufferUtilization * 100).toFixed(1)}%</div>
      <div>Direction: {acquisitionStats.currentDirection}</div>
      <div>Trial: {acquisitionStats.currentTrial}/{acquisitionStats.totalTrials}</div>
    </div>
  );

  return (
    <div className={`preview-monitor ${className}`} style={{ position: 'relative' }}>
      {/* Stimulus Preview */}
      {preview?.stimulus && (
        <div style={{ marginBottom: 16 }}>
          <h3 style={{ margin: '0 0 8px 0', fontSize: 14, fontWeight: 600 }}>
            Stimulus Preview
          </h3>
          <WebGLCanvas
            frameData={preview.stimulus}
            width={width}
            height={height}
            quality={display.previewQuality}
            overlay={statsOverlay}
            className="stimulus-preview"
          />
        </div>
      )}

      {/* Camera Preview */}
      {preview?.camera && (
        <div>
          <h3 style={{ margin: '0 0 8px 0', fontSize: 14, fontWeight: 600 }}>
            Camera Preview
          </h3>
          <WebGLCanvas
            frameData={preview.camera}
            width={width}
            height={height}
            quality={display.previewQuality}
            className="camera-preview"
          />
        </div>
      )}

      {/* No Preview State */}
      {!preview?.stimulus && !preview?.camera && (
        <div
          style={{
            width,
            height,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: '#f5f5f5',
            border: '1px solid #ddd',
            borderRadius: 4,
            color: '#666',
            fontSize: 14,
          }}
        >
          No preview available
        </div>
      )}
    </div>
  );
};

export default PreviewMonitor;