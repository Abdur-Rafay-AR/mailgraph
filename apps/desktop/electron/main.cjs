const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

let mainWindow;
let pythonProcess = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1360,
    height: 880,
    minWidth: 1024,
    minHeight: 700,
    backgroundColor: '#0c0814',
    title: 'MailGraph',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true
    }
  });

  const distHtml = path.join(__dirname, '../dist/index.html');
  const devUrl = 'http://localhost:5173';

  // In desktop mode or when built bundle exists without dev server url, load file directly
  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else if (process.env.MAILGRAPH_MODE === 'desktop' || process.env.NODE_ENV === 'production' || fs.existsSync(distHtml)) {
    mainWindow.loadFile(distHtml).catch(err => {
      console.warn('loadFile failed, attempting dev URL fallback:', err);
      mainWindow.loadURL(devUrl);
    });
  } else {
    mainWindow.loadURL(devUrl).catch(() => {
      // Fallback if vite dev server is still starting
      setTimeout(() => mainWindow.loadURL(devUrl), 1500);
    });
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// Native dialog handler for selecting MBOX archives
ipcMain.handle('dialog:selectMboxFile', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Select MBOX Archive File',
    properties: ['openFile'],
    filters: [
      { name: 'Email Archives', extensions: ['mbox', 'txt', 'eml'] },
      { name: 'All Files', extensions: ['*'] }
    ]
  });
  if (result.canceled || !result.filePaths.length) {
    return null;
  }
  return result.filePaths[0];
});

ipcMain.handle('shell:openExternal', async (_, url) => {
  if (url.startsWith('https://') || url.startsWith('http://')) {
    await shell.openExternal(url);
  }
});

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
