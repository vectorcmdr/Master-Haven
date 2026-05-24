'use strict';

const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');

// Polling and the network fetch live in the main process so the renderer stays
// sandboxed (contextIsolation on, nodeIntegration off) and we sidestep CORS.
const DEFAULT_CONFIG = {
  host: '10.0.0.229', // Haven Pi on the LAN; use the Tailscale IP when remote
  port: 8087, // 8080 is taken by another python service on the Pi

  intervalMs: 2000,
  alwaysOnTop: true,
  token: '',
  openAtLogin: false,
};

let win = null;
let cfg = null;
let pollTimer = null;

function configPath() {
  return path.join(app.getPath('userData'), 'config.json');
}

function loadConfig() {
  try {
    return { ...DEFAULT_CONFIG, ...JSON.parse(fs.readFileSync(configPath(), 'utf8')) };
  } catch {
    return { ...DEFAULT_CONFIG };
  }
}

function saveConfig(next) {
  try {
    fs.writeFileSync(configPath(), JSON.stringify(next, null, 2));
  } catch (err) {
    console.error('Failed to save config:', err.message);
  }
}

// Register/unregister the widget as a startup item. No packaging needed — on
// Windows this writes a standard HKCU\...\Run entry pointing at electron.exe +
// the app dir (electron.exe is a GUI app, so no console window appears at login).
function applyLoginItem() {
  if (process.platform !== 'win32' && process.platform !== 'darwin') return;
  app.setLoginItemSettings({
    openAtLogin: !!cfg.openAtLogin,
    path: process.execPath,
    args: app.isPackaged ? [] : [path.resolve(__dirname)],
  });
}

async function pollOnce() {
  const tokenQs = cfg.token ? `?token=${encodeURIComponent(cfg.token)}` : '';
  const url = `http://${cfg.host}:${cfg.port}/metrics${tokenQs}`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), Math.max(1500, cfg.intervalMs - 200));
  try {
    const res = await fetch(url, {
      signal: controller.signal,
      headers: cfg.token ? { 'X-Monitor-Token': cfg.token } : {},
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    send('metrics', { ok: true, data });
  } catch (err) {
    const msg = err.name === 'AbortError' ? 'timeout' : (err.message || String(err));
    send('metrics', { ok: false, error: msg, host: cfg.host, port: cfg.port });
  } finally {
    clearTimeout(timeout);
  }
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollOnce();
  pollTimer = setInterval(pollOnce, cfg.intervalMs);
}

function send(channel, payload) {
  if (win && !win.isDestroyed()) win.webContents.send(channel, payload);
}

function createWindow() {
  win = new BrowserWindow({
    width: 380,
    height: 600,
    minWidth: 320,
    minHeight: 460,
    title: 'Pi Monitor',
    alwaysOnTop: cfg.alwaysOnTop,
    backgroundColor: '#0b0f1a',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.removeMenu();
  win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  win.webContents.on('did-finish-load', () => {
    send('config', cfg);
    startPolling();
  });
}

app.whenReady().then(() => {
  cfg = loadConfig();
  applyLoginItem();
  createWindow();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

ipcMain.handle('get-config', () => cfg);

ipcMain.handle('set-config', (_event, partial) => {
  cfg = { ...cfg, ...partial };
  // sanitize
  cfg.port = Number(cfg.port) || DEFAULT_CONFIG.port;
  cfg.intervalMs = Math.max(500, Number(cfg.intervalMs) || DEFAULT_CONFIG.intervalMs);
  saveConfig(cfg);
  if (win) win.setAlwaysOnTop(!!cfg.alwaysOnTop);
  applyLoginItem();
  startPolling();
  return cfg;
});
