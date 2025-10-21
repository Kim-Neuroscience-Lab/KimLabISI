import React, { useState, useRef, useEffect } from 'react'

export interface CalibrationCircleProps {
  visible: boolean
  canvasWidth: number
  canvasHeight: number
  actualCameraWidth: number
  actualCameraHeight: number
  headFrameDiameterMm: number
  onCalibrationChange: (mmPerPixel: number, circleDiameterPixels: number) => void
}

/**
 * Draggable and resizable circle overlay for spatial calibration.
 * Scientists can align the circle with the head frame in the camera view,
 * then the system calculates pixels per mm based on known head frame size.
 */
export function CalibrationCircleOverlay({
  visible,
  canvasWidth,
  canvasHeight,
  actualCameraWidth,
  actualCameraHeight,
  headFrameDiameterMm,
  onCalibrationChange
}: CalibrationCircleProps) {
  // Circle state (in pixels)
  const [centerX, setCenterX] = useState(canvasWidth / 2)
  const [centerY, setCenterY] = useState(canvasHeight / 2)
  const [radius, setRadius] = useState(Math.min(canvasWidth, canvasHeight) / 4)

  // Drag state
  const [isDragging, setIsDragging] = useState(false)
  const [dragType, setDragType] = useState<'move' | 'resize' | null>(null)
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null)
  const [initialRadius, setInitialRadius] = useState(radius)

  const svgRef = useRef<SVGSVGElement>(null)

  // Calculate scale factor: how much the canvas is scaled relative to actual camera
  const scaleFactor = actualCameraWidth / canvasWidth

  // Calculate mm per pixel whenever circle size or head frame diameter changes
  useEffect(() => {
    if (headFrameDiameterMm > 0 && scaleFactor > 0) {
      // Scale the rendered diameter to actual camera pixels
      const actualDiameter = (radius * 2) * scaleFactor
      const mmPerPixel = headFrameDiameterMm / actualDiameter
      onCalibrationChange(mmPerPixel, actualDiameter)
    }
  }, [radius, headFrameDiameterMm, scaleFactor, onCalibrationChange])

  // Recenter circle when canvas size changes
  useEffect(() => {
    setCenterX(canvasWidth / 2)
    setCenterY(canvasHeight / 2)
  }, [canvasWidth, canvasHeight])

  if (!visible) return null

  const handleMouseDown = (e: React.MouseEvent, type: 'move' | 'resize') => {
    e.preventDefault()
    e.stopPropagation()

    if (!svgRef.current) return

    const rect = svgRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    setIsDragging(true)
    setDragType(type)
    setDragStart({ x, y })
    setInitialRadius(radius)
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging || !dragStart || !svgRef.current) return

    const rect = svgRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    const dx = x - dragStart.x
    const dy = y - dragStart.y

    if (dragType === 'move') {
      // Move circle
      const newX = centerX + dx
      const newY = centerY + dy

      // Keep circle within bounds
      const minX = radius
      const maxX = canvasWidth - radius
      const minY = radius
      const maxY = canvasHeight - radius

      setCenterX(Math.max(minX, Math.min(maxX, newX)))
      setCenterY(Math.max(minY, Math.min(maxY, newY)))

      setDragStart({ x, y })
    } else if (dragType === 'resize') {
      // Resize circle based on distance from center
      const distanceFromCenter = Math.sqrt(
        Math.pow(x - centerX, 2) + Math.pow(y - centerY, 2)
      )

      // Clamp radius to reasonable bounds
      const minRadius = 20
      const maxRadius = Math.min(canvasWidth, canvasHeight) / 2
      const newRadius = Math.max(minRadius, Math.min(maxRadius, distanceFromCenter))

      setRadius(newRadius)
    }
  }

  const handleMouseUp = () => {
    setIsDragging(false)
    setDragType(null)
    setDragStart(null)
  }

  const handleMouseLeave = () => {
    if (isDragging) {
      setIsDragging(false)
      setDragType(null)
      setDragStart(null)
    }
  }

  // Generate handle positions (8 handles around perimeter)
  const handles = []
  const numHandles = 8
  for (let i = 0; i < numHandles; i++) {
    const angle = (i * Math.PI * 2) / numHandles
    const handleX = centerX + radius * Math.cos(angle)
    const handleY = centerY + radius * Math.sin(angle)
    handles.push({ x: handleX, y: handleY, angle })
  }

  return (
    <svg
      ref={svgRef}
      className="absolute inset-0 pointer-events-none z-40"
      width={canvasWidth}
      height={canvasHeight}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeave}
      style={{ pointerEvents: visible ? 'auto' : 'none' }}
    >
      {/* Main circle */}
      <circle
        cx={centerX}
        cy={centerY}
        r={radius}
        fill="none"
        stroke="cyan"
        strokeWidth={2}
        strokeDasharray="8,4"
        opacity={0.8}
        className="pointer-events-auto"
        style={{ cursor: isDragging && dragType === 'move' ? 'grabbing' : 'grab' }}
        onMouseDown={(e) => handleMouseDown(e, 'move')}
      />

      {/* Crosshair at center */}
      <g opacity={0.8}>
        <line
          x1={centerX - 15}
          y1={centerY}
          x2={centerX + 15}
          y2={centerY}
          stroke="cyan"
          strokeWidth={2}
        />
        <line
          x1={centerX}
          y1={centerY - 15}
          x2={centerX}
          y2={centerY + 15}
          stroke="cyan"
          strokeWidth={2}
        />
      </g>

      {/* Resize handles */}
      {handles.map((handle, index) => (
        <circle
          key={index}
          cx={handle.x}
          cy={handle.y}
          r={6}
          fill="cyan"
          stroke="white"
          strokeWidth={2}
          opacity={0.9}
          className="pointer-events-auto"
          style={{ cursor: 'nwse-resize' }}
          onMouseDown={(e) => handleMouseDown(e, 'resize')}
        />
      ))}

      {/* Diameter label - show actual camera pixels */}
      <g>
        <rect
          x={centerX - 60}
          y={centerY - radius - 35}
          width={120}
          height={25}
          fill="black"
          opacity={0.7}
          rx={4}
        />
        <text
          x={centerX}
          y={centerY - radius - 17}
          textAnchor="middle"
          fill="cyan"
          fontSize={14}
          fontWeight="bold"
          fontFamily="monospace"
        >
          ⌀ {((radius * 2) * scaleFactor).toFixed(1)} px
        </text>
      </g>
    </svg>
  )
}
