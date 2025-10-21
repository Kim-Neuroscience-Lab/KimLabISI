import { app, BrowserWindow, ipcMain, screen, shell } from 'electron'
import * as path from 'node:path'
import { spawn, execSync, spawnSync } from 'node:child_process'
import type { ChildProcess, SpawnOptions } from 'node:child_process'
import * as zmq from 'zeromq'
import * as fs from 'node:fs'
import * as os from 'node:os'
import type {
  ControlMessage,
  SyncMessage,
  StartupCommand,
  ISIMessage,
} from '../types/ipc-messages'
import type { HealthMessage, SharedMemoryFrameData, SharedMemoryFrameMetadata } from '../types/electron'
import { mainLogger } from '../utils/logger'
import { IPC_CONFIG, UI_CONFIG, PATHS, ELECTRON_CONFIG } from '../config/constants'

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
let secondaryDisplayBounds: Electron.Rectangle | null = null
let isInitialLoad = true

// Shared Memory Frame Reader for high-performance streaming
class SharedMemoryFrameReader {
  private zmqSocket: zmq.Subscriber | null = null
  private isRunning = false
  private ipcChannel: string // IPC channel to send frames to renderer

  constructor(ipcChannel: string = 'shared-memory-frame') {
    this.ipcChannel = ipcChannel
  }

  async initialize(zmqPort: number = IPC_CONFIG.SHARED_MEMORY_PORT): Promise<void> {
    try {
      // Initialize ZeroMQ subscriber for frame metadata
      this.zmqSocket = new zmq.Subscriber()
      this.zmqSocket.connect(`tcp://localhost:${zmqPort}`)
      this.zmqSocket.subscribe() // Subscribe to all messages

      this.isRunning = true
      mainLogger.info(`SharedMemoryFrameReader initialized on port ${zmqPort}, channel: ${this.ipcChannel}`)

      // Start listening for frame metadata
      this.startMetadataListener()
    } catch (error) {
      mainLogger.error('Failed to initialize SharedMemoryFrameReader:', error)
      throw error
    }
  }

  private async startMetadataListener(): Promise<void> {
    mainLogger.debug('SharedMemoryFrameReader: Starting metadata listener on ZeroMQ...')
    try {
      for await (const [msg] of this.zmqSocket!) {
        if (!this.isRunning) break

        try {
          const metadata = JSON.parse(msg.toString())
          await this.handleFrameMetadata(metadata)
        } catch (error) {
          mainLogger.error('Error processing frame metadata:', error)
        }
      }
    } catch (error) {
      mainLogger.error('Metadata listener error:', error)
    }
  }

  private async handleFrameMetadata(metadata: SharedMemoryFrameMetadata): Promise<void> {
    try {
      // Detect test message for ZeroMQ synchronization handshake
      // This proves the subscriber is fully connected and ready
      if ('camera_name' in metadata && metadata.camera_name === 'TEST') {
        mainLogger.info('✅ Test message received - ZeroMQ camera subscriber confirmed active')

        // Send confirmation to backend so it can start real camera acquisition
        await backendManager.sendStartupCommand({ type: 'camera_subscriber_confirmed' })
        mainLogger.info('Sent camera_subscriber_confirmed to backend')

        // Don't forward test message to renderer - it's only for synchronization
        return
      }

      // Send ONLY metadata to renderer - frame data stays in shared memory
      const frameMetadata = {
        frame_id: metadata.frame_id,
        timestamp_us: metadata.timestamp_us,
        frame_index: metadata.frame_index,
        direction: metadata.direction,
        angle_degrees: metadata.angle_degrees,
        width_px: metadata.width_px,
        height_px: metadata.height_px,
        total_frames: metadata.total_frames,
        start_angle: metadata.start_angle,
        end_angle: metadata.end_angle,
        offset_bytes: metadata.offset_bytes,
        data_size_bytes: metadata.data_size_bytes,
        shm_path: metadata.shm_path
      }

      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send(this.ipcChannel, frameMetadata)
      }

      if (presentationWindow && !presentationWindow.isDestroyed()) {
        presentationWindow.webContents.send(this.ipcChannel, frameMetadata)
      }
    } catch (error) {
      mainLogger.error('Error handling frame metadata:', error)
    }
  }

  cleanup(): void {
    this.isRunning = false

    if (this.zmqSocket) {
      this.zmqSocket.close()
      this.zmqSocket = null
    }

    mainLogger.info('SharedMemoryFrameReader cleaned up')
  }
}

