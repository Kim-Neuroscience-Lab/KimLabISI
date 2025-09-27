/**
 * ISI Macroscope Control System - Window Manager
 *
 * Manages Electron windows with security best practices:
 * - Secure window configuration
 * - Context isolation enforcement
 * - CSP implementation
 * - Window state management
 * - Multi-display support for scientific applications
 */

import { BrowserWindow, screen, dialog, Menu } from 'electron';
import * as path from 'path';

// Security configuration constants
const SECURITY_WEBPREFERENCES = {
  nodeIntegration: false,
  contextIsolation: true,
  enableRemoteModule: false,
  sandbox: true,
  webSecurity: true,
  allowRunningInsecureContent: false,
  experimentalFeatures: false,
} as const;

// CSP (Content Security Policy) for additional security
const CONTENT_SECURITY_POLICY = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'", // Allow inline scripts for React
  "style-src 'self' 'unsafe-inline'",   // Allow inline styles for React
  "img-src 'self' data: blob:",         // Allow data URLs and blobs for images
  "font-src 'self'",
  "connect-src 'self'",                 // Only allow connections to self
  "frame-src 'none'",                   // Prevent framing
  "object-src 'none'",                  // Prevent plugins
].join('; ');

interface WindowOptions {
  width?: number;
  height?: number;
  minWidth?: number;
  minHeight?: number;
  x?: number;
  y?: number;
  show?: boolean;
  webPreferences?: Electron.WebPreferences;
}

interface WindowState {
  id: number;
  bounds: Electron.Rectangle;
  isMaximized: boolean;
  isFullScreen: boolean;
  isMinimized: boolean;
}

/**
 * Window Manager for ISI Macroscope Control System
 */
export class WindowManager {
  private mainWindow: BrowserWindow | null = null;
  private previewWindow: BrowserWindow | null = null;
  private analysisWindow: BrowserWindow | null = null;
  private windows: Map<string, BrowserWindow> = new Map();
  private windowStates: Map<number, WindowState> = new Map();

  constructor() {
    this.setupApplicationMenu();
  }

  // ============================================================================
  // MAIN WINDOW MANAGEMENT
  // ============================================================================

  /**
   * Create the main application window
   */
  createMainWindow(options: WindowOptions = {}): BrowserWindow {
    if (this.mainWindow && !this.mainWindow.isDestroyed()) {
      this.mainWindow.focus();
      return this.mainWindow;
    }

    // Get primary display for initial positioning
    const primaryDisplay = screen.getPrimaryDisplay();
    const { width: screenWidth, height: screenHeight } = primaryDisplay.workAreaSize;

    // Default window configuration
    const defaultOptions: WindowOptions = {
      width: Math.min(1200, screenWidth - 100),
      height: Math.min(800, screenHeight - 100),
      minWidth: 800,
      minHeight: 600,
      show: false, // Don't show until ready
      webPreferences: {
        ...SECURITY_WEBPREFERENCES,
        preload: path.join(__dirname, 'preload.js'),
      },
    };

    // Merge with provided options
    const windowOptions = { ...defaultOptions, ...options };

    // Create the window
    this.mainWindow = new BrowserWindow({
      ...windowOptions,
      title: 'ISI Macroscope Control System',
      icon: this.getApplicationIcon(),
      titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
      backgroundColor: '#ffffff',
      webPreferences: {
        ...windowOptions.webPreferences,
        additionalArguments: [`--content-security-policy=${CONTENT_SECURITY_POLICY}`],
      },
    });

    // Setup window event handlers
    this.setupMainWindowHandlers();

    // Track window
    this.windows.set('main', this.mainWindow);

    console.log('Window Manager: Main window created');
    return this.mainWindow;
  }

