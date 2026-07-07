// Electron main process for Genie.
// In dev: loads the Vite dev server (http://localhost:5173).
// In prod: loads the built index.html from ../dist.
const { app, BrowserWindow, shell, ipcMain } = require("electron");
const path = require("path");

const isDev = process.env.NODE_ENV === "development";

let mainWindow = null;

// IPC handlers used by the frameless window's custom titlebar.
ipcMain.on("window:minimize", () => mainWindow && mainWindow.minimize());
ipcMain.on("window:close", () => mainWindow && mainWindow.close());

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 420,
    height: 760,
    minWidth: 360,
    minHeight: 560,
    frame: false,            // frameless for the custom futuristic shell
    transparent: false,
    resizable: true,
    backgroundColor: "#222222",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Open external links in the system browser, not inside Genie.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  if (isDev) {
    mainWindow.loadURL("http://localhost:5173");
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }
}

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
