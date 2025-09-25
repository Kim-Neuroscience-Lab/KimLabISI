/**
 * ISI Macroscope Control System - Results Display
 *
 * Displays analysis results including retinotopic maps and statistics.
 * Uses WebGL canvas for efficient map rendering.
 */

import React, { useState } from 'react';
import { WebGLCanvas } from '../hardware/WebGLCanvas';
import { useResults, useResultsMaps, useResultsStatistics } from '../../stores/backend-mirror';
import { useIPCActions } from '../../services/ipc-client';

// ============================================================================
// RESULTS DISPLAY COMPONENT
// ============================================================================

interface ResultsDisplayProps {
  /** Width of the map displays */
  mapWidth?: number;
  /** Height of the map displays */
  mapHeight?: number;
  /** CSS class name */
  className?: string;
}

export const ResultsDisplay: React.FC<ResultsDisplayProps> = ({
  mapWidth = 400,
  mapHeight = 300,
  className = '',
}) => {
  const results = useResults();
  const maps = useResultsMaps();
  const statistics = useResultsStatistics();
  const ipcActions = useIPCActions();

  const [selectedMapIndex, setSelectedMapIndex] = useState(0);

  const handleExport = async (format: string, actionElement: string) => {
    try {
      await ipcActions.sendClick(actionElement);
    } catch (error) {
      console.error('Failed to export results:', error);
    }
  };

  // Convert map data to preview frame format for WebGL canvas
  const convertMapToFrameData = (map: any) => {
    if (!map) return null;

    return {
      frameNumber: 0,
      timestamp: Date.now(),
      imageData: map.imageData,
      width: map.width,
      height: map.height,
      format: 'PNG' as const,
    };
  };

  if (!results) {
    return (
      <div className={`results-display ${className}`}>
        <div style={{ textAlign: 'center', color: '#666', padding: 40 }}>
          No results available
        </div>
      </div>
    );
  }

  return (
    <div className={`results-display ${className}`}>
      {/* Maps Display */}
      {maps && maps.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: 16, fontWeight: 600 }}>
            Retinotopic Maps
          </h3>

          {/* Map Selection */}
          {maps.length > 1 && (
            <div style={{ marginBottom: 12 }}>
              <select
                value={selectedMapIndex}
                onChange={(e) => setSelectedMapIndex(parseInt(e.target.value))}
                style={{
                  padding: '4px 8px',
                  borderRadius: 4,
                  border: '1px solid #ccc',
                  fontSize: 14,
                }}
              >
                {maps.map((map, index) => (
                  <option key={index} value={index}>
                    {map.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Selected Map Display */}
          {maps[selectedMapIndex] && (
            <div>
              <div style={{ marginBottom: 8 }}>
                <strong>{maps[selectedMapIndex].name}</strong>
                <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                  {maps[selectedMapIndex].description}
                </div>
                <div style={{ fontSize: 12, color: '#666' }}>
                  Range: {maps[selectedMapIndex].valueRange[0].toFixed(2)} - {maps[selectedMapIndex].valueRange[1].toFixed(2)}
                </div>
              </div>

              <WebGLCanvas
                frameData={convertMapToFrameData(maps[selectedMapIndex])}
                width={mapWidth}
                height={mapHeight}
                quality="high"
                className="results-map"
              />
            </div>
          )}
        </div>
      )}

      {/* Statistics */}
      {statistics && (
        <div style={{ marginBottom: 24 }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: 16, fontWeight: 600 }}>
            Analysis Statistics
          </h3>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: 16,
          }}>
            <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Processing</div>
              <div>Frames: {statistics.totalFramesProcessed.toLocaleString()}</div>
              <div>Time: {statistics.processingTimeSeconds.toFixed(1)}s</div>
            </div>

            <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Quality</div>
              <div>Correlation: {(statistics.correlationQuality * 100).toFixed(1)}%</div>
              <div>SNR: {statistics.signalToNoise.toFixed(2)}</div>
            </div>

            <div style={{ padding: 16, backgroundColor: '#f9f9f9', borderRadius: 4 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Coverage</div>
              <div>{(statistics.coveragePercentage * 100).toFixed(1)}%</div>
            </div>
          </div>
        </div>
      )}

      {/* Quality Metrics */}
      {results.qualityMetrics && (
        <div style={{ marginBottom: 24 }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: 16, fontWeight: 600 }}>
            Quality Assessment
          </h3>

          <div style={{ marginBottom: 16 }}>
            <div style={{ marginBottom: 8 }}>
              <span style={{ fontWeight: 600 }}>Overall Quality: </span>
              <span style={{
                color: results.qualityMetrics.overall > 80 ? '#22c55e' :
                      results.qualityMetrics.overall > 60 ? '#f59e0b' : '#ef4444'
              }}>
                {results.qualityMetrics.overall.toFixed(1)}%
              </span>
            </div>

            <div style={{ fontSize: 12, color: '#666' }}>
              <div>Spatial Coverage: {results.qualityMetrics.spatialCoverage.toFixed(1)}%</div>
              <div>Temporal Stability: {results.qualityMetrics.temporalStability.toFixed(1)}%</div>
              <div>Signal Clarity: {results.qualityMetrics.signalClarity.toFixed(1)}%</div>
            </div>
          </div>

          {results.qualityMetrics.recommendations && results.qualityMetrics.recommendations.length > 0 && (
            <div>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Recommendations:</div>
              <ul style={{ margin: 0, paddingLeft: 20, fontSize: 12, color: '#666' }}>
                {results.qualityMetrics.recommendations.map((rec, index) => (
                  <li key={index}>{rec}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Export Options */}
      {results.exportOptions && results.exportOptions.length > 0 && (
        <div>
          <h3 style={{ margin: '0 0 16px 0', fontSize: 16, fontWeight: 600 }}>
            Export Results
          </h3>

          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {results.exportOptions.map((option, index) => (
              <button
                key={index}
                onClick={() => handleExport(option.format, option.actionElement)}
                disabled={!option.isAvailable}
                style={{
                  padding: '8px 16px',
                  borderRadius: 4,
                  border: '1px solid #ccc',
                  backgroundColor: option.isAvailable ? '#fff' : '#f5f5f5',
                  color: option.isAvailable ? '#333' : '#999',
                  cursor: option.isAvailable ? 'pointer' : 'not-allowed',
                  fontSize: 14,
                }}
              >
                Export as {option.format}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ResultsDisplay;