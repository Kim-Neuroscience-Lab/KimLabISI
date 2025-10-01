import { app, BrowserWindow, ipcMain, screen, shell } from 'electron'
import * as path from 'node:path'
import { spawn, execSync } from 'node:child_process'
import type { ChildProcess } from 'node:child_process'
import * as zmq from 'zeromq'
import * as fs from 'node:fs'

// The built directory structure
//
// ├─┬ dist-electron
// │ ├─┬ main.cjs    > Electron main
// │ │ └─┬ preload.cjs    > Preload scripts
// │ └─┬ renderer.js > Electron renderer
//
process.env.DIST_ELECTRON = path.join(__dirname, '../')
process.env.DIST = path.join(__dirname, '../renderer')
process.env.VITE_PUBLIC = process.env.VITE_DEV_SERVER_URL
  ? path.join(process.env.DIST_ELECTRON, './public')
  : process.env.DIST

// Disable GPU Acceleration for Windows 7
if (process.platform === 'win32') app.disableHardwareAcceleration()

// Set application name for Windows 10+ notifications
if (process.platform === 'win32') app.setAppUserModelId(app.getName())

if (!app.requestSingleInstanceLock()) {
  app.quit()
  process.exit(0)
}

// Global variables for processes
let mainWindow: BrowserWindow | null = null
let presentationWindow: BrowserWindow | null = null
let isInitialLoad = true

// Shared Memory Frame Reader for high-performance streaming
class SharedMemoryFrameReader {
  private zmqSocket: zmq.Subscriber | null = null
  private sharedMemoryFd: number | null = null
  private sharedMemoryPath = '/tmp/stimulus_stream_shm'
  private isRunning = false

  async initialize(zmqPort: number = 5557): Promise<void> {
    try {
      // Initialize ZeroMQ subscriber for frame metadata
      this.zmqSocket = new zmq.Subscriber()
      this.zmqSocket.connect(`tcp://localhost:${zmqPort}`)
      this.zmqSocket.subscribe() // Subscribe to all messages

      this.isRunning = true
      console.log(`SharedMemoryFrameReader initialized on port ${zmqPort}`)

      // Start listening for frame metadata
      this.startMetadataListener()
    } catch (error) {
      console.error('Failed to initialize SharedMemoryFrameReader:', error)
      throw error
    }
  }

  private async startMetadataListener(): Promise<void> {
    try {
      for await (const [msg] of this.zmqSocket!) {
        if (!this.isRunning) break

        try {
          const metadata = JSON.parse(msg.toString())
          await this.handleFrameMetadata(metadata)
        } catch (error) {
          console.error('Error processing frame metadata:', error)
        }
      }
    } catch (error) {
      console.error('Metadata listener error:', error)
    }
  }

  private async handleFrameMetadata(metadata: any): Promise<void> {
    try {
      // Read frame data directly from shared memory file
      const frameData = await this.readFrameFromSharedMemory(
        metadata.offset_bytes,
        metadata.data_size_bytes
      )

      // Send raw binary PNG data to both main and presentation windows
      const frameMessage = {
        frame_id: metadata.frame_id,
        timestamp_us: metadata.timestamp_us,
        frame_index: metadata.frame_index,
        direction: metadata.direction,
        angle_degrees: metadata.angle_degrees,
        width_px: metadata.width_px,
        height_px: metadata.height_px,
        frame_data: frameData  // Raw binary PNG data
      }

      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('shared-memory-frame', frameMessage)
      }

      if (presentationWindow && !presentationWindow.isDestroyed()) {
        presentationWindow.webContents.send('shared-memory-frame', frameMessage)
      }
    } catch (error) {
      console.error('Error handling frame metadata:', error)
    }
  }

  private async readFrameFromSharedMemory(offset: number, size: number): Promise<Buffer> {
    try {
      // Open shared memory file if not already open
      if (!this.sharedMemoryFd) {
        if (!fs.existsSync(this.sharedMemoryPath)) {
          throw new Error(`Shared memory file does not exist: ${this.sharedMemoryPath}`)
        }
        this.sharedMemoryFd = fs.openSync(this.sharedMemoryPath, 'r')
      }

      // Read frame data at specified offset
      const buffer = Buffer.alloc(size)
      const bytesRead = fs.readSync(this.sharedMemoryFd, buffer, 0, size, offset)

      if (bytesRead !== size) {
        throw new Error(`Expected to read ${size} bytes, but read ${bytesRead}`)
      }

      return buffer
    } catch (error) {
      console.error('Error reading from shared memory:', error)
      throw error
    }
  }

  cleanup(): void {
    this.isRunning = false

    if (this.zmqSocket) {
      this.zmqSocket.close()
      this.zmqSocket = null
    }

    if (this.sharedMemoryFd) {
      fs.closeSync(this.sharedMemoryFd)
      this.sharedMemoryFd = null
    }

    console.log('SharedMemoryFrameReader cleaned up')
  }
}

