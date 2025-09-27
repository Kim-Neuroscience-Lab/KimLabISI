import { app, BrowserWindow, ipcMain } from 'electron'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { ChildProcess, execFile } from 'node:child_process'

const require = createRequire(import.meta.url)
const __dirname = path.dirname(fileURLToPath(import.meta.url))

// The built directory structure
//
// ├─┬ dist-electron
// │ ├─┬ main.js    > Electron main
// │ │ └─┬ preload.js    > Preload scripts
// │ └─┬ renderer.js > Electron renderer
//
process.env.DIST_ELECTRON = path.join(__dirname, '../')
process.env.DIST = path.join(__dirname, '../dist')
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
let pythonBackend: ChildProcess | null = null

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
          ? path.join(__dirname, '../../..')
          : process.resourcesPath

        // Kill any existing Python processes that might conflict
        this.killExistingPythonProcesses()

        this.process = execFile('poetry', ['run', 'python', 'src/backend/src/isi_control/main.py'], {
          stdio: ['pipe', 'pipe', 'pipe'],
          cwd: rootDir,
          env: {
            ...process.env,
            PYTHONPATH: path.join(rootDir, 'src/backend/src')
          }
        }) as ChildProcess

        if (!this.process.pid) {
          reject(new Error('Failed to get process PID'))
          return
        }


        this.process.stdout?.on('data', (data) => {
          const message = data.toString().trim()

          if (message.includes('IPC_READY')) {
            this.onBackendReady(resolve)
          } else {
            this.handleBackendMessage(message)
          }
        })

        this.process.stderr?.on('data', (data) => {
          const errorMsg = data.toString()
          console.error('Python backend error:', errorMsg)
        })

        this.process.on('error', (error) => {
          console.error('Python process error:', error)
          this.cleanup()
          reject(error)
        })

        this.process.on('exit', (code, signal) => {
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
        console.error('Error starting Python backend:', error)
        reject(error)
      }
    })
  }

  private onBackendReady(resolve: () => void): void {
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
      console.log('Backend log:', message)
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
      const { execSync } = require('child_process')

      // First, check if any processes exist
      let processes: string
      try {
        processes = execSync('pgrep -f "isi_control/main.py"', { encoding: 'utf8' })
      } catch (error) {
        // No processes found - this is expected most of the time
        return
      }

      if (processes.trim()) {
        console.log('Found existing ISI backend processes, terminating...')
        execSync('pkill -f "isi_control/main.py"')
      }
    } catch (error) {
      // Only log actual errors, not expected "no processes found" cases
      if (error.status !== 1) { // pgrep returns 1 when no processes found
        console.error('Error during process cleanup:', error.message)
      }
    }
  }

  private async cleanup(): Promise<void> {
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
        if (!this.process.killed) {
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

const preload = path.join(__dirname, 'preload.js')
const url = process.env.VITE_DEV_SERVER_URL || 'http://localhost:5173'
const indexHtml = path.join(process.env.DIST, 'index.html')

async function createWindow() {
  mainWindow = new BrowserWindow({
    title: 'ISI Control System',
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 800,
    icon: path.join(process.env.VITE_PUBLIC, 'electron.png'),
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

  // Test actively push message to the Electron-Renderer
  mainWindow.webContents.on('did-finish-load', () => {
    mainWindow?.webContents.send('main-process-message', `Renderer loaded at ${new Date().toLocaleString()}`)
  })

  // Make all links open with the browser, not with the application
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('https:')) {
      require('electron').shell.openExternal(url)
    }
    return { action: 'deny' }
  })

  // Start Python backend after window is ready
  try {
    await backendManager.start()
  } catch (error) {
    // Continue running but show error in UI
    mainWindow.webContents.send('backend-error', error.message)
  }
}

// IPC Handlers
ipcMain.handle('send-to-python', async (event, message) => {
  backendManager.send(message)
  return { success: true }
})

ipcMain.handle('get-system-status', async () => {
  // Request system status from Python backend
  backendManager.send({ type: 'get_system_status' })
  return { success: true }
})

ipcMain.handle('emergency-stop', async () => {
  backendManager.send({ type: 'emergency_stop' })
  return { success: true }
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