// Global shared memory reader instances
let sharedMemoryReader: SharedMemoryFrameReader | null = null  // For stimulus frames
let cameraFrameReader: SharedMemoryFrameReader | null = null  // For camera frames
let analysisFrameReader: SharedMemoryFrameReader | null = null  // For analysis frames

function resolveBackendRoot(): string {
  const appPath = app?.getAppPath?.() ?? process.cwd()

  const candidates = [
    path.resolve(__dirname, '../../backend'),
    path.resolve(__dirname, '../backend'),
    path.resolve(appPath, '../backend'),
    path.resolve(appPath, '../../backend'),
    path.resolve(process.cwd(), '../backend'),
    path.resolve(process.cwd(), 'apps/backend'),
  ]

  for (const candidate of candidates) {
    const manifest = path.join(candidate, 'pyproject.toml')
    if (fs.existsSync(manifest)) {
      return candidate
    }
  }

  throw new Error(
    `Unable to locate backend root; checked: ${candidates.map((candidate) => path.normalize(candidate)).join(', ')}`,
  )
}

function resolvePoetryExecutable(): { command: string; args: string[] } {
  const explicit = process.env.ISI_POETRY_PATH?.trim()
  if (explicit) {
    const parts = explicit.split(/\s+/)
    return { command: parts[0], args: parts.slice(1) }
  }

  const hardcoded = '/Users/Adam/.local/pipx/venvs/poetry/bin/poetry'
  if (fs.existsSync(hardcoded)) {
    return { command: hardcoded, args: [] }
  }

  const pythonCandidates = process.platform === 'win32'
    ? ['py', 'python', 'python3']
    : ['python3', 'python']

  const shellLookup = spawnSync(process.platform === 'win32' ? 'where' : 'which', ['poetry'], {
    encoding: 'utf-8',
  })
  if (shellLookup.status === 0 && shellLookup.stdout) {
    const resolved = shellLookup.stdout.split(/\r?\n/).find(line => line.trim().length > 0)
    if (resolved) {
      return { command: resolved.trim(), args: [] }
    }
  }

  const homeDir = os.homedir()
  const platformCandidates: string[] = []
  if (process.platform === 'win32') {
    const appData = process.env.APPDATA
    if (appData) {
      platformCandidates.push(path.join(appData, 'Python', 'Scripts', 'poetry.exe'))
    }
    platformCandidates.push(path.join(homeDir, 'AppData', 'Roaming', 'Python', 'Scripts', 'poetry.exe'))
  } else {
    platformCandidates.push(path.join(homeDir, '.local', 'bin', 'poetry'))
    platformCandidates.push('/usr/local/bin/poetry')
    platformCandidates.push('/usr/bin/poetry')
  }

  for (const candidate of platformCandidates) {
    if (fs.existsSync(candidate)) {
      return { command: candidate, args: [] }
    }
  }

  for (const cmd of pythonCandidates) {
    const check = spawnSync(cmd, ['-m', 'poetry', '--version'], { encoding: 'utf-8' })
    if (check.status === 0) {
      return { command: cmd, args: ['-m', 'poetry'] }
    }
  }

  throw new Error('Unable to locate Poetry executable. Set ISI_POETRY_PATH or add poetry to PATH.')
}

// Multi-Channel IPC Backend Management
class MultiChannelIPCManager {
  private process: ChildProcess | null = null
  private isReady = false
  private healthSocket: zmq.Subscriber | null = null
  private syncSocket: zmq.Subscriber | null = null
  private healthCheckInterval: NodeJS.Timeout | null = null
  private startupTimeout: NodeJS.Timeout | null = null
  private readonly STARTUP_TIMEOUT = IPC_CONFIG.STARTUP_TIMEOUT
  private readonly HEALTH_CHECK_INTERVAL = IPC_CONFIG.HEALTH_CHECK_INTERVAL
  private readonly HEALTH_PORT = IPC_CONFIG.HEALTH_PORT
  private readonly SYNC_PORT = IPC_CONFIG.SYNC_PORT
  private zeroMQInitialized = false
  private handshakeInProgress = false
  private backendRootOverride: string | null = null
  private startupResolve: ((value: void | PromiseLike<void>) => void) | null = null
  private pendingRequests: Map<string, { resolve: (value: any) => void; reject: (error: any) => void; timeout: NodeJS.Timeout | null }> = new Map()
  private nextMessageId = 1

  overrideBackendRoot(rootDir: string): void {
    this.backendRootOverride = rootDir
  }

  hasBackendRoot(): boolean {
    return Boolean(this.backendRootOverride)
  }