// Global shared memory reader instance
let sharedMemoryReader: SharedMemoryFrameReader | null = null

// Multi-Channel IPC Backend Management
class MultiChannelIPCManager {
  private process: ChildProcess | null = null
  private isReady = false
  private healthSocket: zmq.Subscriber | null = null
  private syncSocket: zmq.Subscriber | null = null
  private healthCheckInterval: NodeJS.Timeout | null = null
  private startupTimeout: NodeJS.Timeout | null = null
  private readonly STARTUP_TIMEOUT = 15000 // 15 seconds
  private readonly HEALTH_CHECK_INTERVAL = 5000 // 5 seconds
  private readonly HEALTH_PORT = 5555   // HEALTH channel (PUB/SUB) - continuous health monitoring
  private readonly SYNC_PORT = 5558     // SYNC channel (PUB/SUB) - coordination messages after startup
  private zeroMQInitialized = false
  private handshakeInProgress = false

  async start(): Promise<void> {
    // Clean up any existing processes first
    await this.cleanup()

    return new Promise((resolve, reject) => {
      try {
        const isDevelopment = process.env.NODE_ENV !== 'production' || process.env.VITE_DEV_SERVER_URL
        const rootDir = isDevelopment
          ? path.join(__dirname, '../..')
          : process.resourcesPath

        console.log('Starting Python backend with multi-channel IPC system')

        // Kill any existing Python processes that might conflict
        this.killExistingPythonProcesses()

        this.process = spawn('/Users/Adam/.local/bin/poetry', ['run', 'python', '-u', '-m', 'isi_control.main'], {
          stdio: ['pipe', 'pipe', 'pipe'],
          cwd: rootDir,
          env: {
            ...process.env,
            PYTHONPATH: 'src/backend/src'
          }
        })

        // Monitor backend startup messages - JSON messages via CONTROL channel (stdout)
        this.process.stdout?.on('data', (data: Buffer) => {
          const output = data.toString().trim()
          if (!output) return

          // Split by lines in case multiple JSON messages are in one chunk
          const lines = output.split('\n').filter(line => line.trim())

          for (const line of lines) {
            try {
              // Try to parse as JSON first (startup status messages)
              const jsonMessage = JSON.parse(line.trim())
              this.handleBackendMessage(jsonMessage).catch((error) => {
                console.error('Error handling backend message:', error)
              })

              // Check for IPC initialization complete
              if (jsonMessage.type === 'startup_status' &&
                  jsonMessage.message &&
                  jsonMessage.message.includes('Multi-channel IPC system initialized')) {
                // Backend IPC is ready, initialize our ZeroMQ connections
                this.initializeZeroMQConnections().then(() => {
                  resolve && this.onBackendReady(resolve)
                }).catch(reject)
              }
            } catch (error) {
              // Not JSON, treat as plain text log
              console.log('Backend output:', line)

              // Fallback check for legacy startup message
              if (line.includes('Multi-channel IPC system initialized')) {
                this.initializeZeroMQConnections().then(() => {
                  resolve && this.onBackendReady(resolve)
                }).catch(reject)
              }
            }
          }
        })

        this.process.stderr?.on('data', (data: Buffer) => {
          const errorMsg = data.toString()
          console.error('Python backend stderr:', errorMsg)
          if (mainWindow) {
            mainWindow.webContents.send('backend-error', `Backend error: ${errorMsg}`)
          }
        })

        this.process.on('error', (error) => {
          console.error('Python process error:', error)
          reject(error)
          this.cleanup()
        })

        this.process.on('exit', (_code, _signal) => {
          console.log('Backend process exited')
          this.isReady = false
          this.cleanup()
          if (mainWindow) {
            mainWindow.webContents.send('backend-error', 'Backend process exited')
          }
        })

        // Set startup timeout
        this.startupTimeout = setTimeout(() => {
          if (!this.isReady) {
            this.cleanup()
            reject(new Error('Python backend startup timeout after 15 seconds'))
          }
        }, this.STARTUP_TIMEOUT)

      } catch (error) {
        console.error('Error starting Python backend:', error)
        reject(error)
      }
    })
  }

