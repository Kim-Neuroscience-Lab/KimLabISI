import { app, BrowserWindow, ipcMain, screen, shell } from 'electron'
import * as path from 'node:path'
import { spawn, execSync } from 'node:child_process'
import type { ChildProcess } from 'node:child_process'

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
let isInitialLoad = true

// Python Backend Management
class PythonBackendManager {
  private process: ChildProcess | null = null
  private isReady = false
  private messageQueue: any[] = []
  private healthCheckInterval: NodeJS.Timeout | null = null
  private startupTimeout: NodeJS.Timeout | null = null
  private readonly STARTUP_TIMEOUT = 15000 // 15 seconds
  private readonly HEALTH_CHECK_INTERVAL = 5000 // 5 seconds

  async start(): Promise<void> {
    // Clean up any existing processes first
    await this.cleanup()

    return new Promise((resolve, reject) => {

      try {
        const isDevelopment = process.env.NODE_ENV !== 'production' || process.env.VITE_DEV_SERVER_URL
        const rootDir = isDevelopment
          ? path.join(__dirname, '../..')
          : process.resourcesPath

        // Starting Python backend with ISI Control system

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

        this.process.stdout?.on('data', (data: Buffer) => {
          const messages = data.toString().split('\n').filter(msg => msg.trim())
          // Processing backend stdout messages

          for (const message of messages) {
            if (message.includes('IPC_READY')) {
              // Backend ready signal received
              this.onBackendReady(resolve)
            } else {
              this.handleBackendMessage(message)
            }
          }
        })

        this.process.stderr?.on('data', (data: Buffer) => {
          const errorMsg = data.toString()
          console.error('Python backend stderr:', errorMsg)
          // Send error to renderer so user can see it
          if (mainWindow) {
            mainWindow.webContents.send('backend-error', `Backend error: ${errorMsg}`)
          }
        })

        this.process.on('error', (error) => {
          if (error instanceof Error) {
            console.error('Python process error:', error)
            reject(error)
          } else {
            console.error('Python process error:', String(error))
            reject(new Error(String(error)))
          }
          this.cleanup()
        })

        this.process.on('exit', (_code, _signal) => {
          this.isReady = false
          this.cleanup()

          // Notify renderer of backend failure
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
        if (error instanceof Error) {
          console.error('Error starting Python backend:', error)
          reject(error)
        } else {
          const unknownError = new Error(String(error))
          console.error('Error starting Python backend:', unknownError)
          reject(unknownError)
        }
      }
    })
  }

  private onBackendReady(resolve: () => void): void {
    // Backend initialization completed
    this.isReady = true

    // Clear startup timeout
    if (this.startupTimeout) {
      clearTimeout(this.startupTimeout)
      this.startupTimeout = null
    }

    // Signal to renderer
    if (mainWindow) {
      mainWindow.webContents.send('main-process-message', 'Backend ready')
    }

    // Process queued messages
    this.messageQueue.forEach(msg => this.send(msg))
    this.messageQueue = []

    // Start health monitoring
    this.startHealthCheck()

    resolve()
  }

  private handleBackendMessage(message: string): void {
    // Check if message looks like JSON (starts with '{' or '[')
    const trimmed = message.trim()
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
      try {
        const parsedMessage = JSON.parse(trimmed)
        this.handleMessage(parsedMessage)
      } catch (e) {
        console.error('Failed to parse JSON message from backend:', message, e)
      }
    } else {
      // Regular log message - log it for debugging
      // Backend log message received
    }
  }

  private startHealthCheck(): void {
    this.healthCheckInterval = setInterval(() => {
      if (this.isReady && this.process) {
        // Send ping to check if backend is responsive
        this.send({ type: 'ping' })
      }
    }, this.HEALTH_CHECK_INTERVAL)
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
        // Terminating existing ISI backend processes
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

    if (this.process) {
      try {
        this.process.kill('SIGTERM')

        // Give process time to shut down gracefully
        await new Promise(resolve => setTimeout(resolve, 1000))

        // Force kill if still running
        if (this.process && !this.process.killed) {
          this.process.kill('SIGKILL')
        }
      } catch (error) {
        console.error('Error stopping Python process:', error)
      }

      this.process = null
    }

    this.isReady = false
    this.messageQueue = []
  }

  send(message: any): void {
    if (!this.isReady || !this.process) {
      this.messageQueue.push(message)
      return
    }

    const jsonMessage = JSON.stringify(message) + '\n'
    this.process.stdin?.write(jsonMessage)
  }

  async sendCommand(message: any): Promise<any> {
    // Sending command to backend
    if (!this.isReady || !this.process) {
      // Backend not ready for commands
      throw new Error('Backend not ready')
    }

    return new Promise((resolve, reject) => {
      // Create unique message ID for correlation
      const messageId = `${Date.now()}_${Math.random()}`
      const messageWithId = { ...message, messageId }

      // Set up timeout
      const timeout = setTimeout(() => {
        this.process?.stdout?.off('data', dataHandler)
        reject(new Error('Command timeout'))
      }, 10000)

      // Response handler
      const dataHandler = (data: Buffer) => {
        const messages = data.toString().split('\n').filter(msg => msg.trim())

        for (const msg of messages) {
          if (!msg.startsWith('{')) continue

          try {
            const response = JSON.parse(msg)

            if (response.messageId === messageId) {
              clearTimeout(timeout)
              this.process?.stdout?.off('data', dataHandler)

              // Remove messageId and resolve with clean response
              const { messageId: _, ...cleanResponse } = response
              resolve(cleanResponse)
              return
            }
          } catch (e) {
            // Ignore invalid JSON
          }
        }
      }

      // Attach listener and send command
      this.process.stdout?.on('data', dataHandler)

      const jsonMessage = JSON.stringify(messageWithId) + '\n'
      this.process.stdin?.write(jsonMessage)
    })
  }

  private handleMessage(message: any): void {

    // Forward to renderer process
    if (mainWindow) {
      mainWindow.webContents.send('python-message', message)
    }
  }

  stop(): void {
    if (this.process) {
      this.process.kill()
      this.process = null
    }
    this.isReady = false
  }

}

const backendManager = new PythonBackendManager()

const preload = path.join(__dirname, '../preload/preload.js')
const url = process.env.VITE_DEV_SERVER_URL || 'http://localhost:5173'
const indexHtml = path.join(process.env.DIST, 'index.html')

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

ipcMain.handle('get-system-status', async () => {
  return await backendManager.sendCommand({ type: 'get_system_status' })
})

ipcMain.handle('emergency-stop', async () => {
  return await backendManager.sendCommand({ type: 'emergency_stop' })
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