/**
 * Electron Main Process - ISI Macroscope Control System
 *
 * Implements secure Electron main process with Python backend spawning
 * following Clean Architecture and security best practices.
 */

import { app, BrowserWindow, ipcMain, shell } from 'electron';
import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

interface BackendConfig {
  pythonPath: string;
  backendPath: string;
  devMode: boolean;
}

interface BackendProcess {
  process: ChildProcess | null;
  isRunning: boolean;
  startTime: number;
  restartCount: number;
}

class ISIElectronApp {
  private mainWindow: BrowserWindow | null = null;
  private backend: BackendProcess = {
    process: null,
    isRunning: false,
    startTime: 0,
    restartCount: 0
  };
  private isDev: boolean = false;

  constructor() {
    this.isDev = process.argv.includes('--dev') || process.env.NODE_ENV === 'development';
    this.initializeApp();
  }

  private initializeApp(): void {
    // Set security defaults
    app.enableSandbox();

    // Prevent multiple instances
    const gotTheLock = app.requestSingleInstanceLock();
    if (!gotTheLock) {
      app.quit();
      return;
    }

    app.on('second-instance', () => {
      // Someone tried to run a second instance, focus our window instead
      if (this.mainWindow) {
        if (this.mainWindow.isMinimized()) this.mainWindow.restore();
        this.mainWindow.focus();
      }
    });

    // App event handlers
    app.whenReady().then(() => this.onReady());
    app.on('window-all-closed', () => this.onWindowAllClosed());
    app.on('activate', () => this.onActivate());
    app.on('before-quit', () => this.onBeforeQuit());

    // Security handlers
    app.on('web-contents-created', (_, contents) => {
      contents.setWindowOpenHandler(() => {
        return { action: 'deny' };
      });

      contents.on('will-navigate', (event, navigationUrl) => {
        const parsedUrl = new URL(navigationUrl);
        if (parsedUrl.origin !== 'http://localhost:3000' && parsedUrl.origin !== 'file://') {
          event.preventDefault();
        }
      });
    });

    // IPC handlers
    this.setupIpcHandlers();
  }

  private async onReady(): Promise<void> {
    console.log('ISI Macroscope Electron App starting...');

    try {
      // Start Python backend first
      await this.startPythonBackend();

      // Create main window
      await this.createMainWindow();

      console.log('ISI Macroscope Electron App ready');
    } catch (error) {
      console.error('Failed to start ISI Macroscope App:', error);
      app.quit();
    }
  }

  private onWindowAllClosed(): void {
    if (process.platform !== 'darwin') {
      app.quit();
    }
  }

  private onActivate(): void {
    if (BrowserWindow.getAllWindows().length === 0) {
      this.createMainWindow();
    }
  }

  private onBeforeQuit(): void {
    this.stopPythonBackend();
  }

  private async createMainWindow(): Promise<void> {
    this.mainWindow = new BrowserWindow({
      width: 1400,
      height: 900,
      minWidth: 1200,
      minHeight: 800,
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        sandbox: true,
        preload: path.join(__dirname, 'preload.js')
      },
      titleBarStyle: 'hiddenInset',
      title: 'ISI Macroscope Control System',
      show: false // Don't show until ready-to-show
    });

    // Load the frontend
    if (this.isDev) {
      // For development, load the built files directly since we're not running a dev server
      await this.mainWindow.loadFile(path.join(__dirname, '../build/index.html'));
      this.mainWindow.webContents.openDevTools();
    } else {
      await this.mainWindow.loadFile(path.join(__dirname, '../build/index.html'));
    }

    // Show window when ready
    this.mainWindow.once('ready-to-show', () => {
      if (this.mainWindow) {
        this.mainWindow.show();
        this.mainWindow.focus();
      }
    });