  async initializeZeroMQConnections(): Promise<void> {
    if (this.zeroMQInitialized) {
      return
    }

    try {
      // Initialize health channel for continuous monitoring (PUB/SUB pattern)
      this.healthSocket = new zmq.Subscriber()
      this.healthSocket.connect(`tcp://localhost:${this.HEALTH_PORT}`)
      this.healthSocket.subscribe() // Subscribe to all health messages

      // Initialize sync channel for system coordination (PUB/SUB pattern)
      this.syncSocket = new zmq.Subscriber()
      this.syncSocket.connect(`tcp://localhost:${this.SYNC_PORT}`)
      this.syncSocket.subscribe() // Subscribe to all coordination messages

      console.log('ZeroMQ PUB/SUB channels initialized successfully')
      console.log('CONTROL channel uses stdin/stdout for startup coordination')

      // Start listening for health and sync messages
      this.startHealthListener()
      this.startSyncListener()

      this.zeroMQInitialized = true

    } catch (error) {
      console.error('Failed to initialize ZeroMQ connections:', error)
      this.zeroMQInitialized = false
      throw error
    }
  }

  private async startSyncListener(): Promise<void> {
    try {
      if (!this.syncSocket) return

      for await (const [msg] of this.syncSocket) {
        try {
          const syncMessage = JSON.parse(msg.toString())
          this.handleSyncMessage(syncMessage)
        } catch (error) {
          console.error('Error processing sync message:', error)
        }
      }
    } catch (error) {
      console.error('Sync listener error:', error)
    }
  }

  private handleSyncMessage(message: any): void {
    console.log('Received SYNC channel message:', message)

    // Forward sync coordination messages to renderer via dedicated channel
    if (mainWindow) {
      mainWindow.webContents.send('sync-message', message)
    }
  }

  private async handleBackendMessage(message: any): Promise<void> {
    console.log('Received CONTROL channel message via stdout:', message)

    // Log system_fully_ready specifically for debugging
    if (message.type === 'system_fully_ready') {
      console.log('*** SYSTEM_FULLY_READY MESSAGE RECEIVED ***', message)
    }

    // Forward control messages (startup status, parameter updates, etc.) to renderer
    if (mainWindow) {
      mainWindow.webContents.send('control-message', message)
      console.log('Forwarded control-message to renderer:', message.type)
    } else {
      console.warn('Cannot forward message - mainWindow not available')
    }

    if (message.type === 'system_state' && message.state === 'waiting_frontend') {
      await this.performFrontendHandshake()
    }

    if (
      message.type === 'startup_coordination' &&
      message.command === 'check_frontend_ready'
    ) {
      await this.performFrontendHandshake(message.ping_id)
    }
  }

  private async onBackendReady(resolve: () => void): Promise<void> {
    console.log('Backend multi-channel IPC system is ready')
    this.isReady = true

    // Initialize shared memory reader for high-performance streaming
    try {
      sharedMemoryReader = new SharedMemoryFrameReader()
      await sharedMemoryReader.initialize()
      console.log('Shared memory frame reader initialized')
    } catch (error) {
      console.error('Failed to initialize shared memory reader:', error)
    }

    // Clear startup timeout
    if (this.startupTimeout) {
      clearTimeout(this.startupTimeout)
      this.startupTimeout = null
    }

    // Signal to renderer
    if (mainWindow) {
      mainWindow.webContents.send('main-process-message', 'Backend ready')
    }

    // Start health monitoring
    this.startHealthCheck()

    resolve()
  }

  private startHealthCheck(): void {
    // Health monitoring now uses PUB/SUB pattern - we listen for health updates
    // rather than actively requesting them
    // Note: Health listener is already started during initialization, no need to start it again
    console.log('Health monitoring started - listening for health updates from backend')
  }

  private async startHealthListener(): Promise<void> {
    if (!this.healthSocket) return

    try {
      for await (const [msg] of this.healthSocket) {
        try {
          const healthData = JSON.parse(msg.toString())
          this.handleHealthUpdate(healthData)
        } catch (error) {
          console.error('Error processing health update:', error)
        }
      }
    } catch (error) {
      console.error('Health listener error:', error)
    }
  }

  private handleHealthUpdate(healthData: any): void {
    // Silently forward health data to renderer - don't log to console
    if (mainWindow) {
      mainWindow.webContents.send('health-message', healthData)
    }
  }

  private killExistingPythonProcesses(): void {
    try {
      let processes: string
      try {
        processes = execSync('pgrep -f "isi_control.main"', { encoding: 'utf8' })
      } catch (error) {
        return
      }

      if (processes.trim()) {
        console.log('Terminating existing ISI backend processes')
        execSync('pkill -f "isi_control.main"')
      }
    } catch (error) {
      const err = error as NodeJS.ErrnoException & { status?: number }
      if (err.status !== 1) {
        console.error('Error during process cleanup:', err.message)
      }
    }
  }