  async start(): Promise<void> {
    if (!this.process) {
      const rootDir = this.backendRootOverride ?? resolveBackendRoot()
      this.overrideBackendRoot(rootDir)
    }
    // Clean up any existing processes first
    await this.cleanup()

    return new Promise((resolve, reject) => {
      // Store resolve callback for when backend reaches ready state
      this.startupResolve = resolve

      // Set up timeout to detect if backend never reaches ready state
      this.startupTimeout = setTimeout(() => {
        if (!this.isReady) {
          const error = 'Python backend failed to reach ready state within 15 seconds'
          mainLogger.error(error)
          if (mainWindow) {
            mainWindow.webContents.send('backend-error', error)
          }
          this.startupResolve = null
          reject(new Error(error))
        }
      }, this.STARTUP_TIMEOUT)

      try {
        const rootDir = this.backendRootOverride ?? resolveBackendRoot()

        mainLogger.info('Starting Python backend with multi-channel IPC system')

        this.killExistingPythonProcesses()

        const { command: poetryCommand, args: poetryCommandArgs } = resolvePoetryExecutable()

        // BACKEND REFACTOR: Dual-boot support for old vs new backend
        // DEFAULT: New refactored backend (src.main) - Phase 1-8 complete
        // USE_OLD_BACKEND=1 -> Switch back to legacy backend (isi_control.main) if needed
        const backendModule = process.env.USE_OLD_BACKEND === '1' ? 'isi_control.main' : 'src.main'
        mainLogger.info(`🚀 Backend module: ${backendModule} ${process.env.USE_OLD_BACKEND === '1' ? '(LEGACY - FALLBACK)' : '(REFACTORED)'}`)

        const poetryArgs = [...poetryCommandArgs, 'run', 'python', '-u', '-m', backendModule]
        const spawnOptions: SpawnOptions = {
          stdio: ['pipe', 'pipe', 'pipe'],
          cwd: rootDir,
          env: {
            ...process.env,
            PYTHONPATH: path.join(rootDir, 'src')
          },
        }

        mainLogger.info(`Launching Poetry command: ${poetryCommand} ${poetryArgs.join(' ')}`)
        this.process = spawn(poetryCommand, poetryArgs, spawnOptions)

        this.process.stdout?.on('data', (data: Buffer) => {
          const output = data.toString().trim()
          if (!output) return

          const lines = output.split('\n').filter(line => line.trim())

          for (const line of lines) {
            try {
              const jsonMessage = JSON.parse(line.trim())

              this.handleBackendMessage(jsonMessage).catch((error) => {
                mainLogger.error('Error handling backend message:', error)
              })
            } catch (error) {
              mainLogger.debug('Backend output (non-JSON):', line)
            }
          }
        })

        this.process.stderr?.on('data', (data: Buffer) => {
          const errorMsg = data.toString()
          mainLogger.error('Python backend stderr:', errorMsg)
          if (mainWindow) {
            mainWindow.webContents.send('backend-error', `Backend error: ${errorMsg}`)
          }
        })

        this.process.on('error', (error) => {
          mainLogger.error('Python process error:', error)
          reject(error)
          this.cleanup()
        })

        this.process.on('exit', (_code, _signal) => {
          mainLogger.info('Backend process exited')
          this.isReady = false
          this.cleanup()
          if (this.startupResolve) {
            reject(new Error('Python backend exited before startup completed'))
            this.startupResolve = null
          }
          if (mainWindow) {
            mainWindow.webContents.send('backend-error', 'Backend process exited')
          }
        })

      } catch (error) {
        mainLogger.error('Error starting Python backend:', error)
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

      mainLogger.info('ZeroMQ PUB/SUB channels initialized successfully')
      mainLogger.info('CONTROL channel uses stdin/stdout for startup coordination')

      // Start listening for health and sync messages
      this.startHealthListener()
      this.startSyncListener()

      this.zeroMQInitialized = true

    } catch (error) {
      mainLogger.error('Failed to initialize ZeroMQ connections:', error)
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
          mainLogger.error('Error processing sync message:', error)
        }
      }
    } catch (error) {
      mainLogger.error('Sync listener error:', error)
    }
  }

