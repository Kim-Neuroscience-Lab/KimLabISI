var __defProp = Object.defineProperty;
var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
var __publicField = (obj, key, value) => __defNormalProp(obj, typeof key !== "symbol" ? key + "" : key, value);
import { app, ipcMain, BrowserWindow } from "electron";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { execFile } from "node:child_process";
const require2 = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
process.env.DIST_ELECTRON = path.join(__dirname, "../");
process.env.DIST = path.join(__dirname, "../dist");
process.env.VITE_PUBLIC = process.env.VITE_DEV_SERVER_URL ? path.join(process.env.DIST_ELECTRON, "./public") : process.env.DIST;
if (process.platform === "win32") app.disableHardwareAcceleration();
if (process.platform === "win32") app.setAppUserModelId(app.getName());
if (!app.requestSingleInstanceLock()) {
  app.quit();
  process.exit(0);
}
let mainWindow = null;
class PythonBackendManager {
  constructor() {
    __publicField(this, "process", null);
    __publicField(this, "isReady", false);
    __publicField(this, "messageQueue", []);
    __publicField(this, "healthCheckInterval", null);
    __publicField(this, "startupTimeout", null);
    __publicField(this, "STARTUP_TIMEOUT", 15e3);
    // 15 seconds
    __publicField(this, "HEALTH_CHECK_INTERVAL", 5e3);
  }
  // 5 seconds
  async start() {
    await this.cleanup();
    return new Promise((resolve, reject) => {
      var _a, _b;
      try {
        const isDevelopment = process.env.NODE_ENV !== "production" || process.env.VITE_DEV_SERVER_URL;
        const rootDir = isDevelopment ? path.join(__dirname, "../../..") : process.resourcesPath;
        this.killExistingPythonProcesses();
        this.process = execFile("poetry", ["run", "python", "src/backend/src/isi_control/main.py"], {
          stdio: ["pipe", "pipe", "pipe"],
          cwd: rootDir,
          env: {
            ...process.env,
            PYTHONPATH: path.join(rootDir, "src/backend/src")
          }
        });
        if (!this.process.pid) {
          reject(new Error("Failed to get process PID"));
          return;
        }
        (_a = this.process.stdout) == null ? void 0 : _a.on("data", (data) => {
          const message = data.toString().trim();
          if (message.includes("IPC_READY")) {
            this.onBackendReady(resolve);
          } else {
            this.handleBackendMessage(message);
          }
        });
        (_b = this.process.stderr) == null ? void 0 : _b.on("data", (data) => {
          const errorMsg = data.toString();
          console.error("Python backend error:", errorMsg);
        });
        this.process.on("error", (error) => {
          console.error("Python process error:", error);
          this.cleanup();
          reject(error);
        });
        this.process.on("exit", (code, signal) => {
          this.isReady = false;
          this.cleanup();
          if (mainWindow) {
            mainWindow.webContents.send("backend-error", "Backend process exited");
          }
        });
        this.startupTimeout = setTimeout(() => {
          if (!this.isReady) {
            this.cleanup();
            reject(new Error("Python backend startup timeout after 15 seconds"));
          }
        }, this.STARTUP_TIMEOUT);
      } catch (error) {
        console.error("Error starting Python backend:", error);
        reject(error);
      }
    });
  }
  onBackendReady(resolve) {
    this.isReady = true;
    if (this.startupTimeout) {
      clearTimeout(this.startupTimeout);
      this.startupTimeout = null;
    }
    if (mainWindow) {
      mainWindow.webContents.send("main-process-message", "Backend ready");
    }
    this.messageQueue.forEach((msg) => this.send(msg));
    this.messageQueue = [];
    this.startHealthCheck();
    resolve();
  }
  handleBackendMessage(message) {
    const trimmed = message.trim();
    if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
      try {
        const parsedMessage = JSON.parse(trimmed);
        this.handleMessage(parsedMessage);
      } catch (e) {
        console.error("Failed to parse JSON message from backend:", message, e);
      }
    } else {
      console.log("Backend log:", message);
    }
  }
  startHealthCheck() {
    this.healthCheckInterval = setInterval(() => {
      if (this.isReady && this.process) {
        this.send({ type: "ping" });
      }
    }, this.HEALTH_CHECK_INTERVAL);
  }
  killExistingPythonProcesses() {
    try {
      const { execSync } = require2("child_process");
      let processes;
      try {
        processes = execSync('pgrep -f "isi_control/main.py"', { encoding: "utf8" });
      } catch (error) {
        return;
      }
      if (processes.trim()) {
        console.log("Found existing ISI backend processes, terminating...");
        execSync('pkill -f "isi_control/main.py"');
      }
    } catch (error) {
      if (error.status !== 1) {
        console.error("Error during process cleanup:", error.message);
      }
    }
  }
  async cleanup() {
    if (this.startupTimeout) {
      clearTimeout(this.startupTimeout);
      this.startupTimeout = null;
    }
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }
    if (this.process) {
      try {
        this.process.kill("SIGTERM");
        await new Promise((resolve) => setTimeout(resolve, 1e3));
        if (!this.process.killed) {
          this.process.kill("SIGKILL");
        }
      } catch (error) {
        console.error("Error stopping Python process:", error);
      }
      this.process = null;
    }
    this.isReady = false;
    this.messageQueue = [];
  }
  send(message) {
    var _a;
    if (!this.isReady || !this.process) {
      this.messageQueue.push(message);
      return;
    }
    const jsonMessage = JSON.stringify(message) + "\n";
    (_a = this.process.stdin) == null ? void 0 : _a.write(jsonMessage);
  }
  handleMessage(message) {
    if (mainWindow) {
      mainWindow.webContents.send("python-message", message);
    }
  }
  stop() {
    if (this.process) {
      this.process.kill();
      this.process = null;
    }
    this.isReady = false;
  }
}
const backendManager = new PythonBackendManager();
const preload = path.join(__dirname, "preload.js");
const url = process.env.VITE_DEV_SERVER_URL || "http://localhost:5173";
const indexHtml = path.join(process.env.DIST, "index.html");
async function createWindow() {
  mainWindow = new BrowserWindow({
    title: "ISI Control System",
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 800,
    icon: path.join(process.env.VITE_PUBLIC, "electron.png"),
    webPreferences: {
      preload,
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true
    }
  });
  const isDevelopment = process.env.NODE_ENV !== "production" || process.env.VITE_DEV_SERVER_URL;
  mainWindow.loadFile(indexHtml);
  if (isDevelopment) {
    mainWindow.webContents.openDevTools();
  }
  mainWindow.webContents.on("did-finish-load", () => {
    mainWindow == null ? void 0 : mainWindow.webContents.send("main-process-message", `Renderer loaded at ${(/* @__PURE__ */ new Date()).toLocaleString()}`);
  });
  mainWindow.webContents.setWindowOpenHandler(({ url: url2 }) => {
    if (url2.startsWith("https:")) {
      require2("electron").shell.openExternal(url2);
    }
    return { action: "deny" };
  });
  try {
    await backendManager.start();
  } catch (error) {
    mainWindow.webContents.send("backend-error", error.message);
  }
}
ipcMain.handle("send-to-python", async (event, message) => {
  backendManager.send(message);
  return { success: true };
});
ipcMain.handle("get-system-status", async () => {
  backendManager.send({ type: "get_system_status" });
  return { success: true };
});
ipcMain.handle("emergency-stop", async () => {
  backendManager.send({ type: "emergency_stop" });
  return { success: true };
});
app.whenReady().then(createWindow);
app.on("window-all-closed", () => {
  mainWindow = null;
  backendManager.stop();
  if (process.platform !== "darwin") app.quit();
});
app.on("second-instance", () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});
app.on("activate", () => {
  const allWindows = BrowserWindow.getAllWindows();
  if (allWindows.length) {
    allWindows[0].focus();
  } else {
    createWindow();
  }
});
app.on("before-quit", () => {
  backendManager.stop();
});
ipcMain.handle("open-win", (_, arg) => {
  const childWindow = new BrowserWindow({
    webPreferences: {
      preload,
      nodeIntegration: false,
      contextIsolation: true
    }
  });
  const isDevelopment = process.env.NODE_ENV !== "production" || process.env.VITE_DEV_SERVER_URL;
  if (isDevelopment) {
    childWindow.loadURL(`${url}#${arg}`);
  } else {
    childWindow.loadFile(indexHtml, { hash: arg });
  }
});
//# sourceMappingURL=main.js.map