  async cleanup(): Promise<void> {
    if (this.startupTimeout) {
      clearTimeout(this.startupTimeout)
      this.startupTimeout = null
    }

    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval)
      this.healthCheckInterval = null
    }

    // Cleanup shared memory reader
    if (sharedMemoryReader) {
      sharedMemoryReader.cleanup()
      sharedMemoryReader = null
    }

    // Close ZeroMQ PUB/SUB sockets
    if (this.healthSocket) {
      this.healthSocket.close()
      this.healthSocket = null
    }

    if (this.syncSocket) {
      this.syncSocket.close()
      this.syncSocket = null
    }

    if (this.process) {
      try {
        this.process.kill('SIGTERM')
        await new Promise(resolve => setTimeout(resolve, 1000))

        if (this.process && !this.process.killed) {
          this.process.kill('SIGKILL')
        }
      } catch (error) {
        console.error('Error stopping Python process:', error)
      }

      this.process = null
    }

    this.isReady = false
    this.zeroMQInitialized = false
  }

  async sendStartupCommand(message: any): Promise<void> {
    if (!this.process) {
      throw new Error('Backend process not available')
    }
    const payload = JSON.stringify(message) + '\n'
    this.process.stdin?.write(payload)
  }

  async sendCommand(message: any): Promise<any> {
    if (!this.process) {
      throw new Error('Backend process not available')
    }

    try {
      const command = JSON.stringify(message) + '\n'
      this.process.stdin?.write(command)
      return { success: true }
    } catch (error) {
      console.error('Command failed:', error)
      throw error
    }
  }

  stop(): void {
    this.cleanup()
  }

  private async performFrontendHandshake(pingId?: string): Promise<void> {
    if (this.handshakeInProgress) {
      return
    }

    this.handshakeInProgress = true

    try {
      await this.initializeZeroMQConnections()

      const readyPayload = pingId
        ? { type: 'frontend_ready', ping_id: pingId }
        : { type: 'frontend_ready' }

      await this.sendStartupCommand(readyPayload)

      if (pingId) {
        await this.sendStartupCommand({
          type: 'frontend_ready_response',
          ping_id: pingId,
          success: true
        })
      }
    } catch (error) {
      console.error('Frontend handshake failed:', error)
      throw error
    } finally {
      this.handshakeInProgress = false
    }
  }
}

const backendManager = new MultiChannelIPCManager()

const preload = path.join(__dirname, '../preload/preload.js')
const url = process.env.VITE_DEV_SERVER_URL || 'http://localhost:5173'
const indexHtml = path.join(process.env.DIST, 'index.html')

function createPresentationWindow() {
  // Find secondary display
  const displays = screen.getAllDisplays()
  const externalDisplay = displays.find((display) => {
    return display.bounds.x !== 0 || display.bounds.y !== 0
  })

  if (!externalDisplay) {
    console.log('No secondary display found - presentation window will not be created')
    return
  }

  console.log(`Creating presentation window on secondary display: ${externalDisplay.bounds.width}x${externalDisplay.bounds.height}`)

  // Create fullscreen window on secondary display
  presentationWindow = new BrowserWindow({
    x: externalDisplay.bounds.x,
    y: externalDisplay.bounds.y,
    width: externalDisplay.bounds.width,
    height: externalDisplay.bounds.height,
    fullscreen: true,
    frame: false,  // No window frame for presentation
    title: 'ISI Stimulus Presentation',
    backgroundColor: '#000000',  // Black background
    webPreferences: {
      preload,
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true,
    },
  })

  // Load the dedicated presentation HTML that renders only StimulusPresentationViewport
  const presentationHtml = path.join(process.env.DIST, 'presentation.html')
  presentationWindow.loadFile(presentationHtml)

  // Close presentation window when main window closes
  mainWindow?.on('closed', () => {
    if (presentationWindow && !presentationWindow.isDestroyed()) {
      presentationWindow.close()
    }
  })

  presentationWindow.on('closed', () => {
    presentationWindow = null
  })

  console.log('Presentation window created successfully')
}