  private handleSyncMessage(message: SyncMessage): void {
    // Special logging for analysis layer messages (important events only)
    if (message.type === 'analysis_layer_ready') {
      mainLogger.info(`🎯 ANALYSIS LAYER READY: ${(message as any).layer_name}`)
    } else if (message.type === 'analysis_started') {
      mainLogger.info('🚀 ANALYSIS STARTED')
    } else if (message.type === 'analysis_complete') {
      mainLogger.info('✅ ANALYSIS COMPLETE')
    } else if (message.type === 'system_health') {
      // Silently forward system_health messages - don't log (sent every second)
      // Logging is already handled in handleHealthUpdate()
    } else if (message.type === 'camera_histogram_update') {
      // Silently forward histogram updates - don't log (sent every frame @ 30-60fps)
    } else if (message.type === 'correlation_update') {
      // Silently forward correlation updates - don't log (sent every frame during acquisition)
    } else if (message.type === 'acquisition_progress') {
      // Silently forward acquisition progress - don't log (sent every frame during recording)
    } else {
      // Log unexpected message types for debugging
      mainLogger.debug('Received SYNC channel message:', message)
    }

    // Check if backend has reached ready state and initialize shared memory reader
    if (message.type === 'system_state' && message.state === 'ready' && !this.isReady) {
      mainLogger.info('Backend ready state detected via SYNC channel')
      this.onBackendFullyReady()
    }

    // Forward sync coordination messages to renderer via dedicated channel
    if (mainWindow) {
      mainWindow.webContents.send('sync-message', message)
    }
  }

  private onBackendFullyReady(): void {
    if (this.isReady) {
      return // Already initialized
    }

    mainLogger.info('Backend multi-channel IPC system is ready')
    this.isReady = true

    // Note: Shared memory readers already initialized earlier in zeromq_ready handler
    // This ensures subscribers are ready BEFORE backend starts publishing frames

    // Clear startup timeout if still active
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

    // Resolve the startup Promise
    if (this.startupResolve) {
      this.startupResolve()
      this.startupResolve = null
    }
  }

  private async initializeSharedMemoryReader(): Promise<void> {
    const maxRetries = 3
    const delays = [1000, 2000, 4000] // Exponential backoff: 1s, 2s, 4s

    const initializeWithRetry = async (
      name: string,
      channel: string,
      port: number,
      retryCount = 0
    ): Promise<SharedMemoryFrameReader | null> => {
      try {
        const reader = new SharedMemoryFrameReader(channel)
        await reader.initialize(port)
        mainLogger.info(`${name} initialized successfully on port ${port}`)
        return reader
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : String(error)
        mainLogger.error(`Failed to initialize ${name} (attempt ${retryCount + 1}/${maxRetries}):`, errorMsg)

        if (retryCount < maxRetries - 1) {
          const delay = delays[retryCount]
          mainLogger.info(`Retrying ${name} in ${delay}ms...`)
          await new Promise(resolve => setTimeout(resolve, delay))
          return initializeWithRetry(name, channel, port, retryCount + 1)
        } else {
          // All retries exhausted - send error to frontend
          const userMessage = `Failed to initialize ${name} after ${maxRetries} attempts. Frame streaming may be unavailable.`
          mainLogger.error(userMessage)
          if (mainWindow) {
            mainWindow.webContents.send('shared-memory-error', {
              component: name,
              error: errorMsg,
              message: userMessage
            })
          }
          return null
        }
      }
    }

    // Initialize all readers with retry logic (graceful degradation)
    // Continue even if some readers fail - show controls but warn user
    sharedMemoryReader = await initializeWithRetry(
      'Stimulus frame reader',
      'shared-memory-frame',
      IPC_CONFIG.SHARED_MEMORY_PORT
    )

    cameraFrameReader = await initializeWithRetry(
      'Camera frame reader',
      'camera-frame',
      IPC_CONFIG.CAMERA_METADATA_PORT
    )

    analysisFrameReader = await initializeWithRetry(
      'Analysis frame reader',
      'analysis-frame',
      IPC_CONFIG.ANALYSIS_METADATA_PORT
    )

    // Report overall status
    const failedReaders = [
      !sharedMemoryReader && 'stimulus',
      !cameraFrameReader && 'camera',
      !analysisFrameReader && 'analysis'
    ].filter(Boolean)

    if (failedReaders.length === 0) {
      mainLogger.info('All shared memory readers initialized successfully')
    } else {
      const warningMsg = `Shared memory initialization incomplete: ${failedReaders.join(', ')} streaming unavailable. System will continue with reduced functionality.`
      mainLogger.warn(warningMsg)
      if (mainWindow) {
        mainWindow.webContents.send('system-warning', {
          type: 'shared_memory_partial_failure',
          message: warningMsg,
          failedComponents: failedReaders
        })
      }
    }
  }

