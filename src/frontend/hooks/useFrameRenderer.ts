import { useRef, useEffect, useCallback } from 'react'

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
 */
export function useFrameRenderer() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const renderFrame = useCallback((frameData: FrameData) => {
    const canvas = canvasRef.current
    if (!canvas) return

    const { width_px, height_px, frame_data } = frameData

    // Set canvas dimensions if they've changed
    if (canvas.width !== width_px || canvas.height !== height_px) {
      canvas.width = width_px
      canvas.height = height_px
    }

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Convert frame data to Uint8Array
    const uint8Array = new Uint8Array(frame_data)
    const totalPixels = width_px * height_px
    const channels = uint8Array.length / totalPixels

    // Create ImageData for canvas rendering
    const imageData = ctx.createImageData(width_px, height_px)

    if (channels === 1) {
      // Grayscale - expand to RGBA
      for (let i = 0; i < totalPixels; i++) {
        const val = uint8Array[i]
        imageData.data[i * 4] = val     // R
        imageData.data[i * 4 + 1] = val // G
        imageData.data[i * 4 + 2] = val // B
        imageData.data[i * 4 + 3] = 255 // A
      }
    } else if (channels === 3) {
      // RGB - add alpha channel
      for (let i = 0; i < totalPixels; i++) {
        imageData.data[i * 4] = uint8Array[i * 3]         // R
        imageData.data[i * 4 + 1] = uint8Array[i * 3 + 1] // G
        imageData.data[i * 4 + 2] = uint8Array[i * 3 + 2] // B
        imageData.data[i * 4 + 3] = 255                    // A
      }
    } else if (channels === 4) {
      // Already RGBA - direct copy
      imageData.data.set(uint8Array)
    } else {
      console.error(`Unsupported channel count: ${channels}`)
      return
    }

    // Render to canvas
    ctx.putImageData(imageData, 0, 0)
  }, [])

  return { canvasRef, renderFrame }
}