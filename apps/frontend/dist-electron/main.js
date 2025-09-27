var __defProp = Object.defineProperty;
var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
var __publicField = (obj, key, value) => __defNormalProp(obj, typeof key !== "symbol" ? key + "" : key, value);
import { app, ipcMain, BrowserWindow } from "electron";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { spawn } from "node:child_process";
const require2 = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
process.env.DIST_ELECTRON = path.join(__dirname, "../");
process.env.DIST = path.join(process.env.DIST_ELECTRON, "./dist");
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
  }
  start() {
    return new Promise((resolve, reject) => {
      var _a, _b;
      console.log("Starting Python backend with fixed paths...");
      const isDevelopment = process.env.NODE_ENV !== "production" || process.env.VITE_DEV_SERVER_URL;
      const backendDir = isDevelopment ? path.join(__dirname, "../../../backend") : path.join(process.resourcesPath, "backend");
      this.process = spawn("/Users/Adam/.local/bin/poetry", ["run", "python", "src/isi_control/main.py"], {
        stdio: ["pipe", "pipe", "pipe"],
        cwd: backendDir,
        env: {
          ...process.env,
          PYTHONPATH: "src"
        }
      });
      (_a = this.process.stdout) == null ? void 0 : _a.on("data", (data) => {
        const message = data.toString().trim();
        console.log("Python backend:", message);
        if (message.includes("IPC_READY")) {
          this.isReady = true;
          console.log("Python backend ready for IPC");
          resolve();
          this.messageQueue.forEach((msg) => this.send(msg));
          this.messageQueue = [];
        } else {
          try {
            const parsedMessage = JSON.parse(message);
            this.handleMessage(parsedMessage);
          } catch (e) {
            console.log("Python log:", message);
          }
        }
      });
      (_b = this.process.stderr) == null ? void 0 : _b.on("data", (data) => {
        console.error("Python backend error:", data.toString());
      });
      this.process.on("error", (error) => {
        console.error("Failed to start Python backend:", error);
        reject(error);
      });
      this.process.on("exit", (code) => {
        console.log(`Python backend exited with code ${code}`);
        this.isReady = false;
      });
      setTimeout(() => {
        if (!this.isReady) {
          reject(new Error("Python backend startup timeout"));
        }
      }, 1e4);
    });
  }
  send(message) {
    var _a;
    if (!this.isReady || !this.process) {
      console.log("Queuing message for Python backend");
      this.messageQueue.push(message);
      return;
    }
    const jsonMessage = JSON.stringify(message) + "\n";
    (_a = this.process.stdin) == null ? void 0 : _a.write(jsonMessage);
  }
  handleMessage(message) {
    console.log("Received from Python backend:", message);
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
  if (isDevelopment) {
    mainWindow.loadURL(url);
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(indexHtml);
  }
  mainWindow.webContents.on("did-finish-load", () => {
    mainWindow == null ? void 0 : mainWindow.webContents.send("main-process-message", (/* @__PURE__ */ new Date()).toLocaleString());
  });
  mainWindow.webContents.setWindowOpenHandler(({ url: url2 }) => {
    if (url2.startsWith("https:")) {
      require2("electron").shell.openExternal(url2);
    }
    return { action: "deny" };
  });
  try {
    await backendManager.start();
    console.log("Python backend started successfully");
  } catch (error) {
    console.error("Failed to start Python backend:", error);
    mainWindow.webContents.send("backend-error", error.message);
  }
}
ipcMain.handle("send-to-python", async (event, message) => {
  console.log("Sending to Python backend:", message);
  backendManager.send(message);
  return { success: true };
});
ipcMain.handle("get-system-status", async () => {
  backendManager.send({ type: "get_system_status" });
  return { success: true };
});
ipcMain.handle("emergency-stop", async () => {
  console.log("EMERGENCY STOP triggered");
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