  private async handleBackendMessage(message: ControlMessage): Promise<void> {
    mainLogger.debug('Received CONTROL channel message via stdout:', message)

    // Check if this is a response to a pending request
    const messageId = 'messageId' in message ? (message as any).messageId : undefined
    if (messageId && this.pendingRequests.has(messageId)) {
      const pending = this.pendingRequests.get(messageId)!
      this.pendingRequests.delete(messageId)
      if (pending.timeout !== null) {
        clearTimeout(pending.timeout)
      }
      pending.resolve(message)
      return
    }

    // Log system_fully_ready specifically for debugging
    if (message.type === 'system_fully_ready') {
      mainLogger.debug('*** SYSTEM_FULLY_READY MESSAGE RECEIVED ***', message)
    }

    // Forward control messages (startup status, parameter updates, etc.) to renderer
    if (mainWindow) {
      mainWindow.webContents.send('control-message', message)
      mainLogger.debug('Forwarded control-message to renderer:', message.type)
    } else {
      mainLogger.warn('Cannot forward message - mainWindow not available')
    }

    // Backend explicitly tells frontend to connect to ZeroMQ
    if (message.type === 'zeromq_ready') {
      mainLogger.info('Backend ZeroMQ ready - initializing ALL subscriptions...')
      mainLogger.info(`Health port: ${message.health_port}, Sync port: ${message.sync_port}`)

      // Initialize health and sync channels
      await this.initializeZeroMQConnections()

      // CRITICAL FIX: Initialize shared memory frame readers BEFORE frontend_ready signal
      // This prevents ZeroMQ "slow joiner" problem where backend starts publishing
      // camera frames before frontend subscribers are ready
      await this.initializeSharedMemoryReader()

      mainLogger.info('All ZeroMQ subscriptions established (including frame readers) - ready for frames')

      // Send explicit ready signal to backend that frame readers are subscribed
      await this.sendStartupCommand({ type: 'shared_memory_readers_ready' })
      mainLogger.info('Sent shared_memory_readers_ready signal to backend')
    }
    // Note: Frontend handshake will be triggered by waiting_frontend state (handled in SystemContext.tsx)

    if (
      message.type === 'startup_coordination' &&
      'command' in message &&
      message.command === 'check_frontend_ready'
    ) {
      const pingId = 'ping_id' in message && typeof message.ping_id === 'string' ? message.ping_id : undefined
      await this.performFrontendHandshake(pingId)
    }
  }


  private startHealthCheck(): void {
    // Health monitoring now uses PUB/SUB pattern - we listen for health updates
    // rather than actively requesting them
    // Note: Health listener is already started during initialization, no need to start it again
    mainLogger.info('Health monitoring started - listening for health updates from backend')
  }

  private async startHealthListener(): Promise<void> {
    if (!this.healthSocket) return

    try {
      for await (const [msg] of this.healthSocket) {
        try {
          const healthData = JSON.parse(msg.toString())
          this.handleHealthUpdate(healthData)
        } catch (error) {
          mainLogger.error('Error processing health update:', error)
        }
      }
    } catch (error) {
      mainLogger.error('Health listener error:', error)
    }
  }

