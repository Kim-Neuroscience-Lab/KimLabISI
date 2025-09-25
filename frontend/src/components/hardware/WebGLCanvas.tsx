/**
 * ISI Macroscope Control System - WebGL Canvas
 *
 * WebGL canvas component for frame display.
 * Uses WebGL for GPU rendering and efficient binary data handling.
 */

import React, { useRef, useEffect, useCallback, useState } from 'react';
import type { PreviewFrameData } from '../../types/ipc-messages';

// ============================================================================
// WEBGL CANVAS COMPONENT
// ============================================================================

interface WebGLCanvasProps {
  /** Frame data to display */
  frameData: PreviewFrameData | null;
  /** Canvas width */
  width: number;
  /** Canvas height */
  height: number;
  /** Whether to maintain aspect ratio */
  maintainAspectRatio?: boolean;
  /** Quality setting for display */
  quality?: 'low' | 'medium' | 'high';
  /** Optional overlay content */
  overlay?: React.ReactNode;
  /** Callback when frame is rendered */
  onFrameRendered?: (frameNumber: number, renderTime: number) => void;
  /** Canvas styling */
  className?: string;
}

export const WebGLCanvas: React.FC<WebGLCanvasProps> = ({
  frameData,
  width,
  height,
  maintainAspectRatio = true,
  quality = 'medium',
  overlay,
  onFrameRendered,
  className = '',
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const glRef = useRef<WebGLRenderingContext | null>(null);
  const textureRef = useRef<WebGLTexture | null>(null);
  const programRef = useRef<WebGLProgram | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);
  const [renderStats, setRenderStats] = useState({
    fps: 0,
    frameCount: 0,
    lastTime: 0,
  });

  // Initialize WebGL context and shaders
  const initializeWebGL = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return false;

    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
    if (!gl) {
      console.error('WebGL not supported');
      return false;
    }

    glRef.current = gl;

    // Vertex shader for quad rendering
    const vertexShaderSource = `
      attribute vec2 a_position;
      attribute vec2 a_texCoord;
      varying vec2 v_texCoord;

      void main() {
        gl_Position = vec4(a_position, 0.0, 1.0);
        v_texCoord = a_texCoord;
      }
    `;

    // Fragment shader with quality-based filtering
    const fragmentShaderSource = `
      precision mediump float;
      uniform sampler2D u_texture;
      uniform float u_brightness;
      uniform float u_contrast;
      varying vec2 v_texCoord;

      void main() {
        vec4 color = texture2D(u_texture, v_texCoord);
        // Apply brightness and contrast adjustments
        color.rgb = (color.rgb - 0.5) * u_contrast + 0.5 + u_brightness;
        gl_FragColor = color;
      }
    `;

    const program = createShaderProgram(gl, vertexShaderSource, fragmentShaderSource);
    if (!program) return false;

    programRef.current = program;

    // Create texture for frame data
    const texture = gl.createTexture();
    textureRef.current = texture;

    // Set up quad geometry
    setupQuadGeometry(gl, program);

    setIsInitialized(true);
    return true;
  }, []);

  // Create and compile shader program
  const createShaderProgram = (
    gl: WebGLRenderingContext,
    vertexSource: string,
    fragmentSource: string
  ): WebGLProgram | null => {
    const vertexShader = createShader(gl, gl.VERTEX_SHADER, vertexSource);
    const fragmentShader = createShader(gl, gl.FRAGMENT_SHADER, fragmentSource);

    if (!vertexShader || !fragmentShader) return null;

    const program = gl.createProgram();
    if (!program) return null;

    gl.attachShader(program, vertexShader);
    gl.attachShader(program, fragmentShader);
    gl.linkProgram(program);

    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.error('Program link error:', gl.getProgramInfoLog(program));
      return null;
    }

    return program;
  };

  const createShader = (
    gl: WebGLRenderingContext,
    type: number,
    source: string
  ): WebGLShader | null => {
    const shader = gl.createShader(type);
    if (!shader) return null;

    gl.shaderSource(shader, source);
    gl.compileShader(shader);

    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      console.error('Shader compile error:', gl.getShaderInfoLog(shader));
      gl.deleteShader(shader);
      return null;
    }

    return shader;
  };

  // Set up quad geometry for full-canvas rendering
  const setupQuadGeometry = (gl: WebGLRenderingContext, program: WebGLProgram) => {
    const positions = new Float32Array([
      -1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1,
    ]);

    const texCoords = new Float32Array([
      0, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 0,
    ]);

    // Position buffer
    const positionBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, positions, gl.STATIC_DRAW);

    const positionLocation = gl.getAttribLocation(program, 'a_position');
    gl.enableVertexAttribArray(positionLocation);
    gl.vertexAttribPointer(positionLocation, 2, gl.FLOAT, false, 0, 0);

    // Texture coordinate buffer
    const texCoordBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, texCoordBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, texCoords, gl.STATIC_DRAW);

    const texCoordLocation = gl.getAttribLocation(program, 'a_texCoord');
    gl.enableVertexAttribArray(texCoordLocation);
    gl.vertexAttribPointer(texCoordLocation, 2, gl.FLOAT, false, 0, 0);
  };

  // Render frame data to canvas
  const renderFrame = useCallback((frameData: PreviewFrameData) => {
    const gl = glRef.current;
    const program = programRef.current;
    const texture = textureRef.current;

    if (!gl || !program || !texture || !canvasRef.current) return;

    const startTime = performance.now();

    // Update canvas size if needed
    const canvas = canvasRef.current;
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
      gl.viewport(0, 0, width, height);
    }

    // Convert ArrayBuffer to ImageData
    const imageData = arrayBufferToImageData(frameData.imageData, frameData.width, frameData.height);

    // Update texture with new frame data
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, imageData);

    // Set texture parameters based on quality setting
    const filterType = quality === 'high' ? gl.LINEAR : gl.NEAREST;
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, filterType);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, filterType);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);

    // Use shader program
    gl.useProgram(program);

    // Set uniforms
    const textureLocation = gl.getUniformLocation(program, 'u_texture');
    const brightnessLocation = gl.getUniformLocation(program, 'u_brightness');
    const contrastLocation = gl.getUniformLocation(program, 'u_contrast');

    gl.uniform1i(textureLocation, 0);
    gl.uniform1f(brightnessLocation, 0.0); // Default brightness
    gl.uniform1f(contrastLocation, 1.0);   // Default contrast

    // Clear and draw
    gl.clearColor(0, 0, 0, 1);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.drawArrays(gl.TRIANGLES, 0, 6);

    const renderTime = performance.now() - startTime;

    // Update render statistics
    setRenderStats(prev => {
      const now = performance.now();
      const deltaTime = now - prev.lastTime;
      const newFrameCount = prev.frameCount + 1;

      let newFps = prev.fps;
      if (deltaTime > 1000) {
        // Update FPS every second
        newFps = (newFrameCount * 1000) / deltaTime;
        return {
          fps: newFps,
          frameCount: 0,
          lastTime: now,
        };
      }

      return {
        fps: newFps,
        frameCount: newFrameCount,
        lastTime: prev.lastTime || now,
      };
    });

    // Notify callback
    onFrameRendered?.(frameData.frameNumber, renderTime);
  }, [width, height, quality, onFrameRendered]);

  // Convert ArrayBuffer to ImageData for WebGL texture
  const arrayBufferToImageData = (buffer: ArrayBuffer, width: number, height: number): ImageData => {
    // Assuming RGBA format from backend
    const uint8Array = new Uint8ClampedArray(buffer);
    return new ImageData(uint8Array, width, height);
  };

  // Initialize WebGL on mount
  useEffect(() => {
    initializeWebGL();

    return () => {
      // Cleanup WebGL resources
      const gl = glRef.current;
      if (gl && textureRef.current) {
        gl.deleteTexture(textureRef.current);
      }
      if (gl && programRef.current) {
        gl.deleteProgram(programRef.current);
      }
    };
  }, [initializeWebGL]);

  // Render frame when frameData updates
  useEffect(() => {
    if (isInitialized && frameData) {
      renderFrame(frameData);
    }
  }, [isInitialized, frameData, renderFrame]);

  return (
    <div className={`hardware-canvas-container ${className}`} style={{ position: 'relative' }}>
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        style={{
          display: 'block',
          maxWidth: '100%',
          maxHeight: '100%',
          objectFit: maintainAspectRatio ? 'contain' : 'fill',
        }}
      />

      {overlay && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            pointerEvents: 'none',
            zIndex: 1,
          }}
        >
          {overlay}
        </div>
      )}

      {process.env.NODE_ENV === 'development' && (
        <div
          style={{
            position: 'absolute',
            top: 8,
            right: 8,
            background: 'rgba(0, 0, 0, 0.7)',
            color: 'white',
            padding: '4px 8px',
            borderRadius: 4,
            fontSize: 12,
            fontFamily: 'monospace',
          }}
        >
          {renderStats.fps.toFixed(1)} FPS
        </div>
      )}
    </div>
  );
};

export default WebGLCanvas;