  /**
   * Setup event handlers for main window
   */
  private setupMainWindowHandlers(): void {
    if (!this.mainWindow) return;

    // Show window when ready to prevent visual flash
    this.mainWindow.once('ready-to-show', () => {
      if (this.mainWindow) {
        this.mainWindow.show();
        this.mainWindow.focus();
      }
    });

    // Handle window closed
    this.mainWindow.on('closed', () => {
      this.mainWindow = null;
      this.windows.delete('main');
      console.log('Window Manager: Main window closed');
    });

    // Track window state changes
    this.mainWindow.on('resize', () => this.saveWindowState('main'));
    this.mainWindow.on('move', () => this.saveWindowState('main'));
    this.mainWindow.on('maximize', () => this.saveWindowState('main'));
    this.mainWindow.on('unmaximize', () => this.saveWindowState('main'));
    this.mainWindow.on('enter-full-screen', () => this.saveWindowState('main'));
    this.mainWindow.on('leave-full-screen', () => this.saveWindowState('main'));

    // Security: Prevent new window creation
    this.mainWindow.webContents.setWindowOpenHandler(() => {
      console.warn('Window Manager: Blocked attempt to open new window');
      return { action: 'deny' };
    });

    // Security: Prevent navigation to external URLs
    this.mainWindow.webContents.on('will-navigate', (event, url) => {
      const allowedOrigins = ['file://', 'http://localhost:', 'https://localhost:'];
      const isAllowed = allowedOrigins.some(origin => url.startsWith(origin));

      if (!isAllowed) {
        console.warn('Window Manager: Blocked navigation to:', url);
        event.preventDefault();
      }
    });

    // Handle certificate errors (for development)
    this.mainWindow.webContents.on('certificate-error', (event, url, error, certificate, callback) => {
      if (url.startsWith('https://localhost:')) {
        // Allow self-signed certificates for local development
        event.preventDefault();
        callback(true);
      } else {
        callback(false);
      }
    });
  }

  // ============================================================================
  // SPECIALIZED WINDOWS
  // ============================================================================

  /**
   * Create preview window for stimulus display
   */
  createPreviewWindow(): BrowserWindow {
    if (this.previewWindow && !this.previewWindow.isDestroyed()) {
      this.previewWindow.focus();
      return this.previewWindow;
    }

    // Find secondary display for preview (if available)
    const displays = screen.getAllDisplays();
    const externalDisplay = displays.find(display => display.bounds.x !== 0 || display.bounds.y !== 0);

    const targetDisplay = externalDisplay || screen.getPrimaryDisplay();
    const { x, y, width, height } = targetDisplay.bounds;

    this.previewWindow = new BrowserWindow({
      width: Math.min(800, width - 100),
      height: Math.min(600, height - 100),
      x: x + 50,
      y: y + 50,
      title: 'Stimulus Preview',
      parent: this.mainWindow || undefined,
      modal: false,
      show: false,
      webPreferences: {
        ...SECURITY_WEBPREFERENCES,
        preload: path.join(__dirname, 'preload.js'),
      },
    });

    this.previewWindow.once('ready-to-show', () => {
      this.previewWindow?.show();
    });

    this.previewWindow.on('closed', () => {
      this.previewWindow = null;
      this.windows.delete('preview');
    });

    this.windows.set('preview', this.previewWindow);
    console.log('Window Manager: Preview window created');
    return this.previewWindow;
  }

  /**
   * Create analysis window for data visualization
   */
  createAnalysisWindow(): BrowserWindow {
    if (this.analysisWindow && !this.analysisWindow.isDestroyed()) {
      this.analysisWindow.focus();
      return this.analysisWindow;
    }

    const primaryDisplay = screen.getPrimaryDisplay();
    const { width: screenWidth, height: screenHeight } = primaryDisplay.workAreaSize;

    this.analysisWindow = new BrowserWindow({
      width: Math.min(1000, screenWidth - 200),
      height: Math.min(700, screenHeight - 200),
      minWidth: 600,
      minHeight: 400,
      title: 'Analysis Results',
      parent: this.mainWindow || undefined,
      modal: false,
      show: false,
      webPreferences: {
        ...SECURITY_WEBPREFERENCES,
        preload: path.join(__dirname, 'preload.js'),
      },
    });

    this.analysisWindow.once('ready-to-show', () => {
      this.analysisWindow?.show();
    });

    this.analysisWindow.on('closed', () => {
      this.analysisWindow = null;
      this.windows.delete('analysis');
    });

    this.windows.set('analysis', this.analysisWindow);
    console.log('Window Manager: Analysis window created');
    return this.analysisWindow;
  }

  // ============================================================================
  // WINDOW STATE MANAGEMENT
  // ============================================================================

  /**
   * Save window state for persistence
   */
  private saveWindowState(windowKey: string): void {
    const window = this.windows.get(windowKey);
    if (!window || window.isDestroyed()) return;

    const state: WindowState = {
      id: window.id,
      bounds: window.getBounds(),
      isMaximized: window.isMaximized(),
      isFullScreen: window.isFullScreen(),
      isMinimized: window.isMinimized(),
    };

    this.windowStates.set(window.id, state);
  }