  private handleHealthUpdate(healthData: HealthMessage): void {
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
        mainLogger.info('Terminating existing ISI backend processes')
        execSync('pkill -f "isi_control.main"')
      }
    } catch (error) {
      const err = error as NodeJS.ErrnoException & { status?: number }
      if (err.status !== 1) {
        mainLogger.error('Error during process cleanup:', err.message)
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

    // Reject all pending requests
    for (const pending of this.pendingRequests.values()) {
      if (pending.timeout !== null) {
        clearTimeout(pending.timeout)
      }
      pending.reject(new Error('Backend process terminated'))
    }
    this.pendingRequests.clear()

    // Cleanup shared memory readers
    if (sharedMemoryReader) {
      sharedMemoryReader.cleanup()
      sharedMemoryReader = null
    }
    if (cameraFrameReader) {
      cameraFrameReader.cleanup()
      cameraFrameReader = null
    }
    if (analysisFrameReader) {
      analysisFrameReader.cleanup()
      analysisFrameReader = null
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

        // Wait for graceful shutdown with timeout
        await Promise.race([
          new Promise<void>(resolve => {
            this.process?.once('exit', () => resolve())
          }),
          new Promise<void>(resolve => setTimeout(resolve, IPC_CONFIG.PROCESS_KILL_TIMEOUT))
        ])

        // Force kill if still running
        if (this.process && !this.process.killed) {
          this.process.kill('SIGKILL')
        }
      } catch (error) {
        mainLogger.error('Error stopping Python process:', error)
      }

      this.process = null
    }

    this.isReady = false
    this.zeroMQInitialized = false
  }

  async sendStartupCommand(message: StartupCommand): Promise<void> {
    if (!this.process) {
      throw new Error('Backend process not available')
    }
    const payload = JSON.stringify(message) + '\n'
    this.process.stdin?.write(payload)
  }

  async sendCommand(message: ISIMessage): Promise<any> {
    if (!this.process) {
      throw new Error('Backend process not available')
    }

    const process = this.process // Capture for use in Promise
    return new Promise((resolve, reject) => {
      try {
        // Generate unique message ID
        const messageId = `msg_${this.nextMessageId++}`

        // NO TIMEOUTS: Backend responds when ready
        // Commands take variable time based on hardware, data size, and system load
        // Timeouts cause false failures and mask real issues
        // If backend is truly hung, user can restart application
        const timeout: NodeJS.Timeout | null = null

        // Store the promise handlers
        this.pendingRequests.set(messageId, { resolve, reject, timeout })

        // Send command with message ID
        const commandWithId = { ...message, messageId }
        const command = JSON.stringify(commandWithId) + '\n'
        if (!process.stdin) {
          if (timeout !== null) {
            clearTimeout(timeout)
          }
          this.pendingRequests.delete(messageId)
          reject(new Error('Backend process stdin not available'))
          return
        }
        process.stdin.write(command)
      } catch (error) {
        mainLogger.error('Command failed:', error)
        reject(error)
      }
    })
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

      // Send simple frontend_ready message
      const readyPayload = pingId
        ? { type: 'frontend_ready', ping_id: pingId }
        : { type: 'frontend_ready' }

      await this.sendStartupCommand(readyPayload)

      mainLogger.info('Frontend handshake complete - ZeroMQ connections established')
    } catch (error) {
      mainLogger.error('Frontend handshake failed:', error)
      throw error
    } finally {
      this.handshakeInProgress = false
    }
  }
}

const backendManager = new MultiChannelIPCManager()

const preload = path.join(__dirname, '../preload/preload.js')
const devUrl = process.env.ELECTRON_RENDERER_URL || process.env.VITE_DEV_SERVER_URL
const indexHtml = path.join(process.env.DIST, 'index.html')