    this.mainWindow.on('closed', () => {
      this.mainWindow = null;
    });
  }

  private async startPythonBackend(): Promise<void> {
    console.log('Starting Python backend...');

    try {
      const config = await this.detectBackendConfig();

      const args = [
        path.join(config.backendPath, 'src/isi_control/main.py'),
        '--dev'
      ];

      console.log(`Spawning Python backend: ${config.pythonPath} ${args.join(' ')}`);

      this.backend.process = spawn(config.pythonPath, args, {
        cwd: config.backendPath,
        env: {
          ...process.env,
          PYTHONPATH: path.join(config.backendPath, 'src')
        },
        stdio: ['pipe', 'pipe', 'pipe']
      });

      this.backend.isRunning = true;
      this.backend.startTime = Date.now();

      // Handle backend process events
      this.backend.process.stdout?.on('data', (data) => {
        const output = data.toString();
        console.log('[Backend STDOUT]:', output);

        // Forward backend messages to renderer
        if (this.mainWindow?.webContents) {
          try {
            const lines = output.split('\n').filter(line => line.trim());
            for (const line of lines) {
              if (line.startsWith('{') && line.includes('type')) {
                const message = JSON.parse(line);
                this.mainWindow.webContents.send('backend-message', message);
              }
            }
          } catch (error) {
            // Not a JSON message, ignore
          }
        }
      });

      this.backend.process.stderr?.on('data', (data) => {
        console.error('[Backend STDERR]:', data.toString());
      });

      this.backend.process.on('exit', (code, signal) => {
        console.log(`Backend process exited with code ${code}, signal ${signal}`);
        this.backend.isRunning = false;

        if (code !== 0 && this.backend.restartCount < 3) {
          console.log('Attempting to restart backend...');
          this.backend.restartCount++;
          setTimeout(() => this.startPythonBackend(), 2000);
        }
      });

      this.backend.process.on('error', (error) => {
        console.error('Backend process error:', error);
        this.backend.isRunning = false;
      });

      // Wait for backend to be ready
      await this.waitForBackendReady();

      console.log('Python backend started successfully');
    } catch (error) {
      console.error('Failed to start Python backend:', error);
      throw error;
    }
  }

  private async detectBackendConfig(): Promise<BackendConfig> {
    const backendPath = path.resolve(__dirname, '../../backend');

    // Check if backend directory exists
    if (!fs.existsSync(backendPath)) {
      throw new Error(`Backend directory not found: ${backendPath}`);
    }

    // Try to detect Python executable
    const pythonPaths = [
      // Poetry virtual environment
      path.join(backendPath, '.venv', 'bin', 'python'),
      path.join(backendPath, '.venv', 'Scripts', 'python.exe'),
      // System Python
      'python3',
      'python'
    ];

    for (const pythonPath of pythonPaths) {
      try {
        const fullPath = path.isAbsolute(pythonPath) ? pythonPath : pythonPath;

        // Test if Python path works
        const testProcess = spawn(fullPath, ['--version'], { stdio: 'pipe' });

        await new Promise((resolve, reject) => {
          testProcess.on('exit', (code) => {
            if (code === 0) resolve(void 0);
            else reject(new Error(`Python test failed with code ${code}`));
          });
          testProcess.on('error', reject);
        });

        return {
          pythonPath: fullPath,
          backendPath,
          devMode: this.isDev
        };
      } catch (error) {
        // Try next Python path
        continue;
      }
    }

    throw new Error('Could not find working Python executable');
  }

  private async waitForBackendReady(timeout: number = 10000): Promise<void> {
    const startTime = Date.now();

    return new Promise((resolve, reject) => {
      const checkReady = () => {
        if (Date.now() - startTime > timeout) {
          reject(new Error('Backend startup timeout'));
          return;
        }

        if (!this.backend.process || !this.backend.isRunning) {
          reject(new Error('Backend process failed to start'));
          return;
        }

        // Check if we can see backend ready message
        // For now, assume ready after process starts successfully
        setTimeout(resolve, 2000);
      };

      checkReady();
    });
  }

  private stopPythonBackend(): void {
    if (this.backend.process && this.backend.isRunning) {
      console.log('Stopping Python backend...');

      // Send graceful shutdown signal
      this.backend.process.kill('SIGTERM');

      // Force kill after timeout
      setTimeout(() => {
        if (this.backend.process && this.backend.isRunning) {
          console.log('Force killing Python backend...');
          this.backend.process.kill('SIGKILL');
        }
      }, 5000);

      this.backend.isRunning = false;
    }
  }

  private setupIpcHandlers(): void {
    // Handle messages to backend
    ipcMain.handle('send-backend-command', async (event, message) => {
      return new Promise((resolve, reject) => {
        if (!this.backend.process || !this.backend.isRunning) {
          reject(new Error('Backend not running'));
          return;
        }

        try {
          const messageString = JSON.stringify(message) + '\n';
          this.backend.process.stdin?.write(messageString);
          resolve({ success: true });
        } catch (error) {
          reject(error);
        }
      });
    });

    // Handle backend status queries
    ipcMain.handle('get-backend-status', async () => {
      return {
        isRunning: this.backend.isRunning,
        startTime: this.backend.startTime,
        restartCount: this.backend.restartCount,
        uptime: this.backend.isRunning ? Date.now() - this.backend.startTime : 0
      };
    });

    // Handle app info queries
    ipcMain.handle('get-app-info', async () => {
      return {
        version: app.getVersion(),
        isDev: this.isDev,
        platform: process.platform,
        arch: process.arch,
        electronVersion: process.versions.electron,
        nodeVersion: process.versions.node
      };
    });
  }
}

// Initialize the application
new ISIElectronApp();