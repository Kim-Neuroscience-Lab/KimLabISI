import { useRef, useEffect, useCallback } from 'react'
import { hookLogger } from '../utils/logger'

interface FrameData {
  frame_id: number
  timestamp_us: number
  frame_index: number
  direction: string
  angle_degrees: number
  width_px: number
  height_px: number
  frame_data: ArrayBuffer | Buffer
}

/**
 * Hook for rendering raw binary frame data to a canvas element
 * Provides high-performance direct rendering for stimulus frames
 *
 * HARDWARE VSYNC:
 * - Uses requestAnimationFrame() which is automatically synchronized to the
 *   display's hardware VSync by the browser/Electron
 * - Actual display happens at exact monitor refresh intervals (~50μs precision)
 * - Backend publishes frames at approximate FPS (time.sleep ~0.5-2ms jitter)
 * - Frontend's hardware VSync ensures display timing is precise regardless of
 *   backend publication timing jitter
 */
export function useFrameRenderer() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const frameCache = useRef<Map<number, ImageData>>(new Map())

  const renderFrame = useCallback((frameData: FrameData) => {
    // DIAGNOSTIC: Log frame rendering attempt
    console.log('[useFrameRenderer] Rendering frame:', {
      frame_id: frameData.frame_id,
      width: frameData.width_px,
      height: frameData.height_px,
      data_size: frameData.frame_data instanceof ArrayBuffer ? frameData.frame_data.byteLength : 'unknown'
    })

    const canvas = canvasRef.current
    if (!canvas) {
      console.warn('[useFrameRenderer] Canvas ref not available!')
      return
    }

    const { width_px, height_px, frame_data, frame_id } = frameData

    // Set canvas dimensions if they've changed
    if (canvas.width !== width_px || canvas.height !== height_px) {
      canvas.width = width_px
      canvas.height = height_px
      frameCache.current.clear() // Clear cache on dimension change
    }

    const ctx = canvas.getContext('2d', { willReadFrequently: false })
    if (!ctx) return

    // Check cache first
    const cached = frameCache.current.get(frame_id)
    if (cached) {
      // Use requestAnimationFrame to capture exact vsync timestamp
      requestAnimationFrame(() => {
        const displayTimestampUs = Math.round(performance.now() * 1000) // Convert ms to microseconds
        ctx.putImageData(cached, 0, 0)

        // Send display timestamp to main process for correlation
        window.electronAPI?.sendToPython({
          type: 'display_timestamp',
          frame_id: frame_id,
          display_timestamp_us: displayTimestampUs
        }).catch(err => hookLogger.error('Failed to send display timestamp:', err))
      })
      return
    }

    // Convert frame data to Uint8Array
    let uint8Array: Uint8Array

    if (frame_data instanceof Uint8Array) {
      uint8Array = frame_data
    } else if (frame_data instanceof ArrayBuffer) {
      uint8Array = new Uint8Array(frame_data)
    } else if (ArrayBuffer.isView(frame_data)) {
      uint8Array = new Uint8Array(
        frame_data.buffer,
        frame_data.byteOffset || 0,
        frame_data.byteLength
      )
    } else if (Array.isArray(frame_data)) {
      uint8Array = Uint8Array.from(frame_data)
    } else {
      hookLogger.error('Unsupported frame data type:', frame_data?.constructor?.name)
      return
    }

    const totalPixels = width_px * height_px
    const channels = uint8Array.length / totalPixels

    // DIAGNOSTIC: Log channel detection
    console.log('[useFrameRenderer] Frame format:', {
      totalPixels,
      dataLength: uint8Array.length,
      calculatedChannels: channels,
      isGrayscale: channels === 1
    })

    // Create ImageData for canvas rendering
    const imageData = ctx.createImageData(width_px, height_px)

    if (channels === 4) {
      // RGBA format - direct transfer (legacy support)
      imageData.data.set(uint8Array)
    } else if (channels === 1) {
      // Grayscale format (NEW: optimized for zero-overhead backend)
      // Convert grayscale to RGBA for Canvas API
      // This happens in the frontend, not in the critical backend playback loop!
      const rgbaData = imageData.data
      for (let i = 0; i < totalPixels; i++) {
        const gray = uint8Array[i]
        const rgbaIndex = i * 4
        rgbaData[rgbaIndex] = gray     // R
        rgbaData[rgbaIndex + 1] = gray // G
        rgbaData[rgbaIndex + 2] = gray // B
        rgbaData[rgbaIndex + 3] = 255  // A
      }
    } else {
      hookLogger.error(`Unexpected channel count: ${channels}. Expected 1 (grayscale) or 4 (RGBA).`)
      return
    }

    // Cache the converted image (limit cache size)
    if (frameCache.current.size > 100) {
      const firstKey = frameCache.current.keys().next().value
      frameCache.current.delete(firstKey)
    }
    frameCache.current.set(frame_id, imageData)

    // Use requestAnimationFrame to capture exact vsync timestamp when frame is displayed
    requestAnimationFrame(() => {
      const displayTimestampUs = Math.round(performance.now() * 1000) // Convert ms to microseconds
      ctx.putImageData(imageData, 0, 0)

      // Send display timestamp to main process for correlation
      window.electronAPI?.sendToPython({
        type: 'display_timestamp',
        frame_id: frame_id,
        display_timestamp_us: displayTimestampUs
      }).catch(err => hookLogger.error('Failed to send display timestamp:', err))
    })
  }, [])

  return { canvasRef, renderFrame }
}