async function createWindow() {
  const primaryDisplay = screen.getPrimaryDisplay()
  const { width: screenWidth, height: screenHeight } = primaryDisplay.workAreaSize

  const allDisplays = screen.getAllDisplays()
  if (!secondaryDisplayBounds) {
    secondaryDisplayBounds = allDisplays.find((display) => display.id !== primaryDisplay.id)?.bounds ?? null
    mainLogger.info('Detected displays:', allDisplays.map((display) => ({
      id: display.id,
      bounds: display.bounds,
      workArea: display.workArea,
      scaleFactor: display.scaleFactor,
      rotation: display.rotation,
      isPrimary: display.id === primaryDisplay.id,
    })))
  }

  // Calculate window dimensions as a percentage of screen size
  const windowWidth = Math.floor(screenWidth * UI_CONFIG.WINDOW_WIDTH_PERCENT)
  const windowHeight = Math.floor(screenHeight * UI_CONFIG.WINDOW_HEIGHT_PERCENT)

  // Set reasonable minimum dimensions to ensure usability
  const minWidth = Math.min(UI_CONFIG.MIN_WIDTH_PX, screenWidth * UI_CONFIG.MIN_WIDTH_PERCENT)
  const minHeight = Math.min(UI_CONFIG.MIN_HEIGHT_PX, screenHeight * UI_CONFIG.MIN_HEIGHT_PERCENT)

  mainWindow = new BrowserWindow({
    title: 'ISI Control System',
    width: windowWidth,
    height: windowHeight,
    minWidth: Math.floor(minWidth),
    minHeight: Math.floor(minHeight),
    icon: process.env.VITE_PUBLIC ? path.join(process.env.VITE_PUBLIC, 'electron.png') : undefined,
    webPreferences: {
      preload,
      nodeIntegration: ELECTRON_CONFIG.NODE_INTEGRATION,
      contextIsolation: ELECTRON_CONFIG.CONTEXT_ISOLATION,
      webSecurity: ELECTRON_CONFIG.WEB_SECURITY,
    },
  })

  // Check if we're in development mode by trying to detect Vite dev server
  const isDevelopment = process.env.NODE_ENV !== 'production' || process.env.VITE_DEV_SERVER_URL

  // Safety timeout: If did-finish-load doesn't fire within 10 seconds, something is wrong
  const loadTimeout = setTimeout(() => {
    if (isInitialLoad) {
      mainLogger.error('CRITICAL: did-finish-load event never fired within 10 seconds!')
      mainLogger.error('This indicates the renderer failed to load or main process is blocked')
      // Try to create presentation window anyway
      mainLogger.info('Attempting emergency presentation window creation...')
      createPresentationWindow()
    }
  }, 10000)

  // IMPORTANT: Register event handler BEFORE loading URL to avoid race condition
  mainWindow.webContents.on('did-finish-load', async () => {
    clearTimeout(loadTimeout)  // Clear the safety timeout
    mainLogger.info('=== Main window did-finish-load event triggered ===')
    mainWindow?.webContents.send('main-process-message', `Renderer loaded at ${new Date().toLocaleString()}`)

    // Only restart backend on refresh, not initial load
    // Note: start() internally calls cleanup() first, so no need to cleanup separately
    if (!isInitialLoad) {
      mainLogger.info('Reloading detected - restarting backend...')
      // Non-blocking restart
      backendManager.start().catch(error => {
        const message = error instanceof Error ? error.message : String(error)
        mainLogger.error('Backend restart failed:', message)
        mainWindow?.webContents.send('backend-error', message)
      })
    }

    // Mark that initial load is complete
    isInitialLoad = false

    // Create presentation window on secondary display (if available)
    mainLogger.info('=== Attempting to create presentation window ===')
    mainLogger.info(`Secondary display bounds: ${secondaryDisplayBounds ? JSON.stringify(secondaryDisplayBounds) : 'null'}`)
    createPresentationWindow()
  })

  // NOW load the URL - event handler is already registered
  if (devUrl) {
    await mainWindow.loadURL(devUrl)

    mainWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
      if (details.responseHeaders) {
        const cspKey = Object.keys(details.responseHeaders).find((key) => key.toLowerCase() === 'content-security-policy')
        if (cspKey) {
          delete details.responseHeaders[cspKey]
        }
        details.responseHeaders['Content-Security-Policy'] = ["default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob:;"]
      }
      callback({ cancel: false, responseHeaders: details.responseHeaders })
    })
  } else {
    await mainWindow.loadFile(indexHtml)
  }

  if (isDevelopment && ELECTRON_CONFIG.OPEN_DEV_TOOLS_IN_DEVELOPMENT) {
    // Open devtools in development
    mainWindow.webContents.openDevTools()
  }

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
            nodeIntegration: ELECTRON_CONFIG.NODE_INTEGRATION,
            contextIsolation: ELECTRON_CONFIG.CONTEXT_ISOLATION,
            webSecurity: ELECTRON_CONFIG.WEB_SECURITY,
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

  // Resolve backend root once per application instance
  let backendRoot: string | null = null
  try {
    backendRoot = resolveBackendRoot()
    backendManager.overrideBackendRoot(backendRoot)
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    mainLogger.error('Failed to resolve backend root:', message)
    mainWindow.webContents.send('backend-error', message)
  }

  // Start Python backend asynchronously (non-blocking)
  // CRITICAL: Do NOT await here - it would block event loop and prevent did-finish-load from firing
  backendManager.start().catch(error => {
    const message = error instanceof Error ? error.message : String(error)
    mainLogger.error('Backend startup failed:', message)
    if (mainWindow) {
      mainWindow.webContents.send('backend-error', message)
    }
  })
  mainLogger.info('Backend startup initiated (non-blocking)')
}

