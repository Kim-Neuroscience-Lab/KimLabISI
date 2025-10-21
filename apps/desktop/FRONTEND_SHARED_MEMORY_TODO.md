# Frontend Shared Memory Integration - TODO

## Current Status: BREAKING CHANGE

The backend was updated to use shared memory for analysis composite images (eliminating the timeout), but the frontend still expects the old base64-encoded format.

## What Changed in Backend

**Before:**
```python
return {
    "success": True,
    "image_base64": "iVBORw0KGgo...",  # 2-5 MB base64 PNG
    "width": 1080,
    "height": 1080,
    "format": "png"
}
```

**After:**
```python
return {
    "success": True,
    "frame_id": 42,  # Tiny response!
    "width": 1080,
    "height": 1080,
    "format": "rgb24"
}
```

## What Needs to Be Done

### 1. Update TypeScript Types

File: `apps/desktop/src/types/ipc-messages.ts`

```typescript
export interface GetAnalysisCompositeImageResponse {
  success: boolean
  frame_id?: number        // ← NEW: Frame ID for shared memory lookup
  width?: number
  height?: number
  format?: 'rgb24'         // ← CHANGED: Was 'png', now 'rgb24'
  image_base64?: string    // ← DEPRECATED: Keep for backward compat during migration
  error?: string
}
```

### 2. Add Analysis Shared Memory Subscriber

Create: `apps/desktop/src/services/AnalysisFrameSubscriber.ts`

```typescript
import * as zmq from 'zeromq'
import * as fs from 'fs'
import * as mmap from 'mmap-io'

interface AnalysisFrameMetadata {
  frame_id: number
  timestamp_us: number
  width_px: number
  height_px: number
  data_size_bytes: number
  offset_bytes: number
  source: string
  session_path?: string
  shm_path: string
}

export class AnalysisFrameSubscriber {
  private socket: zmq.Subscriber
  private shmFd: number | null = null
  private shmBuffer: Buffer | null = null
  private readonly shmPath = '/tmp/stimulus_stream_analysis_shm'
  private readonly metadataPort = 5561  // ← NEW PORT

  constructor() {
    this.socket = new zmq.Subscriber()
  }

  async start() {
    // Connect to analysis metadata port
    this.socket.connect(`tcp://localhost:${this.metadataPort}`)
    this.socket.subscribe()  // Subscribe to all messages

    // Open shared memory file
    this.shmFd = fs.openSync(this.shmPath, 'r')
    const stats = fs.fstatSync(this.shmFd)
    this.shmBuffer = mmap.map(stats.size, mmap.PROT_READ, mmap.MAP_SHARED, this.shmFd)

    // Listen for metadata messages
    for await (const [msg] of this.socket) {
      const metadata: AnalysisFrameMetadata = JSON.parse(msg.toString())
      this.handleFrame(metadata)
    }
  }

  private handleFrame(metadata: AnalysisFrameMetadata) {
    if (!this.shmBuffer) return

    // Extract frame data from shared memory
    const frameData = this.shmBuffer.slice(
      metadata.offset_bytes,
      metadata.offset_bytes + metadata.data_size_bytes
    )

    // Convert RGB24 to displayable format
    const canvas = this.createCanvasFromRGB24(
      frameData,
      metadata.width_px,
      metadata.height_px
    )

    // Emit to renderer process
    // ... (send to AnalysisViewport)
  }

  private createCanvasFromRGB24(
    data: Buffer,
    width: number,
    height: number
  ): HTMLCanvasElement {
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')!

    const imageData = ctx.createImageData(width, height)

    // Convert RGB24 to RGBA
    for (let i = 0; i < width * height; i++) {
      imageData.data[i * 4 + 0] = data[i * 3 + 0]  // R
      imageData.data[i * 4 + 1] = data[i * 3 + 1]  // G
      imageData.data[i * 4 + 2] = data[i * 3 + 2]  // B
      imageData.data[i * 4 + 3] = 255               // A
    }

    ctx.putImageData(imageData, 0, 0)
    return canvas
  }

  cleanup() {
    this.socket.close()
    if (this.shmFd !== null) {
      mmap.unmap(this.shmBuffer!)
      fs.closeSync(this.shmFd)
    }
  }
}
```

### 3. Update AnalysisViewport Component

File: `apps/desktop/src/components/viewports/AnalysisViewport.tsx`

Lines 382-400 need to change from:

```typescript
if (result.success && result.image_base64) {
  // OLD: Convert base64 to blob
  const blob = base64ToBlob(result.image_base64, 'image/png')
  const url = URL.createObjectURL(blob)
  // ...
}
```

To:

```typescript
if (result.success && result.frame_id !== undefined) {
  // NEW: Wait for frame from shared memory subscriber
  const canvas = await analysisFrameSubscriber.getFrame(result.frame_id)
  const url = canvas.toDataURL('image/png')
  // ...
}
```

### 4. Wire Up in Main Process

File: `apps/desktop/src/main/index.ts`

```typescript
import { AnalysisFrameSubscriber } from '../services/AnalysisFrameSubscriber'

// ...

const analysisSubscriber = new AnalysisFrameSubscriber()
analysisSubscriber.start()

// Handle cleanup
app.on('will-quit', () => {
  analysisSubscriber.cleanup()
})
```

## Quick Fix (Temporary)

To restore functionality immediately, you could revert the backend to use base64 encoding, but this will bring back the timeout issue. Not recommended.

## Testing Checklist

- [ ] Analysis metadata arrives on port 5561
- [ ] Shared memory file exists at `/tmp/stimulus_stream_analysis_shm`
- [ ] Frame data can be read from shared memory
- [ ] RGB24 to RGBA conversion works correctly
- [ ] Image displays in AnalysisViewport
- [ ] Settings changes trigger new frame requests
- [ ] Memory leaks are prevented (proper cleanup)

## Files Modified

- `apps/desktop/src/types/ipc-messages.ts` - Update response type
- `apps/desktop/src/services/AnalysisFrameSubscriber.ts` - NEW
- `apps/desktop/src/components/viewports/AnalysisViewport.tsx` - Update handler
- `apps/desktop/src/main/index.ts` - Wire up subscriber
- `apps/desktop/package.json` - Add `mmap-io` dependency

## Dependencies to Add

```bash
npm install --save mmap-io
npm install --save-dev @types/mmap-io
```
