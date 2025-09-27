import { app, BrowserWindow, ipcMain } from 'electron'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { spawn, ChildProcess } from 'node:child_process'

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
process.env.DIST = path.join(process.env.DIST_ELECTRON, './dist')
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

  start(): Promise<void> {
    return new Promise((resolve, reject) => {
      console.log('Starting Python backend...')

      // Start Python process with IPC communication
      const isDevelopment = process.env.NODE_ENV !== 'production' || process.env.VITE_DEV_SERVER_URL
      const backendDir = isDevelopment
        ? path.join(__dirname, '../../../backend')
        : path.join(process.resourcesPath, 'backend')

      this.process = spawn('poetry', ['run', 'python', 'src/isi_control/main.py'], {
        stdio: ['pipe', 'pipe', 'pipe'],
        cwd: backendDir,
        shell: true,
        env: {
          ...process.env,
          PYTHONPATH: 'src'
        }
      })

      this.process.stdout?.on('data', (data) => {
        const message = data.toString().trim()
        console.log('Python backend:', message)

        // Check if backend is ready
        if (message.includes('IPC_READY')) {
          this.isReady = true
          console.log('Python backend ready for IPC')
          resolve()

          // Process queued messages
          this.messageQueue.forEach(msg => this.send(msg))
          this.messageQueue = []
        } else {
          try {
            // Try to parse as JSON IPC message
            const parsedMessage = JSON.parse(message)
            this.handleMessage(parsedMessage)
          } catch (e) {
            // Regular log message
            console.log('Python log:', message)
          }
        }
      })

      this.process.stderr?.on('data', (data) => {
        console.error('Python backend error:', data.toString())
      })

      this.process.on('error', (error) => {
        console.error('Failed to start Python backend:', error)
        reject(error)
      })

      this.process.on('exit', (code) => {
        console.log(`Python backend exited with code ${code}`)
        this.isReady = false
      })

      // Timeout if backend doesn't start
      setTimeout(() => {
        if (!this.isReady) {
          reject(new Error('Python backend startup timeout'))
        }
      }, 10000)
    })
  }

  send(message: any): void {
    if (!this.isReady || !this.process) {
      console.log('Queuing message for Python backend')
      this.messageQueue.push(message)
      return
    }

    const jsonMessage = JSON.stringify(message) + '\n'
    this.process.stdin?.write(jsonMessage)
  }

  private handleMessage(message: any): void {
    console.log('Received from Python backend:', message)

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

  if (isDevelopment) {
    // In development, load from Vite dev server
    mainWindow.loadURL(url)
    // Open devtools in development
    mainWindow.webContents.openDevTools()
  } else {
    // In production, load from built files
    mainWindow.loadFile(indexHtml)
  }

  // Test actively push message to the Electron-Renderer
  mainWindow.webContents.on('did-finish-load', () => {
    mainWindow?.webContents.send('main-process-message', new Date().toLocaleString())
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
    console.log('Python backend started successfully')
  } catch (error) {
    console.error('Failed to start Python backend:', error)
    // Continue running but show error in UI
    mainWindow.webContents.send('backend-error', error.message)
  }
}

// IPC Handlers
ipcMain.handle('send-to-python', async (event, message) => {
  console.log('Sending to Python backend:', message)
  backendManager.send(message)
  return { success: true }
})

ipcMain.handle('get-system-status', async () => {
  // Request system status from Python backend
  backendManager.send({ type: 'get_system_status' })
  return { success: true }
})

ipcMain.handle('emergency-stop', async () => {
  console.log('EMERGENCY STOP triggered')
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