  /**
   * Restore window state from saved data
   */
  restoreWindowState(window: BrowserWindow, savedState?: Partial<WindowState>): void {
    if (!savedState) return;

    // Validate bounds are within current screen setup
    const allDisplays = screen.getAllDisplays();
    const isValidPosition = allDisplays.some(display => {
      const bounds = display.bounds;
      return savedState.bounds &&
             savedState.bounds.x >= bounds.x &&
             savedState.bounds.y >= bounds.y &&
             savedState.bounds.x + savedState.bounds.width <= bounds.x + bounds.width &&
             savedState.bounds.y + savedState.bounds.height <= bounds.y + bounds.height;
    });

    if (isValidPosition && savedState.bounds) {
      window.setBounds(savedState.bounds);
    }

    if (savedState.isMaximized) {
      window.maximize();
    }

    if (savedState.isFullScreen) {
      window.setFullScreen(true);
    }
  }

  // ============================================================================
  // UTILITY METHODS
  // ============================================================================

  /**
   * Get the main window instance
   */
  getMainWindow(): BrowserWindow | null {
    return this.mainWindow;
  }

  /**
   * Get window by key
   */
  getWindow(key: string): BrowserWindow | null {
    return this.windows.get(key) || null;
  }

  /**
   * Close all windows
   */
  closeAllWindows(): void {
    console.log('Window Manager: Closing all windows...');

    for (const [key, window] of this.windows) {
      if (!window.isDestroyed()) {
        window.close();
      }
    }

    this.windows.clear();
    this.windowStates.clear();
  }

  /**
   * Show error dialog
   */
  showErrorDialog(title: string, content: string): void {
    const window = this.mainWindow || undefined;

    dialog.showErrorBox(title, content);
  }

  /**
   * Show message dialog
   */
  async showMessageDialog(title: string, message: string, type: 'info' | 'warning' | 'error' = 'info'): Promise<number> {
    const window = this.mainWindow || undefined;

    const result = await dialog.showMessageBox(window, {
      type,
      title,
      message,
      buttons: ['OK'],
      defaultId: 0,
    });

    return result.response;
  }

  /**
   * Get application icon path
   */
  private getApplicationIcon(): string {
    // Return path to application icon based on platform
    const iconName = process.platform === 'win32' ? 'icon.ico' : 'icon.png';
    return path.join(__dirname, '..', 'assets', 'icons', iconName);
  }

  /**
   * Setup application menu
   */
  private setupApplicationMenu(): void {
    if (process.platform === 'darwin') {
      // macOS menu
      const template: Electron.MenuItemConstructorOptions[] = [
        {
          label: 'ISI Macroscope',
          submenu: [
            { role: 'about' },
            { type: 'separator' },
            { role: 'services' },
            { type: 'separator' },
            { role: 'hide' },
            { role: 'hideOthers' },
            { role: 'unhide' },
            { type: 'separator' },
            { role: 'quit' },
          ],
        },
        {
          label: 'View',
          submenu: [
            { role: 'reload' },
            { role: 'forceReload' },
            { role: 'toggleDevTools' },
            { type: 'separator' },
            { role: 'resetZoom' },
            { role: 'zoomIn' },
            { role: 'zoomOut' },
            { type: 'separator' },
            { role: 'togglefullscreen' },
          ],
        },
        {
          label: 'Window',
          submenu: [
            { role: 'minimize' },
            { role: 'close' },
          ],
        },
      ];

      const menu = Menu.buildFromTemplate(template);
      Menu.setApplicationMenu(menu);
    } else {
      // Windows/Linux menu
      Menu.setApplicationMenu(null);
    }
  }

  // ============================================================================
  // DISPLAY MANAGEMENT
  // ============================================================================

  /**
   * Get available displays for multi-monitor setups
   */
  getAvailableDisplays(): Electron.Display[] {
    return screen.getAllDisplays();
  }

  /**
   * Move window to specific display
   */
  moveWindowToDisplay(windowKey: string, displayId: number): boolean {
    const window = this.windows.get(windowKey);
    if (!window || window.isDestroyed()) return false;

    const displays = screen.getAllDisplays();
    const targetDisplay = displays.find(display => display.id === displayId);

    if (!targetDisplay) return false;

    const { x, y, width, height } = targetDisplay.bounds;
    const windowBounds = window.getBounds();

    // Center window on target display
    const newX = x + Math.floor((width - windowBounds.width) / 2);
    const newY = y + Math.floor((height - windowBounds.height) / 2);

    window.setPosition(newX, newY);
    return true;
  }
}