function createPresentationWindow() {
  mainLogger.info('=== createPresentationWindow() called ===')

  const bounds = secondaryDisplayBounds
  if (!bounds) {
    mainLogger.warn('❌ No secondary display found - presentation window will not be created')
    mainLogger.warn('This means no presentation monitor was detected. Check if a second monitor is connected.')
    return
  }

  mainLogger.info(`✅ Secondary display detected with bounds: ${JSON.stringify(bounds)}`)
  mainLogger.info(`Creating presentation window at position (${bounds.x}, ${bounds.y}) with size ${bounds.width}x${bounds.height}`)

  try {
    // Create fullscreen window on secondary display
    presentationWindow = new BrowserWindow({
      x: bounds.x,
      y: bounds.y,
      width: bounds.width,
      height: bounds.height,
      fullscreen: true,
      frame: false,  // No window frame for presentation
      title: 'ISI Stimulus Presentation',
      backgroundColor: '#000000',  // Black background
      webPreferences: {
        preload,
        nodeIntegration: ELECTRON_CONFIG.NODE_INTEGRATION,
        contextIsolation: ELECTRON_CONFIG.CONTEXT_ISOLATION,
        webSecurity: ELECTRON_CONFIG.WEB_SECURITY,
      },
    })

    mainLogger.info('✅ Presentation window BrowserWindow created')

    // Load the dedicated presentation HTML that renders only StimulusPresentationViewport
    const presentationEntry = process.env.ELECTRON_RENDERER_URL || process.env.VITE_DEV_SERVER_URL
    const loadingUrl = presentationEntry ? `${presentationEntry}#/presentation` : path.join(process.env.DIST || '', 'presentation.html')

    mainLogger.info(`Loading presentation window content from: ${loadingUrl}`)
    mainLogger.info(`Using ${presentationEntry ? 'dev server URL' : 'production HTML file'}`)

    if (presentationEntry) {
      presentationWindow.loadURL(`${presentationEntry}#/presentation`)
        .then(() => {
          mainLogger.info('✅ Presentation window URL loaded successfully')
        })
        .catch((error) => {
          mainLogger.error('❌ Failed to load presentation window URL:', error)
        })
    } else {
      const presentationHtml = path.join(process.env.DIST || '', 'presentation.html')
      mainLogger.info(`Presentation HTML file path: ${presentationHtml}`)
      mainLogger.info(`File exists: ${fs.existsSync(presentationHtml)}`)

      presentationWindow.loadFile(presentationHtml)
        .then(() => {
          mainLogger.info('✅ Presentation window file loaded successfully')
        })
        .catch((error) => {
          mainLogger.error('❌ Failed to load presentation window file:', error)
        })
    }

    // Add event listeners for debugging
    presentationWindow.webContents.on('did-finish-load', () => {
      mainLogger.info('✅ Presentation window finished loading content')
    })

    presentationWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
      mainLogger.error(`❌ Presentation window failed to load: ${errorCode} - ${errorDescription}`)
    })

    presentationWindow.on('ready-to-show', () => {
      mainLogger.info('✅ Presentation window ready to show')
      presentationWindow?.show()
    })

    // Close presentation window when main window closes
    mainWindow?.on('closed', () => {
      if (presentationWindow && !presentationWindow.isDestroyed()) {
        mainLogger.info('Main window closed - closing presentation window')
        presentationWindow.close()
      }
    })

    presentationWindow.on('closed', () => {
      mainLogger.info('Presentation window closed event triggered')
      presentationWindow = null
    })

    mainLogger.info('✅ Presentation window setup complete')
  } catch (error) {
    mainLogger.error('❌ Error creating presentation window:', error)
    throw error
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

ipcMain.handle('read-shared-memory-frame', async (_event, offset: number, size: number, shmPath: string) => {
  try {
    // Read directly from the specified shared memory file
    if (!fs.existsSync(shmPath)) {
      throw new Error(`Shared memory file does not exist: ${shmPath}`)
    }

    const fd = fs.openSync(shmPath, 'r')
    try {
      const buffer = Buffer.alloc(size)
      const bytesRead = fs.readSync(fd, buffer, 0, size, offset)

      if (bytesRead !== size) {
        throw new Error(`Expected to read ${size} bytes, but read ${bytesRead}`)
      }

      // Return as ArrayBuffer for efficient transfer
      return buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength)
    } finally {
      fs.closeSync(fd)
    }
  } catch (error) {
    mainLogger.error('Failed to read shared memory frame:', error)
    throw error
  }
})

ipcMain.handle('initialize-zeromq', async () => {
  // Initialize ZeroMQ connections when frontend is ready
  if (!backendManager.hasBackendRoot()) {
    const rootDir = resolveBackendRoot()
    backendManager.overrideBackendRoot(rootDir)
  }
  await backendManager.initializeZeroMQConnections()
})

// App event handlers
app.whenReady().then(async () => {
  try {
    const backendRoot = resolveBackendRoot()
    backendManager.overrideBackendRoot(backendRoot)
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    mainLogger.error('Failed to resolve backend root:', message)
    if (mainWindow) {
      mainWindow.webContents.send('backend-error', message)
    }
  }
  await createWindow()
})

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
      nodeIntegration: ELECTRON_CONFIG.NODE_INTEGRATION,
      contextIsolation: ELECTRON_CONFIG.CONTEXT_ISOLATION,
    },
  })

  const isDevelopment = process.env.NODE_ENV !== 'production' || process.env.VITE_DEV_SERVER_URL

  if (isDevelopment && devUrl) {
    childWindow.loadURL(`${devUrl}#${arg}`)
  } else {
    childWindow.loadFile(indexHtml, { hash: arg })
  }
})