async function createWindow() {
  // Get the primary display's work area (screen minus taskbars/docks)
  const primaryDisplay = screen.getPrimaryDisplay()
  const { width: screenWidth, height: screenHeight } = primaryDisplay.workAreaSize

  // Calculate window dimensions as a percentage of screen size
  // Use 85% of screen width and 90% of screen height for optimal fit
  const windowWidth = Math.floor(screenWidth * 0.85)
  const windowHeight = Math.floor(screenHeight * 0.90)

  // Set reasonable minimum dimensions to ensure usability
  const minWidth = Math.min(1200, screenWidth * 0.6)
  const minHeight = Math.min(800, screenHeight * 0.6)

  mainWindow = new BrowserWindow({
    title: 'ISI Control System',
    width: windowWidth,
    height: windowHeight,
    minWidth: Math.floor(minWidth),
    minHeight: Math.floor(minHeight),
    icon: process.env.VITE_PUBLIC ? path.join(process.env.VITE_PUBLIC, 'electron.png') : undefined,
    webPreferences: {
      preload,
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true,
    },
  })

  // Check if we're in development mode by trying to detect Vite dev server
  const isDevelopment = process.env.NODE_ENV !== 'production' || process.env.VITE_DEV_SERVER_URL

  // Always load from built files for pure IPC communication
  mainWindow.loadFile(indexHtml)

  if (isDevelopment) {
    // Open devtools in development
    mainWindow.webContents.openDevTools()
  }

  // Handle renderer reload/refresh events
  mainWindow.webContents.on('did-start-loading', () => {
    // Only cleanup on refresh, not initial load
    if (!isInitialLoad) {
      backendManager.cleanup()
    }
  })

  // Test actively push message to the Electron-Renderer
  mainWindow.webContents.on('did-finish-load', async () => {
    mainWindow?.webContents.send('main-process-message', `Renderer loaded at ${new Date().toLocaleString()}`)

    // Only restart backend on refresh, not initial load
    if (!isInitialLoad) {
      try {
        await backendManager.start()
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error)
        mainWindow?.webContents.send('backend-error', message)
      }
    }

    // Mark that initial load is complete
    isInitialLoad = false

    // Create presentation window on secondary display (if available)
    createPresentationWindow()
  })

  // Handle window opening - allow internal presentation windows, block external URLs
  mainWindow.webContents.setWindowOpenHandler(({ url, frameName }) => {
    // Window open request received

    // Allow our internal presentation windows (they use empty URL and specific frameName)
    if (!url || url === '' || frameName === 'stimulusPresentation') {
      // Allowing presentation window
      return {
        action: 'allow',
        overrideBrowserWindowOptions: {
          webPreferences: {
            preload,
            nodeIntegration: false,
            contextIsolation: true,
            webSecurity: true,
          }
        }
      }
    }

    // Open external HTTPS links in the default browser
    if (url.startsWith('https:') || url.startsWith('http:')) {
      // Opening external URL in browser
      shell.openExternal(url)
    }

    // Deny all other window opening attempts
    // Denying window open request
    return { action: 'deny' }
  })

  // Start Python backend after window is ready
  try {
    await backendManager.start()
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    mainWindow.webContents.send('backend-error', message)
  }
}

// IPC Handlers
ipcMain.handle('send-to-python', async (_event, message) => {
  return await backendManager.sendCommand(message)
})

ipcMain.handle('send-startup-command', async (_event, message) => {
  await backendManager.sendStartupCommand(message)
  return { success: true }
})

ipcMain.handle('get-system-status', async () => {
  return await backendManager.sendCommand({ type: 'get_system_status' })
})

ipcMain.handle('emergency-stop', async () => {
  return await backendManager.sendCommand({ type: 'emergency_stop' })
})

ipcMain.handle('initialize-zeromq', async () => {
  // Initialize ZeroMQ connections when frontend is ready
  await backendManager.initializeZeroMQConnections()
})

// App event handlers
app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  mainWindow = null
  backendManager.stop()
  if (process.platform !== 'darwin') app.quit()
})

app.on('second-instance', () => {
  if (mainWindow) {
    // Focus on the main window if the user tried to open another
    if (mainWindow.isMinimized()) mainWindow.restore()
    mainWindow.focus()
  }
})

app.on('activate', () => {
  const allWindows = BrowserWindow.getAllWindows()
  if (allWindows.length) {
    allWindows[0].focus()
  } else {
    createWindow()
  }
})

// Handle app termination
app.on('before-quit', () => {
  backendManager.stop()
})

// New window example arg: new windows url
ipcMain.handle('open-win', (_, arg) => {
  const childWindow = new BrowserWindow({
    webPreferences: {
      preload,
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  const isDevelopment = process.env.NODE_ENV !== 'production' || process.env.VITE_DEV_SERVER_URL

  if (isDevelopment) {
    childWindow.loadURL(`${url}#${arg}`)
  } else {
    childWindow.loadFile(indexHtml, { hash: arg })
  }
})